"""بسته‌های از پیش‌تعریف‌شده برای فروش."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

_FIELD_ALIASES: dict[str, str] = {
    "اسم بسته": "title",
    "نام بسته": "title",
    "name": "title",
    "title": "title",
    "حجم": "gb",
    "گیگ": "gb",
    "gb": "gb",
    "volume": "gb",
    "قیمت": "price",
    "price": "price",
    "مبلغ": "price",
    "روز": "days",
    "days": "days",
    "day": "days",
    "مدت": "days",
}


@dataclass(frozen=True)
class BuyPackage:
    gb: float
    title: str
    fixed_price: float
    days: int


def _norm_key(raw: str) -> str:
    k = raw.strip().lower().replace("\u200c", "")
    return _FIELD_ALIASES.get(k, k)


def _parse_num(s: str) -> float:
    return float(s.replace(",", "").replace("٬", "").replace(" ", "").replace("،", "."))


def parse_packages_from_json(raw: str) -> list[BuyPackage]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[BuyPackage] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            gb = float(item.get("gb", 0))
            price = float(item.get("fixed_price") or item.get("price") or 0)
            days = int(float(item.get("days", 30)))
        except (TypeError, ValueError):
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        if gb <= 0 or price <= 0 or not title:
            continue
        if days < 0:
            days = 0
        out.append(
            BuyPackage(
                gb=gb,
                title=title,
                fixed_price=price,
                days=days,
            )
        )
    return out


def packages_to_json(packages: list[dict[str, Any]]) -> str:
    return json.dumps(packages, ensure_ascii=False)


def _parse_one_block(block: str) -> dict[str, Any] | None:
    fields: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([^:：]+)\s*[:：]\s*(.+)$", line)
        if not m:
            return None
        key = _norm_key(m.group(1))
        fields[key] = m.group(2).strip()
    if "title" not in fields or "gb" not in fields or "price" not in fields:
        return None
    try:
        gb = _parse_num(fields["gb"])
        price = _parse_num(fields["price"])
        days_raw = fields.get("days", "30")
        days = int(_parse_num(days_raw))
    except (ValueError, TypeError):
        return None
    if gb < 0.1 or gb > 5000 or price <= 0:
        return None
    if days < 0:
        days = 0
    title = fields["title"].strip()
    if not title:
        return None
    entry: dict[str, Any] = {
        "title": title,
        "gb": gb if gb != int(gb) else int(gb),
        "fixed_price": int(price) if price == int(price) else price,
        "days": days,
    }
    return entry


def parse_admin_packages_text(text: str) -> list[dict[str, Any]] | None:
    """
    هر بسته در یک بلوک (با خط خالی جدا شود):

    اسم بسته: بسته ۱۰ گیگی
    حجم: 10
    قیمت: 1000000
    روز: 30

    حذف همه: -
    """
    t = (text or "").strip()
    if t == "-":
        return []
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", t) if b.strip()]
    if not blocks:
        blocks = [t]
    out: list[dict[str, Any]] = []
    for block in blocks:
        parsed = _parse_one_block(block)
        if parsed is None:
            return None
        out.append(parsed)
    return out


def format_package_block_fa(pkg: BuyPackage) -> str:
    gb_s = int(pkg.gb) if pkg.gb == int(pkg.gb) else pkg.gb
    pr = int(pkg.fixed_price) if pkg.fixed_price == int(pkg.fixed_price) else pkg.fixed_price
    return (
        f"اسم بسته: {pkg.title}\n"
        f"حجم: {gb_s}\n"
        f"قیمت: {pr}\n"
        f"روز: {pkg.days}"
    )


def format_packages_preview_fa(packages: list[BuyPackage]) -> str:
    if not packages:
        return "—"
    parts: list[str] = []
    for p in packages:
        gb_s = int(p.gb) if p.gb == int(p.gb) else p.gb
        pr = int(p.fixed_price) if p.fixed_price == int(p.fixed_price) else p.fixed_price
        day_s = "نامحدود" if p.days <= 0 else f"{p.days} روز"
        parts.append(f"{p.title} — {gb_s}G — {pr:,} ت — {day_s}".replace(",", "٬"))
    return "؛ ".join(parts)


def format_packages_admin_current(packages: list[BuyPackage]) -> str:
    if not packages:
        return "—"
    return "\n\n".join(format_package_block_fa(p) for p in packages)
