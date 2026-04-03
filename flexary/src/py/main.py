import asyncio

from pyodide.ffi.wrappers import add_event_listener
from pyodide.http import pyfetch
from pyscript import document
from pyweb import pydom

import catalog
from common import copyright, current_version
from js import window
from i18n import apply_html_translations
import state
from filters import (
    clear_filters,
    update as update_filters,
)
from pdf import download_file, download_pdf_with_options
from ics import download_ics
from workouts import add_workout, hide_sidebar, render_workouts, remove_workouts, update_workout_badge
from custom_exercises import open_add_custom_modal


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

add_event_listener(document.getElementById(state.download_pdf_btn_id), "click", download_file)
add_event_listener(document.getElementById("download-ics"), "click", download_ics)
add_event_listener(document.getElementById("pdf-download-btn"), "click", download_pdf_with_options)

if state.workouts:
    render_workouts(state.workouts)
    update_workout_badge()
else:
    hide_sidebar()


async def _apply_feature_flags() -> None:
    try:
        resp = await pyfetch(f"{window.API_BASE}/api/feature_flags")
        flags = await resp.json()
        if flags.get("describe_workout", False):
            document.body.classList.add("feature-describe")
    except Exception:
        pass


asyncio.ensure_future(_apply_feature_flags())

document.getElementById("loading").close()
document.getElementById("container").classList.remove("d-none")
