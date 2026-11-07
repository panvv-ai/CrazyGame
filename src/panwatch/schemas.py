from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

ASSET_TYPES = {"stock", "listed_etf", "open_end_fund"}
MARKETS = {"CN", "HK", "US", "FUND"}


class WatchlistCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=160)
    market: str
    asset_type: str = "stock"
    kind: str = "stock"

    @model_validator(mode="after")
    def validate_values(self):
        if self.market not in MARKETS:
            raise ValueError("unsupported market")
        if self.asset_type not in ASSET_TYPES:
            raise ValueError("unsupported asset type")
        if self.kind not in {"stock", "fund"}:
            raise ValueError("watchlist kind must be stock or fund")
        return self


class GroupMemberPayload(BaseModel):
    instrument_id: int
    weight: float = Field(gt=0)


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    members: list[GroupMemberPayload] = Field(min_length=1)

