import subprocess
import sys
from pathlib import Path

import pytest

from hue_capture.auto import AutoSession
from hue_games import client
from hue_games.cli import execute, parser
from hue_games.config import load_config
from hue_games.registry import GAMES, GameAdapter

ROOT = Path(__file__).resolve().parents[1]


def test_valheim_does_not_import_wow():
    # A fresh interpreter makes accidental imports observable despite WoW tests.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "from hue_games.config import load_config; "
                "from hue_games.registry import get_game; "
                "c, catalog = load_config(Path('config/valheim.yaml')); "
                "get_game(c.game).load_detection(Path('config') / c.ocr, catalog); "
                "import sys; assert not any(n.startswith('wow_hue') or "
                "n.startswith('hue_games.wow') for n in sys.modules)"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("verb", ["calibrate", "ocr", "auto", "profiles", "validate"])
def test_unified_cli_dispatch(verb, monkeypatch):
    calls = []
    monkeypatch.setattr(client, "game_main", lambda argv: calls.append(argv) or 0)
    args = ["--game", "valheim", "--bridge", "192.168.1.2", verb]
    assert client.main(args) == 0
    assert calls == [args]


def test_legacy_manual_scene_interface_and_reserved_names(capsys, tmp_path):
    cache = ROOT / "config/library.seed.json"
    assert client.main(["--cache", str(cache), "--game", "valheim", "Meadows", "--dry-run"]) == 0
    assert "rectangle_front_left" in capsys.readouterr().out
    from hue_core.catalog import Library

    library = Library.model_validate_json(cache.read_text())
    library.scenes["auto"] = library.scenes["valheim_meadows"]
    custom_cache = tmp_path / "cache.json"
    custom_cache.write_text(library.model_dump_json())
    assert client.main(["--cache", str(custom_cache), "--scene", "auto", "--dry-run"]) == 0


def test_explicit_game_config_mismatch_rejected():
    args = parser().parse_args(
        ["--game", "wow", "--config", str(ROOT / "config/valheim.yaml"), "validate"]
    )
    with pytest.raises(ValueError, match="does not match"):
        execute(args)


def test_third_ocr_game_needs_only_registration_and_data(tmp_path, monkeypatch):
    from hue_core.catalog import Library

    library = Library.model_validate_json((ROOT / "config/library.seed.json").read_text())
    library.games = {"example": library.games["valheim"]}
    (tmp_path / "library.json").write_text(library.model_dump_json())
    (tmp_path / "aliases.yaml").write_text("location_aliases: {}")
    (tmp_path / "ocr.yaml").write_text("process_names: [example.exe]\naliases_file: aliases.yaml")
    config_path = tmp_path / "app.yaml"
    config_path.write_text("game: example\nprofiles: library.json")
    adapter = GameAdapter("Example", str(config_path))
    monkeypatch.setitem(GAMES, "example", adapter)
    config, catalog = load_config(config_path)
    ocr, matcher = adapter.load_detection(tmp_path / config.ocr, catalog)
    assert ocr.process_names == ["example.exe"]
    assert adapter.session_factory(tmp_path / config.ocr, ocr) is AutoSession
    session = adapter.session_factory(tmp_path / config.ocr, ocr)(matcher)
    for now in range(3):
        session.observe("Meadows", 0.99, now)
    assert session.active_profile == "meadows"
    assert execute(parser().parse_args(["--game", "example", "validate"])) == 0
