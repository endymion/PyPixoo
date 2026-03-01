# Releasing

Releases are automated with [python-semantic-release](https://python-semantic-release.readthedocs.io/). When CI passes on `main` and there are conventional commits since the last tag, a new version is created, tagged, and published to PyPI via **trusted publishing** (no API token in GitHub).

## Triggering a release

- Push to `main` with at least one **conventional commit** since the last tag (e.g. `feat: add X`, `fix: Y`, `chore: Z`).
- CI runs → **release** job runs semantic-release → if a new version is determined, it commits the version bump, tags, pushes, and creates a GitHub release → **deploy** job uploads `dist/` to PyPI using trusted publishing (OIDC).

## Trusted publisher

PyPI is configured to trust the GitHub Actions workflow: repository **endymion/PyPixoo**, workflow **ci.yml**. No `PYPI_API_TOKEN` secret is required.
