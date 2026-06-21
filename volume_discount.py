"""تخفیف پلکانی بر اساس حجم خرید (گیگ)."""

from __future__ import annotations

import json
import re
from typing import Any


def parse_tiers_from_json(raw: str) -> list[tuple[float, float]]:
    """لیست (حداقل_گیگ, درصد_تخفیف) مرتب‌شده."""
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    tiers: list[tuple[float, float]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            min_gb = float(item.get("min_gb", 0))
            pct = float(item.get("percent", 0))
        except (TypeError, ValueError):
            continue
        if min_gb > 0 and 0 < pct <= 100:
            tiers.append((min_gb, pct))
    tiers.sort(key=lambda x: x[0])
    return tiers


def tiers_to_json(tiers: list[dict[str, float]]) -> str:
    return json.dumps(tiers, ensure_ascii=False)


def parse_admin_discount_text(text: str) -> list[dict[str, float]] | None:
    """
    هر خط: حداقل_گیگ,درصد
    مثال:
    3,5
    5,10
    برای حذف همه: فقط -
    """
    t = (text or "").strip()
    if t == "-":
        return []
    out: list[dict[str, float]] = []
    for line in t.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p for p in re.split(r"[,،\s]+", line) if p]
        if len(parts) < 2:
            return None
        try:
            min_gb = float(parts[0].replace(",", "."))
            pct = float(parts[1].replace(",", "."))
        except ValueError:
            return None
        if min_gb <= 0 or pct <= 0 or pct > 100:
            return None
        out.append({"min_gb": min_gb, "percent": pct})
    out.sort(key=lambda x: float(x["min_gb"]))
    return out


def discount_percent_for_gb(gb: float, tiers: list[tuple[float, float]]) -> float:
    """بیشترین درصد قابل‌اعمال برای این حجم (پلهٔ بالاتر اولویت دارد)."""
    pct = 0.0
    for min_gb, p in tiers:
        if gb >= min_gb:
            pct = p
    return pct


def compute_volume_price(
    gb: float,
    price_per_gb: float,
    tiers: list[tuple[float, float]],
) -> tuple[float, float, float]:
    """(مبلغ نهایی, درصد تخفیف, مبلغ قبل تخفیف)"""
    subtotal = gb * price_per_gb
    pct = discount_percent_for_gb(gb, tiers)
    amount = round(subtotal * (1.0 - pct / 100.0), 2)
    return amount, pct, subtotal


def format_tiers_preview_fa(tiers: list[tuple[float, float]]) -> str:
    if not tiers:
        return "—"
    parts: list[str] = []
    for min_gb, pct in tiers:
        mg = int(min_gb) if min_gb == int(min_gb) else min_gb
        pg = int(pct) if pct == int(pct) else pct
        parts.append(f"از {mg} گیگ → {pg}٪")
    return "؛ ".join(parts)
