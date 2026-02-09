import threading
import time

class StatusPoller:
    def __init__(self, transcription_id: int, backend, on_update, events, interval=1.0):
        self.transcription_id = transcription_id
        self.backend = backend
        self.on_update = on_update
        self.events = events
        self.interval = interval
        self._stop = False
        self._thread = None

        self._last_formats_seen = set()

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True

    def _run(self):
        while not self._stop:
            try:
                data = self.backend.get_status(self.transcription_id)

                # Only notify UI when new formats appear (prevents spam)
                formats = data.get("formats") or {}
                seen = set(formats.keys())
                if seen != self._last_formats_seen:
                    self._last_formats_seen = seen
                    self.on_update(data)

                if data.get("status") in ("completed", "failed"):
                    self.on_update(data)
                    break

            except Exception as e:
                self.events.status.emit(f"Polling error: {e}")

            time.sleep(self.interval)
