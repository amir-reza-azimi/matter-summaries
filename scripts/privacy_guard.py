#!/usr/bin/env python3
"""Fail closed before public files are written, committed, or pushed.

Private identities and exact-byte editorial review receipts live outside Git.
Diagnostics deliberately report rule names, never matched sensitive text.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
from urllib.parse import unquote, urlsplit, parse_qsl

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = Path(os.environ.get("MATTER_PRIVACY_HOME", Path.home() / ".local/state/matter-summaries"))
IDENTITY = PRIVATE / "identity.json"
RECEIPTS = PRIVATE / "publication-reviews.json"
ATTESTATION = "public-source-only; no private personal or internal-work context"
SELF_URL = re.compile(r"https://[a-z0-9-]+\.github\.io/matter-summaries(?:/[A-Za-z0-9_./-]*)?", re.I)
RULES = {
    "email address": r"[\w.+-]+@[\w.-]+\.[a-z]{2,}",
    "local home path": r"(?:/Users/|/home/|file://|[A-Z]:\\Users\\)",
    "credential": r"(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b)",
    "assigned secret": r"(?<![\w.])(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|client[_ -]?secret|password)[ \t]*[\"']?[ \t]*[:=][ \t]*[\"']?[A-Za-z0-9_./+-]{12,}",
    "phone number": r"(?<![\w])\+\d(?:[ ()-]?\d){9,14}(?!\d)",
    "active HTML": r"<(?:script|iframe|object|embed)\b|data:[a-z]+/[a-z]+;base64,",
    "private record": r"\b(?:calendarEventId|processed_message_ids|processed_annotation_ids|pickup_location|booking_reference|passport_number|tax_id|bank_account|iban)\b",
    "private application link": r"https?://(?:mail\.google\.com|calendar\.google\.com|drive\.google\.com|docs\.google\.com|(?:[\w-]+\.)?notion\.(?:so|site)|(?:[\w-]+\.)?atlassian\.net|app\.getmatter\.com)(?:[/\s]|$)",
    "private email article": r"getmatter\.com/email/",
    "personal or internal context": r"\b(?:my|our|your)\s+(?:journal|diagnosis|medication|passport|tax return|bank account|booking|itinerary|client roster|salary|home address)\b|\b(?:I am already building|I could|my own work|our internal|internal-only|confidential)\b",
}
URL_RE = re.compile(r"https?://[^\s<>\"'`]+", re.I)


class PrivacyError(ValueError):
    pass


def policy() -> dict:
    try:
        value = json.loads(IDENTITY.read_text())
        if not isinstance(value["identifiers"], list) or not value["identifiers"]:
            raise ValueError()
        if not all(isinstance(term, str) and term.strip() for term in value["identifiers"] + value.get("terms", [])):
            raise ValueError()
        return value
    except (OSError, ValueError, KeyError, TypeError):
        raise PrivacyError("private identity policy is missing or invalid; publishing is blocked") from None


def normalize(text: str) -> str:
    for _ in range(4):
        decoded = html.unescape(unquote(text))
        if decoded == text:
            break
        text = decoded
    text = unicodedata.normalize("NFKC", text)
    return "".join(c for c in text if unicodedata.category(c) != "Cf")


def findings(text: str, *, content: bool = True) -> list[str]:
    settings = policy()
    text = normalize(text)
    # The public hosting URL inevitably identifies its account. Only that precise
    # structural URL is exempt, never owner names in prose or other URLs.
    text = SELF_URL.sub("https://public-host.invalid/site", text)
    active = RULES if content else {k: RULES[k] for k in ("credential", "assigned secret", "email address")}
    reasons = [name for name, pattern in active.items() if re.search(pattern, text, re.I)]
    if content:
        # Catch markup splitting names as well as raw attributes/comments/JSON.
        visible = re.sub(r"<[^>]*>", "", text)
        for term in settings["identifiers"] + settings.get("terms", []):
            pattern = r"(?<!\w)" + re.escape(normalize(term)) + r"(?!\w)"
            if re.search(pattern, text, re.I) or re.search(pattern, visible, re.I):
                reasons.append("private identity or context")
                break
    for candidate in re.findall(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", text):
        numeric = "".join(str(ord(c) - 55) if c.isalpha() else c for c in candidate[4:] + candidate[:4])
        if int(numeric) % 97 == 1:
            reasons.append("bank account number")
    for match in URL_RE.finditer(text):
        try:
            url = urlsplit(match.group().rstrip("),.;"))
            host = url.hostname or ""
            if url.username or url.password:
                reasons.append("credentials in URL")
            try:
                if not ipaddress.ip_address(host).is_global:
                    reasons.append("private network URL")
            except ValueError:
                if host in {"localhost"} or host.endswith((".local", ".internal")):
                    reasons.append("private network URL")
            for key, value in parse_qsl(url.query):
                if re.search(r"token|secret|signature|credential|password|email|auth|^key$|^sig$|x-amz-|x-goog-", key, re.I):
                    reasons.append("personal or signed URL parameter")
            if url.fragment and re.search(r"access_token|id_token", url.fragment, re.I):
                reasons.append("credential URL fragment")
        except ValueError:
            reasons.append("malformed URL")
    return sorted(set(reasons))


def assert_public(text: str, label: str = "publication", *, content: bool = True) -> None:
    reasons = findings(text, content=content)
    if reasons:
        raise PrivacyError(f"{label}: blocked by privacy guard ({', '.join(reasons)})")


def check_record(record: dict, allowed: set[str]) -> None:
    if set(record) - allowed:
        raise PrivacyError("record contains unapproved fields; keep private metadata outside the public repository")
    assert_public(json.dumps(record, ensure_ascii=False), "input record")


def public_write(path: str | Path, text: str, *, allow_external: bool = False) -> None:
    path = Path(path)
    assert_public(text)
    assert_public(re.sub(r"[_-]+", " ", path.name), "publication filename")
    # No symlinks, traversal, or writes outside the declared public content tree.
    if not (allow_external and not path.resolve().is_relative_to(ROOT)) and not path.resolve().is_relative_to((ROOT / "docs").resolve()) and not path.resolve().is_relative_to((ROOT / "data").resolve()):
        raise PrivacyError("output must stay within docs/ or data/")
    if path.is_symlink() or any(p.is_symlink() for p in path.parents if p.is_relative_to(ROOT)):
        raise PrivacyError("symlink publication is blocked")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def safe_component(value: str) -> str:
    assert_public(re.sub(r"[_-]+", " ", value), "publication filename")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise PrivacyError("unsafe publication filename")
    return value


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], stderr=subprocess.PIPE)


def is_content(path: str) -> bool:
    return path.startswith(("docs/", "data/"))


def path_error(path: str) -> str | None:
    if path in {".gitignore", "README.md", "PRIVACY.md", "AGENTS.md", "CLAUDE.md", "docs/.nojekyll"}:
        return None
    if re.fullmatch(r"scripts/[a-z_]+\.py|\.githooks/(?:pre-commit|pre-push|commit-msg)", path):
        return None
    if re.fullmatch(r"docs/(?:index\.html|feed\.xml|(?:videos|x|newsletters|daily-news|travel)/[A-Za-z0-9_-]+\.html)", path):
        return None
    if re.fullmatch(r"data/(?:[A-Za-z0-9_-]+\.json|travel/[A-Za-z0-9_-]+\.json|daily-news/fixtures/[A-Za-z0-9_-]+\.json)", path):
        return None
    return "path is outside the public file allowlist"


def load_receipts() -> dict:
    try:
        value = json.loads(RECEIPTS.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def reviewed(path: str, data: bytes) -> bool:
    entry = load_receipts().get(path, {})
    return entry.get("sha256") == hashlib.sha256(data).hexdigest() and entry.get("attestation") == ATTESTATION and bool(entry.get("sources"))


def scan_entries(entries: list[tuple[str, str, bytes]], required: set[str]) -> list[str]:
    errors = []
    for mode, path, data in entries:
        reason = path_error(path)
        if reason:
            errors.append(f"{path}: {reason}")
            continue
        if mode not in {"100644", "100755"}:
            errors.append(f"{path}: symlinks and submodules are blocked")
            continue
        try:
            text = data.decode("utf-8")
            if path.endswith(".json"):
                text = json.dumps(json.loads(text), ensure_ascii=False)
            if "\0" in text:
                raise ValueError()
            assert_public(path, "filename")
            assert_public(text, path, content=is_content(path) or path.endswith(".md"))
        except (UnicodeError, ValueError) as exc:
            errors.append(str(exc) if isinstance(exc, PrivacyError) else f"{path}: binary or unreadable file is blocked")
        if path in required and is_content(path) and not reviewed(path, data):
            errors.append(f"{path}: exact-byte public-source review is missing or stale")
    return errors


def tree_entries(ref: str) -> list[tuple[str, str, bytes]]:
    result = []
    for line in git("ls-tree", "-rz", ref).split(b"\0"):
        if not line:
            continue
        meta, name = line.split(b"\t", 1)
        mode, kind, sha = meta.decode().split()
        result.append((mode, name.decode(), git("cat-file", "-p", sha) if kind == "blob" else b""))
    return result


def changed(ref: str, base: str | None = None) -> set[str]:
    if base is None:
        parents = git("rev-list", "--parents", "-n", "1", ref).decode().split()[1:]
        if parents:
            return set().union(*(changed(ref, parent) for parent in parents))
        data = git("diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-z", ref)
    else:
        data = git("diff", "--name-only", "-z", base, ref)
    return set(filter(None, data.decode().split("\0")))


def staged_errors() -> list[str]:
    entries = []
    for line in git("ls-files", "--stage", "-z").split(b"\0"):
        if not line:
            continue
        meta, name = line.split(b"\t", 1)
        mode, sha, stage = meta.decode().split()
        if stage != "0":
            return ["unmerged index is blocked"]
        entries.append((mode, name.decode(), git("cat-file", "-p", sha) if mode != "160000" else b""))
    required = set(filter(None, git("diff", "--cached", "--name-only", "-z").decode().split("\0")))
    return scan_entries(entries, required)


def push_errors(lines: str) -> list[str]:
    errors = []
    for line in lines.splitlines():
        local_ref, local_sha, remote_ref, remote_sha = line.split()
        if set(local_sha) == {"0"}:
            continue
        if local_ref != "refs/heads/main" or remote_ref != "refs/heads/main" or set(remote_sha) == {"0"}:
            errors.append("only updates to the existing main branch are permitted")
            continue
        # Every outgoing commit, not just the final tree: add-then-delete is a leak.
        if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", remote_sha, local_sha], capture_output=True).returncode:
            errors.append("non-fast-forward publication is blocked")
            continue
        for sha in git("rev-list", "--reverse", f"{remote_sha}..{local_sha}").decode().splitlines():
            errors.extend(scan_entries(tree_entries(sha), changed(sha)))
            metadata = git("show", "-s", "--format=%an%n%ae%n%cn%n%ce%n%B", sha).decode()
            assert_metadata = re.sub(r"\b\d+\+[a-z0-9-]+@users\.noreply\.github\.com\b", "public commit identity", metadata, flags=re.I)
            try:
                assert_public(assert_metadata, "commit metadata")
            except PrivacyError as exc:
                errors.append(str(exc))
    return errors


def review(paths: list[str], sources: list[str], attested: bool) -> None:
    if not attested or not sources:
        raise PrivacyError("review requires --attest-public-source-only and at least one --source public URL")
    for source in sources:
        assert_public(source, "review source")
        if urlsplit(source).scheme != "https" or not urlsplit(source).hostname:
            raise PrivacyError("review sources must be public HTTPS URLs verified by the reviewer")
    receipts = load_receipts()
    pending = {}
    for name in paths:
        path = Path(name).resolve()
        relative = str(path.relative_to(ROOT))
        data = path.read_bytes()
        errors = scan_entries([("100644", relative, data)], set())
        if errors:
            raise PrivacyError("\n".join(errors))
        if not is_content(relative):
            raise PrivacyError("editorial receipts are only for public content files")
        pending[relative] = {"sha256": hashlib.sha256(data).hexdigest(), "attestation": ATTESTATION, "sources": sources}
    receipts.update(pending)
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    RECEIPTS.write_text(json.dumps(receipts, indent=2) + "\n")
    RECEIPTS.chmod(0o600)
    print(f"Recorded exact-byte public-source review for {len(pending)} file(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["audit", "staged", "pre-push", "review", "commit-message"])
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--attest-public-source-only", action="store_true")
    args = parser.parse_args()
    try:
        policy()
        if args.command == "review":
            if not args.paths:
                raise PrivacyError("name the exact files reviewed")
            review(args.paths, args.source, args.attest_public_source_only)
            return
        if args.command == "pre-push":
            errors = push_errors(sys.stdin.read())
        elif args.command == "staged":
            errors = staged_errors()
        elif args.command == "commit-message":
            assert_public(Path(args.paths[0]).read_text(), "commit message")
            errors = []
        else:
            entries = [("100644" if not (ROOT / p).is_symlink() else "120000", p, (ROOT / p).read_bytes()) for p in git("ls-files", "-z").decode().split("\0") if p and (ROOT / p).exists()]
            errors = scan_entries(entries, set())
        if errors:
            raise PrivacyError("\n".join(sorted(set(errors))))
        print("Privacy guard passed.")
    except (PrivacyError, OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(str(exc) if isinstance(exc, PrivacyError) else "privacy verification failed; publishing is blocked", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
