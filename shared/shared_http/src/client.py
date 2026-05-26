"""HTTP client with identity and correlation propagation."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Optional

import requests

from .propagation import build_outbound_headers, get_bearer_token


class ServiceHttpClient:
    """Thin wrapper around requests with outbound propagation headers."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        verify: bool | str = True,
        cert: Optional[tuple[str, str]] = None,
        default_headers: Optional[Mapping[str, str]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verify = verify
        self.cert = cert
        self.default_headers = dict(default_headers or {})

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: Optional[Mapping[str, str]] = None,
        headers: Optional[Mapping[str, str]] = None,
        include_auth: bool = True,
        **kwargs: Any,
    ) -> requests.Response:
        url = f"{self.base_url}{path}"
        outbound = build_outbound_headers(headers, include_auth=include_auth)
        outbound.update(self.default_headers)
        if not include_auth:
            outbound.pop("Authorization", None)

        return requests.request(
            method,
            url,
            json=json,
            params=params,
            headers=outbound,
            timeout=kwargs.pop("timeout", self.timeout),
            verify=kwargs.pop("verify", self.verify),
            cert=kwargs.pop("cert", self.cert),
            **kwargs,
        )

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", path, **kwargs)
