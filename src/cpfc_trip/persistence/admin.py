import sys

from alembic import command
from alembic.config import Config


def main() -> None:
    if sys.argv[1:] != ["upgrade"]:
        raise SystemExit("Usage: cpfc-db upgrade")
    command.upgrade(Config("alembic.ini"), "head")
