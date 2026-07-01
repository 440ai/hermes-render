"""Allowlisted Clerk/OAuth dashboard auth for the 440.ai Hermes gateway."""

from __future__ import annotations

import logging
import os
import time
import base64
import urllib.parse
from typing import Any, Iterable

import httpx
from fastapi import HTTPException
from hermes_cli.config import cfg_get, load_config
from hermes_cli.dashboard_auth import InvalidCodeError, ProviderError, RefreshExpiredError, Session
from plugins.dashboard_auth.self_hosted import SelfHostedOIDCProvider

logger = logging.getLogger(__name__)

# Clerk OAuth applications in the 440.ai instance are OAuth2 userinfo clients,
# not full OIDC clients with `openid` enabled. Requesting `openid` makes Clerk
# reject the authorization request before the user can sign in. We still use
# Clerk's discovery document for endpoints, then verify the opaque access token
# by calling Clerk's userinfo endpoint on every session check.
_DEFAULT_SCOPES = "profile email"
_PROVIDER_NAME = "allowlisted-oidc"
_TOKEN_TIMEOUT_SEC = 10.0
_DEFAULT_ACCESS_TOKEN_TTL_SEC = 3600


def _split_emails(raw: str) -> set[str]:
    return {part.strip().lower() for part in raw.replace("\n", ",").split(",") if part.strip()}


def _email_set(values: Any) -> set[str]:
    if isinstance(values, str):
        return _split_emails(values)
    if isinstance(values, Iterable):
        return {str(value).strip().lower() for value in values if str(value).strip()}
    return set()


def _oauth_config() -> dict[str, Any]:
    try:
        cfg = load_config() or {}
    except Exception as exc:  # pragma: no cover - defensive startup logging
        logger.warning("allowlisted-oidc: failed to load config.yaml: %s", exc)
        return {}
    section = cfg_get(cfg, "dashboard", "oauth", "allowlisted_oidc", default=None)
    return section if isinstance(section, dict) else {}


def _setting(env_var: str, cfg_value: Any) -> str:
    env = os.environ.get(env_var, "").strip()
    if env:
        return env
    return str(cfg_value or "").strip()


class AllowlistedOIDCProvider(SelfHostedOIDCProvider):
    name = _PROVIDER_NAME
    display_name = "440.ai Clerk"

    def __init__(self, *, allowed_emails: set[str], client_secret: str = "", **kwargs: Any) -> None:
        if not allowed_emails:
            raise ValueError("allowed_emails is required")
        self._allowed_emails = allowed_emails
        self._client_secret = client_secret.strip()
        super().__init__(**kwargs)

    def _userinfo_endpoint(self) -> str:
        return f"{self._issuer}/oauth/userinfo"

    def _token_endpoint_auth(self, disco: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
        if not self._client_secret:
            return {}, {}

        methods = disco.get("token_endpoint_auth_methods_supported") or []
        if isinstance(methods, list) and "client_secret_basic" in methods:
            encoded_client = urllib.parse.quote(self._client_id, safe="")
            encoded_secret = urllib.parse.quote(self._client_secret, safe="")
            token = base64.b64encode(f"{encoded_client}:{encoded_secret}".encode("ascii")).decode("ascii")
            return {}, {"Authorization": f"Basic {token}"}

        return {"client_secret": self._client_secret}, {}

    def _fetch_userinfo(self, access_token: str) -> dict[str, Any]:
        try:
            response = httpx.get(
                self._userinfo_endpoint(),
                headers={"Accept": "application/json", "Authorization": f"Bearer {access_token}"},
                timeout=_TOKEN_TIMEOUT_SEC,
            )
        except httpx.RequestError as exc:
            raise ProviderError(f"Clerk userinfo endpoint unreachable: {exc}") from exc
        if response.status_code in (401, 403):
            raise InvalidCodeError("Clerk rejected access token")
        if response.status_code != 200:
            raise ProviderError(
                f"Clerk userinfo endpoint returned {response.status_code}: {response.text[:200]!r}"
            )
        body = self._parse_json_body(response)
        if not body:
            raise ProviderError("Clerk userinfo returned a non-JSON body")
        return body

    def _exchange_for_session(
        self,
        *,
        data: dict[str, str],
        bad_request_exc: type[Exception],
        previous_refresh_token: str = "",
    ) -> Session:
        disco = self._get_discovery()
        extra_data, extra_headers = self._token_endpoint_auth(disco)
        data.update(extra_data)
        headers = {"Accept": "application/json"}
        headers.update(extra_headers)
        try:
            response = httpx.post(
                disco["token_endpoint"],
                data=data,
                headers=headers,
                timeout=_TOKEN_TIMEOUT_SEC,
            )
        except httpx.RequestError as exc:
            raise ProviderError(f"Clerk token endpoint unreachable: {exc}") from exc
        if response.status_code == 400:
            body = self._parse_json_body(response)
            raise bad_request_exc(f"Clerk rejected token request: {body.get('error', 'invalid_request')}")
        if response.status_code != 200:
            raise ProviderError(
                f"Clerk token endpoint returned {response.status_code}: {response.text[:200]!r}"
            )
        payload = self._parse_json_body(response)
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ProviderError("Clerk token response missing access_token")
        token_type = str(payload.get("token_type", "bearer")).lower()
        if token_type and token_type != "bearer":
            raise ProviderError(f"unexpected Clerk token_type={token_type!r}")
        claims = self._fetch_userinfo(access_token)
        refresh_token = payload.get("refresh_token")
        if not isinstance(refresh_token, str) or not refresh_token:
            refresh_token = previous_refresh_token or ""
        try:
            expires_in = int(payload.get("expires_in") or _DEFAULT_ACCESS_TOKEN_TTL_SEC)
        except (TypeError, ValueError):
            expires_in = _DEFAULT_ACCESS_TOKEN_TTL_SEC
        return self._session_from_userinfo(
            access_token=access_token,
            refresh_token=refresh_token,
            claims=claims,
            expires_at=int(time.time()) + max(60, expires_in),
        )

    def _session_from_userinfo(
        self,
        *,
        access_token: str,
        refresh_token: str,
        claims: dict[str, Any],
        expires_at: int,
    ) -> Session:
        user_id = str(claims.get("sub") or claims.get("id") or "")
        if not user_id:
            raise ProviderError("Clerk userinfo missing subject")
        email = str(claims.get("email") or "").strip().lower()
        display_name = str(
            claims.get("name")
            or claims.get("preferred_username")
            or claims.get("given_name")
            or email
            or ""
        )
        return Session(
            user_id=user_id,
            email=email,
            display_name=display_name,
            org_id=str(claims.get("org_id") or claims.get("organization") or ""),
            provider=self.name,
            expires_at=expires_at,
            access_token=access_token,
            refresh_token=refresh_token,
        )

    def _enforce_allowlist(self, session: Session) -> Session:
        email = (session.email or "").strip().lower()
        if email not in self._allowed_emails:
            logger.warning("allowlisted-oidc: denied dashboard login for non-allowlisted email %r", email)
            raise HTTPException(status_code=403, detail="Dashboard access is restricted.")
        return session

    def complete_login(self, *, code: str, state: str, code_verifier: str, redirect_uri: str) -> Session:
        _ = state
        self._validate_redirect_uri(redirect_uri)
        session = self._exchange_for_session(
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": self._client_id,
                "code_verifier": code_verifier,
            },
            bad_request_exc=InvalidCodeError,
        )
        return self._enforce_allowlist(session)

    def verify_session(self, *, access_token: str) -> Session | None:
        try:
            claims = self._fetch_userinfo(access_token)
        except InvalidCodeError:
            return None
        return self._enforce_allowlist(
            self._session_from_userinfo(
                access_token=access_token,
                refresh_token="",
                claims=claims,
                expires_at=int(time.time()) + 300,
            )
        )

    def refresh_session(self, *, refresh_token: str) -> Session:
        if not refresh_token:
            raise RefreshExpiredError("no refresh token present in session")
        session = self._exchange_for_session(
            data={
                "grant_type": "refresh_token",
                "client_id": self._client_id,
                "refresh_token": refresh_token,
                "scope": self._scopes,
            },
            bad_request_exc=RefreshExpiredError,
            previous_refresh_token=refresh_token,
        )
        return self._enforce_allowlist(session)


def register(ctx) -> None:
    cfg = _oauth_config()
    issuer = _setting(
        "HERMES_DASHBOARD_ALLOWLISTED_OIDC_ISSUER",
        cfg.get("issuer") or os.environ.get("HERMES_DASHBOARD_OIDC_ISSUER", ""),
    )
    client_id = _setting("HERMES_DASHBOARD_ALLOWLISTED_OIDC_CLIENT_ID", cfg.get("client_id"))
    client_secret = _setting(
        "HERMES_DASHBOARD_ALLOWLISTED_OIDC_CLIENT_SECRET",
        cfg.get("client_secret"),
    )
    scopes = _setting("HERMES_DASHBOARD_ALLOWLISTED_OIDC_SCOPES", cfg.get("scopes")) or _DEFAULT_SCOPES
    allowed_emails = _email_set(os.environ.get("HERMES_DASHBOARD_ALLOWED_EMAILS", "")) or _email_set(
        cfg.get("allowed_emails")
    )

    if not issuer or not client_id:
        logger.warning(
            "allowlisted-oidc: missing issuer/client_id; issuer set=%s client_id set=%s",
            bool(issuer),
            bool(client_id),
        )
        return
    if not allowed_emails:
        logger.warning("allowlisted-oidc: no allowed dashboard emails configured; refusing to register")
        return

    provider = AllowlistedOIDCProvider(
        issuer=issuer,
        client_id=client_id,
        scopes=scopes,
        client_secret=client_secret,
        allowed_emails=allowed_emails,
    )
    ctx.register_dashboard_auth_provider(provider)
    logger.info(
        "allowlisted-oidc: registered provider (issuer_configured=%s, client_id_configured=%s, allowed_email_count=%d, confidential=%s, scopes=%r)",
        bool(issuer),
        bool(client_id),
        len(allowed_emails),
        bool(client_secret),
        scopes,
    )
