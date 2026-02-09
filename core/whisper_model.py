# core/whisper_model.py
from faster_whisper import WhisperModel
import os

MODEL_PATH = os.path.abspath("./models/faster-whisper-base")
# or "./models/faster-whisper-small"

_model = None  # singleton

def get_whisper_model():
    global _model

    if _model is not None:
        return _model

    if not os.path.exists(MODEL_PATH):
        raise RuntimeError(
            f"Whisper model not found at {MODEL_PATH}. "
            "Please download the model first."
        )

    try:
        _model = WhisperModel(
            MODEL_PATH,
            device="auto",
            compute_type="auto"
        )
        return _model

    except RuntimeError as e:
        raise RuntimeError(
            "Failed to load Whisper model. "
            "Check disk space and model files."
        ) from e
