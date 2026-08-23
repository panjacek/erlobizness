# Architecture

How the backend, frontend and tests fit together. Implemented rules:
[`rules.md`](rules.md); official Eurobiznes reference:
[`eurobiznes_rules.md`](eurobiznes_rules.md); CI pipeline: [`ci.md`](ci.md).

## Module map

| module | responsibility |
|--------|----------------|
| `src/erlobiznes/dice.py` | `Dice.roll()` — one random 1–6 pip value |
| `src/erlobiznes/board.py` + `board_layout.json` | `Board` loads the 40-field layout (`pl` section): `__name__`, `type`, `country`, `price`, `rent[]`, `rent_multiplier[]`, chance color |
| `src/erlobiznes/player.py` | `Player`: money/position/properties/in_jail; `walk()` (returns crossings of Start), `attempt_jail_escape()` (skip 2 turns), `pay()`/`receive()` (pay may go negative) |
| `src/erlobiznes/cards.py` | Chance cards as action functions + `CardDeck.draw()`; red and blue decks |
| `src/erlobiznes/lang_pl.py` | `MESSAGES` — Polish log templates used by the engine (backend messages are not i18n-switchable) |
| `src/erlobiznes/game.py` | `ErloGame` engine: `play_turn`, field resolution (rent/buy/tax/chance/jail), trade state (`active_trade`, pending purchase), `get_state()` |
| `src/erlobiznes/web_app.py` | FastAPI routes around one global game instance |
| `src/erlobiznes/static/main.js` | UI: board render, dice/pawn animation, trade modals, log; consumes structured API data only |
| `src/erlobiznes/static/lang/pl.json` | UI strings via `data-i18n` keys (frontend i18n) |

## Request flow: `POST /roll`

1. Frontend disables the roll button, POSTs `/roll`.
2. `web_app.roll()` takes `game.players[current_player_idx]` and calls
   `ErloGame.play_turn()`.
3. `play_turn` rolls two dice in a loop: a double resolves then grants an
   extra roll; the **second consecutive double sends the player to jail**
   without moving that roll. Every physical dice move is appended to
   `last_moves[]` as `{"roll": {"total", "rolls"}, "start", "end"}`.
4. The landing field resolves: rent (×2 full-country for cities, count-based
   railways, dice-sum × multiplier utilities), purchase, tax, chance card,
   jail. Passing Start pays 400 per crossing.
5. Back in `web_app`: `money < 0` → `game_over`; otherwise
   `current_player_idx` advances to the next player.
6. Response shape:

```json
{
  "messages": ["...Polish log lines..."],
  "state": { "players": [...], "board": [...], "game_over": false,
             "active_trade": null, "current_player_idx": 1 },
  "moves": [{"roll": {"total": 5, "rolls": [[2, 3]]}, "start": 0, "end": 5}],
  "rolled_by": 0,
  "roll": {"total": 5, "rolls": [[2, 3]]}
}
```

7. Frontend animates each entry of `moves[]` in order (~900 ms dice shake,
   then 140 ms per field step). It reads positions/totals from the JSON —
   it never parses the human-readable log strings (those are display-only).
8. Purchase decision flow: an unowned, affordable property sets
   `game.pending_purchase` instead of auto-buying. `/roll` refuses while a
   purchase is pending; the client shows buy/decline buttons that POST
   `/purchase/decide` with `{decision: "buy" | "decline"}` — this resolves
   the purchase and advances the turn.

## State ownership

The whole match lives in one module-level global `game = ErloGame()` plus
`current_player_idx` inside `web_app.py`. There is no session handling by
design (hot-seat POC). Documented limitation: **multi-tab** — every open tab
shares the same server-side game; two tabs are two views of one match, not
two matches, and either can act as the current player. Single uvicorn worker
assumed; state is lost on restart (only `/reset` rebuilds it).

## API contract

| endpoint | request | response essentials |
|----------|---------|---------------------|
| `GET /state` | – | players (name, position, money, properties, in_jail), board (40 fields), `game_over`, `active_trade`, `current_player_idx` |
| `POST /roll` | – | `{messages, state, moves[], rolled_by, roll}`; empty moves + current state if game over; refused while a purchase is pending |
| `POST /purchase/decide` | `{decision: "buy"\|"decline"}` | messages + state; resolves `pending_purchase`, advances turn |
| `POST /trade/offer` | `{proposer_idx, target_idx, property_name, price, action: "buy"\|"sell"}` | messages + state (with `active_trade` set); HTTP 400 if proposer ≠ current player; price must be positive int |
| `POST /trade/respond` | `{responder_idx, response: "accept"\|"reject"\|"counter", new_price?}` | messages + state; accept swaps money+property after funds check, counter flips roles and keeps the offer alive on invalid input |
| `POST /reset` | – | fresh game, `current_player_idx = 0` |

Every response carries `current_player_idx` inside `state`; the frontend
treats it as authoritative.

## Testing pyramid

| layer | location | tool | covers / does NOT cover |
|-------|----------|------|-------------------------|
| unit | `tests/test_*.py` | pytest (+pytest-mock) | engine rules with mocked dice rolls, player math, trades, FastAPI routes via TestClient. No browser, no real JS. |
| DOM unit | `tests/main.test.js` | vitest (jsdom) | `main.js` helpers: dice rendering, board validation, marker/ownership classes. No server, no network. |
| e2e | `e2e/ui.spec.js` | Playwright, Chromium only | real app booted via `webServer` (uvicorn), seeded via API calls: board render, roll animation, trade propose→counter→accept, reset. Not multi-browser/mobile; not rules-edge coverage. |
