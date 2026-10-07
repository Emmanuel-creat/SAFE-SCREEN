// Mock pywebview API — pour prévisualiser l'UI dans un navigateur ordinaire.
// Ajouter <script src="mock.js"></script> AVANT app.js pour l'activer.
(() => {
  let on = false;
  let susp = 0;
  let faces = 1;
  let att = 0.7;
  let scans = 0;
  let alerts = 0;
  let start = 0;
  let shareEnd = 0;
  let state = "idle";

  const settings = {
    scan_interval_ms: 500,
    suspicion_threshold: 6,
    suspicion_decay: 0.8,
    false_positive_delay: 3,
    gaze_yaw_threshold: 25.0,
    gaze_pitch_threshold: 20.0,
    camera_preview: false,
    auto_start: true,
    log_enabled: true,
    overlay_opacity: 0.92,
    share_duration_s: 60,
    camera_index: 0,
    pin_code: "",
    absence_threshold_multiplier: 2.0,
  };

  setInterval(() => {
    if (!on) return;
    scans++;
    if (Math.random() < 0.1) susp = Math.min(settings.suspicion_threshold * 1.2, susp + 1.5);
    else susp = Math.max(0, susp - 0.3);
    if (susp >= settings.suspicion_threshold && state === "active") {
      state = "protected";
      alerts++;
    }
    if (shareEnd > 0 && Date.now() / 1000 > shareEnd) {
      shareEnd = 0;
      state = "active";
    }
  }, 400);

  window.pywebview = {
    api: {
      async get_state() {
        return {
          state,
          suspicion: susp,
          threshold: settings.suspicion_threshold,
          faces,
          secondary: state === "protected" ? 1 : 0,
          attention: att,
          looking: att > 0.5,
          scans,
          alerts,
          session_s: on && start ? (Date.now() - start) / 1000 : 0,
          share_remaining: shareEnd > 0 ? shareEnd - Date.now() / 1000 : 0,
          share_total: settings.share_duration_s,
          calibrated: true,
        };
      },
      async get_settings() {
        return { ...settings };
      },
      async set_settings(p) {
        Object.assign(settings, p);
        return true;
      },
      async toggle_power(v) {
        on = v;
        if (v) {
          start = Date.now();
          state = "active";
          susp = 0;
          scans = 0;
          alerts = 0;
        } else {
          state = "idle";
        }
        return true;
      },
      async grant_share(d) {
        shareEnd = Date.now() / 1000 + d;
        state = "sharing";
        susp = 0;
      },
      async dismiss_protection() {
        susp = 0;
        state = "active";
      },
      async reset_profile() {},
      async start_calibration() {
        return "ok";
      },
    },
  };
  setTimeout(() => window.dispatchEvent(new Event("pywebviewready")), 50);
})();
