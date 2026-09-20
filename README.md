# WoW Forever Hue Ambient

A local Python companion for curated, slow five-light ambience. This first
implementation provides validated YAML profiles, Hue v2 connectivity, persistent
light mapping, manual scenes, and independent ambient motion.

**Implemented:** manual lighting plus local minimap OCR, drag-to-select calibration,
subzone resolution, three-read confirmation, and automatic scene switching.
**Not yet implemented:** tray UI, executable packaging, automatic weather/time detection,
or an exhaustive subzone alias database.
Classic Era logs contain location records but were only readable after exit in our
test. Minimap OCR is now the primary detector and has no logging/addon dependency.

## Install and preview

From this project directory in PowerShell:

```powershell
uv sync --group dev
uv run wow-hue validate
uv run wow-hue profiles
uv run wow-hue profile duskwood --dry-run --seed 42
uv run pytest
```

`--dry-run` makes no network requests and prints the initial five targets.
An ambient dry run also prints just the initial targets and exits.
Configuration defaults to `config/app.yaml`; use `--config PATH` from another
directory. Paths inside that file resolve relative to its directory.

## Credentials and bridge

Your existing `.env` is ignored by Git. It should contain:

```dotenv
HUE_USERNAME=your-bridge-registration-username
API_TOKEN=your-existing-token
HUE_BRIDGE_IP=192.168.1.123
```

`HUE_USERNAME` is the Hue registration `username`, sent as the
`hue-application-key` header. Environment variables override `.env` values.
`API_TOKEN` is preserved but not used: this application uses local REST control,
not cloud OAuth or Entertainment streaming. If that token is a registration
`clientkey`, it is only needed for Entertainment streaming.

To find the bridge IP:

```powershell
uv run wow-hue discover
```

Discovery queries Hue's HTTPS discovery service without sending credentials.
Manual `HUE_BRIDGE_IP` configuration keeps all runtime control local. The bridge
must have a private LAN IP; use `--bridge IP` to override configuration.

TLS verification is enabled by default. Configure `bridge.ca_file` with a trusted
certificate bundle, or explicitly use `--insecure` to accept your local bridge's
self-signed certificate. This disables certificate authentication for that bridge
connection; it is never applied to discovery. HTTP proxy environment variables
are ignored to keep bridge credentials on the direct connection.

```powershell
uv run wow-hue --insecure lights
```

This lists v2 resource IDs, names and color capabilities without changing lights.

## Map five physical lights

Use the IDs returned by `lights`, replacing each placeholder:

```powershell
uv run wow-hue --insecure map rectangle_front_left RESOURCE_ID_1
uv run wow-hue --insecure map rectangle_front_right RESOURCE_ID_2
uv run wow-hue --insecure map rectangle_rear_left RESOURCE_ID_3
uv run wow-hue --insecure map rectangle_rear_right RESOURCE_ID_4
uv run wow-hue --insecure map bedside RESOURCE_ID_5
```

Mapping checks that the light exists on the bridge and supports dimming. It writes
`config/lights.yaml`, ignored by Git, and rejects duplicate assignments. Scene
application requires all five mappings. Physical positions must be selected by
you; names alone do not establish a light's position. Colorless dimmable lights
receive brightness and transitions only.

## Apply and run

These commands change the five mapped lights:

```powershell
uv run wow-hue --insecure profile duskwood
uv run wow-hue --insecure ambient elwynn_forest --duration 600
uv run wow-hue --insecure ambient "Onyxia's Lair"
```

Manual application sends one smooth scene transition. Ambient mode continues
until Ctrl+C, or the specified duration expires. Ctrl+C pauses updates and leaves
the lights in their current state; an already-issued Hue transition may finish.
Restore neutral lighting with:

```powershell
uv run wow-hue --insecure profile neutral
```

Elwynn Forest, Duskwood and Stranglethorn Vale use the spec's explicit palettes.
Onyxia's Lair now also uses its explicit five-light specification. Other profiles
interpret the spec's artistic direction with editable palettes.
Edit `config/profiles.yaml` to tune palettes, brightness and scene transitions.

Default motion modes have independently randomized per-light timing: static 90–180s,
subtle 45–120s, ambient 20–90s, active 12–40s. Location-specific effects override
these defaults as described below. Targets stay within their configured
palettes and brightness bounds. Hue performs the smooth transitions; the app
does not stream frame-by-frame changes. Color targets are clipped to each light's
reported gamut. Requests are serialized and limited to at most four per second.

Ambient mode retains only the latest pending target per light during outages,
backs off from 1s to 30s, and resumes delivery after reconnection. Initial bridge
connection failures and authentication errors exit with a clear message. A manual
scene may partially apply if the bridge fails mid-delivery; rerun it to retry.

Rotating JSON logs are stored under `logs/` (1 MB each, three backups). Credentials
are excluded from application logs. Do not run multiple ambient processes against
the same mapped lights: each process has its own scheduler.

## Location motion and tuning

The [profile catalog](docs/PROFILE_CATALOG.md) lists 98 complete five-light profiles:
every location named in the specification, six additional Classic Era raids, and
neutral lighting. New colors are artistic interpretations where only descriptive
palette directions were supplied. They still benefit from tuning in your room.

| Effect | Time between targets at speed 1 | Behavior |
|---|---|---|
| Forest | 20–90s fronts, 60–120s fill | Slow green drift, quieter warm accents |
| Embers | 3–15s | Independent red/orange targets with bounded brightness changes |
| Arcane | 10–30s | Adjacent palette steps and smooth long fades |
| Snow | 40–120s | Restrained brightness changes, up to 3 percentage points |
| Haunted | 30–100s | Slow dark drift, up to 4 percentage points |

Effects do not add colors outside the curated palette. All lights have independent
random timing. Fade duration is 75% of the target interval, with a two-second floor;
there are no strobes or synchronized breathing cycles. Initial scene transitions
retain each profile's configured duration.

```powershell
uv run wow-hue --insecure auto --brightness 0.8 --intensity 0.6 --speed 0.75
uv run wow-hue --insecure ambient onyxias_lair --intensity 0.5
uv run wow-hue profile winterspring --dry-run --seed 42 --brightness 0.7
```

- `--brightness`: 0–1 multiplier on configured brightness; 0 turns mapped lights off.
- `--intensity`: 0–1 variation around the brightness midpoint and probability of a
  neighboring palette step. Zero sends one stable midpoint scene per location.
- `--speed`: 0.25–2 interval multiplier; 0.5 takes twice as long between targets.
  A three-second minimum target interval remains enforced.

Set persistent defaults in `config/app.yaml` under `lighting`. Optional
`channel_brightness: {bedside: 0.6}` dims the bedside relative to the other lights.
CLI values override the saved defaults for that session. Restart the command to
pick up configuration edits. These controls work in manual and automatic modes.

Profiles can override a particular light's timing using `interval_seconds: [60, 120]`
inside that light's definition. Invalid ranges, unknown light names and out-of-range
tuning values fail validation. Day/night and weather modifiers remain deferred.

## Next development step

Calibrate and validate the OCR on the actual WoW minimap font and your UI scale.
The automated OCR smoke test uses a generated label, not a real game capture.
Extend the editable alias database when the debug output reports an unknown
subzone. Forever's vocabulary still needs validation in that client.

## Minimap OCR setup and automatic lighting

See [subzone registry and discovery](docs/SUBZONE_REGISTRY.md) for parent routing,
dedicated subzone scenes, duplicate-name handling and unknown-label review.
The supplied Classic inventory contributes 863 minimap labels (27 parent-scoped),
with manual alias overrides kept separate from the generated registry.

Dependencies include a local CPU OCR engine and bundled models. No Tesseract
installation, cloud OCR, screenshot uploads, addons or combat logging are needed.

Start WoW in windowed or borderless mode, log into a character, and run:

```powershell
uv run wow-hue calibrate
```

Switch back to WoW within five seconds. A local still-image window opens; drag a
small rectangle around **only the minimap location text**, including a little
padding. Release to save, or press Escape to cancel. Calibration prints an OCR
preview. The full game image is used in memory for calibration only; normal
detection captures just the saved rectangle. No screenshots are saved.

The ROI is relative to the WoW client area and follows window movement, including
between monitors. A window-size change stops detection with a recalibration
message. Recalibrate after changing UI scale or moving the minimap.

Test detection without touching Hue:

```powershell
uv run wow-hue ocr
```

The console shows raw OCR text, matched name, parent location, match score, OCR
confidence, confirmed profile and Hue status. It waits while another app is in
front. Switch to WoW to capture, then return to the console to review output.

Run automatic lighting:

```powershell
uv run wow-hue --insecure auto
# Optional bounded test or simulation:
uv run wow-hue --insecure auto --duration 120
uv run wow-hue auto --dry-run --duration 120
```

Stop any manual ambient process first. Ctrl+C stops the automatic session and
retains current lights. When WoW loses focus or is minimized, capture and further
Hue updates pause; an already-issued transition may complete. Detection resumes
when WoW becomes foreground. No scene is sent before the first confirmed match.

`config/ocr.yaml` controls the 2–4 Hz sampling target, confidence thresholds and
three-read confirmation. Actual rate can be lower when OCR or network requests
take longer. Ambiguous matches are rejected. Unknown/blank/low-confidence reads
break a pending confirmation streak and keep the previous confirmed scene and
its ambience. Moving between subzones of the same parent does not restart it.

Clipped minimap labels also support conservative prefix matching. For example,
`Stranglethorn...` can resolve to Stranglethorn Vale, including small OCR errors
in the visible prefix. By default at least eight normalized characters and half
the name must be visible, with 90% prefix similarity. Shared prefixes such as
`Scarlet Monastery` cannot select a wing and are rejected. Candidates for different
parents still need the configured score margin, OCR confidence and three-read
confirmation. Debug matches include `match_method: prefix` when this is used.
Tune `minimum_prefix_characters`, `minimum_prefix_fraction`, and
`minimum_prefix_similarity` in `config/ocr.yaml`. This supports right-truncated
names; text missing its beginning is not treated as a prefix.

`config/location_aliases.yaml` maps labels such as Goldshire → Elwynn Forest and
Trade District → Stormwind City. Parents must have an existing profile; conflicting
aliases fail validation. The initial catalog also includes The Deadmines and
Alterac Valley as editable starting palettes. Internal instance-room aliases
remain to be collected; unknown names hold the current scene.

Calibration lives in ignored `config/ocr.local.yaml`. Local rotating logs include
raw text from the selected rectangle to help extend the database. Keep the ROI
tight to avoid reading other UI text. No game inputs are automated.

Hue protocol references: [official getting started guide](https://developers.meethue.com/develop/get-started-2/)
and [API v2 guidance](https://developers.meethue.com/new-hue-api/).
