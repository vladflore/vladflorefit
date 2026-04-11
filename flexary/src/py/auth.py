import asyncio

from js import window
from pyodide.ffi import create_proxy
from pyscript import document

from i18n import t

_auth_change_proxy = None
_click_outside_proxy = None


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


def open_auth_modal(event=None) -> None:
    _set_feedback("")
    _el("auth-modal").showModal()


def close_auth_modal(event=None) -> None:
    _set_feedback("")
    _el("auth-modal").close()


def _close_user_menu() -> None:
    dropdown = _el("auth-user-dropdown")
    if dropdown:
        dropdown.classList.add("d-none")
    button = _el("auth-user-button")
    if button:
        button.classList.remove("is-open")


def toggle_user_menu(event=None) -> None:
    dropdown = _el("auth-user-dropdown")
    if dropdown:
        hidden = dropdown.classList.toggle("d-none")
        button = _el("auth-user-button")
        if button:
            button.classList.toggle("is-open", not hidden)


def _handle_document_click(event) -> None:
    dropdown = _el("auth-user-dropdown")
    button = _el("auth-user-button")
    if not dropdown or not button:
        return
    if dropdown.contains(event.target) or button.contains(event.target):
        return
    dropdown.classList.add("d-none")
    button.classList.remove("is-open")


def _set_nav_state(user) -> None:
    guest = _el("auth-guest-actions")
    signed = _el("auth-user-menu")
    badge = _el("auth-status-badge")
    account_btn = _el("auth-account-trigger")
    save_btn = _el("save-workouts")

    is_signed_in = bool(user)
    guest.classList.toggle("d-none", is_signed_in)
    signed.classList.toggle("d-none", not is_signed_in)
    if save_btn:
        save_btn.classList.toggle("d-none", not is_signed_in)

    if is_signed_in:
        email = str(user.email) if getattr(user, "email", None) else t("account")
        badge.textContent = email
        badge.className = "auth-status-pill-label"
        account_btn.title = email
    else:
        badge.textContent = t("auth_guest_badge")
        badge.className = "auth-status-pill-label auth-status-badge--muted"
        account_btn.title = t("account")

    _close_user_menu()


def _set_sign_in_visibility(enabled: bool) -> None:
    nav = _el("auth-nav")
    if nav:
        nav.style.visibility = "" if enabled else "hidden"


async def refresh_auth_ui() -> None:
    if not await _wait_for_bridge():
        _set_sign_in_visibility(False)
        _set_nav_state(None)
        return

    sign_in_enabled = bool(window.flexaryAuth.isSignInEnabled())
    _set_sign_in_visibility(sign_in_enabled)
    if not sign_in_enabled:
        return

    user = await window.flexaryAuth.getCurrentUser()
    _set_nav_state(user)


async def _send_magic_link() -> None:
    if not await _wait_for_bridge():
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
    if not await _wait_for_bridge():
        return
    await window.flexaryAuth.signOut()
    await refresh_auth_ui()


def sign_out(event=None) -> None:
    asyncio.ensure_future(_sign_out())


def open_contact(event=None) -> None:
    email = ""
    if _has_auth_bridge() and window.flexaryAuth.state.user:
        email = str(getattr(window.flexaryAuth.state.user, "email", "") or "")
    msg = f"Hello! This is {email}. Write the rest of your message... ;)"
    url = f"https://wa.me/+34613429288?text={window.encodeURIComponent(msg)}"
    window.open(url, "_blank")


def _on_auth_change(event) -> None:
    asyncio.ensure_future(refresh_auth_ui())


async def initialize_auth_ui() -> None:
    global _auth_change_proxy, _click_outside_proxy

    if await _wait_for_bridge():
        await window.flexaryAuth.ready
        if _auth_change_proxy is None:
            _auth_change_proxy = create_proxy(_on_auth_change)
            window.addEventListener("flexary-auth-change", _auth_change_proxy)
        if _click_outside_proxy is None:
            _click_outside_proxy = create_proxy(_handle_document_click)
            document.addEventListener("click", _click_outside_proxy)

    await refresh_auth_ui()
