import threading
import time
from .backend_client import BackendClient

class StreamWorker:
    def __init__(self, transcription_id: int, backend: BackendClient, events):
        self.transcription_id = transcription_id
        self.backend = backend
        self.events = events
        self._stop = False

    def start(self):
        t = threading.Thread(target=self._poll, daemon=True)
        t.start()

    def stop(self):
        self._stop = True

    def _poll(self):
        while not self._stop:
            try:
                status_data = self.backend.get_status(self.transcription_id)
                for key in ("summary", "action_items", "meeting_notes", "journal_notes"):
                    if key in status_data and status_data[key]:
                        self.events.insight_delta.emit(f"[{key}] {status_data[key]}\n\n")
            except Exception as e:
                self.events.status.emit(f"Error: {e}")
                break
            time.sleep(1)
