import time
import cv2
import numpy as np
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from config.settings import Settings
from config.profiles import ProfileManager
from .state_machine import StateMachine, GuardState
from .logger import Logger
from vision.mediapipe_detector import MediaPipeDetector, DetectionResult
from vision.gaze_estimator import GazeEstimator
from vision.user_profiles import UserProfileMatcher


class GuardEngine(QObject):
    state_changed = pyqtSignal(object)
    detection_update = pyqtSignal(object)
    protection_triggered = pyqtSignal(str)  # reason: 'observer' | 'absence'
    protection_cleared = pyqtSignal()
    share_expired = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, settings: Settings, profile_mgr: ProfileManager) -> None:
        super().__init__()
        self._settings = settings
        self._profile = profile_mgr
        self._log = Logger.get()

        self._gaze = GazeEstimator(
            yaw_threshold=settings.get("gaze_yaw_threshold"),
            pitch_threshold=settings.get("gaze_pitch_threshold"),
        )
        self._matcher = UserProfileMatcher()
        self._detector = MediaPipeDetector(self._gaze, self._matcher)
        self._sm = StateMachine()
        self._sm.state_changed.connect(self._on_sm_state_changed)

        self._cap: cv2.VideoCapture | None = None
        self._suspicion_score: float = 0.0
        self._consecutive_detections: int = 0
        self._session_start: float = 0.0
        self._total_scans: int = 0
        self._total_alerts: int = 0
        self._share_end_time: float = 0.0
        self._last_detection = DetectionResult()

        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._scan_tick)

        self._share_timer = QTimer(self)
        self._share_timer.setSingleShot(True)
        self._share_timer.timeout.connect(self._on_share_expired)

        # Load user profile encoding if available
        enc = self._profile.get_encoding()
        if enc is not None:
            self._matcher.set_reference(enc)

    @property
    def state(self) -> GuardState:
        return self._sm.state

    @property
    def suspicion_score(self) -> float:
        return self._suspicion_score

    @property
    def last_detection(self) -> DetectionResult:
        return self._last_detection

    @property
    def session_seconds(self) -> float:
        if self._session_start == 0:
            return 0.0
        return time.time() - self._session_start

    @property
    def total_scans(self) -> int:
        return self._total_scans

    @property
    def total_alerts(self) -> int:
        return self._total_alerts

    @property
    def share_remaining(self) -> float:
        if self._sm.state != GuardState.SHARING:
            return 0.0
        return max(0.0, self._share_end_time - time.time())

    def reload_profile(self) -> None:
        enc = self._profile.get_encoding()
        if enc is not None:
            self._matcher.set_reference(enc)
            self._log.info("User profile encoding reloaded")

    def start(self) -> bool:
        if self._sm.state not in (GuardState.IDLE, GuardState.ERROR):
            return True

        cam_idx = self._settings.get("camera_index")
        self._cap = cv2.VideoCapture(cam_idx)
        if not self._cap.isOpened():
            self._sm.transition_to(GuardState.ERROR)
            self.error_occurred.emit(f"Impossible d'ouvrir la caméra {cam_idx}")
            return False

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self._session_start = time.time()
        self._suspicion_score = 0.0
        self._consecutive_detections = 0
        self._total_scans = 0
        self._total_alerts = 0

        self._gaze.update_thresholds(
            self._settings.get("gaze_yaw_threshold"),
            self._settings.get("gaze_pitch_threshold"),
        )

        interval = self._settings.get("scan_interval_ms")
        self._scan_timer.start(interval)
        self._sm.transition_to(GuardState.ACTIVE)
        self._log.info("Guard engine started")
        return True

    def stop(self) -> None:
        self._scan_timer.stop()
        self._share_timer.stop()
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._detector.release()
        self._suspicion_score = 0.0
        self._session_start = 0.0
        self._sm.reset()
        self._log.info("Guard engine stopped")

    def pause(self) -> None:
        if self._sm.state == GuardState.ACTIVE:
            self._scan_timer.stop()
            self._sm.transition_to(GuardState.PAUSED)

    def resume(self) -> None:
        if self._sm.state == GuardState.PAUSED:
            interval = self._settings.get("scan_interval_ms")
            self._scan_timer.start(interval)
            self._sm.transition_to(GuardState.ACTIVE)

    def grant_share(self, duration_s: int) -> None:
        self._suspicion_score = 0.0
        self._share_end_time = time.time() + duration_s
        self._share_timer.start(duration_s * 1000)
        self.protection_cleared.emit()
        self._sm.transition_to(GuardState.SHARING)
        self._log.info(f"Share granted for {duration_s}s")

    def dismiss_protection(self) -> None:
        self._suspicion_score = 0.0
        self._consecutive_detections = 0
        self.protection_cleared.emit()
        self._sm.transition_to(GuardState.ACTIVE)

    def update_scan_interval(self) -> None:
        if self._scan_timer.isActive():
            self._scan_timer.setInterval(self._settings.get("scan_interval_ms"))

    def get_camera(self) -> cv2.VideoCapture | None:
        return self._cap

    def _on_sm_state_changed(self, old: GuardState, new: GuardState) -> None:
        self.state_changed.emit(new)

    def _scan_tick(self) -> None:
        if self._cap is None or not self._cap.isOpened():
            self._sm.transition_to(GuardState.ERROR)
            self.error_occurred.emit("Caméra déconnectée")
            self._scan_timer.stop()
            return

        ret, frame = self._cap.read()
        if not ret or frame is None:
            return

        self._total_scans += 1
        result = self._detector.detect(frame)
        self._last_detection = result
        self.detection_update.emit(result)

        if self._sm.state == GuardState.SHARING:
            return

        threshold = self._settings.get("suspicion_threshold")
        decay = self._settings.get("suspicion_decay")
        fp_delay = self._settings.get("false_positive_delay")
        absence_mult = self._settings.get("absence_threshold_multiplier")
        absence_threshold = threshold * absence_mult

        trigger_reason = ""

        # Secondary faces detected
        if result.secondary_faces:
            self._consecutive_detections += 1
            if self._consecutive_detections >= fp_delay:
                increment = len(result.secondary_faces) * 1.5
                self._suspicion_score = min(threshold * 2, self._suspicion_score + increment)
            if self._suspicion_score >= threshold:
                trigger_reason = "observer"

        # Primary face absent — slower increment, higher threshold
        elif result.primary_face_landmarks is None:
            self._consecutive_detections += 1
            if self._consecutive_detections >= fp_delay:
                self._suspicion_score = min(absence_threshold * 1.5, self._suspicion_score + 0.3)
            if self._suspicion_score >= absence_threshold:
                trigger_reason = "absence"

        # Only primary face, check gaze
        else:
            self._consecutive_detections = max(0, self._consecutive_detections - 1)
            if not result.gaze.looking_at_screen:
                self._suspicion_score = min(threshold * 2, self._suspicion_score + 0.3)
            elif result.attention_score > 0.5:
                self._suspicion_score = max(0.0, self._suspicion_score - decay)

        self._suspicion_score = max(0.0, self._suspicion_score)

        if self._sm.state == GuardState.ACTIVE and trigger_reason:
            self._total_alerts += 1
            self._sm.transition_to(GuardState.PROTECTED)
            self.protection_triggered.emit(trigger_reason)
            self._log.warning(
                f"Protection triggered: {trigger_reason} (score={self._suspicion_score:.1f}, "
                f"faces={result.faces_count}, gaze={result.gaze.looking_at_screen})"
            )

    def _on_share_expired(self) -> None:
        self._share_end_time = 0.0
        self._suspicion_score = 0.0
        self._consecutive_detections = 0
        self._sm.transition_to(GuardState.ACTIVE)
        self.share_expired.emit()
        self._log.info("Share expired")
