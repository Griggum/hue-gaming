# Observed Classic Era location events

Captured locally on 2026-09-18, client build 1.15.9, combat log version 9,
project ID 2, advanced logging disabled. The user enabled combat logging in
Stormwind City, walked into Elwynn Forest, and attacked creatures.

`stormwind_to_elwynn.txt` contains only the version header and explicit location
events from the real log. Player names, GUIDs, and combat events were excluded.

Observed map records:

- Stormwind City: `MAP_CHANGE` ID 1453.
- Elwynn Forest: `MAP_CHANGE` ID 1429.

Both `ZONE_CHANGE` records have first numeric field 0. Do not treat that field
as the location's unique map ID. Other field semantics remain unverified.
These observations apply to this Classic Era client, not yet Forever.

## Live delivery remains unverified

The file existed but read as zero bytes after logging started, after the zone
transition and combat, and after the user disabled combat logging. Once the
client closed, the file contained 19,974 bytes including both location changes.

This proves that location events are recorded, but not that a tailer can receive
them promptly during gameplay. It does not establish whether client buffering,
a logging setting, or another mechanism caused the delay. Investigate live
flush behavior before wiring these records to automatic lighting. Do not replay
old records at startup as if they describe the current location.
