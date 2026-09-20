import numpy as np

# Landmark pairs for encoding: distances between these landmarks form the encoding vector
_ENCODING_PAIRS = [
    (33, 263),   # outer eye to outer eye
    (1, 152),    # nose tip to chin
    (10, 152),   # forehead to chin
    (33, 133),   # left eye width
    (362, 263),  # right eye width
    (61, 291),   # mouth width
    (0, 17),     # upper lip to lower lip
    (33, 61),    # left eye to left mouth
    (263, 291),  # right eye to right mouth
    (1, 10),     # nose to forehead
    (133, 362),  # inner eye to inner eye
    (70, 300),   # left brow to right brow
    (1, 61),     # nose to left mouth
    (1, 291),    # nose to right mouth
    (33, 152),   # left eye to chin
    (263, 152),  # right eye to chin
]


class UserProfileMatcher:
    MATCH_THRESHOLD = 0.35

    def __init__(self) -> None:
        self._reference: np.ndarray | None = None

    @property
    def has_reference(self) -> bool:
        return self._reference is not None

    def set_reference(self, encoding: np.ndarray) -> None:
        self._reference = encoding

    def clear_reference(self) -> None:
        self._reference = None

    @staticmethod
    def compute_encoding(landmarks: list) -> np.ndarray | None:
        if not landmarks or len(landmarks) < 400:
            return None
        try:
            distances = []
            for i, j in _ENCODING_PAIRS:
                a = np.array([landmarks[i].x, landmarks[i].y, landmarks[i].z])
                b = np.array([landmarks[j].x, landmarks[j].y, landmarks[j].z])
                distances.append(float(np.linalg.norm(a - b)))

            vec = np.array(distances, dtype=np.float64)
            norm = np.linalg.norm(vec)
            if norm < 1e-8:
                return None
            return vec / norm

        except (IndexError, ValueError):
            return None

    def match(self, landmarks: list) -> float:
        if self._reference is None:
            return 0.0
        encoding = self.compute_encoding(landmarks)
        if encoding is None:
            return 0.0
        # Cosine similarity
        dot = float(np.dot(self._reference, encoding))
        similarity = max(0.0, min(1.0, dot))
        return similarity

    def is_primary_user(self, landmarks: list) -> bool:
        if self._reference is None:
            return True  # No calibration = assume primary
        similarity = self.match(landmarks)
        return similarity > (1.0 - self.MATCH_THRESHOLD)
