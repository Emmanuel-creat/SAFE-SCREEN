from dataclasses import dataclass, field
import cv2
import numpy as np
from .gaze_estimator import GazeEstimator, GazeResult
from .user_profiles import UserProfileMatcher
from .model_manager import ensure_model
from core.logger import Logger


@dataclass
class DetectionResult:
    faces_count: int = 0
    primary_face_landmarks: list | None = None
    primary_face_bbox: tuple[int, int, int, int] | None = None
    secondary_faces: list[tuple[int, int, int, int]] = field(default_factory=list)
    is_primary_user: bool = False
    gaze: GazeResult = field(default_factory=GazeResult)
    attention_score: float = 0.0
    frame: np.ndarray | None = None
    raw_frame: np.ndarray | None = None


@dataclass
class _LM:
    x: float; y: float; z: float


def _create_face_mesh():
    log = Logger.get()

    # 1. Try legacy solutions API (mediapipe < 0.10.14)
    try:
        import mediapipe as mp
        if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'face_mesh'):
            fm = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False, max_num_faces=4,
                refine_landmarks=True,
                min_detection_confidence=0.5, min_tracking_confidence=0.4,
            )
            log.info("MediaPipe: solutions API")
            return fm, "solutions"
    except Exception:
        pass

    # 2. Tasks API with auto-download model
    try:
        import mediapipe as mp
        from mediapipe.tasks.python import vision as mpv
        from mediapipe.tasks import python as mpp

        model_path = ensure_model()
        if model_path is None:
            log.warning("Could not obtain face_landmarker model")
            return None, "none"

        opts = mpv.FaceLandmarkerOptions(
            base_options=mpp.BaseOptions(model_asset_path=model_path),
            running_mode=mpv.RunningMode.IMAGE,
            num_faces=4,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
        )
        det = mpv.FaceLandmarker.create_from_options(opts)
        log.info(f"MediaPipe: Tasks API (model={model_path})")
        return det, "tasks"
    except Exception as e:
        log.error(f"MediaPipe Tasks init failed: {e}")

    return None, "none"


class MediaPipeDetector:
    def __init__(self, gaze_estimator: GazeEstimator, profile_matcher: UserProfileMatcher) -> None:
        self._log = Logger.get()
        self._gaze = gaze_estimator
        self._matcher = profile_matcher
        self._mesh, self._api_mode = _create_face_mesh()
        if self._mesh is None:
            self._log.warning("MediaPipe unavailable → Haar Cascades fallback (no gaze/recognition)")
            self._haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        else:
            self._haar = None
        self._stab = 0
        self._max_stab = 10
        self._prev_cx: float | None = None
        self._prev_cy: float | None = None

    @property
    def api_mode(self) -> str:
        return self._api_mode

    def detect(self, frame: np.ndarray) -> DetectionResult:
        if self._mesh is not None:
            return self._detect_mp(frame)
        return self._detect_haar(frame)

    def _detect_mp(self, frame: np.ndarray) -> DetectionResult:
        r = DetectionResult(raw_frame=frame.copy())
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        all_lm: list[list] = []

        if self._api_mode == "solutions":
            res = self._mesh.process(rgb)
            if res.multi_face_landmarks:
                all_lm = [f.landmark for f in res.multi_face_landmarks]
        elif self._api_mode == "tasks":
            import mediapipe as mp
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            res = self._mesh.detect(mp_img)
            if res.face_landmarks:
                for face in res.face_landmarks:
                    all_lm.append([_LM(l.x, l.y, l.z) for l in face])

        if not all_lm:
            self._stab = max(0, self._stab - 1)
            self._prev_cx = self._prev_cy = None
            r.frame = frame
            return r

        r.faces_count = len(all_lm)
        pi = self._pick_primary(all_lm, w, h)
        plm = all_lm[pi]
        r.primary_face_landmarks = plm
        r.primary_face_bbox = self._bbox(plm, w, h)
        r.is_primary_user = self._matcher.is_primary_user(plm)
        r.gaze = self._gaze.estimate(plm, w, h)
        r.attention_score = self._attention(plm, r.gaze)
        for i, lm in enumerate(all_lm):
            if i != pi:
                r.secondary_faces.append(self._bbox(lm, w, h))
        r.frame = frame
        return r

    def _detect_haar(self, frame: np.ndarray) -> DetectionResult:
        r = DetectionResult(raw_frame=frame.copy())
        gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        faces = self._haar.detectMultiScale(gray, 1.15, 5, minSize=(60, 60))
        if len(faces) == 0:
            self._stab = max(0, self._stab - 1)
            r.frame = frame
            return r
        fl = [tuple(map(int, f)) for f in faces]
        r.faces_count = len(fl)
        primary = max(fl, key=lambda f: f[2] * f[3])
        r.primary_face_bbox = primary
        r.is_primary_user = True
        r.gaze = GazeResult(looking_at_screen=True)
        r.attention_score = 0.6
        r.secondary_faces = [f for f in fl if f != primary]
        r.frame = frame
        return r

    def _pick_primary(self, faces, w, h):
        if len(faces) == 1:
            lm = faces[0]
            cx = sum(p.x for p in lm) / len(lm)
            cy = sum(p.y for p in lm) / len(lm)
            self._update_stab(cx, cy)
            return 0
        best, best_s = 0, -1.0
        for i, lm in enumerate(faces):
            ms = self._matcher.match(lm) if self._matcher.has_reference else 0.5
            bbox = self._bbox(lm, w, h)
            ss = min(1.0, (bbox[2] * bbox[3]) / (w * h * 0.08))
            cx = sum(p.x for p in lm) / len(lm)
            cy = sum(p.y for p in lm) / len(lm)
            cs = max(0, 1 - ((cx - 0.5)**2 + (cy - 0.5)**2)**0.5 * 2)
            t = ms * 0.5 + ss * 0.3 + cs * 0.2
            if t > best_s:
                best, best_s = i, t
        lm = faces[best]
        self._update_stab(sum(p.x for p in lm)/len(lm), sum(p.y for p in lm)/len(lm))
        return best

    def _update_stab(self, cx, cy):
        if self._prev_cx is not None:
            d = ((cx - self._prev_cx)**2 + (cy - self._prev_cy)**2)**0.5
            self._stab = min(self._stab + 1, self._max_stab) if d < 0.05 else max(0, self._stab - 2)
        self._prev_cx, self._prev_cy = cx, cy

    def _attention(self, lm, gaze):
        cx = sum(p.x for p in lm) / len(lm)
        cy = sum(p.y for p in lm) / len(lm)
        pos = max(0, 1 - (abs(cx - 0.5) * 1.2 + abs(cy - 0.5) * 0.8))
        gz = 1.0 if gaze.looking_at_screen else 0.2
        st = self._stab / self._max_stab
        return round(min(1, max(0, pos * 0.3 + gz * 0.4 + st * 0.3)), 3)

    @staticmethod
    def _bbox(lm, w, h):
        xs = [int(l.x * w) for l in lm]
        ys = [int(l.y * h) for l in lm]
        x1, x2 = max(0, min(xs)), min(w, max(xs))
        y1, y2 = max(0, min(ys)), min(h, max(ys))
        return (x1, y1, x2 - x1, y2 - y1)

    def release(self):
        self._prev_cx = self._prev_cy = None
        self._stab = 0
