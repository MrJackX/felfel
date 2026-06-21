from __future__ import annotations

import datetime as dt
import json
from typing import Any
from urllib.parse import quote

import httpx


def subscription_url_with_base(base_url: str, subscription_url: str | None) -> str:
    if not subscription_url:
        return ""
    u = str(subscription_url).strip()
    if not u:
        return ""
    low = u.lower()
    if low.startswith("http://") or low.startswith("https://"):
        return u
    if u.startswith("//"):
        return "https:" + u
    base = base_url.rstrip("/")
    path = u if u.startswith("/") else "/" + u
    return base + path


class PasarGuardAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body

    def __str__(self) -> str:
        base = self.args[0] if self.args else ""
        if self.body:
            detail = _api_error_detail(self.body)
            if detail and detail not in base:
                return f"{base} — {detail}"
        return base


def _api_error_detail(body: str) -> str:
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            detail = data.get("detail")
            if isinstance(detail, str):
                return detail
    except (json.JSONDecodeError, TypeError):
        pass
    text = (body or "").strip()
    return text[:300] if text else ""


class PasarGuardClient:
    """Async client for PasarGuard Panel REST API (https://github.com/PasarGuard/panel)."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        verify_ssl: bool = True,
        timeout: float = 90.0,
    ):
        self._base = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._timeout = timeout
        self._token: str | None = None
        self._client = self._new_http_client()

    def _new_http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base,
            verify=self._verify_ssl,
            timeout=httpx.Timeout(self._timeout),
        )

    def absolutize_subscription_url(self, data: dict[str, Any]) -> None:
        raw = data.get("subscription_url")
        if raw:
            data["subscription_url"] = subscription_url_with_base(self._base, str(raw))

    @property
    def base_url(self) -> str:
        return self._base

    async def aclose(self) -> None:
        await self._client.aclose()

    async def reconfigure(self, base_url: str, username: str, password: str) -> None:
        base = base_url.rstrip("/")
        if base == self._base and username == self._username and password == self._password:
            return
        await self._client.aclose()
        self._base = base
        self._username = username
        self._password = password
        self._token = None
        self._client = self._new_http_client()

    async def login(self) -> None:
        try:
            r = await self._client.post(
                "/api/admin/token",
                data={"username": self._username, "password": self._password},
            )
        except httpx.HTTPError as e:
            raise PasarGuardAPIError(f"اتصال به پنل ناموفق بود: {e}") from e
        if r.status_code >= 400:
            raise PasarGuardAPIError(
                "ورود به پنل ناموفق بود.",
                status_code=r.status_code,
                body=r.text,
            )
        data = r.json()
        self._token = str(data["access_token"])

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}))
        last: httpx.Response | None = None
        for _ in range(2):
            if not self._token:
                await self.login()
            headers["Authorization"] = f"Bearer {self._token}"
            try:
                last = await self._client.request(method, path, headers=headers, **kwargs)
            except httpx.HTTPError as e:
                raise PasarGuardAPIError(f"خطا در ارتباط با پنل: {e}") from e
            if last.status_code != 401:
                return last
            self._token = None
        assert last is not None
        return last

    async def get_me(self) -> dict[str, Any]:
        r = await self._request("GET", "/api/admin")
        if r.status_code >= 400:
            raise PasarGuardAPIError("دریافت اطلاعات ادمین ناموفق بود.", status_code=r.status_code, body=r.text)
        return r.json()

    async def list_groups_simple(self) -> dict[str, Any]:
        r = await self._request("GET", "/api/groups/simple")
        if r.status_code >= 400:
            raise PasarGuardAPIError("لیست گروه‌ها ناموفق بود.", status_code=r.status_code, body=r.text)
        return r.json()

    def _user_path(self, username: str) -> str:
        return f"/api/user/{quote(username, safe='')}"

    async def get_user(self, username: str) -> dict[str, Any]:
        r = await self._request("GET", self._user_path(username))
        if r.status_code == 404:
            raise PasarGuardAPIError("کاربر پیدا نشد.", status_code=404, body=r.text)
        if r.status_code >= 400:
            raise PasarGuardAPIError("دریافت کاربر ناموفق بود.", status_code=r.status_code, body=r.text)
        data = r.json()
        if isinstance(data, dict):
            self.absolutize_subscription_url(data)
        return data

    async def create_user(
        self,
        *,
        username: str,
        days: int | None,
        data_limit_bytes: int,
        group_ids: list[int],
        note: str | None = None,
    ) -> dict[str, Any]:
        if days is None or days <= 0:
            expire: int | str = 0
        else:
            until = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=int(days))
            expire = until.replace(microsecond=0).isoformat().replace("+00:00", "Z")

        body: dict[str, Any] = {
            "username": username,
            "status": "active",
            "expire": expire,
            "data_limit": int(data_limit_bytes),
            "group_ids": list(group_ids),
        }
        if note:
            body["note"] = note

        r = await self._request("POST", "/api/user", json=body)
        if r.status_code == 409:
            raise PasarGuardAPIError("این نام کاربری از قبل وجود دارد.", status_code=409, body=r.text)
        if r.status_code >= 400:
            raise PasarGuardAPIError("ساخت کاربر ناموفق بود.", status_code=r.status_code, body=r.text)
        data = r.json()
        if isinstance(data, dict):
            self.absolutize_subscription_url(data)
        return data

    async def modify_user(self, username: str, patch: dict[str, Any]) -> dict[str, Any]:
        r = await self._request("PUT", self._user_path(username), json=patch)
        if r.status_code == 404:
            raise PasarGuardAPIError("کاربر پیدا نشد.", status_code=404, body=r.text)
        if r.status_code >= 400:
            raise PasarGuardAPIError("ویرایش کاربر ناموفق بود.", status_code=r.status_code, body=r.text)
        data = r.json()
        if isinstance(data, dict):
            self.absolutize_subscription_url(data)
        return data

    async def delete_user(self, username: str) -> None:
        r = await self._request("DELETE", self._user_path(username))
        if r.status_code == 404:
            raise PasarGuardAPIError("کاربر پیدا نشد.", status_code=404, body=r.text)
        if r.status_code >= 400:
            raise PasarGuardAPIError("حذف کاربر ناموفق بود.", status_code=r.status_code, body=r.text)

    async def reset_user_usage(self, username: str) -> dict[str, Any]:
        r = await self._request("POST", f"{self._user_path(username)}/reset")
        if r.status_code >= 400:
            raise PasarGuardAPIError("ریست ترافیک ناموفق بود.", status_code=r.status_code, body=r.text)
        data = r.json()
        if isinstance(data, dict):
            self.absolutize_subscription_url(data)
        return data

    async def revoke_subscription(self, username: str) -> dict[str, Any]:
        r = await self._request("POST", f"{self._user_path(username)}/revoke_sub")
        if r.status_code >= 400:
            raise PasarGuardAPIError("تغییر لینک ساب ناموفق بود.", status_code=r.status_code, body=r.text)
        data = r.json()
        if isinstance(data, dict):
            self.absolutize_subscription_url(data)
        return data

    async def list_sub_updates(self, username: str, *, limit: int = 5) -> dict[str, Any]:
        r = await self._request(
            "GET",
            f"{self._user_path(username)}/sub_update",
            params={"offset": 0, "limit": limit},
        )
        if r.status_code >= 400:
            raise PasarGuardAPIError("دریافت تاریخچهٔ ساب ناموفق بود.", status_code=r.status_code, body=r.text)
        return r.json()

    async def search_users(self, *, search: str, limit: int = 20) -> dict[str, Any]:
        r = await self._request("GET", "/api/users", params={"search": search, "limit": limit})
        if r.status_code >= 400:
            raise PasarGuardAPIError("جستجوی کاربران ناموفق بود.", status_code=r.status_code, body=r.text)
        data = r.json()
        if isinstance(data, dict):
            for u in data.get("users") or []:
                if isinstance(u, dict):
                    self.absolutize_subscription_url(u)
        return data

    async def list_all_users(self, *, page_size: int = 200) -> list[dict[str, Any]]:
        users: list[dict[str, Any]] = []
        offset = 0
        page_size = max(1, min(int(page_size), 500))
        while True:
            r = await self._request(
                "GET",
                "/api/users",
                params={"offset": offset, "limit": page_size},
            )
            if r.status_code >= 400:
                raise PasarGuardAPIError("دریافت لیست کاربران ناموفق بود.", status_code=r.status_code, body=r.text)
            data = r.json()
            if not isinstance(data, dict):
                break
            batch = [u for u in (data.get("users") or []) if isinstance(u, dict)]
            total = int(data.get("total") or 0)
            for u in batch:
                self.absolutize_subscription_url(u)
                users.append(u)
            offset += len(batch)
            if not batch or (total > 0 and offset >= total):
                break
            if len(batch) < page_size:
                break
        return users
