import os
import threading
from faster_whisper import WhisperModel

import soundfile as sf
import numpy as np

# Pick ONE model folder you downloaded with `hf download ...`
MODEL_PATH = os.path.abspath("./models/faster-whisper-base")
# or: "./models/faster-whisper-small"

class WhisperWorker:
    def __init__(self, on_text, events, device="auto", compute_type="auto"):
        self.on_text = on_text
        self.events = events
        self._stop = False
        self._lock = threading.Lock()

        if not os.path.exists(MODEL_PATH):
            raise RuntimeError(
                f"Local Whisper model not found at {MODEL_PATH}. "
                f"Download it first (hf download ...)."
            )

        # ✅ Load from local path (no HF download, no flaky internet)
        self.model = WhisperModel(MODEL_PATH, device=device, compute_type=compute_type)

    def stop(self):
        self._stop = True

    def transcribe_async(self, wav_path: str, chunk_index: int, start_ms: int, end_ms: int):
        t = threading.Thread(
            target=self._transcribe,
            args=(wav_path, chunk_index, start_ms, end_ms),
            daemon=True
        )
        t.start()

    def _transcribe(self, wav_path, chunk_index, start_ms, end_ms):
        print(f"[Whisper] Starting transcription on {wav_path}")
        if self._stop:
            return
        
        # Read and normalize audio
        data, sr = sf.read(wav_path)
        print(f"[Audio] sample rate: {sr}")
        print(f"[Audio] max amplitude BEFORE: {np.max(np.abs(data))}")
        
        # NORMALIZE AUDIO - boost quiet recordings
        max_amp = np.max(np.abs(data))
        if max_amp > 0:
            # Amplify to target level of 0.3 (safe level, won't clip)
            target_amplitude = 0.3
            amplification_factor = target_amplitude / max_amp
            data = data * amplification_factor
            
            # Save normalized version
            normalized_path = wav_path.replace('.wav', '_normalized.wav')
            sf.write(normalized_path, data, sr)
            wav_path = normalized_path
            
            print(f"[Audio] Amplified by {amplification_factor:.1f}x")
            print(f"[Audio] max amplitude AFTER: {np.max(np.abs(data))}")
        
        self.events.status.emit("Transcribing locally…")
        
        try:
            # Use normalized audio, disable VAD initially
            segments_gen, info = self.model.transcribe(
                wav_path, 
                vad_filter=False,  # Try without VAD first
                language="en"
            )
            segments = list(segments_gen)
            print(f"[Whisper] Got segments: {segments}")
            
        except Exception as e:
            print(f"[Whisper] ERROR during transcription: {e}")
            return
        
        text_parts = [seg.text.strip() for seg in segments if seg.text]
        text = " ".join([p for p in text_parts if p])
        print(f"[Whisper] Final text: {text}")
        
        if text:
            self.on_text(chunk_index, start_ms, end_ms, text)
            self.events.status.emit("Recording…")
        else:
            print(f"[Whisper] No speech detected in chunk {chunk_index}")