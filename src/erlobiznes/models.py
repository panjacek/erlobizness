from typing import Literal

from pydantic import BaseModel


class TradeOffer(BaseModel):
    proposer_idx: int
    target_idx: int
    property_name: str
    price: int
    action: Literal["buy", "sell"]


class TradeResponse(BaseModel):
    responder_idx: int
    response: Literal["accept", "reject", "counter"]
    new_price: int | None = None
