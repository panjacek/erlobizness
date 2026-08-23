from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .game import ErloGame
from .lang_pl import MESSAGES
from .models import TradeOffer, TradeResponse
import json
import os
import tempfile


app = FastAPI()

SAVE_PATH = os.environ.get("ERLO_SAVE_PATH") or os.path.join(
    tempfile.gettempdir(), "erlobiznes_save.json"
)

# Global game instance for simplicity as requested
game = ErloGame()
current_player_idx = 0

# Restore the previous session on startup; a corrupt or unreadable save
# falls back to a fresh game instead of crashing startup.
try:
    if os.path.exists(SAVE_PATH):
        with open(SAVE_PATH) as f:
            game.restore(json.load(f))
except Exception:
    game = ErloGame()  # corrupt save -> fresh game


class PurchaseDecision(BaseModel):
    decision: Literal["buy", "decline"]


class DebugState(BaseModel):
    state: dict


def persist():
    # Persistence is best-effort: a failed disk write must never break a
    # game request, so errors are swallowed and the game continues.
    try:
        with open(SAVE_PATH, "w") as f:
            json.dump(game.save(), f)
    except Exception:
        pass


def advance_turn():
    global current_player_idx
    current_player_idx = (current_player_idx + 1) % len(game.players)


# Get absolute path to static directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

templates = Jinja2Templates(directory=static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import Response

    return Response(content=b"", media_type="image/x-icon")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/state")
async def get_state():
    state = game.get_state()
    state["current_player_idx"] = current_player_idx
    return state


@app.post("/roll")
async def roll():
    global current_player_idx
    if game.game_over:
        state = game.get_state()
        state["current_player_idx"] = current_player_idx
        persist()
        return {
            "messages": [],
            "state": state,
            "moves": [],
            "rolled_by": current_player_idx,
            "roll": None,
        }

    # A pending buy decision blocks rolling until it is resolved
    if game.pending_purchase is not None:
        p = game.players[game.pending_purchase["player_idx"]]
        state = game.get_state()
        state["current_player_idx"] = current_player_idx
        return {
            "messages": [MESSAGES["purchase_required"].format(name=p.name)],
            "state": state,
            "moves": [],
            "rolled_by": current_player_idx,
            "roll": None,
        }

    rolled_by = current_player_idx
    player = game.players[current_player_idx]
    messages = game.play_turn(player)

    if player.money < 0:
        game.game_over = True

    # Pending purchase pauses the turn: same player must decide first
    if not game.game_over and game.pending_purchase is None:
        advance_turn()

    # current_player_idx inside state is authoritative everywhere
    state = game.get_state()
    state["current_player_idx"] = current_player_idx
    persist()

    return {
        "messages": messages,
        "state": state,
        "moves": game.last_moves,
        "rolled_by": rolled_by,
        "roll": game.last_roll,
    }


@app.post("/purchase/decide")
async def purchase_decide(decision: PurchaseDecision):
    had_pending = game.pending_purchase is not None
    messages = game.decide_purchase(decision.decision == "buy")
    if had_pending and game.pending_purchase is None and not game.game_over:
        advance_turn()
    state = game.get_state()
    state["current_player_idx"] = current_player_idx
    persist()
    return {"messages": messages, "state": state}


@app.post("/trade/offer")
async def trade_offer(offer: TradeOffer):
    if offer.proposer_idx != current_player_idx:
        raise HTTPException(
            status_code=400, detail="Only current player can propose trade"
        )
    messages = game.propose_trade(
        offer.proposer_idx,
        offer.target_idx,
        offer.property_name,
        offer.price,
        offer.action,
    )
    state = game.get_state()
    state["current_player_idx"] = current_player_idx
    persist()
    return {"messages": messages, "state": state}


@app.post("/trade/respond")
async def trade_respond(resp: TradeResponse):
    messages = game.respond_trade(resp.responder_idx, resp.response, resp.new_price)
    state = game.get_state()
    state["current_player_idx"] = current_player_idx
    persist()
    return {"messages": messages, "state": state}


@app.post("/reset")
async def reset():
    global game, current_player_idx
    game = ErloGame()
    current_player_idx = 0
    if os.path.exists(SAVE_PATH):
        os.remove(SAVE_PATH)
    return {"message": "Game reset", "state": game.get_state()}


@app.post("/debug/state")
async def debug_state(payload: DebugState):
    if os.environ.get("ERLO_ALLOW_INJECTION") != "1":
        raise HTTPException(status_code=403, detail="State injection disabled")
    global game, current_player_idx
    new_game = ErloGame()
    new_game.restore(payload.state)
    game = new_game
    current_player_idx = int(payload.state.get("current_player_idx", 0))
    return {"message": "state injected", "state": game.get_state()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
