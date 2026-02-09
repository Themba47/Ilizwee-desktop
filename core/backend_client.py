import httpx

class BackendClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def upload_transcript(self, title: str, mode: str, transcript: str):
        r = httpx.post(
            f"{self.base_url}/api/uploadtext/",
            json={
                "title": title,
                "mode": mode,
                "transcript": transcript
            },
            headers=self._headers(),
            timeout=60
        )
        r.raise_for_status()
        return r.json()["transcription_id"]

    def get_status(self, transcription_id: int):
        r = httpx.get(
            f"{self.base_url}/api/status/{transcription_id}/",
            headers=self._headers(),
            timeout=15
        )
        r.raise_for_status()
        return r.json()
