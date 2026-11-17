from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import select

from src.crazygame.api.dependencies import get_session
from src.crazygame.domain.groups import shared_group_scope
from src.crazygame.domain.models import (
    AlertRule,
    AppSetting,
    AssetGroup,
    GroupMember,
    Holding,
    Instrument,
    NotifyChannel,
    WatchlistItem,
)

router = APIRouter()
SUPPORTED_MODULES = {"watchlist", "groups", "holdings", "alerts", "llm"}


def _json_row(db, key: str) -> dict:
    row = db.get(AppSetting, key)
    if row is None or not row.value:
        return {}
    try:
        value = json.loads(row.value)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _put_json(db, key: str, value: dict) -> None:
    row = db.get(AppSetting, key)
    serialized = json.dumps(value, ensure_ascii=False)
    if row is None:
        db.add(AppSetting(key=key, value=serialized))
    else:
        row.value = serialized


def _derive_key(password: str, salt: bytes) -> bytes:
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=210_000,
    ).derive(password.encode("utf-8"))


def _encrypt_bundle(bundle: dict, password: str) -> dict:
    salt = os.urandom(16)
    iv = os.urandom(12)
    encrypted = AESGCM(_derive_key(password, salt)).encrypt(
        iv,
        json.dumps(bundle, ensure_ascii=False).encode("utf-8"),
        None,
    )
    return {
        "format": "crazygame-transfer",
        "version": 1,
        "salt": base64.b64encode(salt).decode("ascii"),
        "iv": base64.b64encode(iv).decode("ascii"),
        "data": base64.b64encode(encrypted).decode("ascii"),
    }


def _decrypt_bundle(payload: dict, password: str) -> dict:
    try:
        salt = base64.b64decode(payload["salt"])
        iv = base64.b64decode(payload["iv"])
        encrypted = base64.b64decode(payload["data"])
        clear = AESGCM(_derive_key(password, salt)).decrypt(iv, encrypted, None)
        bundle = json.loads(clear.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(400, "transfer_password_or_package_invalid") from exc
    if (
        not isinstance(bundle, dict)
        or bundle.get("format") != "crazygame-transfer"
        or bundle.get("version") != 1
    ):
        raise HTTPException(400, "unsupported_transfer_bundle")
    return bundle


def _selected_modules(values: list[str]) -> list[str]:
    modules = [value for value in values if value in SUPPORTED_MODULES]
    if not modules:
        raise HTTPException(400, "transfer_module_required")
    return modules


def _instrument_dict(item: Instrument) -> dict:
    return {
        "id": item.id,
        "symbol": item.symbol,
        "name": item.name,
        "market": item.market,
        "asset_type": item.asset_type,
        "currency": item.currency,
        "quote_mode": item.quote_mode,
    }


def _build_bundle(
    request: Request,
    db,
    modules: list[str],
    include_credentials: bool,
) -> dict:
    selected = set(modules)
    instruments = db.scalars(select(Instrument).order_by(Instrument.id)).all()
    watchlist = db.scalars(select(WatchlistItem).order_by(WatchlistItem.id)).all()
    groups = db.scalars(select(AssetGroup).order_by(AssetGroup.id)).all()
    holdings = db.scalars(select(Holding).order_by(Holding.id)).all()
    alerts = db.scalars(select(AlertRule).order_by(AlertRule.id)).all()
    channels = db.scalars(select(NotifyChannel).order_by(NotifyChannel.id)).all()
    data: dict = {"instruments": [_instrument_dict(item) for item in instruments]}
    data["watchlist"] = (
        [
            {
                "id": item.id,
                "instrument_id": item.instrument_id,
                "kind": item.kind,
                "sort_order": item.sort_order,
            }
            for item in watchlist
        ]
        if "watchlist" in selected
        else []
    )
    data["groups"] = (
        [
            {
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "sort_order": item.sort_order,
                "member_ids": [
                    {
                        "instrument_id": member.instrument_id,
                        "weight": member.weight,
                    }
                    for member in item.members
                ],
            }
            for item in groups
        ]
        if "groups" in selected
        else []
    )
    data["holdings"] = (
        [
            {
                "id": item.id,
                "instrument_id": item.instrument_id,
                "quantity": item.quantity,
                "average_cost": item.average_cost,
                "note": item.note,
                "updated_at": item.updated_at.isoformat(),
            }
            for item in holdings
        ]
        if "holdings" in selected
        else []
    )
    data["alerts"] = (
        [
            {
                "id": item.id,
                "instrument_id": item.instrument_id,
                "name": item.name,
                "metric": item.metric,
                "direction": item.direction,
                "threshold": item.threshold,
                "channel_ids": json.loads(item.channel_ids or "[]"),
                "enabled": item.enabled,
                "once_per_day": item.once_per_day,
                "market_hours_only": item.market_hours_only,
                "cooldown_minutes": item.cooldown_minutes,
                "last_triggered_at": (
                    item.last_triggered_at.isoformat()
                    if item.last_triggered_at
                    else None
                ),
            }
            for item in alerts
        ]
        if "alerts" in selected
        else []
    )
    if "alerts" in selected:
        rows = []
        for channel in channels:
            config = {}
            if include_credentials:
                try:
                    config = json.loads(
                        request.app.state.secret_box.decrypt(
                            channel.config_encrypted
                        )
                    )
                except Exception:
                    config = {}
            rows.append(
                {
                    "id": channel.id,
                    "name": channel.name,
                    "type": channel.type,
                    "config": config,
                    "enabled": channel.enabled,
                }
            )
        data["channels"] = rows
    if "llm" in selected:
        ai = _json_row(db, "ai")
        news = _json_row(db, "news")
        if include_credentials:
            for config in (ai, news):
                stored = config.get("api_key")
                if stored:
                    try:
                        config["api_key"] = request.app.state.secret_box.decrypt_nested(
                            stored
                        )[0]
                    except Exception:
                        config["api_key"] = ""
        else:
            ai["api_key"] = ""
            news["api_key"] = ""
        data["settings"] = {"ai": ai, "news": news}
    return {
        "format": "crazygame-transfer",
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "modules": modules,
        "credentials_included": include_credentials,
        "data": data,
    }


@router.post("/export")
def export_transfer(
    request: Request,
    payload: dict,
    db=Depends(get_session),
):
    modules = _selected_modules(list(payload.get("modules") or []))
    include_credentials = bool(payload.get("include_credentials"))
    password = str(payload.get("password") or "")
    if len(password) < 8:
        raise HTTPException(400, "transfer_password_too_short")
    bundle = _build_bundle(request, db, modules, include_credentials)
    outer = _encrypt_bundle(bundle, password)
    return Response(
        json.dumps(outer, ensure_ascii=False).encode("utf-8"),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": 'attachment; filename="CrazyGame.crazygame"'
        },
    )


@router.post("/import")
async def import_transfer(
    request: Request,
    file: UploadFile = File(...),
    password: str = Form(...),
    modules: str = Form("[]"),
    db=Depends(get_session),
):
    try:
        selected = _selected_modules(json.loads(modules))
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, "invalid_transfer_modules") from exc
    try:
        outer = json.loads((await file.read()).decode("utf-8"))
        bundle = _decrypt_bundle(outer, password)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, "invalid_transfer_package") from exc
    selected_set = set(selected)
    imported_instruments = bundle.get("data", {}).get("instruments", [])
    id_map: dict[int, int] = {}
    for row in imported_instruments:
        instrument = db.scalar(
            select(Instrument).where(
                Instrument.symbol == str(row["symbol"]),
                Instrument.market == str(row["market"]),
                Instrument.asset_type == str(row["asset_type"]),
            )
        )
        if instrument is None:
            instrument = Instrument(
                symbol=str(row["symbol"]),
                name=str(row.get("name") or row["symbol"]),
                market=str(row["market"]),
                asset_type=str(row["asset_type"]),
                currency=str(row.get("currency") or "CNY"),
                quote_mode=str(row.get("quote_mode") or "realtime"),
            )
            db.add(instrument)
            db.flush()
        else:
            instrument.name = str(row.get("name") or instrument.name)
        id_map[int(row["id"])] = instrument.id

    data = bundle.get("data", {})
    if "watchlist" in selected_set:
        for row in data.get("watchlist", []):
            instrument_id = id_map.get(int(row["instrument_id"]))
            if not instrument_id:
                continue
            item = db.scalar(
                select(WatchlistItem).where(
                    WatchlistItem.instrument_id == instrument_id,
                    WatchlistItem.kind == str(row["kind"]),
                )
            )
            if item is None:
                item = WatchlistItem(
                    instrument_id=instrument_id,
                    kind=str(row["kind"]),
                    sort_order=int(row.get("sort_order") or 0),
                )
                db.add(item)
            else:
                item.sort_order = int(row.get("sort_order") or item.sort_order)

    if "holdings" in selected_set:
        for row in data.get("holdings", []):
            instrument_id = id_map.get(int(row["instrument_id"]))
            if not instrument_id:
                continue
            holding = db.scalar(
                select(Holding).where(Holding.instrument_id == instrument_id)
            )
            if holding is None:
                holding = Holding(
                    instrument_id=instrument_id,
                    quantity=float(row["quantity"]),
                    average_cost=float(row["average_cost"]),
                    note=str(row.get("note") or ""),
                )
                db.add(holding)
            else:
                holding.quantity = float(row["quantity"])
                holding.average_cost = float(row["average_cost"])
                holding.note = str(row.get("note") or "")

    if "groups" in selected_set:
        for row in data.get("groups", []):
            member_ids = [
                (id_map.get(int(item["instrument_id"])), float(item["weight"]))
                for item in row.get("member_ids", [])
            ]
            members = [
                (instrument_id, weight)
                for instrument_id, weight in member_ids
                if instrument_id
            ]
            if not members:
                continue
            instruments = [
                db.get(Instrument, instrument_id)
                for instrument_id, _weight in members
            ]
            try:
                shared_group_scope(
                    [item for item in instruments if item is not None]
                )
            except ValueError as exc:
                raise HTTPException(422, "group_scope_mismatch") from exc
            group = db.scalar(
                select(AssetGroup).where(AssetGroup.name == str(row["name"]))
            )
            if group is None:
                group = AssetGroup(
                    name=str(row["name"]),
                    description=str(row.get("description") or ""),
                    sort_order=int(row.get("sort_order") or 0),
                )
                db.add(group)
                db.flush()
            group.members.clear()
            db.flush()
            for instrument_id, weight in members:
                group.members.append(
                    GroupMember(
                        instrument_id=instrument_id,
                        weight=weight,
                    )
                )

    if "alerts" in selected_set:
        channel_map: dict[int, int] = {}
        for row in data.get("channels", []):
            if row.get("type") == "local":
                continue
            channel = db.scalar(
                select(NotifyChannel).where(
                    NotifyChannel.name == str(row["name"]),
                    NotifyChannel.type == str(row["type"]),
                )
            )
            encrypted = request.app.state.secret_box.encrypt(
                json.dumps(row.get("config") or {}, ensure_ascii=False)
            )
            if channel is None:
                channel = NotifyChannel(
                    name=str(row["name"]),
                    type=str(row["type"]),
                    config_encrypted=encrypted,
                    enabled=bool(row.get("enabled", True)),
                )
                db.add(channel)
                db.flush()
            else:
                if row.get("config"):
                    channel.config_encrypted = encrypted
                channel.enabled = bool(row.get("enabled", True))
            channel_map[int(row["id"])] = channel.id
        for row in data.get("alerts", []):
            instrument_id = id_map.get(int(row["instrument_id"]))
            if not instrument_id:
                continue
            alert = db.scalar(
                select(AlertRule).where(
                    AlertRule.instrument_id == instrument_id,
                    AlertRule.metric == str(row["metric"]),
                    AlertRule.direction == str(row["direction"]),
                    AlertRule.threshold == float(row["threshold"]),
                )
            )
            if alert is None:
                alert = AlertRule(
                    instrument_id=instrument_id,
                    name=str(row.get("name") or ""),
                    metric=str(row["metric"]),
                    direction=str(row["direction"]),
                    threshold=float(row["threshold"]),
                    channel_ids="[]",
                    enabled=bool(row.get("enabled", True)),
                    once_per_day=bool(row.get("once_per_day", True)),
                    market_hours_only=bool(row.get("market_hours_only", True)),
                    cooldown_minutes=int(row.get("cooldown_minutes") or 30),
                )
                db.add(alert)
            alert.name = str(row.get("name") or alert.name)
            alert.channel_ids = json.dumps(
                [
                    channel_map[channel_id]
                    for channel_id in row.get("channel_ids", [])
                    if channel_id in channel_map
                ]
            )

    if "llm" in selected_set:
        settings = data.get("settings", {})
        for key in ("ai", "news"):
            incoming = settings.get(key)
            if not isinstance(incoming, dict):
                continue
            current = _json_row(db, key)
            api_key = str(incoming.get("api_key") or "")
            if api_key and api_key != current.get("api_key"):
                incoming["api_key"] = request.app.state.secret_box.encrypt(api_key)
            elif not api_key:
                incoming["api_key"] = current.get("api_key", "")
            _put_json(db, key, incoming)

    db.commit()
    return {"ok": True, "modules": selected}
