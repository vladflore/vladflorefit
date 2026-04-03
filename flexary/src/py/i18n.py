import json

from js import localStorage, window, Object
from pyodide.ffi import to_js
from pyscript import document

SUPPORTED = frozenset(["en", "es", "de", "ca"])


def _detect_lang() -> str:
    stored = localStorage.getItem("flexary_lang")
    if stored and str(stored) in SUPPORTED:
        return str(stored)
    nav = str(window.navigator.language or "en").split("-")[0].lower()
    return nav if nav in SUPPORTED else "en"


lang: str = _detect_lang()

try:
    with open(f"{lang}.json") as _f:
        _msgs: dict = json.load(_f)
except Exception:
    _msgs = {}

try:
    window.flexaryI18n = to_js(_msgs, dict_converter=Object.fromEntries)
    window.flexaryLang = lang
except Exception:
    pass


def t(key: str, **kwargs) -> str:
    """Return translated string for key, with optional format kwargs."""
    msg = _msgs.get(key, key)
    if kwargs:
        try:
            msg = msg.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return msg


def _translate_root(root) -> None:
    """Apply all data-i18n* translations to a given DOM root or DocumentFragment."""
    els = root.querySelectorAll("[data-i18n]")
    for i in range(els.length):
        el = els.item(i)
        val = _msgs.get(str(el.getAttribute("data-i18n")))
        if val is not None:
            el.textContent = val

    els = root.querySelectorAll("[data-i18n-html]")
    for i in range(els.length):
        el = els.item(i)
        val = _msgs.get(str(el.getAttribute("data-i18n-html")))
        if val is not None:
            el.innerHTML = val

    els = root.querySelectorAll("[data-i18n-ph]")
    for i in range(els.length):
        el = els.item(i)
        val = _msgs.get(str(el.getAttribute("data-i18n-ph")))
        if val is not None:
            el.placeholder = val

    els = root.querySelectorAll("[data-i18n-title]")
    for i in range(els.length):
        el = els.item(i)
        val = _msgs.get(str(el.getAttribute("data-i18n-title")))
        if val is not None:
            el.setAttribute("title", val)


def apply_html_translations() -> None:
    """Apply locale to all [data-i18n*] elements in the active DOM and templates."""
    _translate_root(document)

    templates = document.querySelectorAll("template")
    for i in range(templates.length):
        _translate_root(templates.item(i).content)

    sel = document.getElementById("lang-select")
    if sel:
        sel.value = lang
