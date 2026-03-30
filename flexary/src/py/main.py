import asyncio

from pyodide.ffi.wrappers import add_event_listener
from pyodide.http import pyfetch
from pyscript import document
from pyweb import pydom

from common import copyright, current_version, csv_to_json
from js import window
from i18n import apply_html_translations
import state
from filters import (
    attach_body_part_filter_listeners,
    attach_category_filter_listeners,
    build_body_part_badges,
    build_category_badges,
    clear_filters,
    update as update_filters,
    update_exercise_stats,
)
from pdf import download_file, download_pdf_with_options
from ics import download_ics
from workouts import add_workout, hide_sidebar, render_workouts, remove_workouts, update_workout_badge
from custom_exercises import open_add_custom_modal


def show_info(event) -> None:
    document.getElementById("info-modal").showModal()


apply_html_translations()

state.base_data = sorted(csv_to_json("exercises.csv"), key=lambda x: x["name"])
state.data = sorted(state.custom_exercises, key=lambda x: x["name"]) + state.base_data

body_parts_seen: set[str] = set()
for exercise_data in state.data:
    for category in exercise_data["category"].split(","):
        category = category.strip()
        state.category_count[category] = state.category_count.get(category, 0) + 1
    for bp in exercise_data["body_parts"].split(","):
        bp = bp.strip()
        if bp and bp not in body_parts_seen:
            body_parts_seen.add(bp)
            state.body_parts_list.append(bp)
state.body_parts_list.sort()

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
