from pathlib import Path

from wow_hue.config import load_config, read_yaml
from wow_hue.location_ocr import Matcher, OCRConfig, load_aliases, load_detection

ROOT = Path(__file__).resolve().parents[1]


def test_every_generated_label_routes_exactly_in_its_scope():
    _, catalog = load_config(ROOT / "config/app.yaml")
    _, matcher = load_detection(ROOT / "config/ocr.yaml", catalog)
    imported = read_yaml(ROOT / "config/subzones.generated.yaml")["location_aliases"]
    manual = read_yaml(ROOT / "config/location_aliases.yaml")["location_aliases"]
    for name, value in imported.items():
        if name in manual:
            continue
        scoped = isinstance(value, list)
        for entry in value if scoped else [value]:
            parent = catalog.resolve(entry["parent"])
            match = matcher.match(name, 1, parent if scoped else None)
            assert match is not None, name
            assert match.profile == parent, name
            assert match.confidence == 1, name
        if scoped:
            assert matcher.match(name, 1) is None, name


def test_existing_instance_routes_preserved():
    _, catalog = load_config(ROOT / "config/app.yaml")
    _, matcher = load_detection(ROOT / "config/ocr.yaml", catalog)
    assert matcher.match("Gnomeregan", 1).profile == "gnomeregan"
    assert matcher.match("Zul'Gurub", 1).profile == "zul_gurub"
    # This source explicitly lists the generic outdoor label under Feralas.
    assert matcher.match("Dire Maul", 1).profile == "feralas"
    assert matcher.match("The Maul", 1) is None
    assert matcher.match("The Maul", 1, "dire_maul_west").profile == "dire_maul_west"


def test_manual_alias_overrides_generated_mapping(tmp_path):
    (tmp_path / "generated.yaml").write_text("location_aliases:\n  Goldshire: {parent: Westfall}\n")
    (tmp_path / "manual.yaml").write_text(
        "location_aliases:\n  GOLDSHIRE: {parent: Elwynn Forest, profile: deadmines}\n"
    )
    cfg = OCRConfig(registry_files=["generated.yaml"], aliases_file="manual.yaml")
    aliases = load_aliases(tmp_path / "ocr.yaml", cfg)
    _, catalog = load_config(ROOT / "config/app.yaml")
    assert Matcher(catalog, aliases, cfg).match("Goldshire", 1).profile == "deadmines"


def test_source_metadata_preserved_and_inventory_accounted_for():
    source = read_yaml(ROOT / "config/subzones.source.yaml")
    assert source["classic"]["Dun Morogh"]["map_id"] == 1426
    assert source["classic"]["Dun Morogh"]["subzones"][77] == "Anvilmar"
    count = sum(
        len(parent["subzones"]) for section in source.values() for parent in section.values()
    )
    report = read_yaml(ROOT / "config/subzones.import-report.yaml")
    assert report["source_records"] == count == 918
    assert report["generated_labels"] == 863
    assert not report["unresolved_parents"]
