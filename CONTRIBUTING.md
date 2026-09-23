# Contributing to notrack

Thanks for helping improve the official NoTrack SDK. © 3MH Technologies — https://3mh.pages.dev/ — https://t.me/j49_c

## Ground rules

- **Offline tests only.** The suite runs against `httpx.MockTransport`; never add a test that hits the network.
- **Strict typing.** `mypy --strict` must pass; the package ships `py.typed`.
- **No new dependencies** without prior discussion — the SDK is deliberately `httpx`-only at runtime.
- **No secrets.** Never commit cookies, tokens, or `.env` files.

## Workflow

1. Fork and create a feature branch from `main`.
2. Install dev tooling: `pip install -e ".[dev]"`.
3. Make your change, add tests under `tests/`.
4. Run the full gate locally:

   ```bash
   pytest -q
   ruff check . && ruff format --check .
   mypy
   ```

5. Open a PR with a clear description of the problem and the approach.

## Release checklist (maintainers)

1. Bump `__version__` in `src/notrack/_version.py` (semver).
2. `pytest -q && ruff check . && mypy && python -m build`
3. Tag (`git tag vX.Y.Z && git push --tags`) — CI builds and uploads `dist/`.
4. Publish to PyPI: `twine upload dist/*`

## Reporting issues

Use [GitHub Issues](https://github.com/3MH-Technologies/notrack/issues). Include the SDK version, Python version, and a minimal repro (redact cookies!). Security issues: see [SECURITY.md](SECURITY.md).
