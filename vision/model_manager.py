"""Manages MediaPipe model download and location."""
import os
import pathlib
import urllib.request
import ssl
from core.logger import Logger

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
MODEL_NAME = "face_landmarker.task"


def get_model_dir() -> pathlib.Path:
    d = pathlib.Path.home() / ".screenguard" / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_model_path() -> str | None:
    """Return path to face_landmarker.task, searching in order:
    1. ~/.screenguard/models/
    2. MediaPipe package directory
    3. Next to the executable (for PyInstaller)
    """
    log = Logger.get()

    # 1. User cache
    cached = get_model_dir() / MODEL_NAME
    if cached.exists() and cached.stat().st_size > 100_000:
        return str(cached)

    # 2. MediaPipe package
    try:
        import mediapipe as mp
        mp_path = pathlib.Path(mp.__file__).parent
        candidates = [
            mp_path / "modules" / "face_landmarker" / MODEL_NAME,
            mp_path / "modules" / "face_landmark" / "face_landmark_front.tflite",
        ]
        for c in candidates:
            if c.exists():
                return str(c)
    except Exception:
        pass

    # 3. PyInstaller bundle
    import sys
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        bundled = os.path.join(base, "models", MODEL_NAME)
        if os.path.exists(bundled):
            return bundled

    # Not found anywhere
    log.warning(f"Model {MODEL_NAME} not found locally")
    return None


def download_model() -> str | None:
    """Download the model. Returns path on success, None on failure."""
    log = Logger.get()
    dest = get_model_dir() / MODEL_NAME
    if dest.exists() and dest.stat().st_size > 100_000:
        return str(dest)

    log.info(f"Downloading {MODEL_NAME}...")
    try:
        # Try with SSL verification
        urllib.request.urlretrieve(MODEL_URL, str(dest))
        log.info(f"Downloaded {MODEL_NAME} ({dest.stat().st_size} bytes)")
        return str(dest)
    except Exception as e1:
        log.warning(f"Download with SSL failed: {e1}")
        try:
            # Retry without SSL verification (corporate proxies)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(MODEL_URL)
            with urllib.request.urlopen(req, context=ctx) as resp:
                data = resp.read()
                dest.write_bytes(data)
            log.info(f"Downloaded {MODEL_NAME} (no-verify, {dest.stat().st_size} bytes)")
            return str(dest)
        except Exception as e2:
            log.error(f"Download failed: {e2}")
            # Clean up partial file
            if dest.exists():
                dest.unlink()
            return None


def ensure_model() -> str | None:
    """Get model path, downloading if necessary."""
    path = get_model_path()
    if path:
        return path
    return download_model()
