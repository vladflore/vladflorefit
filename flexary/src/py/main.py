import asyncio
import importlib

from pyodide.ffi import create_proxy
from pyodide.ffi.wrappers import add_event_listener
from pyscript import document
from pyweb import pydom

import catalog
from common import copyright, current_version
from js import window
from i18n import apply_html_translations
import state
from auth import (
    close_auth_modal,
    initialize_auth_ui,
    open_auth_modal,
    open_contact,
    send_magic_link,
    sign_out,
    toggle_user_menu,
)
from filters import (
    clear_filters,
    update as update_filters,
)
from ics import download_ics
from workouts import add_workout, hide_sidebar, render_workouts, remove_workouts, update_workout_badge
from custom_exercises import open_add_custom_modal

_pdf_module = None


def _pdf():
    global _pdf_module
    if _pdf_module is None:
        _pdf_module = importlib.import_module("pdf")
    return _pdf_module


def open_pdf_modal(*args) -> None:
    _pdf().download_file(*args)


def download_pdf_with_options(*args) -> None:
    _pdf().download_pdf_with_options(*args)


def on_logo_file_change(*args) -> None:
    _pdf().on_logo_file_change(*args)


def clear_logo(*args) -> None:
    _pdf().clear_logo(*args)


def show_info(event) -> None:
    document.getElementById("info-modal").showModal()


apply_html_translations()

catalog.initialize(state.custom_exercises)

update_filters("")

pydom["#skeleton-row"][0]._js.classList.add("d-none")
pydom["#filter-row"][0]._js.classList.remove("d-none")

pydom[state.copyright_el_id][0]._js.innerHTML = copyright()
pydom[state.version_el_id][0]._js.innerHTML = current_version()
pydom[state.footer_el_id][0]._js.classList.remove("d-none")

add_event_listener(document.getElementById(state.download_pdf_btn_id), "click", open_pdf_modal)
add_event_listener(document.getElementById("download-ics"), "click", download_ics)
add_event_listener(document.getElementById("pdf-download-btn"), "click", download_pdf_with_options)
add_event_listener(document.getElementById("pdf-logo-input"), "change", on_logo_file_change)
add_event_listener(document.getElementById("pdf-logo-clear"), "click", clear_logo)

def _refresh_workouts_ui() -> None:
    if state.workouts:
        render_workouts(state.workouts)
        update_workout_badge()
    else:
        hide_sidebar()


def _on_auth_change(event) -> None:
    if not state.is_authenticated() and state.strip_custom_video_overrides():
        _refresh_workouts_ui()


async def _bootstrap() -> None:
    await initialize_auth_ui()
    if not state.is_authenticated():
        state.strip_custom_video_overrides()
    _refresh_workouts_ui()
    window.addEventListener("flexary-auth-change", create_proxy(_on_auth_change))
    document.getElementById("loading").close()
    document.getElementById("container").classList.remove("d-none")


asyncio.ensure_future(_bootstrap())
