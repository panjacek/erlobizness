# ErloBiznes

[![CI](https://github.com/panjacek/erlobizness/actions/workflows/ci.yml/badge.svg)](https://github.com/panjacek/erlobizness/actions/workflows/ci.yml)

Eurobiznes-style (Polish Monopoly) board game as a web app. FastAPI backend
owns the full game state; vanilla JS frontend renders board, dice and trades.
Two players hot-seat on one screen.

## Features

- Full 40-field Polish board (`board_layout.json`), property buying, rent,
  full-country rent doubling, railways, utilities (dice × multiplier), tax,
  chance decks, jail (skip-2-turns escape, second double → jail)
- Trading: propose buy/sell offers, accept / reject / counter-offer with
  server-side price validation
- Structured roll API — frontend never parses human-readable messages;
  per-move animation data (`moves[]`) drives dice + pawn movement
- i18n-ready: backend messages in `lang_pl.py`, UI strings via
  `data-i18n` keys in `static/lang/pl.json`

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Node.js (or Docker for JS
targets).

```sh
uv sync                       # backend deps
make up                       # http://localhost:8000
```

## Make targets

Run `make help` for the annotated list. The essentials:

- `make up` - run dev server with auto-reload
- `make test` - all suites (pytest + vitest)
- `make lint` - ruff + biome
- `make format` - auto-format both stacks
- `make test-e2e` - browser E2E via Playwright Docker image (needs `make up` running)

No Node.js is required on the host: JS tooling runs in Docker.

## Browser E2E

`e2e/ui.spec.js` drives a real Chromium against the running app:

1. board renders 40 fields + 2 markers
2. roll → dice visible, log entry, button re-enabled
3. trade propose → respond modal → accept → success logged
4. reset clears state

```sh
make up          # terminal 1
make test-e2e    # terminal 2 (Docker, no local Node/browser needed)
```

CI runs the same suite natively on ubuntu-latest.

## Development

```sh
uv run pytest                 # backend suite
uv run pytest --cov --cov-report=term-missing   # backend coverage
npx vitest run                # frontend suite (jsdom)
uv run ruff check .           # python lint
npx @biomejs/biome lint .     # js lint
```

Module map, request flow and API contract: [`docs/architecture.md`](docs/architecture.md).

Architecture notes and implemented game rules: [`docs/rules.md`](docs/rules.md),
CI pipeline: [`docs/ci.md`](docs/ci.md).
Future work: [`docs/roadmap.md`](docs/roadmap.md).

## License

Unlicense — see [LICENSE](LICENSE).
