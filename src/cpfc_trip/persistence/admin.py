"""Database migration command."""

from __future__ import annotations

import argparse

from alembic import command
from alembic.config import Config


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("upgrade", "downgrade"), default="upgrade")
    args = parser.parse_args()
    config = Config("alembic.ini")
    if args.action == "upgrade":
        command.upgrade(config, "head")
    else:
        command.downgrade(config, "base")
