import numpy as np
from dataclasses import dataclass


@dataclass
class GazeResult:
    yaw: float = 0.0    # horizontal angle in degrees
    pitch: float = 0.0   # vertical angle in degrees
    looking_at_screen: bool = True


# Key landmark indices for head pose estimation
_NOSE_TIP = 1
_CHIN = 152
_LEFT_EYE_OUTER = 33
_RIGHT_EYE_OUTER = 263
_LEFT_EYE_INNER = 133
_RIGHT_EYE_INNER = 362
_LEFT_MOUTH = 61
_RIGHT_MOUTH = 291
_FOREHEAD = 10


class GazeEstimator:
    def __init__(self, yaw_threshold: float = 25.0, pitch_threshold: float = 20.0) -> None:
        self._yaw_thresh = yaw_threshold
        self._pitch_thresh = pitch_threshold

    def update_thresholds(self, yaw: float, pitch: float) -> None:
        self._yaw_thresh = yaw
        self._pitch_thresh = pitch

    def estimate(self, landmarks: list, frame_w: int, frame_h: int) -> GazeResult:
        if not landmarks or len(landmarks) < 400:
            return GazeResult()

        try:
            nose = np.array([landmarks[_NOSE_TIP].x, landmarks[_NOSE_TIP].y, landmarks[_NOSE_TIP].z])
            chin = np.array([landmarks[_CHIN].x, landmarks[_CHIN].y, landmarks[_CHIN].z])
            left_eye = np.array([landmarks[_LEFT_EYE_OUTER].x, landmarks[_LEFT_EYE_OUTER].y, landmarks[_LEFT_EYE_OUTER].z])
            right_eye = np.array([landmarks[_RIGHT_EYE_OUTER].x, landmarks[_RIGHT_EYE_OUTER].y, landmarks[_RIGHT_EYE_OUTER].z])
            forehead = np.array([landmarks[_FOREHEAD].x, landmarks[_FOREHEAD].y, landmarks[_FOREHEAD].z])

            # Eye midpoint
            eye_mid = (left_eye + right_eye) / 2.0

            # Yaw: horizontal asymmetry between nose and eye midpoint
            eye_width = abs(right_eye[0] - left_eye[0])
            if eye_width < 1e-6:
                yaw = 0.0
            else:
                nose_offset = (nose[0] - eye_mid[0]) / eye_width
                yaw = float(np.degrees(np.arctan2(nose_offset, 0.5))) * 2.0

            # Pitch: vertical relationship between nose, forehead, chin
            face_height = abs(chin[1] - forehead[1])
            if face_height < 1e-6:
                pitch = 0.0
            else:
                vertical_ratio = (nose[1] - forehead[1]) / face_height
                neutral_ratio = 0.45
                pitch = float((vertical_ratio - neutral_ratio) * 120.0)

            # Add z-depth contribution
            yaw += float(nose[2] * 100.0)

            looking = abs(yaw) < self._yaw_thresh and abs(pitch) < self._pitch_thresh

            return GazeResult(
                yaw=round(yaw, 1),
                pitch=round(pitch, 1),
                looking_at_screen=looking,
            )

        except (IndexError, ValueError, ZeroDivisionError):
            return GazeResult()
