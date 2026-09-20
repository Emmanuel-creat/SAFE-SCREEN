import json
from pathlib import Path
from typing import Any
import numpy as np


class ProfileManager:
    def __init__(self, config_dir: Path) -> None:
        self._path = config_dir / "user_profile.json"
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, ValueError):
                self._data = {}

    def save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    @property
    def has_encoding(self) -> bool:
        return "encoding" in self._data and self._data["encoding"] is not None

    def get_encoding(self) -> np.ndarray | None:
        enc = self._data.get("encoding")
        if enc is not None:
            return np.array(enc, dtype=np.float64)
        return None

    def set_encoding(self, encoding: np.ndarray) -> None:
        self._data["encoding"] = encoding.tolist()
        self.save()

    def get_reference_distances(self) -> dict[str, float] | None:
        return self._data.get("reference_distances")

    def set_reference_distances(self, distances: dict[str, float]) -> None:
        self._data["reference_distances"] = distances
        self.save()

    def clear(self) -> None:
        self._data = {}
        self.save()
