# Subzones and local discovery

`config/location_aliases.yaml` is the trusted, editable registry. Matching checks
full names and conservative fuzzy/prefix candidates, then confirms three reads.
The raw label, resolved lighting profile, and geographic parent are separate.

## Route to a parent

```yaml
location_aliases:
  Raven Hill Cemetery:
    parent: Duskwood
  Fargodeep Mine:
    parent: Elwynn Forest
```

Both entries are included. A parent can be a profile name or canonical ID.
Moving among aliases routed to the same lighting profile preserves the existing
ambient engine and does not replay the scene transition.

## Use a dedicated scene

First create a complete five-light profile in `config/profiles.yaml`, for example
by copying Elwynn Forest to a new `fargodeep_mine` entry, setting its `names` to
`[Fargodeep Mine]`, and adjusting its colors, brightness, motion and effect. Then:

```yaml
location_aliases:
  Fargodeep Mine:
    parent: Elwynn Forest
    profile: fargodeep_mine
```

The optional `profile` must be an existing canonical lighting profile ID. Missing
or conflicting references fail `uv run wow-hue validate`. Parent context remains
Elwynn Forest, even while the dedicated mine scene plays. The application does
not invent or copy lighting profiles automatically. Restart `auto` after edits.

## Duplicate names in multiple places

Use a list of explicit parent-scoped entries:

```yaml
location_aliases:
  The Great Sea:
    - parent: Westfall
    - parent: Durotar
```

This is a schema example, not a shipped assertion about an observed label. A
scoped label is only eligible when the application has a recently confirmed
unambiguous parent (60 seconds by default). It does not guess the parent when
starting in a shared area. Reading the ambiguous label repeatedly cannot renew
that context forever. Each scoped entry can also specify a dedicated `profile`.

## Discover unknown labels during play

Normal `auto` and detection-only `ocr` sessions append confirmed discoveries to
`config/unknown_locations.jsonl`. They do not change the trusted registry.

Defaults in `config/ocr.yaml`, under `unknown_capture`:

- OCR confidence at least 0.75; at least five normalized characters.
- Three consecutive identical normalized unknown reads.
- Five-minute repeat suppression, keyed by parent and normalized text.
- Parent age up to 60 seconds: strong previous context.
- Parent age 60–300 seconds: weak diagnostic context.
- Beyond 300 seconds: parent is null; historical location remains diagnostic.

Focus loss, known text, low confidence, and changed unknown text reset the pending
unknown streak. The discovery record includes timestamps, raw/normalized text,
confidence, session ID, parent source/age/strength, previous known label, active
lighting profile, and a diagnostic best candidate score. Product/build are only
recorded from explicit configuration. The current product setting is Classic Era;
change it when testing Forever. No screenshot is required or saved.

A stable unknown preserves the current ambience. If currently using a dedicated
subzone scene and the parent context is still strong, it transitions back to the
parent scene. Weak/expired context never triggers a guessed parent transition.
Returning to a confirmed known subzone restores its override normally.

Unknown recording is independent from known-location confirmation. To disable
discovery writes, set `unknown_capture.enabled: false`. In that mode unknown reads
simply hold the current scene. File-write failures are logged without crashing
lighting. Run one companion process at a time; this file is not a multi-writer
database. The dataset is intentionally append-only; archive it when desired.

## Review and propose additions

```powershell
uv run python tools/review_unknown_locations.py summary
uv run python tools/review_unknown_locations.py summary --parent "Elwynn Forest"
uv run python tools/review_unknown_locations.py promote --name "A Verified Label" --parent "Elwynn Forest"
```

Summary writes `config/unknown_locations.generated.yaml`, grouped by parent plus
normalized label, with observation/session counts, confidence, raw variants and
previous known locations. Malformed lines are counted and skipped, including a
partial final line. Different normalized OCR spellings remain separate for human
review; the tool deliberately does not infer that similar names are the same place.

`promote` validates and prints a suggested YAML entry only. Optional
`--profile YOUR_PROFILE_ID` selects a dedicated scene. Verify the actual label and
parent before copying the proposal into the trusted registry. Neither discovery
file is loaded for matching, and neither is committed to Git.

The supplied Classic inventory is now preserved in `config/subzones.source.yaml`:
918 area records, including parent map IDs and AreaTable IDs. Those IDs are source
metadata only; text-only OCR cannot observe them. Run
`uv run python tools/build_subzones.py` to rebuild `config/subzones.generated.yaml`
and `config/subzones.import-report.yaml` after source changes.

The generated registry contributes 863 labels, including 27 parent-scoped names.
It is loaded through `registry_files` in `config/ocr.yaml`. The hand-maintained
`location_aliases.yaml` loads last, so it can override any imported routing or add
a dedicated lighting profile without editing generated files. Import spelling is
preserved exactly as supplied; this is not independent verification of every label.

Twelve source labels collide with existing full instance/zone profile names, such
as Gnomeregan under Dun Morogh. Existing dedicated profiles retain precedence;
the source remains intact and the report lists these collisions. OCR cannot tell
an identically named exterior area from the instance solely from that label.

Source group `Ahn'Qiraj` routes to Temple of Ahn'Qiraj, while its separately listed
Ruins group routes to Ruins of Ahn'Qiraj. Shared room names require recent context.
The generic Dire Maul exterior label routes to Feralas as supplied; `The Maul`
requires a previously known Dire Maul wing and preserves that wing's lighting.

This is not an exhaustive Forever subzone database. Next-known boundary evidence
and manual-parent input are not currently captured; previous confirmed context is
explicitly labelled and expires rather than being presented as certain.
