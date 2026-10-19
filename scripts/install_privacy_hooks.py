#!/usr/bin/env python3
"""Install this checkout's privacy hooks without changing shared Git settings."""
from pathlib import Path
import subprocess
from privacy_guard import ROOT, policy


def main():
    settings = policy()  # A fresh machine must provision its private identity policy first.
    email = settings.get("publication_email", "")
    import re
    if not re.fullmatch(r"[0-9]+\+[A-Za-z0-9-]+@users\.noreply\.github\.com", email):
        raise SystemExit("private policy needs publication_email with a GitHub noreply address")
    configured = subprocess.run(["git", "-C", str(ROOT), "config", "--get", "core.hooksPath"], capture_output=True, text=True)
    if configured.stdout.strip():
        raise SystemExit("existing core.hooksPath needs explicit integration; no hooks changed")
    directory = Path(subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--git-path", "hooks"], text=True).strip())
    if not directory.is_absolute():
        directory = ROOT / directory
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("pre-commit", "pre-push", "commit-msg"):
        source = ROOT / ".githooks" / name
        target = directory / name
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise SystemExit(f"existing {name} hook needs explicit integration; no hooks changed")
    for name in ("pre-commit", "pre-push", "commit-msg"):
        target = directory / name
        target.write_bytes((ROOT / ".githooks" / name).read_bytes())
        target.chmod(0o755)
    subprocess.run(["git", "-C", str(ROOT), "config", "--local", "user.name", "Publication Bot"], check=True)
    subprocess.run(["git", "-C", str(ROOT), "config", "--local", "user.email", email], check=True)
    print("Installed pre-commit, pre-push, and commit-msg privacy hooks for this checkout.")


if __name__ == "__main__":
    main()
