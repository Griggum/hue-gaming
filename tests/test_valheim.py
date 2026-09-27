from pathlib import Path

import pytest

from hue_capture.auto import AutoSession
from hue_capture.location_ocr import load_detection
from hue_core.catalog import Library
from hue_games.catalog import game_catalog
from hue_games.cli import execute, parser
from hue_games.config import load_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def matcher():
    config, catalog = load_config(ROOT / "config/valheim.yaml")
    return load_detection(ROOT / "config" / config.ocr, catalog)[1]


@pytest.mark.parametrize(
    "label,key",
    [
        ("Meadows", "meadows"),
        ("Black Forest", "black_forest"),
        ("Swamp", "swamp"),
        ("Mountain", "mountain"),
        ("Plains", "plains"),
        ("Mistlands", "mistlands"),
        ("Ashlands", "ashlands"),
        ("Deep North", "deep_north"),
        ("Ocean", "ocean"),
    ],
)
def test_biome_labels(matcher, label, key):
    assert matcher.match(label, 0.95).profile == key


def test_confirmation_pause_unknown_and_biome_change(matcher):
    session = AutoSession(matcher, seed=42)
    session.observe("Meadows", 0.99, 0)
    session.observe("Meadows", 0.99, 1)
    assert session.engine is None
    session.observe("Meadows", 0.99, 2)
    engine = session.engine
    session.observe("Black Forest", 0.99, 3)
    session.pause()
    session.observe("Black Forest", 0.99, 4)
    assert session.engine is engine
    session.observe("", 0, 5)
    assert session.active_profile == "meadows"
    for t in range(6, 9):
        session.observe("Black Forest", 0.99, t)
    assert session.active_profile == "black_forest"
    assert session.engine is not engine


def test_separate_game_settings_and_vocabulary(matcher):
    from hue_games.wow import load_detection as load_wow

    wow, _ = load_wow(ROOT / "config/ocr.yaml", load_config(ROOT / "config/app.yaml")[1])
    assert matcher.config.calibration_file != wow.calibration_file
    assert matcher.config.process_names == ["valheim.exe"]
    assert not hasattr(matcher.config, "unknown_capture")
    assert matcher.match("Duskwood", 0.99) is None
    assert matcher.match("Meadows", 0.1) is None


def test_library_adapter_uses_valheim_scene_edits():
    library = Library.model_validate_json((ROOT / "config/library.seed.json").read_text())
    library.scenes["valheim_meadows"].name = "Edited Meadows"
    catalog = game_catalog(library, "valheim")
    assert catalog.profiles["meadows"].name == "Edited Meadows"
    assert "duskwood" not in catalog.profiles


def test_valheim_cache_and_fallback(tmp_path):
    library = Library.model_validate_json((ROOT / "config/library.seed.json").read_text())
    library.scenes["valheim_meadows"].name = "Cached Meadows"
    (tmp_path / "cache.json").write_text(library.model_dump_json())
    (tmp_path / "aliases.yaml").write_text("location_aliases: {}")
    (tmp_path / "ocr.yaml").write_text("aliases_file: aliases.yaml\nprocess_names: [valheim.exe]")
    (tmp_path / "app.yaml").write_text(
        "game: valheim\nprofile_cache: cache.json\nprofiles: fallback.json\n"
    )
    assert load_config(tmp_path / "app.yaml")[1].profiles["meadows"].name == "Cached Meadows"
    (tmp_path / "fallback.json").write_text((ROOT / "config/library.seed.json").read_text())
    del library.games["valheim"]
    (tmp_path / "cache.json").write_text(library.model_dump_json())
    assert len(load_config(tmp_path / "app.yaml")[1].profiles) == 9


def test_valheim_cli_offline(capsys):
    cli = parser(str(ROOT / "config/valheim.yaml"))
    assert execute(cli.parse_args(["validate"])) == 0
    assert "9 profiles" in capsys.readouterr().out
    assert execute(cli.parse_args(["profile", "Meadows", "--dry-run"])) == 0
    assert "rectangle_front_left" in capsys.readouterr().out
