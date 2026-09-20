import cv2
import numpy as np
from .user_profiles import UserProfileMatcher
from .model_manager import ensure_model
from core.logger import Logger


class _LM:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


def _detect_single_face(frame: np.ndarray) -> list | None:
    """Detect 468+ landmarks for a single face."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    log = Logger.get()

    # 1. Legacy solutions
    try:
        import mediapipe as mp
        if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'face_mesh'):
            with mp.solutions.face_mesh.FaceMesh(
                static_image_mode=True, max_num_faces=1,
                refine_landmarks=True, min_detection_confidence=0.6,
            ) as mesh:
                r = mesh.process(rgb)
                if r.multi_face_landmarks:
                    return r.multi_face_landmarks[0].landmark
    except Exception:
        pass

    # 2. Tasks API
    try:
        import mediapipe as mp
        from mediapipe.tasks.python import vision as mpv
        from mediapipe.tasks import python as mpp

        model_path = ensure_model()
        if model_path is None:
            log.warning("Calibration: no model available")
            return None

        opts = mpv.FaceLandmarkerOptions(
            base_options=mpp.BaseOptions(model_asset_path=model_path),
            running_mode=mpv.RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=0.6,
        )
        with mpv.FaceLandmarker.create_from_options(opts) as det:
            img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            res = det.detect(img)
            if res.face_landmarks:
                return [_LM(l.x, l.y, l.z) for l in res.face_landmarks[0]]
    except Exception as e:
        log.error(f"Calibration detection error: {e}")

    return None


class Calibrator:
    CAPTURE_COUNT = 5
    CAPTURE_INTERVAL_MS = 600

    def __init__(self) -> None:
        self._log = Logger.get()
        self._encodings: list[np.ndarray] = []

    def process_frame(self, frame: np.ndarray) -> tuple[bool, str]:
        landmarks = _detect_single_face(frame)
        if landmarks is None:
            return False, "Aucun visage détecté. Regardez la caméra."
        encoding = UserProfileMatcher.compute_encoding(landmarks)
        if encoding is None:
            return False, "Landmarks insuffisants. Rapprochez-vous."
        self._encodings.append(encoding)
        n = len(self._encodings)
        if n < self.CAPTURE_COUNT:
            return True, f"Capture {n}/{self.CAPTURE_COUNT}"
        return True, "Calibration terminée !"

    @property
    def is_complete(self) -> bool:
        return len(self._encodings) >= self.CAPTURE_COUNT

    def compute_final_encoding(self) -> np.ndarray | None:
        if not self._encodings:
            return None
        stacked = np.stack(self._encodings)
        mean_enc = np.mean(stacked, axis=0)
        norm = np.linalg.norm(mean_enc)
        return mean_enc / norm if norm > 1e-8 else None

    def reset(self) -> None:
        self._encodings.clear()

    @property
    def progress(self) -> float:
        return len(self._encodings) / self.CAPTURE_COUNT
