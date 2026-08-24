"""OpenAI Team/K12 re-login flow.

After joining a K12 workspace the original registration token is usually still
a personal/free token.  This module performs a second OAuth login and selects
the K12 workspace so that OpenAI issues team-scoped tokens suitable for
sub2api export.
"""

from __future__ import annotations

import json
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, unquote, urlparse

from curl_cffi import requests

from chatgpt_register_k12.register.headers import json_headers, navigate_headers
from chatgpt_register_k12.register.mail_provider import wait_for_code
from chatgpt_register_k12.register.registrar import (
    AUTH_BASE,
    PLATFORM_AUTH0_CLIENT,
    PLATFORM_BASE,
    PLATFORM_OAUTH_AUDIENCE,
    PLATFORM_OAUTH_CLIENT_ID,
    PLATFORM_OAUTH_REDIRECT_URI,
)
from chatgpt_register_k12.register.session import request_with_retry
from chatgpt_register_k12.utils.jwt import extract_account_info
from chatgpt_register_k12.utils.pkce import generate_pkce
from chatgpt_register_k12.utils.proxy import normalize_proxy_url
from chatgpt_register_k12.utils.sentinel import build_sentinel_token


class LoginError(RuntimeError):
    """Re-login step failed."""


class PasswordRequiredError(LoginError):
    """The current OpenAI account requires password authentication."""


def _response_json(resp) -> dict:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _extract_oauth_params(url: str) -> dict[str, str] | None:
    if not url:
        return None
    try:
        params = parse_qs(urlparse(url).query)
    except Exception:
        return None
    code = str((params.get("code") or [""])[0]).strip()
    if not code:
        return None
    return {
        "code": code,
        "state": str((params.get("state") or [""])[0]).strip(),
    }


def _extract_code_from_response(resp) -> str:
    candidates: list[str] = []
    candidates.append(str(getattr(resp, "url", "") or ""))
    try:
        for item in getattr(resp, "history", []) or []:
            candidates.append(str(getattr(item, "url", "") or ""))
            location = str(getattr(item, "headers", {}).get("Location") or "")
            if location:
                candidates.append(location)
    except Exception:
        pass
    try:
        location = str(getattr(resp, "headers", {}).get("Location") or "")
        if location:
            candidates.append(location)
    except Exception:
        pass

    data = _response_json(resp)
    continue_url = str(data.get("continue_url") or "")
    if continue_url:
        candidates.append(continue_url)

    text = str(getattr(resp, "text", "") or "")
    if text:
        candidates.append(text)
        candidates.append(unquote(text))

    for candidate in candidates:
        if not candidate:
            continue
        params = _extract_oauth_params(candidate)
        if params and params.get("code"):
            return params["code"]

        for marker in ("code%3D", "code="):
            if marker in candidate:
                tail = candidate.split(marker, 1)[1]
                value = tail.split("&", 1)[0].split("%26", 1)[0]
                value = unquote(value).strip('"\'<> ')
                if value:
                    return value
    return ""


def _page_type(resp) -> str:
    data = _response_json(resp)
    page = data.get("page") if isinstance(data.get("page"), dict) else {}
    return str(page.get("type") or "")


def _page_type_from_response_url(resp) -> str:
    url = str(getattr(resp, "url", "") or "").lower()
    if "/log-in/password" in url:
        return "login_password"
    if "/email-verification" in url:
        return "email_otp_verification"
    if "/about-you" in url:
        return "about_you"
    if "/error" in url:
        return "error"
    return ""


def _start_authorize(
    session: requests.Session,
    device_id: str,
    workspace_id: str,
) -> tuple[str, str]:
    code_verifier, code_challenge = generate_pkce()
    params = {
        "issuer": AUTH_BASE,
        "client_id": PLATFORM_OAUTH_CLIENT_ID,
        "audience": PLATFORM_OAUTH_AUDIENCE,
        "redirect_uri": PLATFORM_OAUTH_REDIRECT_URI,
        "device_id": device_id,
        "screen_hint": "login",
        "max_age": "0",
        "scope": "openid profile email offline_access",
        "response_type": "code",
        "response_mode": "query",
        "state": secrets.token_urlsafe(32),
        "nonce": secrets.token_urlsafe(32),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "auth0Client": PLATFORM_AUTH0_CLIENT,
    }
    if workspace_id:
        params["workspace_id"] = workspace_id

    target_url = f"{AUTH_BASE}/api/accounts/authorize?{urlencode(params)}"
    resp, error = request_with_retry(
        session,
        "get",
        target_url,
        headers=navigate_headers(f"{PLATFORM_BASE}/"),
        allow_redirects=True,
        verify=True,
    )
    if resp is None:
        raise LoginError(f"authorize failed: {error}")
    if resp.status_code != 200:
        raise LoginError(f"authorize HTTP {resp.status_code}: {resp.text[:300]}")
    return code_verifier, code_challenge


def _continue_with_email(
    session: requests.Session,
    device_id: str,
    email: str,
) -> dict:
    url = f"{AUTH_BASE}/api/accounts/authorize/continue"
    headers = json_headers(f"{AUTH_BASE}/log-in", device_id)
    headers["openai-sentinel-token"] = build_sentinel_token(
        session, device_id, "authorize_continue"
    )[0]
    resp, error = request_with_retry(
        session,
        "post",
        url,
        json={
            "username": {"kind": "email", "value": email},
            "screen_hint": "login",
        },
        headers=headers,
        verify=True,
    )
    if resp is None:
        raise LoginError(f"authorize_continue failed: {error}")
    if resp.status_code != 200:
        raise LoginError(
            f"authorize_continue HTTP {resp.status_code}: {resp.text[:300]}"
        )
    data = _response_json(resp)
    if not data:
        raise LoginError("authorize_continue returned invalid JSON")
    return data


def _submit_password(
    session: requests.Session,
    device_id: str,
    password: str,
) -> dict:
    headers = json_headers(f"{AUTH_BASE}/log-in/password", device_id)
    headers["openai-sentinel-token"] = build_sentinel_token(
        session, device_id, "authorize_continue"
    )[0]
    resp, error = request_with_retry(
        session,
        "post",
        f"{AUTH_BASE}/api/accounts/authorize/continue",
        json={"password": password},
        headers=headers,
        verify=True,
    )
    if resp is None:
        raise LoginError(f"password continue failed: {error}")
    if resp.status_code != 200:
        raise LoginError(
            f"password continue HTTP {resp.status_code}: {resp.text[:300]}"
        )
    data = _response_json(resp)
    if not data:
        raise LoginError("password continue returned invalid JSON")
    return data


def _send_login_otp(session: requests.Session) -> dict:
    url = f"{AUTH_BASE}/api/accounts/email-otp/send"
    resp, error = request_with_retry(
        session,
        "get",
        url,
        headers=navigate_headers(f"{AUTH_BASE}/log-in"),
        allow_redirects=True,
        verify=True,
    )
    if resp is None:
        raise LoginError(f"send login OTP failed: {error}")
    page_type = _page_type(resp) or _page_type_from_response_url(resp)
    if page_type == "login_password":
        raise PasswordRequiredError("Password required for this account")
    if page_type == "error":
        retry_resp, retry_error = request_with_retry(
            session,
            "get",
            f"{AUTH_BASE}/email-verification",
            headers=navigate_headers(f"{AUTH_BASE}/log-in"),
            allow_redirects=True,
            verify=True,
        )
        if retry_resp is not None:
            page_type = _page_type(retry_resp) or _page_type_from_response_url(retry_resp)
            if page_type == "login_password":
                raise PasswordRequiredError("Password required for this account")
            if page_type != "error":
                resp, error = request_with_retry(
                    session,
                    "get",
                    url,
                    headers=navigate_headers(f"{AUTH_BASE}/email-verification"),
                    allow_redirects=True,
                    verify=True,
                )
                if resp is None:
                    raise LoginError(f"send login OTP retry failed: {error}")
                page_type = _page_type(resp) or _page_type_from_response_url(resp)
                if page_type == "login_password":
                    raise PasswordRequiredError("Password required for this account")
        elif retry_error:
            error = retry_error
    if resp.status_code not in (200, 302):
        raise LoginError(f"send login OTP HTTP {resp.status_code}: {resp.text[:300]}")
    page_type = _page_type(resp) or _page_type_from_response_url(resp)
    if page_type == "error":
        raise LoginError("OpenAI returned an error page while sending login OTP")
    return {"page": {"type": page_type}} if page_type else {}


def _validate_login_otp(
    session: requests.Session,
    device_id: str,
    code: str,
) -> dict:
    headers = json_headers(f"{AUTH_BASE}/email-verification", device_id)
    headers["openai-sentinel-token"] = build_sentinel_token(
        session, device_id, "authorize_continue"
    )[0]
    resp, error = request_with_retry(
        session,
        "post",
        f"{AUTH_BASE}/api/accounts/email-otp/validate",
        json={"code": code},
        headers=headers,
        verify=True,
    )
    if resp is None:
        raise LoginError(f"validate login OTP failed: {error}")
    if resp.status_code != 200:
        raise LoginError(
            f"validate login OTP HTTP {resp.status_code}: {resp.text[:300]}"
        )
    data = _response_json(resp)
    if not data:
        raise LoginError("validate login OTP returned invalid JSON")
    return data


def _complete_login_flow(
    *,
    session: requests.Session,
    device_id: str,
    email: str,
    mail_config: dict,
    workspace_id: str,
    response_data: dict,
    code_verifier: str,
    password: str | None,
) -> tuple[str, str]:
    current = response_data
    otp_already_sent = bool(current.get("_otp_already_sent"))
    otp_not_before = current.get("_otp_not_before")
    for _ in range(8):
        continue_url = str(current.get("continue_url") or "").strip()
        if continue_url:
            params = _extract_oauth_params(continue_url)
            if params and params.get("code"):
                return params["code"], code_verifier

        page = current.get("page") if isinstance(current.get("page"), dict) else {}
        page_type = str(page.get("type") or "")

        if page_type == "login_password":
            if not password:
                raise PasswordRequiredError("Password required for this account")
            current = _submit_password(session, device_id, password)
            continue

        if page_type in {
            "email_otp_verification",
            "email_otp_verification_login",
            "email_otp_verification_registration",
        }:
            if not otp_already_sent:
                otp_not_before = datetime.now(timezone.utc)
                _send_login_otp(session)
                otp_already_sent = True
            mailbox = {
                "address": email,
                "_code_not_before": otp_not_before or datetime.now(timezone.utc),
                "_code_subject_hint": "login",
            }
            code = wait_for_code(mail_config, mailbox)
            if not code:
                raise LoginError("Timed out waiting for login verification code")
            current = _validate_login_otp(session, device_id, code)
            continue

        if page_type in {"workspace_select", "account_select", "choose_account"}:
            url = f"{AUTH_BASE}/api/accounts/authorize/continue"
            headers = json_headers(f"{AUTH_BASE}/", device_id)
            payload: dict[str, Any] = {}
            if workspace_id:
                payload["workspace_id"] = workspace_id
                payload["account_id"] = workspace_id
            resp, error = request_with_retry(
                session,
                "post",
                url,
                json=payload,
                headers=headers,
                verify=True,
            )
            if resp is None:
                raise LoginError(f"workspace selection failed: {error}")
            if resp.status_code != 200:
                raise LoginError(
                    f"workspace selection HTTP {resp.status_code}: {resp.text[:300]}"
                )
            current = _response_json(resp)
            continue

        if page_type in {"consent", "oauth_consent"}:
            resp, error = request_with_retry(
                session,
                "post",
                f"{AUTH_BASE}/api/accounts/authorize/continue",
                json={"consent": True},
                headers=json_headers(f"{AUTH_BASE}/", device_id),
                verify=True,
            )
            if resp is None:
                raise LoginError(f"consent failed: {error}")
            if resp.status_code != 200:
                raise LoginError(f"consent HTTP {resp.status_code}: {resp.text[:300]}")
            current = _response_json(resp)
            continue

        if page_type in {"error", "blocked"}:
            raise LoginError(f"OpenAI login flow returned page={page_type}")

        break

    raise LoginError(
        "Unsupported login continuation page: "
        f"{str((current.get('page') or {}).get('type') or '?')}"
    )


def _exchange_code_for_tokens(
    session: requests.Session,
    code_verifier: str,
    code: str,
) -> dict:
    headers = {
        "accept": "*/*",
        "accept-language": "vi-VN,vi;q=0.9,en;q=0.8",
        "auth0-client": PLATFORM_AUTH0_CLIENT,
        "cache-control": "no-cache",
        "content-type": "application/json",
        "origin": PLATFORM_BASE,
        "pragma": "no-cache",
        "referer": f"{PLATFORM_BASE}/",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36"
        ),
    }
    resp = session.post(
        f"{AUTH_BASE}/api/accounts/oauth/token",
        headers=headers,
        json={
            "client_id": PLATFORM_OAUTH_CLIENT_ID,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": PLATFORM_OAUTH_REDIRECT_URI,
        },
        timeout=60,
        verify=True,
    )
    if resp.status_code != 200:
        raise LoginError(f"token exchange HTTP {resp.status_code}: {resp.text[:300]}")
    tokens = _response_json(resp)
    if not tokens.get("access_token"):
        raise LoginError("token exchange returned no access_token")
    return tokens


def _make_session(proxy: str = "") -> requests.Session:
    kwargs: dict[str, Any] = {"impersonate": "chrome", "verify": True}
    proxy_url = normalize_proxy_url(proxy)
    if proxy_url:
        kwargs["proxy"] = proxy_url
    return requests.Session(**kwargs)


def re_login_for_team_token(
    email: str,
    password: str,
    workspace_id: str,
    proxy: str = "",
) -> dict:
    """Login to OpenAI and obtain fresh tokens, preferring the K12 workspace."""
    session = _make_session(proxy)
    device_id = str(uuid.uuid4())
    session.cookies.set("oai-did", device_id, domain=".auth.openai.com")
    session.cookies.set("oai-did", device_id, domain="auth.openai.com")

    try:
        code_verifier, _ = _start_authorize(session, device_id, workspace_id)
        current = _continue_with_email(session, device_id, email)
        code, code_verifier = _complete_login_flow(
            session=session,
            device_id=device_id,
            email=email,
            mail_config={},
            workspace_id=workspace_id,
            response_data=current,
            code_verifier=code_verifier,
            password=password,
        )
        tokens = _exchange_code_for_tokens(session, code_verifier, code)
        info = extract_account_info(str(tokens.get("access_token") or ""))
        return {
            "email": email,
            "password": password,
            "access_token": str(tokens.get("access_token") or "").strip(),
            "refresh_token": str(tokens.get("refresh_token") or "").strip(),
            "id_token": str(tokens.get("id_token") or "").strip(),
            "chatgpt_account_id": info.get("chatgpt_account_id", ""),
            "chatgpt_user_id": info.get("chatgpt_user_id", ""),
            "plan_type": info.get("plan_type", ""),
            "source_type": "team_login",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        session.close()


def re_login_email_otp_for_team_token(
    email: str,
    mail_config: dict,
    workspace_id: str,
    proxy: str = "",
) -> dict:
    """Login using the email OTP flow and obtain fresh workspace tokens."""
    session = _make_session(proxy)
    device_id = str(uuid.uuid4())
    session.cookies.set("oai-did", device_id, domain=".auth.openai.com")
    session.cookies.set("oai-did", device_id, domain="auth.openai.com")
    try:
        code_verifier, _ = _start_authorize(session, device_id, workspace_id)
        current = _continue_with_email(session, device_id, email)
        page = current.get("page") if isinstance(current.get("page"), dict) else {}
        if str(page.get("type") or "") == "login_password":
            raise PasswordRequiredError("Password required for this account")
        current["_otp_not_before"] = datetime.now(timezone.utc)
        sent = _send_login_otp(session)
        if sent:
            current = sent
        current["_otp_already_sent"] = True
        current["_otp_not_before"] = current.get("_otp_not_before") or datetime.now(timezone.utc)
        code, code_verifier = _complete_login_flow(
            session=session,
            device_id=device_id,
            email=email,
            mail_config=mail_config,
            workspace_id=workspace_id,
            response_data=current,
            code_verifier=code_verifier,
            password=None,
        )
        tokens = _exchange_code_for_tokens(session, code_verifier, code)
        info = extract_account_info(str(tokens.get("access_token") or ""))
        return {
            "email": email,
            "password": "",
            "access_token": str(tokens.get("access_token") or "").strip(),
            "refresh_token": str(tokens.get("refresh_token") or "").strip(),
            "id_token": str(tokens.get("id_token") or "").strip(),
            "chatgpt_account_id": info.get("chatgpt_account_id", ""),
            "chatgpt_user_id": info.get("chatgpt_user_id", ""),
            "plan_type": info.get("plan_type", ""),
            "source_type": "email_otp_login",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        session.close()
