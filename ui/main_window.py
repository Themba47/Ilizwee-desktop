import httpx
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel, QHBoxLayout
)
from PySide6.QtCore import Signal, QObject

from core.recorder import AudioRecorder
from core.whisper_recorder import WhisperWorker
from core.backend_client import BackendClient
from core.stream_client import StreamWorker

class UIEvents(QObject):
    transcript_delta = Signal(str)
    insight_delta = Signal(str)
    status = Signal(str)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ilizwee Desktop (Python GUI)")

        self.events = UIEvents()
        self.email_input = QTextEdit()
        self.email_input.setPlaceholderText("Email")
        self.email_input.setFixedHeight(30)

        self.password_input = QTextEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setFixedHeight(30)

        self.btn_login = QPushButton("Login")
        self.btn_login.clicked.connect(self.login)

        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)

        self.insights = QTextEdit()
        self.insights.setReadOnly(True)

        self.status_lbl = QLabel("Idle")

        self.btn_start = QPushButton("Start recording")
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setEnabled(False)

        top = QWidget()
        layout = QVBoxLayout(top)

        row = QHBoxLayout()
        row.addWidget(self.btn_start)
        row.addWidget(self.btn_stop)
        
        layout.addWidget(QLabel("Login to continue"))
        layout.addWidget(self.email_input)
        layout.addWidget(self.password_input)
        layout.addWidget(self.btn_login)


        layout.addLayout(row)
        layout.addWidget(QLabel("Live transcript"))
        layout.addWidget(self.transcript)
        layout.addWidget(QLabel("Ideas / Insights (streaming)"))
        layout.addWidget(self.insights)
        layout.addWidget(self.status_lbl)

        self.setCentralWidget(top)

        # Core services
        self.backend = BackendClient(base_url="http://127.0.0.1:8083", token="YOUR_TOKEN")
        self.recorder = AudioRecorder(on_chunk=self._on_audio_chunk, events=self.events)
        self.whisper = WhisperWorker(on_text=self._on_transcript_text, events=self.events)

        self.streamer = None
        self.session_id = None
        self.chunk_index = 0

        # Signals
        self.btn_start.clicked.connect(self.start)
        self.btn_stop.clicked.connect(self.stop)

        self.events.transcript_delta.connect(self._append_transcript)
        self.events.insight_delta.connect(self._append_insights)
        self.events.status.connect(self.status_lbl.setText)
        
    
    def login(self):
        email = self.email_input.toPlainText().strip()
        password = self.password_input.toPlainText().strip()

        if not email or not password:
            self.status_lbl.setText("Please enter email and password.")
            return

        self.status_lbl.setText("Logging in...")

        try:
            r = httpx.post(
                "http://127.0.0.1:8083/api/auth/login/",
                data={"email": email, "password": password},
                timeout=10
            )
            r.raise_for_status()
            data = r.json()
            token = data["key"]
            self.status_lbl.setText(f"Welcome {data['first_name']}!")

            # Update backend client with real token
            self.backend = BackendClient(base_url="http://127.0.0.1:8083", token=token)
            self.btn_start.setEnabled(True)

            # Optionally disable login UI after success
            self.email_input.setDisabled(True)
            self.password_input.setDisabled(True)
            self.btn_login.setDisabled(True)

        except Exception as e:
            self.status_lbl.setText(f"Login failed: {e}")

    

    def start(self):
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.events.status.emit("Creating session...")

        self.session_id = self.backend.upload_transcript(title="Live recording", mode="meeting", transcript="Recording started")
        self.events.status.emit(f"Recording… (transcript {self.session_id})")

        # Start backend stream
        self.streamer = StreamWorker(
            transcription_id=self.session_id,
            backend=self.backend,
            events=self.events
        )
        self.streamer.start()

        # Start mic recording
        self.chunk_index = 0
        self.recorder.start()

    def stop(self):
        self.events.status.emit("Uploading full transcript...")

        # Join all transcript parts
        full_transcript = "\n".join(self.recorder.transcript_parts)
        transcription_id = self.backend.upload_transcript(
            title="New meeting",
            mode="meeting",
            transcript=full_transcript
        )

        self.events.status.emit("Transcript uploaded. Waiting for insights...")

        self.streamer = StreamWorker(
            transcription_id=transcription_id,
            backend=self.backend,
            events=self.events
        )
        self.streamer.start()


    def _on_audio_chunk(self, wav_path: str, start_ms: int, end_ms: int):
        # Run local whisper in background
        print(f"Chunk received: {wav_path} from {start_ms}ms to {end_ms}ms")
        self.whisper.transcribe_async(
            wav_path=wav_path,
            chunk_index=self.chunk_index,
            start_ms=start_ms,
            end_ms=end_ms
        )
        self.chunk_index += 1

    def _on_transcript_text(self, chunk_index: int, start_ms: int, end_ms: int, text: str):
        # Update UI
        self.events.transcript_delta.emit(text + "\n")

        # Send to backend incrementally
        # if self.session_id:
            # self.backend.post_transcript_chunk(
            #     session_id=self.session_id,
            #     chunk_index=chunk_index,
            #     start_ms=start_ms,
            #     end_ms=end_ms,
            #     text=text
            # )

    def _on_stream_event(self, event_type: str, payload: dict):
        # Example: route “insight” deltas into insights panel
        if event_type in ("insight.delta", "idea.delta", "question.suggested"):
            msg = payload.get("text") or payload.get("delta") or str(payload)
            self.events.insight_delta.emit(msg + "\n")

    def _append_transcript(self, s: str):
        self.transcript.append(s.rstrip('\n'))  # append() auto-adds newline

    def _append_insights(self, s: str):
        self.insights.append(s.rstrip('\n'))
