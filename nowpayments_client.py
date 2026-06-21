# -*- coding: utf-8 -*-
"""کلاینت ساده NOWPayments برای ساخت فاکتور و بررسی وضعیت."""

from __future__ import annotations

from typing import Any

import httpx

API_BASE = "https://api.nowpayments.io/v1"

FINISHED_STATUSES = frozenset({"finished", "confirmed", "sent"})


class NOWPaymentsError(Exception):
    pass


class NOWPaymentsClient:
    def __init__(self, api_key: str):
        self._api_key = (api_key or "").strip()

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self._api_key}

    async def create_invoice(
        self,
        *,
        price_amount: float,
        price_currency: str,
        order_id: str,
        order_description: str,
    ) -> dict[str, Any]:
        if not self.configured:
            raise NOWPaymentsError("API key not set")
        payload = {
            "price_amount": round(float(price_amount), 2),
            "price_currency": price_currency.lower(),
            "order_id": str(order_id),
            "order_description": order_description[:300],
        }
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(
                    f"{API_BASE}/invoice",
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.HTTPError as e:
            raise NOWPaymentsError(f"خطا در اتصال به NOWPayments: {e}") from e
        if resp.status_code >= 400:
            raise NOWPaymentsError(resp.text[:500] or f"HTTP {resp.status_code}")
        data = resp.json()
        if not isinstance(data, dict):
            raise NOWPaymentsError("invalid response")
        return data

    async def get_invoice(self, invoice_id: str) -> dict[str, Any]:
        if not self.configured:
            raise NOWPaymentsError("API key not set")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{API_BASE}/invoice/{invoice_id}",
                    headers=self._headers(),
                )
        except httpx.HTTPError as e:
            raise NOWPaymentsError(f"خطا در اتصال به NOWPayments: {e}") from e
        if resp.status_code >= 400:
            raise NOWPaymentsError(resp.text[:500] or f"HTTP {resp.status_code}")
        data = resp.json()
        if not isinstance(data, dict):
            raise NOWPaymentsError("invalid response")
        return data

    @staticmethod
    def invoice_is_paid(data: dict[str, Any]) -> bool:
        status = str(data.get("payment_status") or data.get("status") or "").lower()
        return status in FINISHED_STATUSES
