# Stable PyPI release policy

`release.yml` continues to run Release Please on `main`, then dispatches
`publish.yml` **at the created tag** with the same `tag_name`. A manually
published GitHub Release also works. A manual retry must select the release tag
as the workflow ref, not `main` or another branch.

The publication workflow fails closed unless:

- The event is a published release or an exact tag dispatch, using a stable
  `vMAJOR.MINOR.PATCH` tag and the publishing workflow from that same commit.
- The live tag, including an annotated tag, peels to the workflow commit.
- The exact tag has a published, non-draft, non-prerelease GitHub Release.
- That commit is an ancestor of the current protected `main` branch. Advancing
  main after a release is allowed. Release Please's SHA-valued
  `target_commitish` is supported; that field is not treated as ancestry proof.
- Project metadata, the Release Please manifest, wheel filename/METADATA,
  and sdist filename/PKG-INFO/pyproject all match the expected package/version.
  Exactly one wheel and one sdist are uploaded.

The tests and build check out the validated **commit SHA**, never resolve the tag
again. Publication and GitHub attachment recheck the live tag, release ID, and
protected-main ancestry immediately before use. The publication recheck runs
inside the `pypi` environment job, after any approval wait. Attestations,
Trusted Publishing/OIDC, the `pypi` environment, and existing dependency tests
remain in place; no PyPI password is used. The final job only downloads the
already-validated artifact and publishes it, without checking out/building code.

## Repository settings are a separate deployment requirement

These workflow checks are defense in depth, not a replacement for settings.
Before enabling unattended publication, an administrator should review and apply:

1. Enforced `main` protection and review of publishing workflow/policy changes.
2. A tag ruleset covering `v*` that blocks updates/deletions, and restricts tag
   creation to the intended release automation/maintainers. Verify the chosen
   bypass actors and GitHub token behavior against Release Please before enabling.
3. A `pypi` deployment policy permitting only intended release tags. Keep the
   environment and its PyPI Trusted Publisher binding. Remove its human reviewer
   only after explicit security-change approval and the tag controls are verified.

The exact repository settings are not changed by this PR. A workflow can be
changed by someone who can modify its source; runtime checks do not provide an
independent security boundary against such an actor. Read-only final checks also
cannot atomically prevent a tag/release edit after the check. Enforced immutable
tags and appropriately limited release/workflow permissions remain necessary.

Existing tag-bound runs retain their old workflow and approval gate. Do not move
release tags or rerun old tags expecting the new policy. Finish existing waiting
releases using their normal approved process. These changes apply to future tags
that include this commit. They do not prove PyPI authentication until a real
approved release completes.

## Policy tests

The CI job `Release policy adversarial tests` executes the actual inline GitHub
policy in all three jobs with mocked API responses, and adversarial artifact
fixtures without credentials, a network connection, or any publication:

```sh
node --test .github/scripts/test-release-policy.cjs
python -m unittest discover -s .github/scripts -p 'test_release_*.py' -v
```

Python 3.12 is used for these release-tool tests, independently of the supported
package-runtime matrix. Tests include legitimate dispatch/release events,
annotated tags, advancing main, branch/wrong-ref dispatch, moved/recreated tags or
releases, unpublished/prerelease releases, missing protection/API failures,
ancestry failures, malformed package metadata, and missing/extra artifacts.
