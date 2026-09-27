"""Compatibility command for the original WoW client."""

from hue_games.cli import execute, parser
from hue_games.cli import main as shared_main

__all__ = ["execute", "main", "parser", "valheim_main"]


def main():
    return shared_main("config/app.yaml")


def valheim_main():
    return shared_main("config/valheim.yaml")


if __name__ == "__main__":
    raise SystemExit(main())
