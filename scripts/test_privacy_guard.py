"""Exercise publication boundaries using synthetic data and isolated Git repos."""
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import privacy_guard as guard


class PrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = (Path(self.temp.name) / "repo").resolve()
        self.root.mkdir()
        shutil.copytree(Path(__file__).parent, self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(Path(__file__).resolve().parents[1] / ".githooks", self.root / ".githooks")
        self.private = Path(self.temp.name) / "private"
        self.private.mkdir()
        (self.private / "identity.json").write_text(json.dumps({"identifiers": ["Private Reader"], "terms": ["secret household plan"], "publication_email": "1+publisher" + "@" + "users.noreply.github.com"}))
        self.env = dict(os.environ, MATTER_PRIVACY_HOME=str(self.private))
        self.patches = [patch.object(guard, "ROOT", self.root), patch.object(guard, "PRIVATE", self.private), patch.object(guard, "IDENTITY", self.private / "identity.json"), patch.object(guard, "RECEIPTS", self.private / "publication-reviews.json")]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Publication Bot")
        self.git("config", "user.email", "1+publisher" + "@" + "users.noreply.github.com")
        self.git("config", "commit.gpgsign", "false")

    def git(self, *args, check=True):
        return subprocess.run(["git", "-C", str(self.root), *args], text=True, capture_output=True, check=check, env=self.env)

    def command(self, *args, input=None):
        return subprocess.run([sys.executable, str(self.root / "scripts" / args[0]), *args[1:]], input=input, text=True, capture_output=True, env=self.env, cwd=self.root)

    def public_page(self, content="<p>A public research summary.</p>"):
        path = self.root / "docs/videos/sample.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_sensitive_text_and_obfuscation(self):
        cases = ["Private Reader has an appointment", "Private <b>Reader</b>", "Private%20Reader", "Private&#32;Reader", "Pri\u200bvate Reader", "reader" + "@" + "example.invalid", "+" + "493012345678", "sk-" + "x" * 30, "https://example.org/a?" + "token=hidden", "https://example.org/a?" + "X-Amz-Signature=hidden", "https://u:password" + "@" + "example.org", "https://" + "localhost/data", "https://getmatter.com/email/abc/", "<script>alert(1)</script>", "<p>my" + " journal</p>", "DE" + "89370400440532013000"]
        for value in cases:
            with self.subTest(value=value[:15]):
                self.assertTrue(guard.findings(value))
        self.assertFalse(guard.findings("https://apnews.com/article/public-ed66f29aa8539941aa8fad311d511cc2"))

    def test_identity_in_code_comments_is_also_blocked(self):
        self.assertTrue(guard.scan_entries([("100644", "scripts/example.py", b"# Private Reader")], set()))

    def test_missing_policy_and_unknown_fields_block(self):
        with self.assertRaises(guard.PrivacyError):
            guard.check_record({"summary_html": "safe", "private_notes": "hidden context"}, {"summary_html"})
        (self.private / "identity.json").unlink()
        with self.assertRaises(guard.PrivacyError):
            guard.assert_public("ordinary public content")

    def test_staged_blob_not_working_copy_and_no_secret_in_diagnostic(self):
        self.public_page("<p>Private Reader</p>")
        self.git("add", "docs")
        self.public_page()  # An unstaged sanitization must not hide the staged leak.
        result = self.command("privacy_guard.py", "staged")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Private Reader", result.stderr)
        self.assertIn("privacy guard", result.stderr)

    def test_receipt_required_and_invalidated_by_edit(self):
        path = self.public_page()
        self.git("add", "docs")
        self.assertTrue(guard.staged_errors())
        guard.review([str(path)], ["https://example.org/research"], True)
        self.assertEqual(guard.staged_errors(), [])
        path.write_text("<p>A different public summary.</p>")
        self.git("add", "docs")
        self.assertTrue(any("stale" in x for x in guard.staged_errors()))

    def test_file_types_state_symlinks_and_json_escapes(self):
        self.assertIsNotNone(guard.path_error("data/daily-news/state.json"))
        self.assertIsNotNone(guard.path_error("docs/secret.pdf"))
        self.assertTrue(guard.scan_entries([("120000", "docs/videos/sample.html", b"target")], set()))
        encoded = json.dumps({"summary_html": "Private Reader"}).replace("P", "\\u0050")
        self.assertTrue(guard.scan_entries([("100644", "data/sample.json", encoded.encode())], set()))

    def test_all_four_publishers_reject_sensitive_input_before_writing(self):
        fixture = Path(__file__).resolve().parents[1] / "data/daily-news/fixtures/2026-09-01.json"
        daily = json.loads(fixture.read_text())
        daily["stories"][0]["summary"] += " Private Reader."
        records = {
            "publish_video.py": {"id": "sample", "title": "Public", "channel": "Public Channel", "url": "https://youtu.be/sample", "summary_html": "<p>Private Reader</p>"},
            "publish_x_digest.py": {"week": "2026-W01", "title": "Public", "summary_html": "<p>Private Reader</p>"},
            "publish_newsletter_digest.py": {"week": "2026-W01", "kind": "tools", "title": "Public", "summary_html": "<p>Private Reader</p>"},
            "publish_daily_news.py": daily,
        }
        for script, record in records.items():
            with self.subTest(script=script):
                source = Path(self.temp.name) / "input.json"
                source.write_text(json.dumps(record))
                result = self.command(script, str(source))
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(list(self.root.glob("docs/**/*.html")))
                self.assertFalse(list(self.root.glob("data/**/*.json")))

    def test_safe_publishers_and_traversal(self):
        records = {
            "publish_video.py": {"id": "sample", "title": "Public", "channel": "Public Channel", "url": "https://youtu.be/sample", "summary_html": "<p>A public source summary.</p>"},
            "publish_x_digest.py": {"week": "2026-W01", "title": "Public", "summary_html": "<p>A public source summary.</p>"},
            "publish_newsletter_digest.py": {"week": "2026-W01", "kind": "tools", "title": "Public", "summary_html": "<p>A public source summary.</p>"},
        }
        for script, record in records.items():
            source = Path(self.temp.name) / "input.json"
            source.write_text(json.dumps(record))
            result = self.command(script, "--page-only", str(source))
            self.assertEqual(result.returncode, 0, result.stderr)
            record["page_id"] = "../../escape"
            source.write_text(json.dumps(record))
            self.assertNotEqual(self.command(script, "--page-only", str(source)).returncode, 0)

    def test_included_html_is_scanned(self):
        self.public_page("<article><h1>Public</h1><p>Private Reader</p></article>")
        record = {"id": "another", "title": "Public", "channel": "Public", "url": "https://youtu.be/another", "summary_from_page": "videos/sample.html"}
        source = Path(self.temp.name) / "input.json"
        source.write_text(json.dumps(record))
        result = self.command("publish_video.py", "--page-only", str(source))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "docs/videos/another.html").exists())

    def test_intermediate_commit_leak_and_metadata_are_blocked(self):
        (self.root / "README.md").write_text("Public source host.\n")
        self.git("add", "README.md")
        self.git("commit", "-m", "Initial public host")
        base = self.git("rev-parse", "HEAD").stdout.strip()
        self.public_page("<p>Private Reader</p>")
        self.git("add", "docs")
        self.git("commit", "-m", "Add page")
        self.git("rm", "docs/videos/sample.html")
        self.git("commit", "-m", "Remove page")
        tip = self.git("rev-parse", "HEAD").stdout.strip()
        errors = guard.push_errors(f"refs/heads/main {tip} refs/heads/main {base}\n")
        self.assertTrue(any("privacy guard" in x for x in errors))
        self.git("config", "user.email", "reader" + "@" + "example.invalid")
        self.git("commit", "--allow-empty", "-m", "Public maintenance")
        tip = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertTrue(any("commit metadata" in x for x in guard.push_errors(f"refs/heads/main {tip} refs/heads/main {base}\n")))

    def test_installed_hooks_block_real_commit(self):
        result = self.command("install_privacy_hooks.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.public_page("<p>Private Reader</p>")
        self.git("add", "docs")
        self.assertNotEqual(self.git("commit", "-m", "Add page", check=False).returncode, 0)
        self.assertNotEqual(self.git("rev-parse", "--verify", "HEAD", check=False).returncode, 0)

    def test_real_push_rejects_intermediate_leak_without_changing_remote(self):
        (self.root / "README.md").write_text("Public host.\n")
        self.git("add", "README.md")
        self.git("commit", "-m", "Initial public host")
        base = self.git("rev-parse", "HEAD").stdout.strip()
        remote = Path(self.temp.name) / "remote.git"
        subprocess.run(["git", "init", "--bare", str(remote)], capture_output=True, check=True)
        self.git("remote", "add", "origin", str(remote))
        self.git("push", "origin", "main")
        self.public_page("<p>Private Reader</p>")
        self.git("add", "docs")
        self.git("commit", "-m", "Add page")
        self.git("rm", "docs/videos/sample.html")
        self.git("commit", "-m", "Remove page")
        self.assertEqual(self.command("install_privacy_hooks.py").returncode, 0)
        result = self.git("push", "origin", "main", check=False)
        self.assertNotEqual(result.returncode, 0)
        published = subprocess.check_output(["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"], text=True).strip()
        self.assertEqual(published, base)


if __name__ == "__main__":
    unittest.main()
