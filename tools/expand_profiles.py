"""One-time, reproducible palette expansion. Existing profiles are preserved.

Rows are hand-selected interpretations of the user's artistic specification.
Run from the repository root; runtime reads the generated YAML, not this script.
"""

import re
from pathlib import Path

import yaml

from wow_hue.models import CHANNELS

# Name | type | motion effect | nominal front brightness | dominant/accent/fill
ROWS = """
Redridge Mountains|zone|forest|40|86513D 467048 B18A4A
Deadwind Pass|zone|haunted|15|362940 672D37 241C33
Swamp of Sorrows|zone|haunted|25|365D57 54613D 423B51
Blasted Lands|zone|embers|35|8F392C B65E30 602A2C
Burning Steppes|zone|embers|35|C05B2A 8D3028 582824
Searing Gorge|zone|embers|32|C4662C 792D27 8D592A
Badlands|zone|default|40|BD925A A98846 624A32
Loch Modan|zone|forest|40|528154 567F99 A08A65
Dun Morogh|zone|snow|48|ACC8D8 7099BA CBB488
Wetlands|zone|forest|32|547F91 53714E 927343
Arathi Highlands|zone|forest|42|64874B B49B53 8E5650
Hillsbrad Foothills|zone|forest|44|719454 C5AC69 A18149
Alterac Mountains|zone|snow|43|8AADC7 807C9A BAC9D1
Silverpine Forest|zone|haunted|25|3B587A 504466 305459
Tirisfal Glades|zone|haunted|23|51603A 544061 303F38
Western Plaguelands|zone|haunted|30|9B9445 687043 76483B
Eastern Plaguelands|zone|haunted|28|A69C3A 657D3E 805B2F
The Hinterlands|zone|forest|36|3F704E A18F50 294A3C
Riverglades|zone|forest|43|769650 C8A457 B47747
Durotar|zone|default|42|B77647 9F5441 C89245
The Barrens|zone|default|45|BDA554 82864D BD8847
Mulgore|zone|default|44|719453 7199AE C0A05A
Stonetalon Mountains|zone|forest|35|466C49 5C7587 9A7645
Ashenvale|zone|forest|32|285B46 494774 354C69
Darkshore|zone|haunted|30|466782 648991 5F607C
Teldrassil|zone|forest|32|635082 49764E 6083A1
Azshara|zone|arcane|37|B17B43 527FAD 534267
Felwood|zone|haunted|25|5D7F3D 624571 293D30
Winterspring|zone|snow|50|91C8D3 779FCD A99BBD
Moonglade|zone|forest|30|4F7A63 567A9D 665482
Desolace|zone|default|30|82768A 93816A 677F91
Feralas|zone|forest|32|316F4F 3F7774 5B4772
Dustwallow Marsh|zone|haunted|27|3B6864 647049 896632
Thousand Needles|zone|default|43|BC8551 C2A45C 99594B
Tanaris|zone|default|48|CCAD61 C78B4B 9B7036
Un'Goro Crater|zone|forest|38|3E874B C47838 286148
Silithus|zone|default|37|B7A450 79587F 4D3C62
Shen'dralas|zone|arcane|35|7A5C9B 937651 4C7BA9
Mount Hyjal|zone|forest|38|427A50 52789E C2AD66
Zephras Isle|zone|arcane|52|78BECD A594CA B2C6D5
Ironforge|city|embers|38|BF6E35 A18053 693C29
Darnassus|city|forest|32|68558E 59816A 6C8EAE
Orgrimmar|city|embers|36|A84032 C27A37 6A2D29
Thunder Bluff|city|default|42|B7A25C 718952 BA854D
Undercity|city|haunted|22|648045 624B78 304838
Ragefire Chasm|dungeon|embers|28|C76529 8E3026 6B3D22
Wailing Caverns|dungeon|forest|26|44704A 3B797B 2B4833
Shadowfang Keep|dungeon|haunted|23|4D7399 6A5387 342A4C
Blackfathom Deeps|dungeon|haunted|24|345B7E 3A797C 3D305A
The Stockade|dungeon|default|26|B08A4B 677D88 895C36
Gnomeregan|dungeon|arcane|28|50959E B97D3F 6D8C3B
Razorfen Kraul|dungeon|forest|26|8D704D 576A3D 9C6735
Razorfen Downs|dungeon|haunted|22|6C4B7E 7D96AD 382846
Scarlet Monastery — Graveyard|dungeon|haunted|23|63517D 55779B 8A3839
Scarlet Monastery — Library|dungeon|default|27|A9403C BD9859 6B2E32
Scarlet Monastery — Armory|dungeon|embers|28|9B393C 7F8793 B9703C
Scarlet Monastery — Cathedral|dungeon|default|29|A44243 C6AC63 702C34
Uldaman|dungeon|arcane|27|B39A59 678F97 786047
Zul'Farrak|dungeon|default|29|B79A4F 62804A AC633D
Maraudon|dungeon|forest|25|4F794A 8766A0 365B77
Temple of Atal'Hakkar|dungeon|haunted|23|4E693D 3E7770 6A4B7B
Blackrock Depths|dungeon|embers|28|C17435 8F4435 5E2C29
Lower Blackrock Spire|dungeon|embers|25|A14932 514A48 B77439
Upper Blackrock Spire|dungeon|embers|28|AA3C30 C97B34 4F2929
Scholomance|dungeon|haunted|18|6B4B89 627444 263649
Stratholme|dungeon|embers|26|BC7336 738249 612F2B
Dire Maul East|dungeon|forest|26|4D7948 7B5C94 2C4A35
Dire Maul West|dungeon|arcane|25|7C5E9D 52799E 564272
Dire Maul North|dungeon|default|27|AA7947 82705B B48A43
Hall of Thanes|dungeon|haunted|26|B49A56 6484A7 A87C40
Ruins of Lordaeron|dungeon|haunted|22|6D5182 718349 486D91
Excavation Site: Wetlands|dungeon|default|26|B28D4D 5E7C8A 7C624A
City of Dalaran|dungeon|arcane|28|8466AF 4C85B6 A66C9B
The Drowned City|dungeon|haunted|24|3C7A7E 557A4B 284B73
Krol'dok Stronghold|dungeon|embers|27|B57B43 67804D 805134
Alcaz Prison|dungeon|haunted|24|567C99 994B43 765735
Blackmaw Hold|dungeon|haunted|24|476B44 77568C 7B873E
Shaper's Terrace|dungeon|arcane|28|61A3AF B29C57 3C6188
Barrow Deeps|raid|haunted|20|365C40 614576 314A67
Hyjal Summit|raid|forest|32|337B52 507A9F 699E92
Warsong Gulch|battleground|forest|36|4A794B 9E4C43 3D597C
Arathi Basin|battleground|forest|40|63894B B99B52 668EA8
Darkspear Islands|battleground|forest|38|3D9690 BC7338 3E7948
Molten Core|raid|embers|30|B64F28 C47A32 612B25
Blackwing Lair|raid|embers|26|9A3431 B86A32 492B38
Zul'Gurub|raid|forest|30|3F784A B59245 513D69
Ruins of Ahn'Qiraj|raid|arcane|29|B19B51 66958F 766084
Temple of Ahn'Qiraj|raid|arcane|25|819052 5C8E8A 695080
Naxxramas|raid|haunted|20|59799C 64834D 57406D
"""


def variant(color):
    values = [int(color[i : i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{min(255, v + 9):02X}" for v in values)


def main():
    path = Path("config/profiles.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    profiles = raw["locations"]
    for row in ROWS.strip().splitlines():
        name, kind, effect, brightness, colors = row.split("|")
        key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        if key in profiles:
            continue
        colors = colors.split()
        nominal = int(brightness)
        motion = {"embers": "active", "arcane": "active", "snow": "subtle"}.get(effect, "ambient")
        if effect == "default":
            motion = "static" if kind == "zone" else "subtle"
        channel_colors = [colors[0], colors[0], colors[1], colors[1], colors[2]]
        if name == "Barrow Deeps":
            channel_colors = ["365C40", "614576", "45678C", "907039", "2C203B"]
        if name == "Hyjal Summit":
            channel_colors = ["337B52", "507A9F", "BDA65D", "2F513B", "699E92"]
        lights = {}
        for index, (channel, color) in enumerate(zip(CHANNELS, channel_colors)):
            level = round(nominal * (1, 0.96, 0.78, 0.73, 0.4)[index])
            width = 2 if effect == "snow" else 4 if effect == "embers" else 3
            lights[channel] = {
                "palette": ["#" + color, variant(color)],
                "brightness": [max(1, level - width), level + width],
            }
        profiles[key] = {
            "names": [name],
            "type": kind,
            "motion": motion,
            "effect": effect,
            "transition_seconds": 2.5 if kind in ("dungeon", "raid", "battleground") else 4,
            "lights": lights,
        }
    for key, effect in {
        "elwynn_forest": "forest",
        "duskwood": "haunted",
        "stranglethorn_vale": "forest",
        "onyxias_lair": "embers",
        "alterac_valley": "snow",
    }.items():
        profiles[key]["effect"] = effect
    # Preserve explicit spec palettes; Onyxia previously used an approximation.
    spec = Path("wow-forever-hue-ambient-spec.md").read_text(encoding="utf-8")
    for block in re.findall(r"```yaml\n(.*?)```", spec, re.DOTALL):
        if block.startswith("onyxias_lair:"):
            specified = yaml.safe_load(block)["onyxias_lair"]
            profiles["onyxias_lair"].update(specified)
    path.write_text(
        "# Editable palettes. New profiles interpret the artistic directions in the spec.\n"
        "# Existing palettes retained; Onyxia uses the explicit spec values.\n"
        + yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"{len(profiles)} profiles written")
    lines = [
        "# Lighting profile catalog",
        "",
        "All locations named in sections 27–34 of the supplied spec are covered.",
        "Also includes six Classic Era raids and a neutral scene. Colors are artistic",
        "interpretations where the spec did not provide hex values. This is palette",
        "coverage, not a claim that every in-game subzone label has been mapped.",
        "",
        "| Location | Type | Effect | Front-left brightness | Bedside brightness |",
        "|---|---|---|---|---|",
    ]
    for profile in sorted(profiles.values(), key=lambda p: (p.get("type", "zone"), p["names"][0])):
        front = profile["lights"]["rectangle_front_left"]["brightness"]
        bedside = profile["lights"]["bedside"]["brightness"]
        lines.append(
            f"| {profile['names'][0]} | {profile.get('type', 'zone')} | {profile.get('effect', 'default')} | {front[0]}–{front[1]}% | {bedside[0]}–{bedside[1]}% |"
        )
    Path("docs").mkdir(exist_ok=True)
    Path("docs/PROFILE_CATALOG.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
