from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .game import ErloGame
from .lang_pl import MESSAGES
from .models import TradeOffer, TradeResponse, AuctionBid, AuctionPass, MortgageRequest
import json
import os
import tempfile


SAVE_PATH = os.environ.get("ERLO_SAVE_PATH") or os.path.join(
    tempfile.gettempdir(), "erlobiznes_save.json"
)


class PurchaseDecision(BaseModel):
    decision: Literal["buy", "decline"]


class DebugState(BaseModel):
    state: dict


def create_app() -> FastAPI:
    application = FastAPI()

    application.state.game = ErloGame()
    try:
        if os.path.exists(SAVE_PATH):
            with open(SAVE_PATH) as f:
                application.state.game.restore(json.load(f))
    except Exception:
        application.state.game = ErloGame()

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)

    templates = Jinja2Templates(directory=static_dir)
    application.mount("/static", StaticFiles(directory=static_dir), name="static")

    def persist():
        try:
            with open(SAVE_PATH, "w") as f:
                json.dump(application.state.game.save(), f)
        except Exception:
            pass

    def advance_turn():
        g = application.state.game
        g.current_player_idx = (g.current_player_idx + 1) % len(g.players)

    @application.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        from fastapi.responses import Response

        return Response(content=b"", media_type="image/x-icon")

    @application.get("/", response_class=HTMLResponse)
    async def read_root(request: Request):
        return templates.TemplateResponse(request, "index.html")

    @application.get("/state")
    async def get_state():
        return application.state.game.get_state()

    @application.post("/roll")
    async def roll():
        g = application.state.game
        if g.game_over:
            persist()
            return {
                "messages": [],
                "state": g.get_state(),
                "moves": [],
                "rolled_by": g.current_player_idx,
                "roll": None,
            }

        if g.pending_purchase is not None:
            p = g.players[g.pending_purchase["player_idx"]]
            return {
                "messages": [MESSAGES["purchase_required"].format(name=p.name)],
                "state": g.get_state(),
                "moves": [],
                "rolled_by": g.current_player_idx,
                "roll": None,
            }

        if g.pending_payment is not None:
            p = g.players[g.pending_payment["player_idx"]]
            return {
                "messages": [MESSAGES["payment_required"].format(name=p.name)],
                "state": g.get_state(),
                "moves": [],
                "rolled_by": g.current_player_idx,
                "roll": None,
            }

        if g.active_auction is not None:
            return {
                "messages": [MESSAGES["auction_in_progress"]],
                "state": g.get_state(),
                "moves": [],
                "rolled_by": g.current_player_idx,
                "roll": None,
            }

        rolled_by = g.current_player_idx
        player = g.players[g.current_player_idx]
        messages = g.play_turn(player)

        if player.money < 0:
            g.game_over = True

        if not g.game_over and g.pending_purchase is None and g.pending_payment is None:
            advance_turn()

        persist()
        return {
            "messages": messages,
            "state": g.get_state(),
            "moves": g.last_moves,
            "rolled_by": rolled_by,
            "roll": g.last_roll,
        }

    @application.post("/purchase/decide")
    async def purchase_decide(decision: PurchaseDecision):
        g = application.state.game
        had_pending = g.pending_purchase is not None
        messages = g.decide_purchase(decision.decision == "buy")
        if (
            had_pending
            and g.pending_purchase is None
            and g.active_auction is None
            and not g.game_over
        ):
            advance_turn()
        elif g.active_auction is not None:
            g.current_player_idx = g.active_auction["auction_turn"]
        persist()
        return {"messages": messages, "state": g.get_state()}

    @application.post("/trade/offer")
    async def trade_offer(offer: TradeOffer):
        g = application.state.game
        if offer.proposer_idx != g.current_player_idx:
            raise HTTPException(
                status_code=400, detail="Only current player can propose trade"
            )
        messages = g.propose_trade(
            offer.proposer_idx,
            offer.target_idx,
            offer.property_name,
            offer.price,
            offer.action,
        )
        persist()
        return {"messages": messages, "state": g.get_state()}

    @application.post("/trade/respond")
    async def trade_respond(resp: TradeResponse):
        g = application.state.game
        messages = g.respond_trade(resp.responder_idx, resp.response, resp.new_price)
        persist()
        return {"messages": messages, "state": g.get_state()}

    @application.post("/auction/bid")
    async def auction_bid(bid: AuctionBid):
        g = application.state.game
        messages = g.place_bid(bid.player_idx, bid.amount)
        if g.active_auction is not None:
            g.current_player_idx = g.active_auction["auction_turn"]
        persist()
        return {"messages": messages, "state": g.get_state()}

    @application.post("/auction/pass")
    async def auction_pass(pass_req: AuctionPass):
        g = application.state.game
        original_player = (
            g.active_auction["original_player"] if g.active_auction else None
        )
        messages = g.pass_bid(pass_req.player_idx)
        if g.active_auction is not None:
            g.current_player_idx = g.active_auction["auction_turn"]
        else:
            # Auction ended: turn goes to player after the original decliner
            g.current_player_idx = (original_player + 1) % len(g.players)
        persist()
        return {"messages": messages, "state": g.get_state()}

    @application.post("/mortgage")
    async def mortgage(req: MortgageRequest):
        g = application.state.game
        if g.game_over:
            persist()
            return {"messages": [], "state": g.get_state()}
        messages = g.handle_mortgage(req.player_idx, req.property_id)
        persist()
        return {"messages": messages, "state": g.get_state()}

    @application.post("/unmortgage")
    async def unmortgage(req: MortgageRequest):
        g = application.state.game
        if g.game_over:
            persist()
            return {"messages": [], "state": g.get_state()}
        messages = g.handle_unmortgage(req.player_idx, req.property_id)
        persist()
        return {"messages": messages, "state": g.get_state()}

    @application.post("/purchase/try")
    async def purchase_try():
        g = application.state.game
        messages = g.try_buy_after_mortgage()
        if g.pending_purchase is None and not g.game_over:
            advance_turn()
        persist()
        return {"messages": messages, "state": g.get_state()}

    @application.post("/purchase/auction")
    async def purchase_auction():
        g = application.state.game
        messages = g.start_auction_from_pending()
        if g.active_auction is not None:
            g.current_player_idx = g.active_auction["auction_turn"]
        else:
            advance_turn()
        persist()
        return {"messages": messages, "state": g.get_state()}

    @application.post("/payment/resolve")
    async def payment_resolve():
        g = application.state.game
        messages = g.resolve_pending_payment()
        if g.pending_payment is None and not g.game_over:
            advance_turn()
        persist()
        return {"messages": messages, "state": g.get_state()}

    @application.post("/reset")
    async def reset():
        application.state.game = ErloGame()
        if os.path.exists(SAVE_PATH):
            os.remove(SAVE_PATH)
        return {"message": "Game reset", "state": application.state.game.get_state()}

    @application.post("/debug/state")
    async def debug_state(payload: DebugState):
        if os.environ.get("ERLO_ALLOW_INJECTION") != "1":
            raise HTTPException(status_code=403, detail="State injection disabled")
        new_game = ErloGame()
        new_game.restore(payload.state)
        application.state.game = new_game
        return {
            "message": "state injected",
            "state": application.state.game.get_state(),
        }

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
