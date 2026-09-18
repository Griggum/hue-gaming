# WoW Forever Hue — Minimap OCR V1

## Goal

Use **screen-only Minimap OCR** as the first method for detecting the player's current WoW Forever location and switching Philips Hue ambient profiles.

No WeakAuras, addons, combat-log dependency, SavedVariables, memory reading, or game injection.

## Architecture

```text
WoW Forever
   │
   │ screen capture only
   ▼
Minimap location ROI
   │
   ▼
Local OCR
   │
   ▼
Normalize / fuzzy match
   │
   ▼
Resolve subzone → parent location
   │
   ▼
Hue profile
   │
   ▼
Ambient engine
   │
   ▼
Hue Bridge Pro
```

## V1 Detection Flow

1. Capture a small configurable rectangle around the minimap location text.
2. OCR the ROI at roughly **2–4 Hz**.
3. Normalize case, whitespace, and punctuation.
4. Fuzzy-match against known WoW locations.
5. Require the same result for about **3 consecutive reads** before accepting a change.
6. Resolve subzones to their parent zone/city/instance.
7. Only switch Hue profile when the **resolved lighting location** changes.

Example:

```text
OCR #1: "Duskwood"   96%
OCR #2: "Duskwo0d"   89%
OCR #3: "Duskwood"   97%

→ CONFIRMED: Duskwood
```

## Raw vs Resolved Location

Keep these separate:

```text
raw_location      = "Goldshire"
resolved_location = "Elwynn Forest"
profile           = "elwynn_forest"
```

This avoids changing lighting for every small subzone.

## Alias Mapping

Use a config file for subzone → parent mappings.

```yaml
location_aliases:

  Goldshire:
    parent: Elwynn Forest

  Northshire Valley:
    parent: Elwynn Forest

  Trade District:
    parent: Stormwind City

  Old Town:
    parent: Stormwind City
```

Unknown locations should not immediately change the lights:

```text
unknown location
→ keep previous confirmed scene
→ log the raw OCR text
→ add mapping later
```

## Instances

Use the same logic for dungeons, raids, and battlegrounds.

```text
"The Deadmines"
→ deadmines profile

"Onyxia's Lair"
→ onyxias_lair profile

"Alterac Valley"
→ alterac_valley profile
```

If the minimap shows an internal room/subzone name, map it back to the containing instance.

## Debug View

```text
OCR text:
"The Slaughtered Lamb"

Matched:
The Slaughtered Lamb

Resolved:
Stormwind City

Profile:
stormwind

Confidence:
94%

Hue:
Connected
```

## Privacy

Keep all processing local.

Do not:

- upload screenshots
- use cloud OCR
- send game frames externally

Prefer local OCR and local fuzzy matching.

## Recommended Development Order

```text
1. Hue control
2. Manual lighting profiles
3. Ambient motion engine
4. Minimap screen capture
5. OCR
6. Location/subzone database
7. Automatic profile switching
8. Tray UI

Later:
9. Day/night detection
10. Weather detection
11. Optional tiny beacon addon if OCR proves insufficient
```

## Design Principle

> **Use the minimap text to detect where the player is, resolve that to a stable parent location, and let Azeroth control the room ambience.**
