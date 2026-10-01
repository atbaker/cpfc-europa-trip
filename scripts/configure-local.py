"""Prepare local configuration without replacing credentials or custom settings."""

import secrets
from pathlib import Path

from cryptography.fernet import Fernet


def configure_local(root: Path) -> None:
    path = root / ".env"
    defaults = (root / ".env.example").read_text().splitlines()
    lines = path.read_text().splitlines() if path.exists() else defaults.copy()
    values = dict(line.split("=", 1) for line in lines if "=" in line and not line.startswith("#"))
    additions = {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in defaults
        if "=" in line and not line.startswith("#") and line.split("=", 1)[0] not in values
    }
    for name, value in {
        "CONTACT_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "SESSION_SECRET": secrets.token_urlsafe(48),
    }.items():
        if not values.get(name):
            additions[name] = value
    # Migrate obsolete shipped defaults, preserving custom queues and cloud regions.
    if values.get("TEMPORAL_TASK_QUEUE") in {"cpfc-trip-v1", "cpfc-trip-v2"}:
        additions["TEMPORAL_TASK_QUEUE"] = "cpfc-trip-v3"
    for name, old, new in (
        ("PLANNER_MODE", "mock", "recorded"),
        ("EMAIL_MODE", "console", "preview"),
    ):
        if values.get(name) == old:
            additions[name] = new
    lines = [line for line in lines if line.split("=", 1)[0] not in additions]
    lines.extend(f"{name}={value}" for name, value in additions.items())
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o600)
    frontend_env = root / "frontend" / ".env.local"
    if not frontend_env.exists():
        frontend_env.write_text((root / "frontend" / ".env.example").read_text())


if __name__ == "__main__":
    configure_local(Path(__file__).resolve().parent.parent)
    print("Local configuration prepared; existing credentials and custom settings preserved.")
