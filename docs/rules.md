# Implemented rules

Scope: which Eurobiznes rules the engine implements, and where. Official
rules reference (Polish, original source): [`eurobiznes_rules.md`](eurobiznes_rules.md).

## Turn flow

`ErloGame.play_turn` (`src/erlobiznes/game.py`):

1. Player in jail → escape attempt first (see [Jail](#jail)). On failure the
   turn ends; on release the roll happens normally.
2. Roll two dice, move forward, resolve the landing field.
3. Doubles grant an extra roll immediately after resolving. **Second
   consecutive double → jail** (no move for that roll).
4. Landing on jail (field or chance card) always ends the turn.
5. Passing or landing on Start pays 400 per crossing (not when going to
   jail — TODO, see gaps).

## Fields

| type | effect |
|------|--------|
| `city` | buy at `price`, or pay `rent[0]`; **×2 if owner holds every city of that country** |
| `railway` | rent by owner's railway count: `[50, 100, 200, 400]` |
| `utility` | rent = dice sum × multiplier: 8× (one utility) / 20× (both) |
| `tax` | pay fixed cost |
| `chance` | draw red/blue card, apply effect |
| `go_to_jail` | go to jail (position 10) |
| `start` / `parking` | no-op |

## Jail

- Entering: `go_to_jail` field, "Go to Jail" chance card, **second
  consecutive double**. Position set to 10, escape counter reset.
- Escape: skip-based — two skipped turns (`1/2`, `2/2`), released on the
  third turn, then rolls normally. Matches "czekasz 2 kolejki, opuszczasz
  2 rzuty".
- Nobody else is affected by a player going to jail.
- Visiting the jail field (just passing through) has no consequences.

## Trading

- Proposer must be the current player (`web_app.py` enforces).
- Offers: `{proposer, target, property, price, action=buy|sell}` from the
  proposer's perspective. Price must be a positive int.
- Target responds: accept (money + property swap, funds pre-checked),
  reject, or counter with a new positive price (roles flip).
- Invalid prices are rejected server-side; the original offer survives a
  failed counter.

## Auction

When a player declines to buy an unowned field (or cannot afford it),
a banker auction starts at half price (`game.py:decide_purchase`).

- **Starting price**: `price // 2` (integer division).
- **Turn order**: auction starts with the other player; all players
  (including decliner) may bid.
- **Bidding**: each bid must exceed the current bid; funds checked at bid
  time. Pass count resets on each bid.
- **Passing**: consecutive passes; when `pass_count >= len(players) - 1`:
  - If bids exist: highest bidder pays bank, gets property.
  - If no bids: field stays unowned.
- **Turn blocks**: auction open → `/roll` refused (same as `pending_purchase`).
- **2-player simplification**: one pass ends the auction immediately.

## Money

- `Player.pay` deducts unconditionally and may go negative; bankruptcy =
  `money < 0` detected after the turn → game over. Buyers are pre-checked
  before purchases/trades, so only rent/tax/cards can push below zero.

## API shape

- `/state` and every POST response carry the authoritative
  `current_player_idx` inside `state`.
- `/roll` additionally returns `moves[]`
  (`{"roll": {"total", "rolls"}, "start", "end"}` per dice move) and
  `rolled_by` — this drives frontend animation; log strings are never parsed.
  Chance-card teleports (move-to-start, go-to-jail card) are not part of
   `moves[]`; the pawn jumps at final render.
- Game state persists across server restarts via a JSON save file (path:
  `ERLO_SAVE_PATH` env, default system tempdir); `/reset` clears it.
  `POST /debug/state` allows full-state injection for E2E seeding but only
  when `ERLO_ALLOW_INJECTION=1` (403 otherwise).

## Gaps vs official rules (not implemented)

Honest list of Eurobiznes rules missing from this POC:

- **Building** (houses/hotels), proportional-build rule, hotel upgrade.
- **Mortgage / zastaw hipoteczny** and selling buildings back to bank.
- **Rent collection is automatic** — official rule requires the owner to
  claim rent before the next player rolls.
- ~~Passing Start while heading to jail should not pay 400 (currently does).~~ ✅ Fixed 2026-09-05
- Win condition: game ends on bankruptcy only; no timed-end money count.
