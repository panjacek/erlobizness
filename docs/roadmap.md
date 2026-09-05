# Roadmap

Honest TODO list for future work. Implemented-rule deviations live in
[`rules.md`](rules.md) → "Gaps"; this file is the plan-of-record for new
features and refactors.

## Big rocks

### 1. Game sessions / multi-tab support (deferred - largest)

Single global `ErloGame` + `current_player_idx` module globals in
`web_app.py`: every visitor shares one match, two tabs race each other.

- `POST /games` creates session, returns id + join token
- all routes take game id; state per session (dict of games or SQLite)
- frontend stores id in localStorage/URL
- unlocks: more than 2 players, remote play, spectator mode

## Gameplay features (missing vs official rules)

See [`eurobiznes_rules.md`](eurobiznes_rules.md) for the source rules.

- [x] **Auction** when player declines to buy (banker auctions at half price)
- [ ] **Building**: houses (max 4/city), hotels, proportional-build rule,
      max 3 houses per round; needs UI + ownership model extension
- [ ] **Mortgage** (zastaw): borrow from bank, redeem +10% interest;
      bankruptcy flow should force selling buildings/mortgages first
- [ ] **Rent claiming**: owner must demand rent before next roll (currently
      automatic); changes turn-flow API
- [ ] **Chance decks full content**: 2 x 16 cards (currently 5 red + 3 blue
      stubs)
- [ ] **Start reward exception**: no 400$ when heading straight to jail
- [ ] **Win condition**: timed game end -> cash + property value count
      (currently only bankruptcy ends the game)

## Smaller items

- [ ] Animate chance-card teleports via `moves[]` (pawn currently jumps)
- [ ] README screenshot (`make screenshot` target idea: Playwright Docker
      one-liner against running server)
- [ ] Mobile layout pass for board/dice panels
- [ ] i18n: single source of truth instead of `lang_pl.py` +
      `static/lang/pl.json` split

## Done (for context)

Buy-decision phase, persistence, coverage in CI, browser E2E suite,
game-over/winner screen, structured `moves[]` animation API, second-double
jail rule per official rules.
