# World of Warcraft Forever Hue Ambient Lighting — Development Specification

**Project name:** WoW Forever Hue Ambient  
**Document purpose:** Development specification for Codex-assisted implementation  
**Primary target:** World of Warcraft: Forever  
**Target platform:** Windows 11 gaming PC  
**Lighting platform:** Philips Hue Bridge Pro + 4 rectangular Hue lights + 1 Hue bedside light  
**Game integration philosophy:** External observation only for V1. No WeakAuras dependency.  
**Primary detection method:** Live parsing of WoW log output, especially zone/map change metadata if available.  
**Fallback detection method:** Screen-based OCR / visual recognition.  
**Server dependency:** None.

---

# 1. Project Goal

Build a local Windows companion application that makes Philips Hue lights behave as an extension of the current World of Warcraft environment.

The system should:

1. Detect the player's current zone, dungeon, raid, battleground, or city.
2. Map that location to a curated lighting profile.
3. Control five Hue lights through a Philips Hue Bridge Pro.
4. Produce subtle, slow, environmental lighting rather than generic RGB effects.
5. Avoid dependence on WeakAuras.
6. Avoid dependence on combat-assistance addons.
7. Avoid reading WoW process memory.
8. Avoid code injection.
9. Avoid player-input automation.
10. Keep all game-to-Hue logic local to the gaming PC.
11. Be structured so future features can add:
   - time-of-day modulation;
   - weather modulation;
   - boss/encounter overrides;
   - PvP state;
   - event overlays;
   - additional games through a shared ambient engine.

The intended experience is:

> Make the room feel like an extension of the current Azeroth environment while keeping the lighting subtle enough that the player notices the world, not the Hue system.

---

# 2. Core Design Decision

The project should **not** behave like Hue Sync.

Hue Sync samples screen colors continuously and mirrors them into the room.

That is not the desired behavior.

The desired behavior is:

```text
CURRENT LOCATION
      ↓
CURATED WORLD PROFILE
      ↓
SUBTLE PROCEDURAL AMBIENCE
      ↓
HUE LIGHTS
```

Example:

```text
Elwynn Forest
→ green + warm sunlight + amber

Duskwood
→ midnight purple + cold blue + very low brightness

Stranglethorn Vale
→ jungle green + tropical amber

Onyxia's Lair
→ deep red + orange + ember movement

Alterac Valley
→ cold blue + white + restrained battle-red accent
```

The lighting must describe the **place**, not the individual pixels currently displayed.

---

# 3. Hardware

Target setup:

```text
1 × Philips Hue Bridge Pro
4 × rectangular Hue lights
1 × Hue bedside lamp
1 × Windows 11 gaming PC
```

Logical light names:

```text
R1 = rectangle_front_left
R2 = rectangle_front_right
R3 = rectangle_rear_left
R4 = rectangle_rear_right
B1 = bedside
```

Do not hardcode actual Hue resource IDs.

Persist mappings in configuration.

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

# 4. Lighting Philosophy

For ordinary outdoor zones:

```text
R1 + R2 = dominant environment
R3 + R4 = secondary/accent environment
B1      = deep background / fill
```

For special content:

```text
raids
dungeons
high-magic areas
fire/lava areas
battlegrounds
```

the engine may control all five independently.

Brightness is as important as hue.

Example:

```text
Westfall:
bright and warm

Duskwood:
dark and cold

Entering Duskwood should noticeably darken the room.
```

---

# 5. Primary Detection Strategy

The preferred architecture is:

```text
World of Warcraft Forever
          │
          │ local log output
          ▼
WoW Log Watcher
          │
          ├── ZONE_CHANGE
          ├── MAP_CHANGE
          └── related location metadata
                 │
                 ▼
         Location Resolver
                 │
                 ▼
          Profile Resolver
                 │
                 ▼
          Ambient Engine
                 │
                 ▼
           Hue Bridge Pro
```

The first technical proof of concept is:

> Does World of Warcraft: Forever write location changes to a live local log file in a usable way?

The application must be designed so this can be validated quickly and changed without restructuring the rest of the system.

---

# 6. No WeakAuras Dependency

The project must not assume WeakAuras exists.

The system should not require:

- WeakAuras;
- combat rotational addons;
- custom aura frameworks;
- secure-action modifications;
- Lua-to-network hacks.

If Forever later exposes a simple, stable, non-combat addon API that could improve location detection, support may be added behind an adapter.

However, **V1 must not depend on it**.

---

# 7. No Game Memory Reading

V1 must not:

- inspect WoW process memory;
- inject DLLs;
- hook rendering APIs for game-state extraction;
- manipulate game state;
- automate controls.

The companion is strictly:

```text
observer
+
lighting controller
```

---

# 8. High-Level Architecture

```text
+----------------------------+
| World of Warcraft: Forever |
+-------------+--------------+
              |
              | logs or pixels
              v
+----------------------------+
| Game State Adapter         |
|                            |
| Preferred: Log Adapter     |
| Fallback: Screen Adapter   |
+-------------+--------------+
              |
              v
+----------------------------+
| Location Resolver          |
|                            |
| zone                       |
| city                       |
| dungeon                    |
| raid                       |
| battleground               |
+-------------+--------------+
              |
              v
+----------------------------+
| State Aggregator           |
+-------------+--------------+
              |
              v
+----------------------------+
| Profile Resolver           |
+-------------+--------------+
              |
              v
+----------------------------+
| Ambient Engine             |
|                            |
| transitions                |
| palettes                   |
| randomized drift           |
| overrides                  |
+-------------+--------------+
              |
              v
+----------------------------+
| Hue Controller             |
+-------------+--------------+
              |
              v
+----------------------------+
| Philips Hue Bridge Pro     |
+----------------------------+
```

---

# 9. Recommended Project Structure

Suggested Python project:

```text
wow-hue/
├── README.md
├── pyproject.toml
├── config/
│   ├── app.yaml
│   ├── lights.yaml
│   └── profiles/
│       ├── outdoor.yaml
│       ├── cities.yaml
│       ├── dungeons.yaml
│       ├── raids.yaml
│       └── battlegrounds.yaml
│
├── src/
│   └── wow_hue/
│       ├── __init__.py
│       ├── main.py
│       ├── app.py
│       │
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── wow_log.py
│       │   └── screen.py
│       │
│       ├── detection/
│       │   ├── __init__.py
│       │   ├── log_parser.py
│       │   ├── location.py
│       │   ├── ocr.py
│       │   └── window.py
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
│       │   ├── transitions.py
│       │   └── modifiers.py
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
    ├── test_log_parser.py
    ├── test_location_resolver.py
    ├── test_profile_resolver.py
    ├── test_hysteresis.py
    ├── test_motion.py
    └── fixtures/
```

Python is recommended for V1 development speed.

The architecture should allow a future C# or Rust rewrite without changing the configuration format.

---

# 10. V1 Scope

V1 should solve only:

```text
detect current WoW location
→ resolve location type
→ load lighting profile
→ transition lights
→ run subtle ambient motion
```

Do not start with:

- weather;
- exact in-game time;
- boss encounters;
- combat effects;
- health-driven lighting;
- player class effects;
- spell effects;
- achievement effects.

These can be added later.

---

# 11. Log Discovery

The application must support configurable log locations.

Do not hardcode one installation path.

Example:

```yaml
wow:
  log_paths:
    - "C:/Program Files (x86)/World of Warcraft/_forever_/Logs/WoWCombatLog.txt"
    - "C:/Program Files (x86)/World of Warcraft/_classic_/Logs/WoWCombatLog.txt"
```

The app should:

1. check configured paths;
2. optionally inspect common WoW install locations;
3. allow manual selection;
4. remember the selected log file.

---

# 12. Log Enablement

The application should detect when the configured file:

```text
does not exist
or
has stopped changing
```

and expose a clear status:

```text
WoW detected
Combat log not active
```

The UI may instruct the user to enable logging manually in WoW if required.

The companion must not automate chat input.

---

# 13. Tail-Following

The log adapter should behave like:

```text
tail -F
```

Requirements:

- begin at end-of-file by default;
- process newly appended lines;
- survive file truncation;
- survive file recreation;
- survive log rotation;
- recover after game restart;
- use efficient file watching or polling;
- avoid rereading the entire file repeatedly.

---

# 14. Location Events

The parser should prioritize explicit location metadata.

Potential record types:

```text
ZONE_CHANGE
MAP_CHANGE
```

The exact Forever format must be validated from real game output.

The parser must be tolerant.

Do not assume exact field positions until fixtures have been collected.

Create raw fixture samples from real Forever logs and write parser tests against those fixtures.

---

# 15. Location Model

Recommended model:

```python
@dataclass
class LocationState:
    canonical_id: str | None
    display_name: str | None
    map_id: int | None
    instance_id: int | None
    instance_type: str | None
    difficulty_id: int | None
    source: str
    confidence: float
```

Possible `instance_type` values:

```text
world
city
dungeon
raid
battleground
arena
unknown
```

Do not assume Forever uses exactly these strings internally.

Normalize raw inputs into these logical categories.

---

# 16. Canonical Location IDs

Profiles must not rely only on display strings.

Preferred key strategy:

```text
map ID / instance ID if available
+
canonical normalized name
```

Example:

```yaml
locations:
  elwynn_forest:
    names:
      - "Elwynn Forest"
    map_ids: []
```

Until IDs are verified, IDs may remain empty.

Once real logs are available, add them to configuration rather than hardcoding them in parser logic.

---

# 17. Alias Handling

The resolver should support aliases.

Example:

```yaml
locations:

  stranglethorn_vale:
    names:
      - "Stranglethorn Vale"
      - "Northern Stranglethorn"
      - "Cape of Stranglethorn"
```

Use only aliases appropriate to Forever.

Unknown names should be logged for later profile creation.

---

# 18. Unknown Location Handling

If an unknown zone appears:

1. preserve the previous valid scene temporarily;
2. log the unknown location;
3. expose it in the tray/debug UI;
4. optionally use a neutral fallback after a timeout.

Suggested behavior:

```text
unknown < 30 sec
→ keep current scene

unknown >= 30 sec
→ fallback neutral scene
```

---

# 19. Fallback Screen Detection

If Forever does not expose reliable zone information through logs, use screen detection.

Preferred fallback:

```text
capture minimap / zone-name UI region
↓
OCR
↓
match against known location list
↓
location resolver
```

Do not OCR the entire screen.

Provide manual ROI calibration.

---

# 20. Screen Detection Architecture

```text
WoW Window
   ↓
Screen Capture
   ↓
Configured ROI
   ↓
Preprocessing
   ↓
OCR
   ↓
Location Matcher
   ↓
Confidence
   ↓
Hysteresis
```

Target OCR rate:

```text
2–4 Hz
```

Location changes are slow.

---

# 21. Fallback Matching

Known location names form a constrained vocabulary.

Therefore fuzzy matching is appropriate.

Example:

```text
OCR: "Stranglethorn VaIe"
→ Stranglethorn Vale
```

Use:

- case normalization;
- punctuation normalization;
- whitespace normalization;
- fuzzy score;
- configurable minimum confidence.

---

# 22. Detection Priority

Recommended state source priority:

```text
1. explicit log map/zone event
2. secondary log location evidence
3. screen OCR
4. previous confirmed location
5. neutral fallback
```

The app should expose which source is currently active.

---

# 23. Scene Transition Behavior

Outdoor zone changes:

```text
3–5 seconds
```

Dungeon/raid/BG entry:

```text
1.5–3 seconds
```

Do not instantly snap between normal profiles.

Exception:

```text
manual test mode
```

may allow immediate switching.

---

# 24. Motion Classes

Use four movement classes.

## STATIC

Characteristics:

- essentially stable;
- brightness drift approximately ±2%;
- long intervals.

Suitable for:

- Barrens
- Westfall
- Mulgore
- open daytime areas.

---

## SUBTLE

Characteristics:

- small color drift;
- ±2–4% brightness;
- transitions every 45–120 seconds.

Suitable for:

- Winterspring
- Dun Morogh
- bright snow
- calm deserts.

---

## AMBIENT

Default.

Characteristics:

- slow independent movement;
- constrained palettes;
- ±3–7% brightness;
- transitions every 20–90 seconds.

Suitable for:

- Ashenvale
- Duskwood
- Stranglethorn
- Feralas
- most dungeons.

---

## ACTIVE

Still atmospheric.

Characteristics:

- stronger motion;
- randomized timing;
- shorter transitions;
- no synchronized breathing;
- no strobing.

Suitable for:

- fire/lava environments;
- arcane zones;
- selected raids;
- selected battlegrounds.

---

# 25. Independent Light Motion

Bad:

```text
all lights:
30%
→ 40%
→ 30%
```

Good:

```text
R1 shifts greener
wait 10 sec

R4 dims 3%
wait 7 sec

R2 shifts slightly warmer
wait 18 sec

B1 brightens 2%
```

Each light should have:

```text
current color
target color
current brightness
target brightness
next transition timestamp
```

Randomization must stay within the curated palette.

---

# 26. Base Artistic Profiles

The following are the initial artistic direction.

All values are editable.

---

# 27. Alliance / Eastern Kingdoms Outdoor Profiles

## Elwynn Forest

```yaml
elwynn_forest:
  type: zone
  motion: ambient
  transition_seconds: 4

  lights:

    rectangle_front_left:
      palette: ["#4F8A3C", "#5A9444"]
      brightness: [40, 47]

    rectangle_front_right:
      palette: ["#4A8138", "#568D42"]
      brightness: [39, 46]

    rectangle_rear_left:
      palette: ["#E6B85C", "#DDAA4D"]
      brightness: [30, 38]

    rectangle_rear_right:
      palette: ["#C89545", "#D5A34E"]
      brightness: [28, 36]

    bedside:
      palette: ["#A86C2D", "#8F5C29"]
      brightness: [12, 19]
```

---

## Westfall

```yaml
westfall:
  type: zone
  motion: subtle

  theme:
    primary: wheat_gold
    accent: dusty_orange
    bedside: sunset_amber

  brightness:
    nominal: 45
```

Palette direction:

```text
gold
ochre
dry orange
warm amber
```

---

## Redridge Mountains

Palette:

```text
rust red
pine green
warm amber
```

Brightness:

```text
~40%
```

---

## Duskwood

```yaml
duskwood:
  type: zone
  motion: ambient
  transition_seconds: 4

  lights:

    rectangle_front_left:
      palette: ["#2A1C42", "#34234E"]
      brightness: [20, 27]

    rectangle_front_right:
      palette: ["#334C62", "#3B566C"]
      brightness: [18, 25]

    rectangle_rear_left:
      palette: ["#423056", "#4B3861"]
      brightness: [17, 23]

    rectangle_rear_right:
      palette: ["#28424F", "#304A58"]
      brightness: [16, 22]

    bedside:
      palette: ["#23142D", "#2B1835"]
      brightness: [8, 14]
```

The room should become noticeably darker.

---

## Deadwind Pass

Palette:

```text
charcoal violet
blood red
near-black purple
```

Brightness:

```text
~15%
```

---

## Stranglethorn Vale

```yaml
stranglethorn_vale:
  type: zone
  motion: ambient

  lights:

    rectangle_front_left:
      palette: ["#17683A", "#205F35", "#286E3C"]
      brightness: [36, 43]

    rectangle_front_right:
      palette: ["#16623B", "#287746"]
      brightness: [32, 40]

    rectangle_rear_left:
      palette: ["#A86D2B", "#BD792D"]
      brightness: [25, 34]

    rectangle_rear_right:
      palette: ["#8E612B", "#B17A32"]
      brightness: [23, 31]

    bedside:
      palette: ["#103C29", "#173F2D"]
      brightness: [12, 18]
```

---

## Swamp of Sorrows

Palette:

```text
murky teal
swamp green
muddy violet
```

Brightness:

```text
~25%
```

---

## Blasted Lands

Palette:

```text
scorched red
burnt orange
dark crimson
```

Brightness:

```text
~35%
```

---

## Burning Steppes

Palette:

```text
ember orange
dark red
deep ember
```

Motion:

```text
ACTIVE
```

Brightness:

```text
~35%
```

---

## Searing Gorge

Palette:

```text
molten orange
coal red
deep amber
```

Motion:

```text
ACTIVE
```

---

## Badlands

Palette:

```text
sandstone
dusty ochre
dark brown
```

---

## Loch Modan

Palette:

```text
highland green
lake blue
warm stone
```

---

## Dun Morogh

Palette:

```text
icy blue-white
cold blue
pale amber
```

Motion:

```text
SUBTLE
```

---

## Wetlands

Palette:

```text
rain blue
moss green
dim amber
```

---

## Arathi Highlands

Palette:

```text
grass green
earth gold
muted red
```

---

## Hillsbrad Foothills

Palette:

```text
meadow green
golden daylight
muted amber
```

---

## Alterac Mountains

Palette:

```text
snow blue
grey violet
cold white
```

---

## Silverpine Forest

Palette:

```text
moonlit blue
muted purple
dark cyan
```

Brightness:

```text
~25%
```

---

## Tirisfal Glades

Palette:

```text
plague violet
sickly green
dark purple
```

---

## Western Plaguelands

Palette:

```text
diseased yellow
dead green
brown-red
```

---

## Eastern Plaguelands

Palette:

```text
toxic yellow
plague green
dark amber
```

---

## The Hinterlands

Palette:

```text
evergreen
highland gold
deep forest
```

---

## Riverglades

Palette:

```text
prairie green
frontier gold
dusk orange
```

---

# 28. Kalimdor Outdoor Profiles

## Durotar

Palette:

```text
clay orange
dry red
fire amber
```

---

## The Barrens

Palette:

```text
savanna gold
dry green
warm orange
```

Motion:

```text
STATIC / SUBTLE
```

---

## Mulgore

Palette:

```text
meadow green
sky blue
sunset gold
```

---

## Stonetalon Mountains

Palette:

```text
pine green
stone blue
earthy amber
```

---

## Ashenvale

```yaml
ashenvale:
  type: zone
  motion: ambient

  theme:
    dominant:
      - "#285B46"
      - "#31644D"
    accents:
      - "#494774"
      - "#354C69"

  brightness:
    nominal: 32
```

Very slow moonlit green/blue drift.

---

## Darkshore

Palette:

```text
storm blue
mist cyan
violet-grey
```

---

## Teldrassil

Palette:

```text
enchanted purple
leaf green
soft blue
```

---

## Azshara

Palette:

```text
autumn orange
arcane blue
deep purple
```

---

## Felwood

Palette:

```text
fel green
corrupted purple
black-green
```

---

## Winterspring

```yaml
winterspring:
  motion: subtle

  theme:
    primary: ice_cyan
    secondary: frost_blue
    accent: pale_violet

  brightness:
    nominal: 50
```

Movement should be extremely restrained.

---

## Moonglade

Palette:

```text
moon green
lunar blue
violet
```

---

## Desolace

Palette:

```text
desaturated violet
dead earth
muted blue
```

---

## Feralas

Palette:

```text
deep emerald
ancient teal
purple
```

---

## Dustwallow Marsh

Palette:

```text
swamp teal
muddy green
dark amber
```

---

## Thousand Needles

Palette:

```text
sandstone orange
dusty gold
canyon red
```

---

## Tanaris

Palette:

```text
desert gold
hot orange
deep amber
```

---

## Un'Goro Crater

Palette:

```text
vivid jungle
volcanic orange
deep emerald
```

---

## Silithus

Palette:

```text
sand yellow
silithid purple
deep violet
```

---

## Shen'dralas

Palette:

```text
Highborne violet
centaur earth
arcane blue
```

---

## Mount Hyjal

Palette:

```text
world-tree green
moon blue
sacred gold
```

---

## Zephras Isle

```yaml
zephras_isle:
  motion: active

  theme:
    primary: sky_cyan
    secondary: arcane_lavender
    accent: cloud_blue_white

  brightness:
    nominal: 52
```

This should be among the brightest and most fluid zones.

---

# 29. Capital Profiles

## Stormwind

```text
royal blue
warm gold
warm white
```

Brightness:

```text
~45%
```

---

## Ironforge

```text
forge orange
stone amber
deep ember
```

---

## Darnassus

```text
night purple
moon green
soft blue
```

---

## Orgrimmar

```text
Horde red
torch orange
dark red
```

---

## Thunder Bluff

```text
prairie gold
grass green
sunset orange
```

---

## Undercity

```text
toxic green
undead purple
dark green
```

Brightness:

```text
~22%
```

---

# 30. Dungeon Profile Principles

Dungeon entry should:

```text
reduce room brightness
increase local contrast
increase atmospheric specialization
```

Typical:

```text
20–30% brightness
```

Dungeons should generally be darker than their surrounding world zone.

---

# 31. Original Dungeon Profiles

## Ragefire Chasm

```text
lava orange
deep red
ember
ACTIVE
```

---

## Wailing Caverns

```text
cave green
turquoise
dark moss
```

---

## The Deadmines

```text
lantern amber
mine blue-grey
dim orange
```

---

## Shadowfang Keep

```text
spectral blue
ghost purple
dark violet
```

---

## Blackfathom Deeps

```text
abyssal blue
naga teal
dark purple
```

---

## The Stockade

```text
torch amber
cold stone
dark orange
```

---

## Gnomeregan

```text
industrial cyan
warning orange
toxic green
```

---

## Razorfen Kraul

```text
dusty brown
thorn green
blood amber
```

---

## Razorfen Downs

```text
necrotic violet
bone blue
dark purple
```

---

## Scarlet Monastery — Graveyard

```text
undead violet
moon blue
blood red
```

---

## Scarlet Monastery — Library

```text
Scarlet red
candle amber
deep red
```

---

## Scarlet Monastery — Armory

```text
crimson
steel grey
fire orange
```

---

## Scarlet Monastery — Cathedral

```text
rich red
holy gold
dark crimson
```

---

## Uldaman

```text
Titan gold
stone cyan
earthen brown
```

---

## Zul'Farrak

```text
desert gold
troll green
blood orange
```

---

## Maraudon

```text
nature green
crystal purple
deep blue
```

---

## Temple of Atal'Hakkar

```text
swamp green
troll teal
ritual purple
```

---

## Blackrock Depths

```text
furnace orange
iron red
coal red
ACTIVE
```

---

## Lower Blackrock Spire

```text
ember red
dark iron
orange
```

---

## Upper Blackrock Spire

```text
dragon red
flame orange
black-red
```

---

## Scholomance

```text
necromantic purple
corpse green
blue-black
```

Brightness:

```text
~18%
```

---

## Stratholme

```text
burning orange
plague green
dark red
```

---

## Dire Maul East

```text
overgrown green
arcane purple
deep forest
```

---

## Dire Maul West

```text
Highborne purple
cold blue
violet
```

---

## Dire Maul North

```text
ogre orange
stone brown
fire amber
```

---

# 32. Forever Dungeon Profiles

Initial named Forever dungeon profiles:

## Hall of Thanes

```text
dwarven gold
spectral blue
torch amber
```

---

## Ruins of Lordaeron

```text
undead purple
plague green
cold blue
```

---

## Excavation Site: Wetlands

```text
lantern amber
wet stone blue
earth brown
```

---

## City of Dalaran

```text
arcane violet
magical blue
pink-purple
ACTIVE
```

---

## The Drowned City

```text
underwater teal
troll green
deep ocean blue
```

---

## Krol'dok Stronghold

```text
ogre orange
frontier green
fire brown
```

---

## Alcaz Prison

```text
cold prison blue
Defias red
dark amber
```

---

## Blackmaw Hold

```text
furbolg forest
corruption violet
sick green
```

---

## Shaper's Terrace

```text
Titan cyan
construct gold
deep blue
```

---

# 33. Raid Profiles

Raids may control all five lights independently.

Do not force 2+2+1 grouping.

---

## Barrow Deeps

```text
R1 ancient green
R2 violet
R3 moon blue
R4 prison amber
B1 near-black purple
```

Brightness:

```text
~20%
```

---

## Hyjal Summit

```text
R1 emerald
R2 moon blue
R3 sacred gold
R4 deep forest
B1 soft turquoise
```

Brightness:

```text
~32%
```

---

## Onyxia's Lair

```yaml
onyxias_lair:
  type: raid
  motion: active
  transition_seconds: 2

  lights:

    rectangle_front_left:
      palette: ["#A9231D", "#B72B20"]
      brightness: [24, 31]

    rectangle_front_right:
      palette: ["#E0631E", "#CF521B"]
      brightness: [29, 37]

    rectangle_rear_left:
      palette: ["#771A17", "#8A211A"]
      brightness: [20, 28]

    rectangle_rear_right:
      palette: ["#B7421C", "#C34D1D"]
      brightness: [24, 33]

    bedside:
      palette: ["#481315", "#561517"]
      brightness: [9, 15]
```

Use randomized fire-like motion.

Do not synchronize flicker.

---

# 34. Battleground Profiles

## Warsong Gulch

```text
forest green
battle red
night blue
```

---

## Arathi Basin

```text
highland green
gold/red accent
sky blue
```

---

## Alterac Valley

```text
ice blue
cold white
battle red accent
```

---

## Darkspear Islands

```text
tropical teal
volcanic orange
jungle green
```

---

# 35. Fire / Lava Motion

Fire scenes should simulate reflected firelight.

Bad:

```text
fixed 4-second pulse
```

Good:

```text
R1 +3%
wait 6.7 sec

R3 shifts slightly more orange
wait 3.1 sec

R4 -4%
wait 8.4 sec
```

Suggested fire timing:

```text
3–15 seconds between individual target changes
```

Brightness variation:

```text
±5–10%
```

Color variation:

```text
restricted red/orange/amber palette
```

No white flashes by default.

---

# 36. Forest Motion

Typical:

```text
20–90 second transitions
```

Characteristics:

```text
greens slowly drift
warm accents mostly stable
brightness ±3–6%
```

Suitable for:

- Elwynn;
- Ashenvale;
- Stranglethorn;
- Feralas;
- Hinterlands.

---

# 37. Arcane Motion

Typical:

```text
10–30 second transitions
```

Palette:

```text
blue
violet
cyan
```

Suitable for:

- City of Dalaran;
- Zephras Isle;
- arcane dungeon/raid spaces.

---

# 38. Snow Motion

Very subtle.

Typical:

```text
40–120 second transitions
```

Palette:

```text
blue
cyan
cool white
faint violet
```

Brightness variation:

```text
±2–4%
```

---

# 39. Haunted Motion

Typical:

```text
30–100 second transitions
```

Palette:

```text
purple
blue
sick green
deep cyan
```

Brightness:

```text
low
```

Suitable for:

- Duskwood;
- Silverpine;
- Tirisfal;
- Scholomance;
- Ruins of Lordaeron.

---

# 40. Day/Night Modulation — Future

Do not implement in V1.

Future model:

```text
location base
× time-of-day modifier
```

Example:

```text
Elwynn Day
green + gold
45%

Elwynn Sunset
green + orange
35%

Elwynn Night
dark green + blue
20%
```

Possible future detection:

- log metadata if available;
- screen luminance;
- game UI clock if reliable.

---

# 41. Weather Modulation — Future

Do not implement in V1.

Future model:

```text
location
× weather modifier
```

Examples:

```text
rain:
brightness -15%
saturation -10%
cool shift +10%

storm:
brightness -25%
cool shift +20%
motion +20%
```

Weather must modify the base location rather than replace it.

---

# 42. Boss / Encounter Overrides — Future

Boss logic is not required for V1.

Possible future sources:

- log encounter events;
- boss names in log;
- boss UI OCR.

Priority:

```text
boss override
> raid/dungeon base
```

Example:

```text
Onyxia's Lair base
+
Onyxia engaged modifier
```

The system should not become a combat assistant.

Lighting may become more intense, but it must not communicate gameplay-critical cues.

---

# 43. State Priority

Future target:

```text
boss/event override
        ↓
instance profile
        ↓
zone profile
        ↓
time modifier
        ↓
weather modifier
```

V1 only needs:

```text
location profile
```

---

# 44. Profile Configuration

Profiles must live outside application code.

Recommended:

```text
YAML
```

Example:

```yaml
locations:

  duskwood:

    names:
      - "Duskwood"

    type: zone

    motion:
      mode: ambient
      transition_min_seconds: 35
      transition_max_seconds: 90

    scene_transition_seconds: 4

    lights:

      rectangle_front_left:
        palette:
          - "#2A1C42"
          - "#34234E"

        brightness:
          min: 20
          max: 27

      bedside:
        palette:
          - "#23142D"
          - "#2B1835"

        brightness:
          min: 8
          max: 14
```

---

# 45. Profile Validation

At startup validate:

- all configured light names exist;
- all colors are valid;
- brightness values are in bounds;
- transition ranges are valid;
- aliases do not create ambiguous mappings;
- canonical IDs are unique.

Invalid profile configuration must produce a useful error and not silently behave unpredictably.

---

# 46. Hue Controller Responsibilities

The Hue layer should:

- discover/configure the Bridge Pro;
- authenticate;
- store credentials locally;
- enumerate lights;
- map Hue IDs to logical channels;
- set color;
- set brightness;
- request transitions;
- reconnect automatically;
- rate-limit commands;
- survive network outages.

---

# 47. Hue Failure Behavior

If the bridge becomes unreachable:

```text
log warning
stop sending commands
retry with exponential backoff
retain desired scene internally
resume desired state after reconnect
```

The app should not crash.

---

# 48. Manual Modes

The application should support:

```text
AUTO
PAUSE
OFF
MANUAL PROFILE
```

AUTO:

```text
game location controls lights
```

PAUSE:

```text
stop changing lights
retain current Hue state
```

OFF:

```text
restore configured neutral scene
```

MANUAL:

```text
select any profile for testing
```

---

# 49. Windows Tray UI

A simple tray app is sufficient.

Suggested display:

```text
WoW Forever Hue Ambient
──────────────────────────
Status: Running
WoW: Detected
Log: Active
Hue Bridge: Connected

Location:
Duskwood

Type:
Zone

Source:
Combat Log

Mode:
AUTO

──────────────────────────
Pause
Manual profile >
Open logs
Open config
Reconnect Hue
Exit
```

---

# 50. Debug UI

Debug mode should expose:

```text
log file path
last raw location line
parsed fields
canonical location
profile name
detection source
Hue state
```

If screen fallback is used, additionally display:

```text
screen ROI
raw OCR text
fuzzy match
confidence
```

---

# 51. Structured Logging

Example:

```text
INFO wow_log_opened path="..."
INFO location_event raw_name="Duskwood" map_id=...
INFO location_changed old="Elwynn Forest" new="Duskwood"
INFO profile_applied profile="duskwood"
WARNING unknown_location raw_name="..."
WARNING hue_bridge_unreachable retry_seconds=4
```

Use rotation.

Do not allow unlimited log growth.

---

# 52. Performance Targets

The application should be effectively invisible during gameplay.

Target:

```text
CPU < 1% average when using log detection
RAM < 250 MB
GPU negligible
```

Screen fallback:

```text
2–4 OCR samples/sec max
small ROI only
```

---

# 53. Game Process Detection

The app should determine whether WoW Forever is running.

Possible methods:

```text
process enumeration
window title matching
configured executable names
```

When game is not running:

```text
stop log watcher retries if appropriate
stop OCR
optionally restore neutral scene
```

When game starts:

```text
resume automatically
```

---

# 54. Startup Sequence

```text
start app
↓
load config
↓
validate profiles
↓
connect Hue Bridge
↓
load logical light mapping
↓
detect WoW
↓
discover/configure log
↓
tail log
↓
wait for confirmed location
↓
apply scene
↓
start ambient motion
```

If log mode fails:

```text
offer / activate screen fallback
```

---

# 55. Shutdown Sequence

```text
stop adapters
↓
stop state aggregator
↓
stop ambient scheduler
↓
optionally restore neutral scene
↓
close Hue connection
↓
exit
```

---

# 56. Async / Task Model

Recommended:

```text
Task 1:
WoW process watcher

Task 2:
log tailer

Task 3:
optional screen detector

Task 4:
state aggregator

Task 5:
ambient motion scheduler

Task 6:
Hue command queue

Task 7:
tray UI
```

Hue commands should pass through one queue.

Do not let multiple components write directly to the bridge.

---

# 57. Rate Limiting

Do not spam Hue.

Ordinary scenes:

```text
a few updates per minute per light
```

Active scenes:

```text
more frequent
but still restrained
```

Ambient transitions should be long enough that the bridge is not receiving continuous micro-updates.

---

# 58. Testing Strategy

## Unit Tests

Must cover:

- log parsing;
- partial/malformed records;
- location alias matching;
- ID-based matching;
- unknown locations;
- profile parsing;
- profile validation;
- scene transitions;
- motion bounds;
- random motion with fixed seed;
- Hue command generation;
- bridge retry state.

---

## Log Fixture Tests

Create:

```text
tests/fixtures/logs/
```

Store sanitized real Forever log excerpts.

Example:

```text
zone_elwynn.txt
zone_duskwood.txt
dungeon_deadmines.txt
raid_onyxia.txt
bg_alterac_valley.txt
```

Each parser test should use actual observed format rather than guessed lines.

---

## Screen Fixture Tests

If screen fallback is implemented:

```text
tests/fixtures/screen/
```

Include:

```text
different resolutions
different UI scales
different lighting
different zone names
```

---

# 59. Calibration

For screen fallback:

```text
1. Launch WoW.
2. Open calibration.
3. Capture current WoW frame.
4. User drags rectangle around zone/location label.
5. Save ROI.
6. Show OCR preview.
```

This avoids hardcoding UI coordinates.

---

# 60. Hue Light Calibration

Setup flow:

```text
enumerate Hue lights
↓
flash one light
↓
ask user which logical position it is
↓
persist mapping
```

Logical labels:

```text
Front Left
Front Right
Rear Left
Rear Right
Bedside
```

---

# 61. Packaging

Target output:

```text
WoWForeverHueAmbient.exe
```

The user should not require Python installed.

Development can use:

```text
uv
```

Packaging can use:

```text
PyInstaller
```

or equivalent.

---

# 62. Configuration Storage

Recommended Windows location:

```text
%APPDATA%\WoWForeverHueAmbient\
```

Example:

```text
config.yaml
lights.yaml
profiles/
credentials.json
logs/
```

---

# 63. Git Security

`.gitignore` should include:

```gitignore
.env
credentials.json
config.local.yaml
logs/
debug/
*.log
```

Do not commit Hue authentication credentials.

---

# 64. Milestone Plan

## Milestone 0 — Project Skeleton

Deliverables:

- Python project;
- typed config;
- structured logging;
- CLI;
- pytest;
- package structure.

Success:

```text
app starts
config loads
tests pass
```

---

## Milestone 1 — Hue Control

Deliverables:

- Bridge Pro connection;
- authentication;
- light enumeration;
- logical light mapping;
- manual scene application;
- smooth transitions.

Success:

```text
CLI can apply a named five-light profile
```

Example:

```bash
wow-hue profile duskwood
```

---

## Milestone 2 — Ambient Engine

Deliverables:

- STATIC;
- SUBTLE;
- AMBIENT;
- ACTIVE;
- individual light state;
- randomized timing;
- constrained palettes;
- smooth targets.

Success:

```text
Duskwood can run for 30 minutes
without obvious repetitive RGB cycling
```

---

## Milestone 3 — WoW Log Discovery

Deliverables:

- locate log;
- monitor file;
- survive rotation;
- debug raw appended lines.

Success:

```text
app reliably follows the active WoW log
```

---

## Milestone 4 — Forever Location Investigation

This milestone is deliberately exploratory.

Deliverables:

- collect real Forever log samples;
- identify usable location events;
- document actual format;
- create parser fixtures.

Success:

```text
changing zones produces a machine-readable location event
```

If successful:

```text
continue log-first architecture
```

If not:

```text
activate Milestone 5 screen fallback
```

---

## Milestone 5 — Log Location Parser

Deliverables:

- parse zone/map metadata;
- normalize fields;
- map to canonical location;
- detect world/dungeon/raid/BG when possible.

Success:

```text
walking Elwynn → Westfall → Duskwood
changes internal location state correctly
```

---

## Milestone 6 — Location Profile Resolver

Deliverables:

- aliases;
- IDs;
- type resolution;
- unknown handling;
- profile selection.

Success:

```text
every known location resolves to the expected profile
```

---

## Milestone 7 — Full Automatic Lighting

Deliverables:

```text
WoW location change
→ resolver
→ Hue transition
→ ambient motion
```

Success:

```text
no manual interaction required during normal gameplay
```

---

## Milestone 8 — Tray App

Deliverables:

- game status;
- log status;
- current location;
- source;
- current profile;
- pause;
- manual selection;
- reconnect.

---

## Milestone 9 — Screen Fallback

Only required if log coverage is incomplete.

Deliverables:

- WoW window capture;
- location ROI;
- OCR;
- fuzzy matching;
- hysteresis;
- calibration tool.

---

## Milestone 10 — Time of Day

Future.

Deliverables:

- day/twilight/night;
- modifiers;
- conservative detection.

---

## Milestone 11 — Weather

Future.

Deliverables:

- weather classification;
- weather modifiers.

---

## Milestone 12 — Boss / Encounter Overrides

Future.

Deliverables:

- encounter state source;
- optional raid/boss overlays;
- non-gameplay-critical lighting only.

---

# 65. Suggested First Codex Task

Start here:

> Create the Python project skeleton for `wow-hue`. Implement typed YAML configuration models, structured logging, a `LocationState` model, profile models, profile validation, and a CLI command that loads and prints a named five-light target profile. Include pytest tests. Do not implement Hue networking or WoW detection yet.

Second task:

> Implement the ambient engine with STATIC, SUBTLE, AMBIENT and ACTIVE modes. Each logical light must move independently within a configured palette and brightness range. Provide deterministic tests using a fixed random seed. Do not implement Hue networking yet.

Third task:

> Implement Philips Hue Bridge Pro connectivity and logical five-light mapping. Add a CLI test mode for applying any profile from configuration.

Only after that:

> Investigate and implement World of Warcraft Forever log detection using real collected log fixtures.

Do **not** ask Codex to build the entire system in one pass.

---

# 66. V1 Acceptance Criteria

V1 is complete when:

1. Companion runs on Windows.
2. No WeakAuras dependency exists.
3. No process memory is read.
4. No code is injected into WoW.
5. App detects whether WoW is running.
6. App monitors the selected WoW log.
7. App detects current location from real Forever data, or uses the configured screen fallback.
8. Location changes are stable and debounced.
9. Unknown locations do not cause rapid scene changes.
10. App connects to Hue Bridge Pro.
11. All five lights are mapped independently.
12. Every supported location has a profile.
13. Entering a location smoothly transitions to its profile.
14. Ambient motion remains subtle and non-repetitive.
15. Bridge loss does not crash the application.
16. Manual profile mode works.
17. Pause mode works.
18. Logs clearly explain detection and scene changes.

---

# 67. Hard Artistic Rules

### Rule 1

**Location identity is more important than animation.**

### Rule 2

**Brightness matters as much as color.**

### Rule 3

**Avoid full saturation unless the location genuinely calls for it.**

### Rule 4

**Do not make all five lights breathe together.**

### Rule 5

**Randomization must remain inside curated palette bounds.**

### Rule 6

**Most motion should be slow.**

### Rule 7

**Fast motion should be rare and meaningful.**

### Rule 8

**The room should feel like Azeroth, not like RGB hardware.**

### Rule 9

**Do not mirror screen pixels during normal gameplay.**

### Rule 10

**Do not create gameplay-critical signals.**

---

# 68. Multi-Game Future

Design the ambient engine independently from WoW.

Long term:

```text
                 ┌── WoW Forever adapter
                 │
Game adapters ───┼── Valheim adapter
                 │
                 └── future games
                        │
                        ▼
                 Common State Model
                        │
                        ▼
                  Ambient Engine
                        │
                        ▼
                     Hue
```

The shared layers should be:

```text
profile format
motion engine
transition engine
Hue controller
logical light mapping
tray framework
logging
```

WoW-specific code should remain in:

```text
adapters/
detection/
location resolver
```

---

# 69. Recommended Initial Development Order

The practical order should be:

```text
1. Profile/config system
2. Hue control
3. Ambient motion
4. Manual testing
5. WoW log investigation
6. Location parser
7. Automatic profile switching
8. Tray UI
9. Screen fallback
10. Day/night/weather
```

This order allows the entire lighting system to be validated before depending on uncertain Forever logging details.

---

# 70. First Real-World Test

Once Hue control works:

1. Create manual profiles for:
   - Elwynn Forest
   - Westfall
   - Duskwood
   - Stranglethorn Vale
   - Onyxia's Lair
2. Run each for 10–20 minutes.
3. Adjust:
   - brightness;
   - saturation;
   - motion speed;
   - bedside intensity.
4. Only then automate zone switching.

The artistic quality of the profiles matters more than adding many technical features early.

---

# 71. First Forever Detection Test

When the Forever client is available:

1. Enable local combat logging if required.
2. Start the companion in raw-log debug mode.
3. Move through several known locations.
4. Capture raw lines around each transition.
5. Test:
   - outdoor zone → outdoor zone;
   - outdoor → city;
   - outdoor → dungeon;
   - dungeon → outdoor;
   - battleground entry;
   - raid entry if available.
6. Build parser fixtures from those actual samples.

Target route example:

```text
Stormwind
↓
Elwynn Forest
↓
Westfall
↓
Duskwood
```

If location metadata is clearly present, lock V1 onto the log-first design.

If not, implement screen fallback without changing the Hue/ambient architecture.

---

# 72. Summary

The project should create a local Windows companion for World of Warcraft: Forever that turns five Philips Hue lights into location-driven ambient lighting.

Core V1:

```text
WoW Forever
↓
location detection
↓
canonical location
↓
curated profile
↓
subtle procedural motion
↓
Hue Bridge Pro
↓
4 rectangular lights + bedside
```

The preferred detection source is:

```text
live WoW log metadata
```

The fallback is:

```text
screen OCR
```

The system must not depend on:

```text
WeakAuras
combat-assistance addons
memory reading
game injection
input automation
screen-color mirroring
```

The core experience is:

> **Azeroth determines the room.**

---

# 73. Development Principle

> **Observe externally. Resolve location conservatively. Use curated palettes. Animate subtly. Keep gameplay untouched.**
