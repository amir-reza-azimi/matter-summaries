# Public-source publication policy

Only summaries of verified public sources belong here. Personalized selection can
happen privately; the published text must not disclose the reader's identity,
projects, preferences, work, relationships, records, or circumstances. Public site
and repository URLs necessarily reveal the GitHub owner. This host provides no
anonymity or access control.

## Before writing or pushing

1. Provision the private identity policy outside Git at
   `~/.local/state/matter-summaries/identity.json`. It contains an `identifiers`
   array, a `publication_email` containing the GitHub noreply address, and an optional `terms` array of private names, handles, organizations,
   projects, and phrases. Never copy the policy into this repository. Missing or
   invalid policy blocks publication. `MATTER_PRIVACY_HOME` can select an isolated
   private directory for tests or another host.
2. Run `python3 scripts/install_privacy_hooks.py` in each checkout. It refuses to
   overwrite existing hooks or a configured hooks directory. It installs
   pre-commit, commit-msg, and pre-push hooks without changing global settings. It sets a generic publication author and the private policy's
   noreply email in this repository's local Git configuration.
3. Draft records outside this checkout. Read the entire record and rendered page,
   including attributes, comments, metadata, URLs, and source lists. Every factual
   assertion must come from a public source. Remove all private application notes,
   even when names have been removed. A newsletter arriving by email is not proof
   that its links or contents are public. Resolve to public publisher/product URLs.
4. Run the appropriate publisher. All four publishers scan complete input records
   and final output before writing. Extra top-level record fields are rejected.
   Manual pages are subject to the same Git gate. Do not publish through an API
   or web editor to evade the checks.
5. After reading each new or changed content file, record its review:

   ```sh
   python3 scripts/privacy_guard.py review docs/videos/VIDEO_ID.html data/VIDEO_ID.json --source https://www.youtube.com/watch?v=VIDEO_ID --attest-public-source-only
   ```

   Use the real public sources you verified. The flag attests to an actual
   editorial review, not just a passing regex scan. Receipts live privately outside
   the repository and bind the exact file bytes to their paths and source URLs.
   Any edit invalidates that file's receipt. Generated feeds and indexes also need
   review. Never bulk-approve uninspected content.
6. Stage only public files, run `python3 scripts/privacy_guard.py staged`, commit,
   and push normally. The complete staged tree is scanned, including unchanged
   files. The pre-push hook scans every outgoing commit, including intermediate
   add-then-delete commits, and checks author emails and commit messages. It
   permits only fast-forward updates to the existing main branch. Do not bypass
   a failed hook. After push, verify public output before saving its URL to Matter.

The guard blocks known identities, common credentials, contact information,
private/signed links, private record markers, unexpected paths, binary files,
symlinks, submodules, and content without a current review receipt. Error messages
contain rule names, never matched secret values. Use a generic publication author
with a GitHub noreply address; never a private or employer email address.

## Private state

Daily-news state now lives at
`~/.local/state/matter-summaries/daily-news-state.json`. Pass it with `--state`.
Its preferences, annotations, email IDs, and reading history must never be staged.
The old in-repository path is ignored and rejected by the file allowlist. Back up
private state through private storage. Other digest state belongs in its private
controller workspace, never here.

## Verification and limits

Run `python3 -m unittest discover -s scripts -p 'test_privacy*.py'` and
`python3 scripts/test_daily_news.py`, then `python3 scripts/privacy_guard.py audit`.
Tests use synthetic identities in isolated repositories. They exercise sensitive
input, rendered output, staged blobs, receipt invalidation, path traversal, missing
policy, and outgoing history.

Pattern checks cannot recognize every sensitive fact or obfuscation. The editorial
review is required for that reason. Local hooks can be bypassed, do not install
themselves in other clones, and do not prevent GitHub web/API edits. A CI check
after push would detect a problem only after the data was public. Stronger
isolation would require a private authoring system and a restricted publishing
identity or a different host. No absolute promise is made for arbitrary sensitive
prose or every future writer.

Removing content from the current tree does not remove it from old commits,
cached pages, clones, forks, or previously ingested Matter articles. History
rewrites and GitHub Support cache removal require a separately coordinated cleanup.
