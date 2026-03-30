import json

from js import localStorage, window
from pyodide.ffi import to_js
from pyscript import document

SUPPORTED = frozenset(["en", "es", "de"])

# ── Language detection ─────────────────────────────────────────────────────────

def _detect_lang() -> str:
    stored = localStorage.getItem("flexary_lang")
    if stored and str(stored) in SUPPORTED:
        return str(stored)
    nav = str(window.navigator.language or "en").split("-")[0].lower()
    return nav if nav in SUPPORTED else "en"


lang: str = _detect_lang()

# ── Load locale from virtual filesystem (mapped via pyscript.toml) ─────────────

try:
    with open(f"{lang}.json") as _f:
        _msgs: dict = json.load(_f)
except Exception:
    _msgs = {}

# ── Expose to JS for JS-only event handlers (sidebar toggle titles etc.) ───────

try:
    window.flexaryI18n = to_js(_msgs)
    window.flexaryLang = lang
except Exception:
    pass


# ── Public API ─────────────────────────────────────────────────────────────────

def t(key: str, **kwargs) -> str:
    """Return translated string for key, with optional format kwargs."""
    msg = _msgs.get(key, key)
    if kwargs:
        try:
            msg = msg.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return msg


def apply_html_translations() -> None:
    """Apply locale to all [data-i18n*] elements in the active DOM."""
    # textContent
    els = document.querySelectorAll("[data-i18n]")
    for i in range(els.length):
        el = els.item(i)
        key = el.getAttribute("data-i18n")
        val = _msgs.get(key)
        if val is not None:
            el.textContent = val

    # innerHTML (for strings containing HTML like icons)
    els = document.querySelectorAll("[data-i18n-html]")
    for i in range(els.length):
        el = els.item(i)
        key = el.getAttribute("data-i18n-html")
        val = _msgs.get(key)
        if val is not None:
            el.innerHTML = val

    # placeholder attribute
    els = document.querySelectorAll("[data-i18n-ph]")
    for i in range(els.length):
        el = els.item(i)
        key = el.getAttribute("data-i18n-ph")
        val = _msgs.get(key)
        if val is not None:
            el.placeholder = val

    # title attribute
    els = document.querySelectorAll("[data-i18n-title]")
    for i in range(els.length):
        el = els.item(i)
        key = el.getAttribute("data-i18n-title")
        val = _msgs.get(key)
        if val is not None:
            el.title = val

    # Set language selector to active language
    sel = document.getElementById("lang-select")
    if sel:
        sel.value = lang
