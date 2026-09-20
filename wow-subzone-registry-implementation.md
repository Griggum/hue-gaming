# WoW Forever Hue — Subzone Registry & Unknown-Location Learning

**Target repository:** `Griggum/hue-gaming`  
**Primary detection:** local OCR of the minimap location label  
**Purpose:** map exact minimap-visible subzone labels to existing parent Hue profiles, while automatically collecting unknown Forever labels for later registry expansion.

---

## 1. Core runtime flow

```text
WoW minimap location text
        ↓
screen capture of configured ROI
        ↓
local OCR
        ↓
normalization
        ↓
known subzone matcher
   ┌─────────────┴─────────────┐
 known                         unknown
   ↓                              ↓
parent profile              unknown detector
   ↓                              ↓
Hue ambience          stable/repeated OCR only
                                  ↓
                         unknown_locations.jsonl
                                  ↓
                     later review / registry promotion
```

The Hue scene is still selected from the **existing parent profile**. The subzone registry exists primarily to improve OCR recognition and routing.

Examples:

```text
Raven Hill Cemetery → Duskwood
Trade District       → Stormwind City
Goldshire            → Elwynn Forest
Fargodeep Mine       → Elwynn Forest
```

---

## 2. Canonical subzone registry

Keep the current repository-compatible schema for the primary alias file.

```yaml
location_aliases:

  Raven Hill Cemetery:
    parent: Duskwood

  Raven Hill:
    parent: Duskwood

  Darkshire:
    parent: Duskwood

  Trade District:
    parent: Stormwind City

  Mage Quarter:
    parent: Stormwind City

  Goldshire:
    parent: Elwynn Forest

  Fargodeep Mine:
    parent: Elwynn Forest
```

The canonical registry should contain only **confirmed minimap-visible labels** that safely map to an existing profile in `config/profiles.yaml`.

Do not insert uncertain OCR strings into this file automatically.

---

## 3. New requirement: unknown-location learning

The application should maintain a separate runtime file:

```text
config/unknown_locations.jsonl
```

Use JSON Lines rather than YAML for runtime writes because:

- one observation can be appended atomically;
- a corrupted final line does not destroy the whole registry;
- it is easy to stream, grep, diff, and post-process;
- multiple observations can later be consolidated by tooling;
- the canonical YAML remains hand-reviewed and deterministic.

This file is **not loaded as a trusted location registry**.

It is a discovery log.

---

## 4. When an OCR result counts as an unknown location

Do **not** log every failed OCR frame.

An unknown candidate should be recorded only when all of these are true:

1. OCR confidence is above the unknown-capture threshold.
2. The normalized text is not empty.
3. It does not safely match a known canonical location.
4. The same normalized unknown text has been observed for several consecutive reads.
5. The label survives for a minimum duration or confirmation count.

Recommended defaults:

```yaml
unknown_capture:
  enabled: true

  # Slightly stricter than normal OCR acceptance because this creates data
  # that may later become part of the registry.
  minimum_ocr_confidence: 0.75

  consecutive_reads: 3

  # Avoid logging tiny OCR fragments such as "The" or "Hill".
  minimum_characters: 5

  # Do not append the same candidate continuously while the player stands still.
  repeat_suppression_seconds: 300
```

At the existing 3 Hz OCR rate, three consistent reads represent roughly one second of stable text.

---

## 5. Parent-zone context

Every unknown observation should contain the best parent-zone context available at the time.

Example:

```json
{
  "raw_text": "Fairwind Mesa",
  "normalized_text": "fairwind mesa",
  "parent_context": "Zephras Isle",
  "parent_profile": "zephras_isle"
}
```

Parent context is valuable because the same subzone name may exist in multiple places.

### Parent-context priority

Use the strongest available source in this order:

```text
1. Current confirmed subzone's known parent
2. Most recently confirmed parent profile
3. Parent inferred from a recently confirmed known sibling subzone
4. Parent supplied manually by the user/debug UI
5. unknown / null
```

Every observation must also say **how** the parent was obtained.

Recommended values:

```text
confirmed_current
previous_confirmed
sibling_context
manual
unknown
```

Do not silently treat a stale previous parent as certain.

---

## 6. Unknown observation schema

Recommended append-only JSONL record:

```json
{
  "schema_version": 1,

  "first_seen": "2026-09-20T10:41:12+02:00",
  "last_seen": "2026-09-20T10:41:13+02:00",

  "raw_text": "Fairwind Mesa",
  "normalized_text": "fairwind mesa",

  "ocr_confidence": 0.93,
  "confirmation_reads": 4,

  "parent_context": "Zephras Isle",
  "parent_profile": "zephras_isle",
  "parent_context_source": "previous_confirmed",
  "parent_context_age_seconds": 8.4,

  "previous_known_location": "Fairweather Stables",
  "previous_parent_profile": "zephras_isle",

  "active_profile_at_detection": "zephras_isle",

  "match_result": "unknown",
  "best_known_candidate": null,
  "best_known_match_score": 0.61,

  "wow_product": "Forever",
  "wow_build": null,

  "session_id": "2026-09-20T08-35-11Z"
}
```

If no parent context is available:

```json
{
  "raw_text": "Stormbreak Rise",
  "normalized_text": "stormbreak rise",
  "parent_context": null,
  "parent_profile": null,
  "parent_context_source": "unknown"
}
```

---

## 7. Consolidated unknown registry

The raw JSONL log should be periodically reduced into a review-friendly file:

```text
config/unknown_locations.generated.yaml
```

Example:

```yaml
unknown_locations:

  zephras_isle__fairwind_mesa:
    display_name: Fairwind Mesa
    normalized_name: fairwind mesa

    parent_context: Zephras Isle
    parent_profile: zephras_isle

    observations: 17
    sessions_seen: 3

    first_seen: "2026-09-20T10:41:12+02:00"
    last_seen: "2026-09-22T19:14:07+02:00"

    confidence:
      mean_ocr: 0.94
      minimum_ocr: 0.88

    raw_variants:
      "Fairwind Mesa": 15
      "Fairwlnd Mesa": 2

    context:
      previous_known_locations:
        Fairweather Stables: 9
        Valanaar: 4

    status: needs_review
```

This generated file should never automatically drive Hue routing.

It exists for registry maintenance.

---

## 8. Deduplication key

Unknowns must **not** be keyed only by display text.

Use:

```text
(parent_profile, normalized_text)
```

when parent context is available.

For example:

```text
("westfall", "the great sea")
("durotar", "the great sea")
```

are two different discoveries.

If the parent is not known, use:

```text
("__unknown_parent__", normalized_text)
```

and allow the consolidation tool to reclassify the entry later.

---

## 9. Handling OCR variants

Preserve the raw OCR strings.

Do not immediately create canonical aliases such as:

```text
Fairwlnd Mesa
Fairwind M esa
Faiwind Mesa
```

Instead aggregate them under one candidate when they are clearly repeated variants.

The review process can then decide whether:

```text
Fairwind Mesa
```

is the true game label.

Only confirmed game labels belong in `location_aliases.yaml`.

OCR mistakes should preferably be solved by fuzzy matching rather than permanently growing the alias registry with garbage.

---

## 10. Known-parent fallback behavior

When a stable unknown label appears but a parent profile is known:

```text
OCR: "New Forever Subzone"
Known parent: Riverglades

→ keep Riverglades Hue profile
→ log the unknown subzone
→ do not switch to neutral
```

This is the preferred Forever behavior.

Pseudo-code:

```python
match = matcher.match(ocr_text, ocr_confidence)

if match:
    confirm_known(match)
    current_parent_context = match.profile
    apply_profile(match.profile)

else:
    unknown = unknown_detector.observe(ocr_text, ocr_confidence)

    if unknown.confirmed:
        unknown_logger.record(
            text=unknown.text,
            parent_context=current_parent_context,
            previous_known_location=last_known_location,
        )

    if current_parent_context:
        # Keep the current parent ambience.
        apply_profile(current_parent_context)
    else:
        # Preserve the previous scene for the normal unknown grace period.
        keep_previous_scene()
```

---

## 11. Parent-context expiry

A previous parent must not remain trusted forever.

Recommended:

```yaml
unknown_capture:
  parent_context_soft_ttl_seconds: 60
  parent_context_hard_ttl_seconds: 300
```

Suggested meaning:

```text
0–60 sec:
parent_context_source = previous_confirmed
confidence = strong

60–300 sec:
retain parent value for diagnostics
confidence = weak

>300 sec:
parent_context = null
```

Entering a known parent/subzone refreshes the timer immediately.

This prevents a completely new Forever zone from being incorrectly recorded under the previous zone simply because the OCR registry does not know the new parent yet.

---

## 12. Boundary observations

For discovery purposes, retain both the previous and next known location when possible.

Example:

```text
Known: Meadowsbrook
Unknown: "Ashen Rise"
Unknown: "Ashen Rise"
Unknown: "Ashen Rise"
Known: Powderfuse Port
```

The consolidated entry can contain:

```yaml
context:
  previous:
    Meadowsbrook: 1
  next:
    Powderfuse Port: 1
```

If both known locations map to Riverglades, confidence that `Ashen Rise` belongs to Riverglades becomes very high.

The implementation may update the discovery record after the next known location is established.

---

## 13. Suggested discovery-state model

```text
KNOWN
  │
  ├── known OCR
  │      └── remain KNOWN
  │
  └── repeated unknown OCR
         ↓
   UNKNOWN_CANDIDATE
         │
         ├── unstable / changes
         │      └── discard candidate
         │
         └── N stable reads
                ↓
        UNKNOWN_CONFIRMED
                │
                ├── append observation
                ├── keep known parent scene if available
                └── suppress repeated writes temporarily
```

This state machine should be separate from the existing known-location `Detector`.

---

## 14. Suggested implementation classes

```text
src/wow_hue/
├── location_ocr.py
├── unknown_locations.py        # NEW
└── ...
```

Suggested responsibilities:

```python
class UnknownDetector:
    """Confirms stable OCR labels that did not resolve in the known registry."""


class UnknownLocationLogger:
    """Writes confirmed unknown observations to JSONL."""


class UnknownLocationIndex:
    """Loads and consolidates observations for review tooling."""
```

Optional tool:

```text
tools/review_unknown_locations.py
```

Example commands:

```bash
uv run python tools/review_unknown_locations.py summary

uv run python tools/review_unknown_locations.py \
    --parent "Zephras Isle"

uv run python tools/review_unknown_locations.py \
    promote \
    --name "Fairwind Mesa" \
    --parent "Zephras Isle"
```

`promote` should generate a suggested YAML change rather than silently modifying the canonical registry unless explicitly requested.

---

## 15. Configuration addition

Recommended addition to `config/ocr.yaml`:

```yaml
aliases_file: location_aliases.yaml
calibration_file: ocr.local.yaml

process_names:
  - WowClassic.exe
  - Wow.exe

samples_per_second: 3

consecutive_reads: 3
minimum_ocr_confidence: 0.65
minimum_match_score: 0.84
ambiguity_margin: 0.08

minimum_prefix_characters: 8
minimum_prefix_fraction: 0.5
minimum_prefix_similarity: 0.9


unknown_capture:

  enabled: true

  output_file: unknown_locations.jsonl

  minimum_ocr_confidence: 0.75

  consecutive_reads: 3

  minimum_characters: 5

  repeat_suppression_seconds: 300

  parent_context_soft_ttl_seconds: 60

  parent_context_hard_ttl_seconds: 300
```

---

## 16. Example Forever discovery session

Assume the known registry contains:

```yaml
Fairweather Stables:
  parent: Zephras Isle

Valanaar:
  parent: Zephras Isle
```

The player travels:

```text
Fairweather Stables
       ↓
UNKNOWN: Windcaller Terrace
       ↓
UNKNOWN: Windcaller Terrace
       ↓
UNKNOWN: Windcaller Terrace
       ↓
Valanaar
```

Runtime:

```text
Fairweather Stables
→ known
→ parent context = Zephras Isle

Windcaller Terrace ×3
→ no known registry entry
→ stable unknown
→ record with parent_context = Zephras Isle
→ continue running Zephras Isle Hue ambience

Valanaar
→ known
→ parent context remains Zephras Isle
→ discovery record can now also note the next known location
```

Result:

```yaml
Windcaller Terrace:
  observations: 1
  likely_parent: Zephras Isle
  previous_known: Fairweather Stables
  next_known: Valanaar
  status: needs_review
```

After verifying the text in-game or against Forever client data, promote it to:

```yaml
location_aliases:

  Windcaller Terrace:
    parent: Zephras Isle
```

No Hue code change is required.

---

## 17. What should be logged

Keep the discovery log text-only.

Recommended:

```text
timestamp
session
raw OCR
normalized OCR
OCR confidence
confirmation count
known/fuzzy candidate score
parent profile/context
parent-context source and age
previous known location
next known location when available
WoW build if known
```

Do **not** store:

```text
full screenshots
continuous screen recordings
unrelated screen regions
game chat
player names
```

The discovery system does not need them.

---

## 18. Logging levels

Normal application log:

```text
INFO  unknown_location_confirmed text="Windcaller Terrace" parent="Zephras Isle"
```

Do not log every OCR frame at INFO.

Detailed frame-by-frame information belongs at:

```text
DEBUG
```

The persistent discovery dataset should only receive **confirmed unknown candidates**.

---

## 19. Promotion workflow

The long-term Forever registry workflow should be:

```text
play WoW Forever
       ↓
unknown label discovered
       ↓
unknown_locations.jsonl
       ↓
consolidation tool
       ↓
unknown_locations.generated.yaml
       ↓
manual / researched verification
       ↓
location_aliases.yaml
       ↓
git commit
       ↓
known forever after
```

This creates a self-improving registry without allowing noisy OCR to corrupt the trusted configuration.

---

## 20. Important interaction with duplicate subzone names

Because the Classic dataset contains names that occur under multiple parents, the future matcher should support parent-scoped candidates.

Unknown logging must already follow that model.

Good:

```text
(parent_profile, normalized_name)
```

Bad:

```text
normalized_name
```

This matters for labels such as:

```text
The Great Sea
The Forbidding Sea
Southfury River
Thandol Span
North Gate Pass
South Gate Pass
```

The discovery system should therefore be implemented in a way that remains compatible with a future parent-aware matcher.

---

## 21. Recommended repo files after implementation

```text
config/
├── profiles.yaml
├── location_aliases.yaml
├── ocr.yaml
├── ocr.local.yaml
├── unknown_locations.jsonl              # runtime, gitignored
└── unknown_locations.generated.yaml     # optional review artifact

tools/
├── build_subzones.py
├── verify_subzones.py
└── review_unknown_locations.py

src/wow_hue/
├── location_ocr.py
├── unknown_locations.py
└── ...
```

Recommended `.gitignore`:

```gitignore
config/unknown_locations.jsonl
config/unknown_locations.generated.yaml
```

If a reviewed discovery becomes canonical, commit the resulting addition to:

```text
config/location_aliases.yaml
```

rather than committing raw runtime logs.

---

## 22. Acceptance criteria

The implementation is complete when all of the following are true:

- Known Classic/Forever subzones resolve to the correct existing parent profile.
- Stable unknown labels are captured automatically.
- Random bad OCR frames are not persisted.
- Unknown labels preserve the current parent profile when reliable parent context exists.
- Each discovery stores parent context and the source/age of that context.
- Unknowns without reliable parent context are still recorded with `parent_context: null`.
- Repeated observations are rate-limited/deduplicated.
- Duplicate names can be distinguished by parent context.
- The raw discovery file never changes Hue routing by itself.
- Unknown labels can later be reviewed and promoted into `location_aliases.yaml`.
- All processing and logging remain local.
- Full screenshots are not required or stored.

---

## 23. Design principle

> **Known locations control the room. Unknown locations teach the registry.**

For WoW Forever, this is preferable to trying to ship a supposedly complete static location database while the game is still evolving.
