import json

from js import localStorage
from pyscript import document
from pyweb import pydom

from models import Workout, workouts_from_json, workouts_to_json

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

ls_workouts_key = "workouts"
ls_filters_key = "filters"
ls_custom_exercises_key = "custom_exercises"


def q(selector, root=document):
    return root.querySelector(selector)


exercises_row = pydom[exercises_row_id][0]
exercise_template = pydom.Element(
    q(exercise_card_template_id).content.querySelector("#card-exercise")
)
w_template = pydom.Element(
    q("#workout-template").content.querySelector("#workout")
)

_raw = localStorage.getItem(ls_workouts_key)
workouts: list[Workout] = workouts_from_json(_raw) if _raw else []
active_workout = workouts[0].id if workouts else None


def save_workouts() -> None:
    localStorage.setItem(ls_workouts_key, workouts_to_json(workouts))


active_category_filters: set[str] = set()
active_body_part_filters: set[str] = set()

_filters_raw = localStorage.getItem(ls_filters_key)
if _filters_raw:
    try:
        _f = json.loads(_filters_raw)
        active_category_filters = set(_f.get("categories", []))
        active_body_part_filters = set(_f.get("body_parts", []))
    except Exception:
        pass

data: list[dict] = []
base_data: list[dict] = []
category_count: dict[str, int] = {}
body_parts_list: list[str] = []

custom_exercises: list[dict] = []
_custom_raw = localStorage.getItem(ls_custom_exercises_key)
if _custom_raw:
    try:
        custom_exercises = json.loads(_custom_raw)
    except Exception:
        pass


def save_custom_exercises() -> None:
    localStorage.setItem(ls_custom_exercises_key, json.dumps(custom_exercises))


def next_custom_id() -> int:
    if not custom_exercises:
        return -1
    return min(int(ex["id"]) for ex in custom_exercises) - 1
