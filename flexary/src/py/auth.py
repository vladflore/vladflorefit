import asyncio

from js import window
from pyodide.ffi import create_proxy
from pyscript import document

from i18n import t

_auth_change_proxy = None


def _el(el_id: str):
    return document.getElementById(el_id)


def _has_auth_bridge() -> bool:
    return hasattr(window, "flexaryAuth") and window.flexaryAuth


async def _wait_for_bridge() -> bool:
    for _ in range(50):
        if _has_auth_bridge():
            return True
        await asyncio.sleep(0.05)
    return False


def _set_feedback(message: str, kind: str = "info") -> None:
    box = _el("auth-feedback")
    if not box:
        return
    if not message:
        box.className = "auth-feedback d-none"
        box.textContent = ""
        return
    box.className = f"auth-feedback auth-feedback--{kind}"
    box.textContent = message


def _set_config_warning(is_visible: bool) -> None:
    warning = _el("auth-config-warning")
    if warning:
        warning.classList.toggle("d-none", not is_visible)


def open_auth_modal(event=None) -> None:
    _set_config_warning(not (_has_auth_bridge() and window.flexaryAuth.isAvailable()))
    _set_feedback("")
    _el("auth-modal").showModal()


def close_auth_modal(event=None) -> None:
    _set_feedback("")
    _el("auth-modal").close()


def close_account_modal(event=None) -> None:
    _el("account-modal").close()


async def _refresh_account_modal() -> None:
    user = None
    token = None
    if _has_auth_bridge():
        user = await window.flexaryAuth.getCurrentUser()
        token = await window.flexaryAuth.getAccessToken()

    _el("account-email").textContent = (
        str(user.email) if user and getattr(user, "email", None) else t("not_available")
    )
    _el("account-user-id").textContent = (
        str(user.id) if user and getattr(user, "id", None) else "-"
    )
    _el("account-session-status").textContent = (
        t("account_session_ready") if token else t("account_session_missing")
    )


def open_account_modal(event=None) -> None:
    async def _open():
        await _refresh_account_modal()
        _el("account-modal").showModal()

    asyncio.ensure_future(_open())


def _set_nav_state(user) -> None:
    guest = _el("auth-guest-actions")
    signed = _el("auth-user-actions")
    badge = _el("auth-status-badge")
    account_btn = _el("auth-account-trigger")

    is_signed_in = bool(user)
    guest.classList.toggle("d-none", is_signed_in)
    signed.classList.toggle("d-none", not is_signed_in)

    if is_signed_in:
        email = str(user.email) if getattr(user, "email", None) else t("account")
        badge.textContent = email
        badge.className = "auth-status-badge"
        account_btn.title = email
    else:
        badge.textContent = t("auth_guest_badge")
        badge.className = "auth-status-badge auth-status-badge--muted"
        account_btn.title = t("account")


async def refresh_auth_ui() -> None:
    if not await _wait_for_bridge():
        _set_nav_state(None)
        _set_config_warning(True)
        return

    available = bool(window.flexaryAuth.isAvailable())
    _set_config_warning(not available)
    if not available:
        _set_nav_state(None)
        return

    user = await window.flexaryAuth.getCurrentUser()
    _set_nav_state(user)
    if _el("account-modal").open:
        await _refresh_account_modal()


async def _send_magic_link() -> None:
    if not await _wait_for_bridge() or not window.flexaryAuth.isAvailable():
        _set_feedback(t("auth_missing_config"), "warning")
        return

    email = _el("auth-email").value.strip()
    if not email or "@" not in email:
        _set_feedback(t("auth_invalid_email"), "error")
        return

    _set_feedback(t("auth_magic_link_working"), "info")
    try:
        await window.flexaryAuth.signInWithMagicLink(email)
        _set_feedback(t("auth_magic_link_sent"), "success")
    except Exception as error:
        _set_feedback(str(error), "error")


def send_magic_link(event=None) -> None:
    asyncio.ensure_future(_send_magic_link())


async def _sign_out() -> None:
    if not await _wait_for_bridge() or not window.flexaryAuth.isAvailable():
        return
    await window.flexaryAuth.signOut()
    await refresh_auth_ui()


def sign_out(event=None) -> None:
    asyncio.ensure_future(_sign_out())


def _on_auth_change(event) -> None:
    asyncio.ensure_future(refresh_auth_ui())


async def initialize_auth_ui() -> None:
    global _auth_change_proxy

    if await _wait_for_bridge():
        await window.flexaryAuth.ready
        if _auth_change_proxy is None:
            _auth_change_proxy = create_proxy(_on_auth_change)
            window.addEventListener("flexary-auth-change", _auth_change_proxy)

    await refresh_auth_ui()
