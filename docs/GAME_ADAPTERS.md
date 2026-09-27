# Game adapters and shared capture

| Package | Responsibility |
|---|---|
| `hue_core` | Scene library, Hue connection, light mapping, ambient engine, manual scene client |
| `hue_capture` | Window metadata, pixel capture, OCR, selection calibration, vocabulary matching, confirmation, automatic session loop |
| `hue_games` | Game registration, local configuration, profile adapters, command dispatch, game-specific extensions |
| `hue_games.wow` / `wow_unknown` | WoW OCR settings, unknown subzone collection, parent-scene fallback policy |
| `wow_hue` | Compatibility imports/commands and legacy WoW profile migration |

Neither `hue_capture` nor the Valheim adapter imports WoW code. Optional graphics
and OCR dependencies are imported only when capture runs. The portal and manual
lighting continue to work without the gaming extras.

Valheim is a data-only registration in `hue_games/registry.py`. It supplies its
name, default configuration path, and library format. Its executable, aliases,
sampling thresholds, and calibration path live in `config/valheim_ocr.yaml`.
WoW registers a lazily loaded extension for its additional discovery behavior.

## Add another game with a visible text label

1. Add the game's scenes and event names to the shared scene library.
2. Create an app YAML containing `game`, `profiles` (library JSON), `ocr`, and a
   separate `log_file`. Optionally set `profile_cache` for synchronized scenes.
   Light mappings and bridge credentials can use the existing shared paths.
3. Create an OCR YAML with `process_names`, `aliases_file`, and a unique
   `calibration_file`. Start with `location_aliases: {}` in its alias file; event
   names already provide the vocabulary. Registry files and parent-scoped aliases
   are optional matching features, not required for a simple biome detector.
4. Register `GameAdapter("Game name", "config/game.yaml")` under its ID in `GAMES`.
5. Run `hue-client --game ID validate`, calibrate, and test with `ocr` or
   `auto --dry-run` before enabling lighting. Add the local calibration to
   `.gitignore`.

No new branch in the shared capture loop or command handler is necessary.
`tests/test_game_architecture.py` exercises this path with a third test game.

## Specialized behavior

A registration can specify an extension module exposing `load_detection(path,
catalog)` and `session_factory(path, config)`. The factory returns a callable
accepting `(matcher, controller, seed, lighting)`. Sessions expose `pause()`,
`observe(raw, confidence, now)`, `detector`, and `active_profile`; subclass the
shared `AutoSession` to retain normal lighting and confirmation behavior.

WoW uses this extension to collect unknown labels and return from a dedicated
subzone scene to its known parent. Valheim uses the base session and holds its
confirmed scene on uncertain reads, without loading WoW discovery configuration.
The runner currently supplies OCR text; future non-text detectors will need a
separate input-source interface rather than game checks inside the OCR loop.

## Compatibility

`wow-hue` and `valheim-hue` call the shared command handler with their original
default config paths. Existing YAML and saved rectangles remain valid; no
recalibration or credential migration is required. Existing `wow_hue` imports
used by repository tools forward to the new owners. `hue-client` routes command
verbs to the shared handler and retains its earlier manual scene syntax.
