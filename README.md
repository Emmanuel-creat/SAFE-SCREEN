# ScreenGuard Phase 2 — Desktop Visual Privacy Shield

## Présentation

ScreenGuard Phase 2 est une application desktop locale de protection visuelle d'écran. Elle utilise **MediaPipe Face Mesh** (468 landmarks faciaux) pour détecter les visages, estimer la direction du regard, calibrer le profil de l'utilisateur principal, et protéger l'écran contre les observateurs non autorisés.

Tout le traitement est **100% local** : aucun cloud, aucune API externe, aucun enregistrement vidéo.

## Installation complète

### Prérequis
- Python 3.10 ou supérieur
- Webcam fonctionnelle
- Windows 10+, macOS 12+, ou Linux (X11)

### Étapes

```bash
cd screenguard2
python -m venv .venv

# Windows :
.venv\Scripts\activate
# macOS/Linux :
source .venv/bin/activate

pip install -r requirements.txt
```

## Exécution

```bash
python main.py
```

Au premier lancement :
1. Un dossier `~/.screenguard/` est créé avec la configuration.
2. La fenêtre principale s'ouvre.
3. Un assistant de calibration vous guide pour enregistrer votre visage.

## Packaging .exe (PyInstaller)

```bash
pip install pyinstaller
pyinstaller build.spec --noconfirm
```

Le résultat sera dans `dist/ScreenGuard/ScreenGuard.exe`.

Le `build.spec` inclut :
- L'icône `.ico` comme icône de l'exécutable
- Les données MediaPipe (modèles `.tflite`) via `collect_data_files`
- Les données OpenCV (Haar cascades en fallback)
- Tous les modules du projet en `hiddenimports`
- `pathex=['.']` pour la résolution des imports
- `console=True` par défaut pour le debug (passer à `False` pour la release)

Pour passer en mode release (sans console) : dans `build.spec`, remplacer `console=True` par `console=False`, puis relancer `pyinstaller build.spec --noconfirm`.

## Paramètres détaillés

| Paramètre | Défaut | Description |
|---|---|---|
| `scan_interval_ms` | 500 | Intervalle entre deux scans caméra (ms). Min 100, max 5000. |
| `suspicion_threshold` | 6 | Score de suspicion déclenchant la protection |
| `suspicion_decay` | 0.8 | Décroissance du score par scan sans détection |
| `false_positive_delay` | 3 | Scans consécutifs requis avant incrémentation |
| `share_duration_s` | 60 | Durée de partage temporaire par défaut (s) |
| `camera_preview` | false | Afficher le flux caméra dans la mini-fenêtre |
| `camera_index` | 0 | Index de la caméra (0 = défaut) |
| `overlay_opacity` | 0.92 | Opacité de l'overlay de protection (0.5–1.0) |
| `log_enabled` | true | Activer la journalisation dans un fichier |
| `auto_start` | true | Activer le système automatiquement au lancement |
| `gaze_yaw_threshold` | 25.0 | Angle de lacet max (°) pour considérer le regard sur l'écran |
| `gaze_pitch_threshold` | 20.0 | Angle de tangage max (°) pour considérer le regard sur l'écran |
| `calibration_done` | false | Indique si la calibration a été effectuée |
| `user_encoding` | null | Encodage facial de l'utilisateur principal (auto-généré) |

## Utilisation

### Premier lancement
1. Lancez l'application.
2. Cliquez sur le bouton ON/OFF pour activer le système.
3. Un dialogue de calibration s'ouvre : regardez la caméra pendant 3 secondes.
4. ScreenGuard apprend votre visage et vos paramètres faciaux de référence.

### Fonctionnement normal
- **Bouton ON/OFF** : active ou désactive le système complet.
- **Mini-fenêtre flottante** : affiche l'état, les stats temps réel, le score de suspicion.
  - Clic sur `›` : replie la fenêtre sur le bord de l'écran.
  - Clic sur l'onglet replié : déplie la fenêtre.
  - Clic sur `⇩` : passe la fenêtre en arrière-plan.
- **Protection déclenchée** : overlay plein écran + popup de décision.
  - "Maintenir la protection" → l'overlay reste, un bouton "Déverrouiller" apparaît en bas.
  - "Partager temporairement" → choisir la durée, protection levée temporairement.
  - "Fausse alerte" → retour à l'état actif.

### Paramètres
Accessibles depuis la fenêtre principale : détection, affichage, système, calibration.

## Logique métier

### Machine à états
```
IDLE ──▶ ACTIVE ──▶ PROTECTED ──▶ ACTIVE (dismiss)
  │         │            │
  │         │            ▼
  │         │        SHARING ──▶ ACTIVE (expiration)
  │         │
  │         ▼
  │       PAUSED ──▶ ACTIVE (resume)
  │
  ▼
ERROR ──▶ IDLE (reset)
```

### Pipeline de détection (chaque scan)
1. Capture d'une frame (640×480).
2. MediaPipe Face Mesh détecte les landmarks faciaux.
3. Identification du visage principal via comparaison avec le profil calibré.
4. Estimation du regard (yaw/pitch) via les landmarks des yeux et du nez.
5. Classification des visages secondaires comme observateurs potentiels.
6. Calcul du score de suspicion :
   - +1.5 par visage secondaire détecté (après `false_positive_delay` scans consécutifs).
   - +0.5 si le visage principal est absent (après délai).
   - +0.3 si le regard de l'utilisateur est détourné de l'écran.
   - −décroissance si aucune menace détectée et regard centré.
7. Si `score >= threshold` → état PROTECTED.

### Calibration
- Capture de 5 frames du visage sur 3 secondes.
- Calcul d'un encodage facial basé sur les distances inter-landmarks normalisées.
- Stockage local dans la configuration.
- Utilisé pour distinguer l'utilisateur principal des observateurs.

## Architecture

```
screenguard2/
├── main.py                     # Point d'entrée avec gestion crash
├── requirements.txt            # Dépendances Python
├── build.spec                  # Configuration PyInstaller
├── README.md                   # Ce fichier
├── assets/
│   ├── icon.ico                # Icône œil barré multi-résolution
│   └── icon.png                # Version PNG
├── config/
│   ├── __init__.py
│   ├── settings.py             # Configuration persistante JSON
│   └── profiles.py             # Gestion profils utilisateur
├── core/
│   ├── __init__.py
│   ├── engine.py               # Moteur principal, boucle de scan
│   ├── logger.py               # Logging rotatif
│   └── state_machine.py        # Machine à états formelle
├── vision/
│   ├── __init__.py
│   ├── mediapipe_detector.py   # Détection MediaPipe Face Mesh
│   ├── calibrator.py           # Calibration visage utilisateur
│   ├── user_profiles.py        # Encodage et comparaison faciale
│   └── gaze_estimator.py       # Estimation direction du regard
└── ui/
    ├── __init__.py
    ├── main_window.py          # Fenêtre principale + paramètres
    ├── mini_window.py          # Mini-fenêtre flottante repliable
    ├── overlay.py              # Overlay protection plein écran
    ├── calibration_dialog.py   # Dialogue de calibration guidé
    ├── styles.qss              # Feuille de style Qt externe
    └── widgets.py              # Widgets custom (PowerButton, jauges)
```

## Dépendances

| Paquet | Version | Rôle |
|---|---|---|
| Python | ≥ 3.10 | Runtime |
| PyQt6 | ≥ 6.6 | Interface graphique |
| mediapipe | ≥ 0.10.9 | Face Mesh 468 landmarks |
| opencv-python-headless | ≥ 4.9 | Capture caméra, traitement image |
| numpy | ≥ 1.24 | Calcul vectoriel |
| PyInstaller | ≥ 6.0 | Packaging (dev uniquement) |

## Limitations

- MediaPipe Face Mesh nécessite un éclairage correct (pas d'obscurité totale).
- L'estimation du regard est heuristique (landmarks, pas eye-tracking IR).
- La calibration doit être refaite si l'apparence change significativement (lunettes, coiffure).
- Les lunettes de soleil opaques bloquent la détection du regard.
- L'overlay peut ne pas couvrir tous les écrans en configuration multi-écrans avancée.
- Le scan à 500ms est un compromis réactivité/énergie.

## Optimisation énergétique

- Scan configurable : 500ms par défaut, jusqu'à 5000ms en mode économie.
- MediaPipe est exécuté en mode CPU (`model_complexity=0` pour la rapidité).
- `max_num_faces=4` pour limiter les calculs.
- Le retour caméra est désactivé par défaut (pas de conversion RGB→QImage inutile).
- La caméra est libérée quand le système est désactivé.
- Les frames ne sont pas stockées au-delà du scan courant.
- L'animation de l'overlay utilise un timer à 50ms uniquement quand visible.

## Guide développeur

### Ajouter un détecteur
Implémenter la même interface que `MediaPipeDetector` dans `vision/` et remplacer l'instanciation dans `engine.py`.

### Modifier l'overlay
Éditer `ui/overlay.py`. Le rendu est en QPainter pur.

### Ajouter un profil
Les profils sont gérés dans `vision/user_profiles.py`. L'encodage est un vecteur de distances inter-landmarks normalisées.

### Tests
Les classes `core/` et `vision/` sont testables unitairement avec pytest :
```bash
pip install pytest
pytest tests/ -v
```

Exemple de test :
```python
from core.state_machine import StateMachine, GuardState

def test_transitions():
    sm = StateMachine()
    assert sm.state == GuardState.IDLE
    sm.transition_to(GuardState.ACTIVE)
    assert sm.state == GuardState.ACTIVE
    sm.transition_to(GuardState.PROTECTED)
    assert sm.state == GuardState.PROTECTED
```

## Pistes d'évolution

- Eye-tracking par détection de l'iris (MediaPipe Iris).
- Multi-utilisateurs autorisés (whitelist de profils).
- Raccourcis clavier globaux (pynput).
- Notifications système natives (plyer).
- Chiffrement AES de la configuration.
- Thème clair optionnel.
- Tray icon avec menu contextuel.
- Mode furtif (fenêtre invisible, activation automatique silencieuse).
- Export des logs en CSV.
- API locale pour intégration domotique.
