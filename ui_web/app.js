// =====================================================================
// ScreenGuard — fenêtre principale (pywebview)
// =====================================================================
"use strict";

const $ = (id) => document.getElementById(id);
const api = () => window.pywebview && window.pywebview.api;

// ── Pages ──────────────────────────────────────────────────────────────
const PAGE_META = {
  dash: ["Tableau de bord", "Vue d'ensemble du système de protection"],
  detect: ["Détection", "Paramètres du scan et de l'estimation du regard"],
  display: ["Affichage", "Overlay, mini-fenêtre, caméra et logs"],
  security: ["Sécurité", "Code PIN et délai avant mode absence"],
  calib: ["Calibration", "Profil facial de l'utilisateur principal"],
  about: ["À propos", "ScreenGuard — protection visuelle locale"],
};

function switchPage(name) {
  for (const el of document.querySelectorAll(".nav-item")) {
    el.classList.toggle("active", el.dataset.page === name);
  }
  for (const el of document.querySelectorAll(".page")) {
    el.classList.toggle("active", el.dataset.page === name);
  }
  const [t, s] = PAGE_META[name] || ["", ""];
  $("page-title").textContent = t;
  $("page-sub").textContent = s;
}
document.addEventListener("click", (e) => {
  const b = e.target.closest(".nav-item[data-page]");
  if (b) switchPage(b.dataset.page);
});

// ── State pill / hero ──────────────────────────────────────────────────
const STATE_LABEL = {
  idle: ["Inactif", "Protection désactivée", ""],
  active: ["Actif", "Protection en veille, scan en cours", "online"],
  protected: ["Protégé", "Observateur détecté — overlay actif", "danger"],
  sharing: ["Partage", "Protection temporairement levée", "external"],
  paused: ["Pause", "Scan interrompu", "busy"],
  error: ["Erreur", "La caméra ne répond pas", "danger"],
};

function setPill(state) {
  const [label, motd, cls] = STATE_LABEL[state] || ["—", "", ""];
  $("status-label").textContent = label;
  $("hero-state").textContent = label;
  $("hero-motd").textContent = motd;
  const pill = $("status-pill");
  pill.className = "status-pill" + (cls ? " " + cls : "");
  const pwr = $("power-btn");
  pwr.classList.toggle("on", state === "active" || state === "sharing");
  pwr.classList.toggle("busy", state === "paused");
  pwr.classList.toggle("danger", state === "protected" || state === "error");
  $("share-btn").disabled = !(state === "protected");
  $("dismiss-btn").disabled = !(state === "protected" || state === "sharing");
}

// ── Gauges ─────────────────────────────────────────────────────────────
const GAUGE_LEN = 2 * Math.PI * 68; // 427
function setGauge(id, ratio, color) {
  ratio = Math.max(0, Math.min(1, ratio));
  const el = $(id);
  el.style.strokeDashoffset = String(GAUGE_LEN * (1 - ratio));
  if (color) el.style.stroke = color;
}

function fmtTime(s) {
  s = Math.max(0, Math.floor(s));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}

// ── Live state refresh ─────────────────────────────────────────────────
let lastSettings = null;
async function refresh() {
  const a = api();
  if (!a) return;
  try {
    const st = await a.get_state();
    setPill(st.state);
    $("susp-val").textContent = st.suspicion.toFixed(1);
    $("susp-count").textContent = `${st.suspicion.toFixed(1)} / ${st.threshold}`;
    const ratio = Math.min(1, st.suspicion / Math.max(1, st.threshold));
    let col = "var(--green)";
    if (ratio >= 0.8) col = "var(--red)";
    else if (ratio >= 0.5) col = "var(--amber)";
    setGauge("susp-bar", ratio, col);
    $("susp-foot").textContent =
      st.state === "protected"
        ? "seuil dépassé"
        : ratio > 0.1
        ? "élévation en cours"
        : "en veille";

    $("face-val").textContent = String(st.faces);
    setGauge("face-bar", Math.min(1, st.faces / 3), st.secondary ? "var(--red)" : "var(--blue)");
    $("face-foot").textContent =
      st.secondary > 0 ? `${st.secondary} observateur${st.secondary > 1 ? "s" : ""}` : "aucun observateur";

    if (st.attention > 0) {
      $("att-val").textContent = `${Math.round(st.attention * 100)}%`;
      setGauge("att-bar", st.attention, st.looking ? "var(--cyan)" : "var(--amber)");
      $("att-foot").textContent = st.looking ? "regard sur l'écran" : "regard détourné";
    } else {
      $("att-val").textContent = "—";
      setGauge("att-bar", 0, "var(--muted)");
      $("att-foot").textContent = "utilisateur absent";
    }

    $("hero-uptime").textContent = st.session_s > 0 ? fmtTime(st.session_s) : "—";
    $("session-time").textContent = fmtTime(st.session_s);
    $("cam-state").className = "tunnel-state" + (st.state === "idle" || st.state === "error" ? " err" : st.state !== "idle" ? " on" : "");
    $("cam-state").textContent = st.state === "idle" ? "en attente" : st.state === "error" ? "déconnectée" : "en ligne";

    $("stat-scans").textContent = String(st.scans);
    $("stat-alerts").textContent = String(st.alerts);
    $("stat-share").textContent = st.share_remaining > 0 ? fmtTime(st.share_remaining) : "—";
    $("scan-count").textContent = String(st.scans);
    $("alert-count").textContent = String(st.alerts);
    $("meter-scans").style.width = Math.min(100, (st.scans % 1000) / 10) + "%";
    $("meter-alerts").style.width = Math.min(100, st.alerts * 5) + "%";
    $("meter-share").style.width = st.share_total > 0 ? Math.min(100, (st.share_remaining / st.share_total) * 100) + "%" : "0%";

    $("calib-status").textContent = st.calibrated ? "Calibré ✓" : "Non calibré";
    $("calib-badge").textContent = st.calibrated ? "" : "!";
  } catch (e) {
    // silently ignore poll errors (window may be closing)
  }
}

// ── Power ──────────────────────────────────────────────────────────────
$("power-btn").addEventListener("click", async () => {
  const a = api();
  if (!a) return;
  const on = !$("power-btn").classList.contains("on");
  const ok = await a.toggle_power(on);
  if (!ok) toast("err", "Impossible de démarrer", "Vérifiez la caméra.");
  else toast(on ? "ok" : "info", on ? "ScreenGuard activé" : "ScreenGuard arrêté");
});

$("share-btn").addEventListener("click", async () => {
  const a = api();
  if (!a) return;
  const dur = lastSettings ? lastSettings.share_duration_s : 60;
  await a.grant_share(dur);
  toast("info", `Partage ${dur}s accordé`);
});

$("dismiss-btn").addEventListener("click", async () => {
  const a = api();
  if (!a) return;
  await a.dismiss_protection();
  toast("ok", "Protection levée");
});

// ── Settings ───────────────────────────────────────────────────────────
const SETTINGS_FIELDS = {
  "s-scan-ms": ["scan_interval_ms", "int"],
  "s-threshold": ["suspicion_threshold", "int"],
  "s-decay": ["suspicion_decay", "float"],
  "s-fp": ["false_positive_delay", "int"],
  "s-yaw": ["gaze_yaw_threshold", "float"],
  "s-pitch": ["gaze_pitch_threshold", "float"],
  "s-cam": ["camera_preview", "bool"],
  "s-autostart": ["auto_start", "bool"],
  "s-log": ["log_enabled", "bool"],
  "s-opacity": ["overlay_opacity", "opacity"],
  "s-share": ["share_duration_s", "int"],
  "s-camidx": ["camera_index", "int"],
  "s-pin": ["pin_code", "pin"],
  "s-abs": ["absence_threshold_multiplier", "float"],
};

async function loadSettings() {
  const a = api();
  if (!a) return;
  const s = await a.get_settings();
  lastSettings = s;
  for (const [id, [key, type]] of Object.entries(SETTINGS_FIELDS)) {
    const el = $(id);
    if (!el) continue;
    const v = s[key];
    if (type === "bool") el.checked = !!v;
    else if (type === "opacity") {
      el.value = Math.round((v ?? 0.92) * 100);
      $("l-opacity").textContent = el.value + "%";
    } else if (type === "pin") el.value = v || "";
    else el.value = v;
  }
  markPristine();
}

function collectSettings() {
  const out = {};
  for (const [id, [key, type]] of Object.entries(SETTINGS_FIELDS)) {
    const el = $(id);
    if (!el) continue;
    if (type === "bool") out[key] = el.checked;
    else if (type === "opacity") out[key] = Number(el.value) / 100;
    else if (type === "pin") out[key] = el.value.trim();
    else if (type === "int") out[key] = parseInt(el.value || 0, 10);
    else if (type === "float") out[key] = parseFloat(el.value || 0);
    else out[key] = el.value;
  }
  return out;
}

function markDirty() {
  $("savebar").classList.add("show");
}
function markPristine() {
  $("savebar").classList.remove("show");
}

for (const id of Object.keys(SETTINGS_FIELDS)) {
  const el = $(id);
  if (!el) continue;
  el.addEventListener(el.type === "checkbox" ? "change" : "input", () => {
    if (id === "s-opacity") $("l-opacity").textContent = el.value + "%";
    markDirty();
  });
}

$("btn-apply").addEventListener("click", async () => {
  const a = api();
  if (!a) return;
  const payload = collectSettings();
  const ok = await a.set_settings(payload);
  if (ok) {
    lastSettings = payload;
    markPristine();
    toast("ok", "Paramètres appliqués");
  } else {
    toast("err", "Code PIN invalide", "4 chiffres ou vide.");
  }
});
$("btn-reset").addEventListener("click", () => loadSettings());

// ── Calibration ────────────────────────────────────────────────────────
$("btn-calib").addEventListener("click", async () => {
  const a = api();
  if (!a) return;
  const r = await a.start_calibration();
  if (r === "ok") toast("ok", "Calibration réussie");
  else if (r === "need_power") toast("err", "Activez d'abord ScreenGuard");
  else if (r === "cancelled") toast("info", "Calibration annulée");
  else toast("err", "Échec de la calibration");
});

$("btn-reset-profile").addEventListener("click", async () => {
  const a = api();
  if (!a) return;
  await a.reset_profile();
  toast("info", "Profil réinitialisé");
});

// ── Toasts ─────────────────────────────────────────────────────────────
const ICON = {
  ok: '<svg><use href="#i-check"/></svg>',
  err: '<svg><use href="#i-warn"/></svg>',
  info: '<svg><use href="#i-info"/></svg>',
};
function toast(kind, title, sub) {
  const t = document.createElement("div");
  t.className = "toast " + kind;
  t.innerHTML = `${ICON[kind] || ICON.info}<div><b>${title}</b>${sub ? `<span class="t">${sub}</span>` : ""}</div>`;
  $("toasts").appendChild(t);
  setTimeout(() => {
    t.classList.add("out");
    setTimeout(() => t.remove(), 300);
  }, 3200);
}

// ── Boot ───────────────────────────────────────────────────────────────
function boot() {
  loadSettings().catch(() => setTimeout(boot, 200));
  refresh();
  setInterval(refresh, 400);
}
if (window.pywebview) boot();
else window.addEventListener("pywebviewready", boot);
