import json
from pathlib import Path
from typing import Any


_DEFAULTS: dict[str, Any] = {
    "scan_interval_ms": 500,
    "suspicion_threshold": 6,
    "suspicion_decay": 0.8,
    "false_positive_delay": 3,
    "share_duration_s": 60,
    "camera_preview": False,
    "camera_index": 0,
    "overlay_opacity": 0.92,
    "log_enabled": True,
    "auto_start": True,
    "gaze_yaw_threshold": 25.0,
    "gaze_pitch_threshold": 20.0,
    "calibration_done": False,
    "user_encoding": None,
    "pin_code": "",
    "absence_threshold_multiplier": 2.5,
}


class Settings:
    def __init__(self) -> None:
        self._dir = Path.home() / ".screenguard"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "screenguard_config.json"
        self._data: dict[str, Any] = dict(_DEFAULTS)
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                for k, v in stored.items():
                    if k in _DEFAULTS:
                        expected = type(_DEFAULTS[k]) if _DEFAULTS[k] is not None else type(v)
                        if _DEFAULTS[k] is None:
                            self._data[k] = v
                        else:
                            try:
                                self._data[k] = expected(v)
                            except (ValueError, TypeError):
                                pass
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

    def save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str) -> Any:
        return self._data.get(key, _DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def all(self) -> dict[str, Any]:
        return dict(self._data)

    def reset(self) -> None:
        self._data = dict(_DEFAULTS)
        self.save()

    @property
    def config_dir(self) -> Path:
        return self._dir
