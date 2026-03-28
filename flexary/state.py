from js import localStorage
from pyscript import document
from pyweb import pydom

import datetime  # noqa: F401 — needed in eval() scope
from uuid import UUID  # noqa: F401 — needed in eval() scope
from models import Exercise, Workout  # noqa: F401 — needed in eval() scope

# ── Element selectors ──────────────────────────────────────────────────────────
exercises_row_id = "#exercises-row"
exercise_card_template_id = "#exercise-card-template"
copyright_el_id = "#copyright"
version_el_id = "#version"
footer_el_id = "#footer"
workout_sidebar_el_id = "#workout-sidebar"
exercises_per_category_badges_row_id = "#exercises-per-category-badges-row"
exercises_per_body_part_badges_row_id = "#exercises-per-body-part-badges-row"
download_pdf_btn_id = "download-workouts"
pdf_color_modal_id = "pdf-color-modal"

# ── localStorage key ───────────────────────────────────────────────────────────
ls_workouts_key = "workouts"


# ── DOM helper ─────────────────────────────────────────────────────────────────
def q(selector, root=document):
    return root.querySelector(selector)


# ── Cached DOM references ──────────────────────────────────────────────────────
exercises_row = pydom[exercises_row_id][0]
exercise_template = pydom.Element(
    q(exercise_card_template_id).content.querySelector("#card-exercise")
)
w_template = pydom.Element(
    q("#workout-template").content.querySelector("#workout")
)

# ── Workout state ──────────────────────────────────────────────────────────────
_raw = localStorage.getItem(ls_workouts_key)
workouts: list[Workout] = eval(_raw if _raw else "[]")
active_workout = workouts[0].id if workouts else None

# ── Filter state ───────────────────────────────────────────────────────────────
active_category_filters: set[str] = set()
active_body_part_filters: set[str] = set()

# ── Exercise library (populated during init in main.py) ────────────────────────
data: list[dict] = []
category_count: dict[str, int] = {}
body_parts_list: list[str] = []
