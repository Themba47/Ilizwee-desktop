import time
import queue
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
import tempfile
import os

class AudioRecorder:
    def __init__(self, on_chunk, events, samplerate=16000, channels=1, chunk_seconds=15):
        self.on_chunk = on_chunk
        self.events = events
        self.samplerate = samplerate
        self.channels = channels
        self.chunk_seconds = chunk_seconds

        self._running = False
        self._q = queue.Queue()
        self._thread = None

    def start(self):
        print("Recorder started")
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        self.events.status.emit("Mic capture started")
        frames_per_chunk = int(self.samplerate * self.chunk_seconds)

        def callback(indata, frames, time_info, status):
            if status:
                # non-fatal warnings
                pass
            self._q.put(indata.copy())

        buf = []
        buf_frames = 0
        start_ts = time.time()

        with sd.InputStream(samplerate=self.samplerate, channels=self.channels, callback=callback):
            while self._running:
                try:
                    data = self._q.get(timeout=0.5)
                except queue.Empty:
                    continue

                buf.append(data)
                buf_frames += data.shape[0]

                if buf_frames >= frames_per_chunk:
                    audio = np.concatenate(buf, axis=0)
                    buf = []
                    buf_frames = 0

                    end_ts = time.time()
                    start_ms = int((start_ts - start_ts) * 1000)  # for now relative inside session if you want
                    end_ms = int((end_ts - start_ts) * 1000)

                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                    tmp.close()
                    sf.write(tmp.name, audio, self.samplerate)

                    self.on_chunk(tmp.name, start_ms, end_ms)

            # cleanup: drain not needed
        self.events.status.emit("Mic capture stopped")
