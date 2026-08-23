# CI pipeline

GitHub Actions: `.github/workflows/ci.yml`.

## Triggers

- push to `main`
- pull_request targeting `main`
- manual (`workflow_dispatch`)

Concurrent runs for the same ref are cancelled.

## Jobs

Lint + unit run independently; the browser suite gates on them:

| job | tooling | command |
|-----|---------|---------|
| python / lint | uv + ruff | `ruff check .` + `ruff format --check .` |
| python / unit tests | uv + pytest + coverage | `make coverage` (uploads `coverage.xml` artifact) |
| js / lint | node 24 + biome | `npx @biomejs/biome lint .` |
| js / unit tests | node 24 + vitest (jsdom) | `npx vitest run` |
| e2e / browser tests | uv + node 24 + Playwright Chromium | `npx playwright test` |

The e2e job needs both stacks: it checks out, syncs python deps, installs
Chromium (`--with-deps`) and runs the suite — the playwright `webServer`
config boots uvicorn itself. Locally the same suite runs via Docker against
an already-running server (`make up && make test-e2e`); inside the
Playwright container there is no Python, so `E2E_IN_DOCKER=1` disables the
auto-boot.

Python env: `uv sync` (runtime deps include dev tools in `[dependency-groups]`).
JS deps: plain `npm install` against the committed `package-lock.json`,
npm cache enabled via `actions/setup-node`.

## Local reproduction

```sh
make lint          # ruff + biome (biome via Docker)
make test          # pytest + vitest (vitest via Docker)
```

Or without Docker: `uv run pytest`, `uv run ruff check .`, `npx vitest run`,
`npx @biomejs/biome lint .`

## Badge

README badge points at this workflow; it renders after the first successful
run on `main`.
