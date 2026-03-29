import asyncio

from pyodide.ffi.wrappers import add_event_listener
from pyodide.http import pyfetch
from pyscript import document
from pyweb import pydom

from common import copyright, current_version, csv_to_json
from js import window
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
from workouts import add_workout, hide_sidebar, render_workouts, remove_workouts, show_sidebar


def show_info(event) -> None:
    with open("info.txt", "r") as f:
        document.getElementById("info-modal-body").innerHTML = f.read()
    document.getElementById("info-modal").showModal()


# ── Initialise exercise library ────────────────────────────────────────────────
state.data = sorted(csv_to_json("exercises.csv"), key=lambda x: x["name"])

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

# ── Render cards + badges (applies any persisted filters) ──────────────────────
update_filters("")

pydom["#skeleton-row"][0]._js.classList.add("d-none")
pydom["#filter-row"][0]._js.classList.remove("d-none")

# ── Footer ─────────────────────────────────────────────────────────────────────
pydom[state.copyright_el_id][0]._js.innerHTML = copyright()
pydom[state.version_el_id][0]._js.innerHTML = current_version()
pydom[state.footer_el_id][0]._js.classList.remove("d-none")

# ── Event listeners ────────────────────────────────────────────────────────────
add_event_listener(document.getElementById(state.download_pdf_btn_id), "click", download_file)
add_event_listener(document.getElementById("download-ics"), "click", download_ics)
add_event_listener(document.getElementById("pdf-download-btn"), "click", download_pdf_with_options)

# ── Initial sidebar state ──────────────────────────────────────────────────────
if state.workouts:
    show_sidebar()
    render_workouts(state.workouts)
else:
    hide_sidebar()


# ── Feature flags ──────────────────────────────────────────────────────────────
async def _apply_feature_flags() -> None:
    try:
        resp = await pyfetch(f"{window.API_BASE}/api/feature_flags")
        flags = await resp.json()
        if flags.get("describe_workout", False):
            document.body.classList.add("feature-describe")
    except Exception:
        pass  # flags endpoint unreachable — all features stay hidden


asyncio.ensure_future(_apply_feature_flags())
