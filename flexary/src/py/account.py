import asyncio

from js import window
from pyscript import document

from i18n import apply_html_translations, t


async def _init() -> None:
    for _ in range(50):
        if hasattr(window, "flexaryAuth") and window.flexaryAuth:
            break
        await asyncio.sleep(0.05)

    if not hasattr(window, "flexaryAuth") or not window.flexaryAuth.isAvailable():
        window.location.href = "index.html"
        return

    user = await window.flexaryAuth.getCurrentUser()
    if not user:
        window.location.href = "index.html"
        return

    token = await window.flexaryAuth.getAccessToken()

    document.getElementById("account-email").textContent = (
        str(user.email) if getattr(user, "email", None) else t("not_available")
    )
    document.getElementById("account-user-id").textContent = (
        str(user.id) if getattr(user, "id", None) else "-"
    )
    document.getElementById("account-session-status").textContent = (
        t("account_session_ready") if token else t("account_session_missing")
    )


def sign_out(event=None) -> None:
    async def _do() -> None:
        if hasattr(window, "flexaryAuth") and window.flexaryAuth.isAvailable():
            await window.flexaryAuth.signOut()
        window.location.href = "index.html"

    asyncio.ensure_future(_do())


apply_html_translations()
asyncio.ensure_future(_init())
document.getElementById("loading").close()
document.getElementById("container").classList.remove("d-none")
