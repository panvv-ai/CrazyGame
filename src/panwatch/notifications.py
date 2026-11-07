from __future__ import annotations


def render_alert_message(rule_name: str, quote: dict, language: str) -> dict[str, str]:
    english = language.startswith("en")
    name = quote.get("name") or quote.get("symbol") or ""
    symbol = quote.get("symbol") or ""
    price = quote.get("current_price")
    change = quote.get("change_pct")
    as_of = quote.get("as_of") or ""
    freshness = quote.get("freshness") or ""
    if english:
        title = f"Price alert · {name} ({symbol})"
        lines = [
            f"Rule: {rule_name}",
            f"Current price: {price:.2f}" if price is not None else "Current price: --",
            f"Change: {change:+.2f}%" if change is not None else "Change: --",
            f"Data: {freshness} · {as_of}",
        ]
    else:
        title = f"价格提醒 · {name} ({symbol})"
        lines = [
            f"规则：{rule_name}",
            f"现价：{price:.2f}" if price is not None else "现价：--",
            f"涨跌幅：{change:+.2f}%" if change is not None else "涨跌幅：--",
            f"数据：{freshness} · {as_of}",
        ]
    return {"title": title, "body": "\n".join(lines)}


def build_feishu_payload(title: str, body: str, url: str = "") -> dict:
    elements = [
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": body},
        }
    ]
    if url:
        elements.append(
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "打开盯盘侠"},
                        "url": url,
                        "type": "primary",
                    }
                ],
            }
        )
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "blue",
                "title": {"tag": "plain_text", "content": title},
            },
            "elements": elements,
        },
    }


def build_aliyun_template_params(context: dict) -> dict[str, str]:
    price = context.get("current_price")
    change = context.get("change_pct")
    return {
        "rule": str(context.get("rule") or "价格提醒"),
        "name": str(context.get("name") or context.get("symbol") or ""),
        "price": f"{float(price):.2f}" if price is not None else "--",
        "change": f"{float(change):+.2f}%" if change is not None else "--",
    }

