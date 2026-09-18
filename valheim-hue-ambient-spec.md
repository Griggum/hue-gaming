# Valheim Hue Ambient Lighting — Development Specification

**Project name:** Valheim Hue Ambient  
**Document purpose:** Development specification for Codex-assisted implementation  
**Target platform:** Windows 11 gaming PC  
**Lighting platform:** Philips Hue Bridge Pro + 4 rectangular Hue lights + 1 Hue bedside light  
**Game:** Valheim  
**Game constraint:** **Vanilla Valheim only. No client mods, no server mods, no BepInEx, no Jötunn, no addons/plugins.**  
**Server model:** Managed hosted Valheim server; the server must remain completely unaware of this project.

---

## 1. Project Goal

Build a local Windows companion application that makes Philips Hue lights behave as an extension of the current Valheim environment.

The system must:

1. Detect the player's current biome using only information visible on screen.
2. Map the detected biome to a curated Hue lighting profile.
3. Control five Hue lights through a Philips Hue Bridge Pro.
4. Produce subtle, slow, environmental lighting rather than flashy RGB effects.
5. Require **zero modification of Valheim**.
6. Require **zero modification of the hosted Valheim server**.
7. Be designed so additional external-only detection can later add:
   - day/night
   - weather
   - dungeons/interiors
   - raids/events
   - bosses

The intended result is:

> Make the room feel like an extension of Valheim while keeping the lighting subtle enough that the player notices the game world, not the Hue system.

---

## 2. Non-Goals

The first versions of the project must **not**:

- modify the Valheim executable;
- inject code into the game;
- read process memory;
- use DLL injection;
- use BepInEx;
- use Jötunn;
- install client-side mods;
- install server-side mods;
- automate player input;
- simulate keyboard or mouse input;
- alter gameplay;
- depend on administrative access to the hosted server;
- require communication with the hosted server;
- mirror the entire screen in the style of Hue Sync;
- react rapidly to every spell/effect/pixel change;
- behave like generic RGB gaming lighting.

The companion app is a passive observer plus Hue controller.

---

## 3. Hardware

### 3.1 Existing Hardware

The intended setup contains:

- **4 × rectangular Philips Hue lights**
- **1 × Philips Hue bedside lamp**
- **1 × Philips Hue Bridge Pro**
- **1 × Windows 11 gaming PC**

The Bridge Pro is connected to the same local network as the PC.

---

## 4. Logical Light Layout

The lighting engine must support five independent logical channels.

Recommended logical naming:

```text
R1 = rectangle_front_left
R2 = rectangle_front_right
R3 = rectangle_rear_left
R4 = rectangle_rear_right
B1 = bedside
```

The actual physical placement may differ. Therefore:

- do not hardcode Hue light IDs;
- provide a configuration step mapping Hue devices to logical channels;
- persist those mappings.

Example:

```yaml
lights:
  rectangle_front_left:  "hue-resource-id-1"
  rectangle_front_right: "hue-resource-id-2"
  rectangle_rear_left:   "hue-resource-id-3"
  rectangle_rear_right:  "hue-resource-id-4"
  bedside:                "hue-resource-id-5"
```

---

## 5. Design Philosophy

### 5.1 Location Drives the Lighting

The system should behave like:

```text
Valheim
   │
   │ visible game state
   ▼
Screen Capture
   │
   ▼
Detection
   │
   ▼
Game State
   │
   ▼
Profile Resolver
   │
   ▼
Ambient Lighting Engine
   │
   ▼
Hue Bridge Pro
   │
   ├── R1
   ├── R2
   ├── R3
   ├── R4
   └── B1
```

The primary state in V1 is:

```text
current biome
```

Future state may become:

```text
biome
+ day/night
+ weather
+ interior/dungeon
+ raid/event
+ boss encounter
```

---

## 6. Why External Screen Detection

Because the project must remain fully vanilla, the companion must derive state from what Valheim renders.

The first and most reliable target is the **biome label displayed near the minimap**.

The problem is therefore a constrained OCR/classification task rather than general text recognition.

Known target categories include:

```text
Meadows
Black Forest
Swamp
Mountain
Plains
Mistlands
Ashlands
Deep North
Ocean
```

The implementation should make biome aliases/configurable because game updates, localization, or future biomes may change this list.

---

# 7. High-Level Architecture

Recommended architecture:

```text
+---------------------+
|      Valheim        |
|    Vanilla Client   |
+----------+----------+
           |
           | screen pixels only
           v
+---------------------+
| Screen Capture      |
| Service             |
+----------+----------+
           |
           v
+---------------------+
| State Detectors     |
|                     |
| V1: Biome OCR       |
| V2: Time classifier |
| V3: Weather         |
| V4: Interior/Event  |
+----------+----------+
           |
           v
+---------------------+
| State Aggregator    |
+----------+----------+
           |
           v
+---------------------+
| Profile Resolver    |
+----------+----------+
           |
           v
+---------------------+
| Ambient Engine      |
| - transitions       |
| - random drift      |
| - modifiers         |
| - hysteresis        |
+----------+----------+
           |
           v
+---------------------+
| Hue Controller      |
+----------+----------+
           |
           v
+---------------------+
| Hue Bridge Pro      |
+---------------------+
```

---

# 8. Recommended Project Structure

Suggested Python implementation:

```text
valheim-hue/
├── README.md
├── pyproject.toml
├── config/
│   ├── app.yaml
│   ├── lights.yaml
│   └── profiles/
│       └── valheim.yaml
├── src/
│   └── valheim_hue/
│       ├── __init__.py
│       ├── main.py
│       ├── app.py
│       │
│       ├── capture/
│       │   ├── __init__.py
│       │   ├── screen.py
│       │   └── roi.py
│       │
│       ├── detection/
│       │   ├── __init__.py
│       │   ├── biome.py
│       │   ├── time_of_day.py
│       │   ├── weather.py
│       │   ├── interior.py
│       │   ├── event.py
│       │   └── boss.py
│       │
│       ├── state/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── aggregator.py
│       │   └── hysteresis.py
│       │
│       ├── ambient/
│       │   ├── __init__.py
│       │   ├── profiles.py
│       │   ├── resolver.py
│       │   ├── engine.py
│       │   ├── motion.py
│       │   └── transitions.py
│       │
│       ├── hue/
│       │   ├── __init__.py
│       │   ├── bridge.py
│       │   ├── discovery.py
│       │   ├── resources.py
│       │   └── controller.py
│       │
│       ├── ui/
│       │   ├── __init__.py
│       │   └── tray.py
│       │
│       └── util/
│           ├── logging.py
│           └── timing.py
│
└── tests/
    ├── test_biome_detection.py
    ├── test_hysteresis.py
    ├── test_profile_resolver.py
    ├── test_motion.py
    └── fixtures/
```

Python is recommended initially for development speed.

A later production rewrite in Rust/C# is optional and not required for V1.

---

# 9. V1 Scope

V1 should only solve:

```text
detect biome
→ map biome to profile
→ control Hue lights
```

Do not add weather, boss detection, or advanced CV before V1 is stable.

---

# 10. Screen Capture

## 10.1 Requirements

The screen capture component must:

- operate locally on Windows;
- capture only the Valheim game window if possible;
- otherwise capture a configured monitor;
- avoid capturing the entire screen if only a small region is required;
- support fullscreen, borderless fullscreen, and windowed modes where practical;
- run with low CPU overhead;
- not interfere with gameplay.

Recommended capture interval for V1:

```text
2–4 samples per second
```

Biome changes are slow. There is no need for 30–60 FPS processing.

---

## 10.2 Region of Interest

V1 should crop only the minimap/biome-label region.

Do not OCR the entire frame.

Example configurable ROI:

```yaml
capture:
  monitor: 1

  biome_roi:
    mode: relative

    x: 0.78
    y: 0.02
    width: 0.20
    height: 0.12
```

Relative coordinates are preferred so different resolutions can be supported.

---

# 11. Biome Detection

## 11.1 Strategy

Recommended pipeline:

```text
screen capture
↓
crop biome ROI
↓
image preprocessing
↓
OCR
↓
normalize text
↓
fuzzy-match against allowed biome list
↓
confidence score
↓
hysteresis/stability filter
↓
accepted biome
```

---

## 11.2 Allowed Biomes

Initial canonical identifiers:

```yaml
biomes:
  meadows:
    labels:
      - Meadows

  black_forest:
    labels:
      - Black Forest

  swamp:
    labels:
      - Swamp

  mountain:
    labels:
      - Mountain

  plains:
    labels:
      - Plains

  mistlands:
    labels:
      - Mistlands

  ashlands:
    labels:
      - Ashlands

  deep_north:
    labels:
      - Deep North

  ocean:
    labels:
      - Ocean
```

The list must remain configuration-driven.

---

## 11.3 Fuzzy Matching

OCR is expected to make errors.

Examples:

```text
"Black Farest"
"BlackForest"
"BlacK Forest"
"Swarnp"
"MistIands"
```

These should resolve to known biome names when similarity exceeds a threshold.

Suggested initial threshold:

```text
85%
```

Tune through testing.

Never accept arbitrary OCR text directly as a biome.

---

## 11.4 Temporal Stability

A single OCR frame must not trigger a lighting switch.

Example rule:

```text
same candidate detected
for >= 3 consecutive samples
AND confidence >= threshold
→ accept new biome
```

Alternative:

```text
candidate is dominant over a rolling 2-second window
→ accept
```

This is important near biome boundaries.

---

# 12. Hysteresis

Valheim biome boundaries can be crossed repeatedly while moving around.

Without hysteresis this could produce:

```text
Meadows
Black Forest
Meadows
Black Forest
Meadows
```

within a few seconds.

The system must avoid rapid scene thrashing.

Recommended rules:

```text
minimum biome stability: 1.5–3 seconds
minimum scene dwell time: 3–5 seconds
```

Optional confidence weighting:

```text
new biome confidence > current biome confidence + margin
```

---

# 13. Base Biome Lighting Profiles

These are initial artistic defaults.

They should remain user-editable.

| Biome | Dominant | Accent | Bedside | Movement |
|---|---|---|---|---|
| Meadows | warm green | sunlight gold | amber | subtle |
| Black Forest | deep green | cool blue | dark green | ambient |
| Swamp | murky green | teal | dirty violet | ambient |
| Mountain | ice blue | cold white | pale violet | subtle |
| Plains | warm gold | dry green | orange | subtle |
| Mistlands | violet | teal/blue | deep purple | ambient |
| Ashlands | deep red | magma orange | crimson | active |
| Deep North | cyan | blue-white | pale blue | ambient |
| Ocean | deep blue | cyan | dark blue | slow ambient |

---

# 14. Example Five-Light Profiles

## Meadows

```yaml
meadows:
  motion: ambient
  scene_transition_seconds: 4

  lights:

    rectangle_front_left:
      palette:
        - "#59844B"
        - "#628D50"
      brightness: [38, 44]

    rectangle_front_right:
      palette:
        - "#5A8249"
        - "#6C904F"
      brightness: [36, 43]

    rectangle_rear_left:
      palette:
        - "#C59A4A"
        - "#D1A351"
      brightness: [28, 35]

    rectangle_rear_right:
      palette:
        - "#B9893D"
        - "#C89A49"
      brightness: [25, 34]

    bedside:
      palette:
        - "#8D6537"
        - "#9A7040"
      brightness: [12, 18]
```

---

## Black Forest

```yaml
black_forest:
  motion: ambient
  scene_transition_seconds: 4

  lights:

    rectangle_front_left:
      palette:
        - "#244F36"
        - "#2D5A3C"
        - "#356246"
      brightness: [28, 35]

    rectangle_front_right:
      palette:
        - "#1E4632"
        - "#28573D"
      brightness: [27, 34]

    rectangle_rear_left:
      palette:
        - "#344B65"
        - "#3C5673"
      brightness: [18, 25]

    rectangle_rear_right:
      palette:
        - "#2D5360"
        - "#365F69"
      brightness: [20, 28]

    bedside:
      palette:
        - "#163226"
        - "#1D3A2A"
      brightness: [9, 15]
```

---

## Swamp

```yaml
swamp:
  motion: ambient
  scene_transition_seconds: 3

  lights:

    rectangle_front_left:
      palette:
        - "#3F5D35"
        - "#4C6939"
      brightness: [22, 30]

    rectangle_front_right:
      palette:
        - "#34574E"
        - "#41655A"
      brightness: [20, 28]

    rectangle_rear_left:
      palette:
        - "#3C5252"
        - "#46615B"
      brightness: [18, 26]

    rectangle_rear_right:
      palette:
        - "#4D5131"
        - "#585C35"
      brightness: [18, 25]

    bedside:
      palette:
        - "#302B38"
        - "#3A3341"
      brightness: [8, 14]
```

---

## Mountain

```yaml
mountain:
  motion: subtle
  scene_transition_seconds: 4

  lights:

    rectangle_front_left:
      palette:
        - "#8EB9CD"
        - "#A0CADB"
      brightness: [38, 48]

    rectangle_front_right:
      palette:
        - "#769FBD"
        - "#88AEC8"
      brightness: [36, 46]

    rectangle_rear_left:
      palette:
        - "#C4D8E1"
        - "#D0E2E8"
      brightness: [30, 40]

    rectangle_rear_right:
      palette:
        - "#8E9FC3"
        - "#A2AED0"
      brightness: [28, 38]

    bedside:
      palette:
        - "#7A86A5"
        - "#8E97B3"
      brightness: [12, 20]
```

---

## Plains

```yaml
plains:
  motion: subtle
  scene_transition_seconds: 4

  lights:

    rectangle_front_left:
      palette:
        - "#B69A3A"
        - "#C3A846"
      brightness: [38, 46]

    rectangle_front_right:
      palette:
        - "#9E903A"
        - "#ADA042"
      brightness: [35, 44]

    rectangle_rear_left:
      palette:
        - "#D0A44A"
        - "#DAB157"
      brightness: [30, 38]

    rectangle_rear_right:
      palette:
        - "#7F8337"
        - "#8B913B"
      brightness: [28, 36]

    bedside:
      palette:
        - "#9A6031"
        - "#A86B37"
      brightness: [13, 20]
```

---

## Mistlands

```yaml
mistlands:
  motion: ambient
  scene_transition_seconds: 3

  lights:

    rectangle_front_left:
      palette:
        - "#604C7F"
        - "#6B568C"
      brightness: [26, 34]

    rectangle_front_right:
      palette:
        - "#385F75"
        - "#426D82"
      brightness: [25, 33]

    rectangle_rear_left:
      palette:
        - "#39716C"
        - "#447C76"
      brightness: [22, 30]

    rectangle_rear_right:
      palette:
        - "#54416D"
        - "#654D7E"
      brightness: [22, 30]

    bedside:
      palette:
        - "#332741"
        - "#3C2C4B"
      brightness: [9, 15]
```

---

## Ashlands

```yaml
ashlands:
  motion: active
  scene_transition_seconds: 2

  lights:

    rectangle_front_left:
      palette:
        - "#8B201B"
        - "#A82B1F"
      brightness: [30, 40]

    rectangle_front_right:
      palette:
        - "#B9441D"
        - "#D25A22"
      brightness: [32, 44]

    rectangle_rear_left:
      palette:
        - "#6F1818"
        - "#8C201A"
      brightness: [24, 34]

    rectangle_rear_right:
      palette:
        - "#A63C1B"
        - "#C14D1F"
      brightness: [27, 38]

    bedside:
      palette:
        - "#4A1215"
        - "#5B1717"
      brightness: [10, 17]
```

---

## Deep North

```yaml
deep_north:
  motion: ambient
  scene_transition_seconds: 4

  lights:

    rectangle_front_left:
      palette:
        - "#8DCBD9"
        - "#A0D7E1"
      brightness: [38, 48]

    rectangle_front_right:
      palette:
        - "#79B8CC"
        - "#8CC8D8"
      brightness: [36, 46]

    rectangle_rear_left:
      palette:
        - "#C1DDE4"
        - "#D0E8EC"
      brightness: [32, 42]

    rectangle_rear_right:
      palette:
        - "#839EC2"
        - "#97ADD0"
      brightness: [28, 38]

    bedside:
      palette:
        - "#7184A0"
        - "#8293AB"
      brightness: [12, 19]
```

---

## Ocean

```yaml
ocean:
  motion: ambient
  scene_transition_seconds: 4

  lights:

    rectangle_front_left:
      palette:
        - "#174A68"
        - "#1C5678"
      brightness: [25, 34]

    rectangle_front_right:
      palette:
        - "#1D5B71"
        - "#256A81"
      brightness: [24, 33]

    rectangle_rear_left:
      palette:
        - "#24788A"
        - "#2F8798"
      brightness: [20, 29]

    rectangle_rear_right:
      palette:
        - "#214E6B"
        - "#295B78"
      brightness: [21, 30]

    bedside:
      palette:
        - "#183247"
        - "#1E3B50"
      brightness: [8, 14]
```

---

# 15. Ambient Motion Model

The lighting should not be completely static in most locations.

However, changes should be subtle.

The player should usually notice:

> The room feels like the biome.

The player should **not** notice:

> The RGB lights changed again.

---

## 15.1 Motion Classes

### STATIC

Characteristics:

- almost no color movement;
- optional brightness drift of approximately ±2%;
- long transition intervals.

Typical use:

- bright calm environments.

---

### SUBTLE

Characteristics:

- tiny color changes;
- ±2–4% brightness;
- transitions every 45–120 seconds.

Typical use:

- Mountains
- Plains
- bright snow environments

---

### AMBIENT

Default mode.

Characteristics:

- slow independent light variation;
- constrained color palette;
- ±3–7% brightness;
- transitions every 20–90 seconds.

Typical use:

- Meadows
- Black Forest
- Swamp
- Mistlands
- Ocean

---

### ACTIVE

Still environmental, not flashy.

Characteristics:

- stronger brightness movement;
- slightly quicker transitions;
- randomized timing;
- no synchronized breathing.

Typical use:

- Ashlands
- fire
- storm
- boss/event overlays

---

# 16. Randomized Independent Motion

Never animate all lights identically.

Bad:

```text
all lights:
30%
→ 40%
→ 30%
every 5 seconds
```

Good:

```text
R1 +3%
wait 7.4 sec

R4 warmer
wait 11.2 sec

R2 -2%
wait 5.7 sec

B1 +2%
wait 13.1 sec
```

Each logical light should maintain:

```text
current color
target color
current brightness
target brightness
next transition time
```

Random values must remain inside that light's allowed profile bounds.

---

# 17. Hue Controller

## 17.1 Responsibilities

The Hue module should:

- discover/configure the Bridge Pro;
- authenticate;
- store credentials locally;
- enumerate lights;
- map Hue resource IDs to logical channels;
- set color;
- set brightness;
- transition smoothly;
- reconnect automatically;
- handle bridge/network outages;
- rate-limit commands.

---

## 17.2 Failure Behavior

If the bridge becomes unavailable:

1. log the error;
2. stop issuing commands;
3. retry with exponential backoff;
4. do not crash the entire companion app;
5. resume the current desired scene after reconnect.

---

# 18. Application State Model

Example internal model:

```python
@dataclass
class GameState:
    biome: str | None
    time_of_day: str | None
    weather: str | None
    interior: str | None
    event: str | None
    boss: str | None
    confidence: float
```

V1 only populates:

```text
biome
confidence
```

All other fields remain:

```text
None
```

---

# 19. Profile Resolution

Future intended priority:

```text
boss/event override
        ↓
interior override
        ↓
weather modifier
        ↓
time-of-day modifier
        ↓
biome base profile
```

Example:

```text
Swamp
+
Night
+
Rain
+
Sunken Crypt
```

should resolve to:

```text
Sunken Crypt base
+
night modifier if appropriate
+
rain ignored because interior
```

The resolver should explicitly decide which modifiers apply in each context.

---

# 20. V2 — Day/Night Detection

Day/night must remain external-only.

Do not attempt exact in-game clock synchronization initially.

Use broad states:

```text
DAY
TWILIGHT
NIGHT
```

---

## 20.1 Detection Strategy

Use screen luminance sampling from multiple configurable regions.

Avoid relying on one location because:

- trees create shade;
- buildings create darkness;
- fog alters brightness;
- looking at the ground alters average luminance.

Suggested approach:

```text
sample several screen regions
↓
exclude UI
↓
calculate luminance statistics
↓
rolling average
↓
state classifier
↓
20–30 second hysteresis
```

---

## 20.2 Example Modifiers

```yaml
time_modifiers:

  day:
    brightness_multiplier: 1.00
    saturation_multiplier: 1.00

  twilight:
    brightness_multiplier: 0.78
    warmth_shift: 0.10

  night:
    brightness_multiplier: 0.55
    warmth_shift: -0.15
```

Biome palette identity must remain intact.

---

# 21. V3 — Weather Detection

Weather is not expected to be explicitly printed by Valheim.

Therefore weather detection is a computer-vision problem.

Initial broad classes:

```text
CLEAR
RAIN
STORM
SNOW
BLIZZARD
MIST
ASH
UNKNOWN
```

Avoid trying to identify every internal Valheim environment state.

---

## 21.1 Weather as Modifier

Weather should not replace the biome.

Instead:

```text
final state =
biome base
× weather modifier
```

Example:

```text
Black Forest
+
Rain
```

Possible modifier:

```yaml
rain:
  brightness_multiplier: 0.80
  saturation_multiplier: 0.90
  cool_shift: 0.10
  motion_multiplier: 1.15
```

---

## 21.2 Storm Modifier

Example:

```yaml
storm:
  brightness_multiplier: 0.70
  saturation_multiplier: 0.85
  cool_shift: 0.20
  motion_multiplier: 1.30
```

Do not flash lights in sync with every lightning strike in the first implementation.

Lightning synchronization could be considered later as an optional effect.

---

# 22. V4 — Dungeon / Interior Detection

This is significantly more difficult without game integration.

Potential interiors include:

```text
Burial Chambers
Troll Cave
Sunken Crypt
Frost Cave
Infested Mine
other future interiors
```

Recommended approach:

```text
visual classifier
```

This can be implemented after collecting screenshot datasets.

---

## 22.1 Dataset

Create:

```text
datasets/interiors/
├── outdoor/
├── burial_chamber/
├── troll_cave/
├── sunken_crypt/
├── frost_cave/
└── infested_mine/
```

Capture screenshots during normal gameplay.

Training data should include:

- different directions;
- different rooms;
- different resolutions if relevant;
- torches/no torches;
- multiplayer players on screen;
- combat;
- menus closed;
- varying gamma.

---

## 22.2 Conservative Activation

Interior classification must be stable before switching.

Example:

```text
same interior classification
>= 2 seconds
with high confidence
→ activate
```

Returning outdoors should follow the same rule.

---

# 23. V5 — Raid / World Event Detection

Valheim world events display recognizable text.

External OCR can detect these event messages.

Examples should be configured rather than hardcoded.

Architecture:

```text
center-screen text ROI
↓
OCR
↓
event phrase matcher
↓
temporary Hue overlay
```

---

## 23.1 Temporary Override Model

Example:

```text
Current:
Meadows

Event starts:
"The forest is moving..."

Lighting:
Meadows base
+
event overlay

Event ends:
restore Meadows state smoothly
```

The event scene should **modify** the base biome where possible rather than discard it completely.

---

# 24. V6 — Boss Detection

Potential approaches:

1. detect boss health-bar/UI;
2. OCR known boss names;
3. combine UI-template detection with text recognition.

Boss state should become the highest-priority lighting override.

Example conceptual profiles:

| Boss | Palette |
|---|---|
| Eikthyr | storm blue / white / violet |
| The Elder | ancient green / ember orange |
| Bonemass | toxic green / muddy teal |
| Moder | ice blue / white / violet |
| Yagluth | fire red / gold / black-red |

Later bosses should receive their own profiles.

---

# 25. Optional Lightning Detection

A future optional feature:

```text
screen flash detection
→ very brief cool-white Hue flash
```

Strict constraints:

- disabled by default;
- low intensity;
- no rapid strobing;
- rate limited;
- user-configurable.

The implementation should prioritize comfort.

---

# 26. Profile Configuration Format

Profiles must remain external to application code.

Recommended:

```text
YAML
```

Example:

```yaml
profiles:

  black_forest:

    motion:
      mode: ambient
      transition_min_seconds: 25
      transition_max_seconds: 70

    scene_transition_seconds: 4

    lights:

      rectangle_front_left:
        palette:
          - "#244F36"
          - "#2D5A3C"
          - "#356246"

        brightness:
          min: 28
          max: 35

      rectangle_rear_left:
        palette:
          - "#344B65"
          - "#3C5673"

        brightness:
          min: 18
          max: 25
```

---

# 27. Manual Overrides

The app should provide:

```text
AUTO
PAUSE
OFF
MANUAL PROFILE
```

AUTO:

```text
game state controls lighting
```

PAUSE:

```text
stop changing lights
retain current state
```

OFF:

```text
restore configured neutral/default scene
```

MANUAL:

```text
user selects a biome profile manually
```

Manual mode is important for testing.

---

# 28. System Tray UI

V1 does not need a large GUI.

A Windows tray application is sufficient.

Suggested status menu:

```text
Valheim Hue Ambient
─────────────────────────────
Status: Running
Valheim: Detected
Hue Bridge: Connected

Biome:
Black Forest

Confidence:
97%

Mode:
AUTO

──────────────
Pause
Manual profile >
Open config
Open logs
Exit
```

---

# 29. Debug Mode

Debugging CV/OCR requires visibility.

Optional debug window should show:

```text
full capture preview
biome ROI
OCR raw text
matched biome
confidence
current game state
resolved Hue profile
```

Debug screenshots may optionally be saved.

Example:

```text
debug/
2026-09-18_190423_black_forest_91.png
```

Debug capture must be disabled by default.

---

# 30. Logging

Use structured logs.

Recommended levels:

```text
DEBUG
INFO
WARNING
ERROR
```

Examples:

```text
INFO biome_candidate raw="Black Farest" matched="black_forest" confidence=0.93
INFO biome_changed old="meadows" new="black_forest"
INFO profile_applied profile="black_forest"
WARNING hue_bridge_unreachable retry_seconds=4
```

Rotate logs.

Do not allow unlimited log growth.

---

# 31. Privacy

Screen processing should be local.

V1 must:

- not upload screenshots;
- not send OCR images to cloud services;
- not use remote vision APIs;
- not transmit gameplay images over the internet.

Preferred OCR and image processing should run locally.

---

# 32. Performance Requirements

Target resource usage during normal V1 operation:

```text
CPU: ideally < 2–3% average on modern gaming PC
RAM: < 300 MB target
GPU: negligible unless GPU capture is used
OCR rate: 2–4 Hz maximum
```

Only process the small ROI where possible.

---

# 33. Game Detection

The companion should determine whether Valheim is running.

Possible methods:

- process enumeration;
- visible window matching.

Expected process/window should be configurable.

When Valheim is not running:

```text
stop OCR
stop screen capture
optionally restore neutral lighting
```

When Valheim starts:

```text
resume monitoring automatically
```

---

# 34. Neutral / Fallback Profile

Unknown OCR state must not cause random behavior.

Example:

```yaml
fallback:
  color_temperature: warm
  brightness: 25
```

However, if biome detection temporarily fails:

```text
retain previous confirmed biome
```

Do not immediately switch to fallback.

Suggested rule:

```text
retain last valid biome
for >= 30 seconds of unknown detections
```

Only then consider fallback behavior.

---

# 35. Startup Sequence

Recommended:

```text
start app
↓
load config
↓
validate profiles
↓
discover/connect Hue Bridge
↓
load logical light mapping
↓
wait for Valheim process
↓
find game window
↓
begin capture
↓
detect biome
↓
stability check
↓
apply scene
↓
start ambient motion
```

---

# 36. Shutdown Sequence

On application exit:

```text
stop capture
↓
stop detector workers
↓
stop ambient scheduler
↓
optionally restore configured neutral scene
↓
close Hue connection
↓
exit
```

---

# 37. Threading / Async Model

Recommended separation:

```text
Task 1:
screen capture

Task 2:
OCR/detection

Task 3:
state aggregation

Task 4:
ambient animation scheduler

Task 5:
Hue command queue

Task 6:
tray UI
```

Hue updates should be queued to avoid concurrent conflicting commands.

---

# 38. Rate Limiting

Do not spam the Hue Bridge.

The ambient engine should generate slow transitions, not constantly write tiny changes.

Target:

```text
ordinary biome:
a few Hue updates per minute per light
```

Active environments:

```text
more frequent,
but still intentionally restrained
```

---

# 39. Testing Strategy

## 39.1 Unit Tests

Must cover:

- OCR normalization;
- fuzzy biome matching;
- confidence thresholding;
- rolling stability;
- hysteresis;
- profile parsing;
- profile validation;
- modifier composition;
- motion bounds;
- deterministic random tests with fixed seed;
- Hue command generation.

---

## 39.2 Image Fixture Tests

Store representative cropped minimap screenshots:

```text
tests/fixtures/biomes/
├── meadows_01.png
├── black_forest_01.png
├── swamp_01.png
├── mountain_01.png
└── ...
```

Tests should verify expected biome output.

---

## 39.3 Resolution Tests

At minimum test:

```text
1920x1080
2560x1440
3840x2160
```

The user's primary expected environment is likely 2560×1440, but the architecture should not assume that permanently.

---

## 39.4 UI Scale Tests

Valheim UI scale may alter the minimap/label position.

Provide:

```text
automatic ROI calibration
OR
manual calibration
```

V1 may begin with manual calibration.

---

# 40. Calibration Tool

Provide a simple calibration command/window.

Expected flow:

```text
1. User launches Valheim.
2. Open calibration.
3. Screenshot appears.
4. User drags rectangle around biome label.
5. Save ROI.
6. OCR preview confirms detected biome.
```

This makes the system resilient across:

- resolution;
- UI scaling;
- window mode;
- monitor changes.

---

# 41. Hue Light Calibration

Setup workflow:

```text
Bridge discovered
↓
lights enumerated
↓
select logical channel
↓
flash one Hue light
↓
user confirms
↓
save mapping
```

Example:

```text
Which light is flashing?

[ Front Left ]
[ Front Right ]
[ Rear Left ]
[ Rear Right ]
[ Bedside ]
```

---

# 42. Packaging

Target eventual output:

```text
ValheimHueAmbient.exe
```

The user should not require Python installed.

Possible packaging:

```text
PyInstaller
```

or similar.

V1 development can remain:

```text
uv run valheim-hue
```

if Python + uv are available.

---

# 43. Configuration Paths

Recommended Windows paths:

```text
%APPDATA%\ValheimHueAmbient\
```

Example:

```text
%APPDATA%\ValheimHueAmbient\
├── config.yaml
├── lights.yaml
├── profiles.yaml
├── credentials.json
└── logs\
```

Bridge credentials must not be committed to Git.

---

# 44. Git Security

`.gitignore` should include:

```gitignore
.env
credentials.json
config.local.yaml
logs/
debug/
*.log
```

Never commit:

- Hue authentication tokens;
- private IP configuration if not desired;
- screenshots containing unrelated personal content.

---

# 45. Development Milestones

## Milestone 0 — Project Skeleton

Deliverables:

- Python project;
- configuration loader;
- logging;
- CLI;
- tests;
- base package structure.

Success condition:

```text
app starts
config loads
tests pass
```

---

## Milestone 1 — Hue Control

Deliverables:

- connect to Hue Bridge Pro;
- enumerate lights;
- logical light mapping;
- manually apply test scenes;
- smooth transitions.

Success condition:

```text
CLI can set all 5 logical lights correctly
```

Example:

```bash
valheim-hue profile black_forest
```

---

## Milestone 2 — Screen Capture

Deliverables:

- detect Valheim window;
- capture configured ROI;
- debug preview;
- calibration support.

Success condition:

```text
biome label region is captured reliably
```

---

## Milestone 3 — Biome OCR

Deliverables:

- local OCR;
- normalization;
- fuzzy matching;
- confidence;
- screenshot fixtures.

Success condition:

```text
>= 95% correct classification
on representative test captures
```

---

## Milestone 4 — Stable Biome State

Deliverables:

- rolling history;
- debounce;
- hysteresis;
- unknown handling.

Success condition:

```text
crossing biome borders does not cause rapid Hue scene flicker
```

---

## Milestone 5 — Ambient Engine

Deliverables:

- STATIC;
- SUBTLE;
- AMBIENT;
- ACTIVE;
- random timing;
- individual light state;
- palette-constrained motion.

Success condition:

```text
Black Forest remains recognizably Black Forest
for long sessions without obvious repetitive patterns
```

---

## Milestone 6 — Windows Tray App

Deliverables:

- status;
- current biome;
- Hue state;
- pause;
- manual profile;
- logs;
- exit.

Success condition:

```text
normal operation no longer requires terminal interaction
```

---

## Milestone 7 — Day/Night

Deliverables:

- luminance sampling;
- DAY/TWILIGHT/NIGHT;
- long hysteresis;
- profile modifiers.

---

## Milestone 8 — Weather

Deliverables:

- broad weather classifier;
- CLEAR/RAIN/STORM/SNOW/BLIZZARD/MIST/ASH;
- weather modifiers.

---

## Milestone 9 — Interiors

Deliverables:

- image dataset;
- classifier;
- Burial Chambers;
- Troll Cave;
- Sunken Crypt;
- Frost Cave;
- Infested Mine;
- conservative state switching.

---

## Milestone 10 — Events

Deliverables:

- center-screen OCR;
- known event phrase matching;
- temporary event overlays.

---

## Milestone 11 — Boss Encounters

Deliverables:

- boss UI detection;
- boss-name classification;
- boss-specific lighting profiles.

---

# 46. Suggested First Codex Task

Start with this scope only:

> Create the Python project skeleton for `valheim-hue`. Implement typed configuration models, YAML loading, structured logging, a `GameState` model, profile models, and a CLI command that loads a named lighting profile and prints the resolved five-light target state. Do not implement Hue networking or screen capture yet. Include pytest unit tests.

Then proceed milestone by milestone.

Do **not** ask Codex to build the whole system in one pass.

---

# 47. Acceptance Criteria — V1

V1 is complete when all of the following work:

1. Companion app runs on Windows.
2. Valheim remains completely unmodified.
3. Hosted Valheim server remains completely unmodified.
4. App detects whether Valheim is running.
5. App captures the biome label region.
6. App detects the current biome reliably.
7. Detection survives minor OCR errors.
8. Detection does not rapidly flip at biome borders.
9. App connects to Hue Bridge Pro.
10. Five Hue lights are mapped independently.
11. Each biome has a profile.
12. Entering a new stable biome starts a smooth transition.
13. Lights exhibit subtle independent motion.
14. Hue communication failure does not crash the app.
15. The app can be paused.
16. Manual biome/profile selection works.
17. Logs provide enough information for debugging.

---

# 48. Initial Artistic Rules

Use these as hard design principles unless intentionally overridden.

### Rule 1

**Biome identity is more important than animation.**

### Rule 2

**Brightness is as important as color.**

Swamp should feel darker than Meadows.

### Rule 3

**Avoid full saturation unless the environment warrants it.**

### Rule 4

**Five lights should not breathe in sync.**

### Rule 5

**Randomization must stay inside curated palette bounds.**

### Rule 6

**Environmental effects should be slow.**

### Rule 7

**Fast lighting should be rare and meaningful.**

### Rule 8

**The system must never interfere with gameplay.**

### Rule 9

**The hosted server must never be required for detection or control.**

### Rule 10

**Vanilla compatibility is a primary requirement, not an optimization.**

---

# 49. Long-Term Architecture

The final system may look like:

```text
                      ┌────────────────────┐
                      │ Vanilla Valheim    │
                      └─────────┬──────────┘
                                │
                                │ pixels only
                                ▼
                      ┌────────────────────┐
                      │ Screen Capture     │
                      └─────────┬──────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
      Biome OCR          Weather Vision       UI OCR/Vision
            │                   │                   │
            └───────────────────┼───────────────────┘
                                ▼
                      ┌────────────────────┐
                      │ State Aggregator   │
                      └─────────┬──────────┘
                                ▼
                      ┌────────────────────┐
                      │ Profile Resolver   │
                      └─────────┬──────────┘
                                ▼
                      ┌────────────────────┐
                      │ Ambient Engine     │
                      │                    │
                      │ palettes           │
                      │ modifiers          │
                      │ motion             │
                      │ transitions        │
                      └─────────┬──────────┘
                                ▼
                      ┌────────────────────┐
                      │ Hue Controller     │
                      └─────────┬──────────┘
                                ▼
                      ┌────────────────────┐
                      │ Hue Bridge Pro     │
                      └─────────┬──────────┘
                                │
             ┌──────────────────┼──────────────────┐
             ▼        ▼         ▼         ▼        ▼
            R1       R2        R3        R4       B1
```

---

# 50. Future Multi-Game Compatibility

The ambient engine should not unnecessarily depend on Valheim.

A future architecture could support:

```text
                    ┌── Valheim screen adapter
                    │
Game adapters ──────┼── WoW Forever adapter
                    │
                    └── future games
                              │
                              ▼
                       Common GameState
                              │
                              ▼
                       Ambient Engine
                              │
                              ▼
                           Hue
```

Keep these layers separate:

```text
game-state acquisition
lighting policy
Hue implementation
```

This makes the Hue/ambient system reusable.

---

# 51. Summary

The project must create an external Windows companion for **vanilla Valheim**.

The implementation path is:

```text
V1
Biome OCR
→ Hue biome scenes

V2
+ day/night

V3
+ weather

V4
+ interiors

V5
+ world events

V6
+ bosses
```

The initial implementation should prioritize:

```text
reliability
simplicity
vanilla compatibility
good lighting design
low performance overhead
```

over advanced computer vision.

The single most important first proof of concept is:

> Can a local application repeatedly read the biome label from Valheim's minimap HUD and reliably transition five Hue lights to the corresponding ambient profile?

If yes, the core project is viable.

---

## Development Principle

> **Keep Valheim vanilla. Observe externally. Interpret conservatively. Animate subtly.**
