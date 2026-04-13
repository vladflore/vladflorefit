import json

import catalog
from js import localStorage, window
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
exercises_per_primary_muscle_badges_row_id = "#exercises-per-primary-muscle-badges-row"
download_pdf_btn_id = "download-workouts"
pdf_color_modal_id = "pdf-color-modal"

ls_workouts_key = "flexary_workouts"
ls_filters_key = "flexary_filters"
ls_custom_exercises_key = "flexary_custom_exercises"
ls_auth_session_key = "flexary_auth_session"


def q(selector, root=document):
    return root.querySelector(selector)


exercises_row = pydom[exercises_row_id][0] if pydom[exercises_row_id] else None
exercise_template = (
    pydom.Element(q(exercise_card_template_id).content.querySelector("#card-exercise"))
    if q(exercise_card_template_id)
    else None
)
w_template = (
    pydom.Element(q("#workout-template").content.querySelector("#workout"))
    if q("#workout-template")
    else None
)

_raw = localStorage.getItem(ls_workouts_key)
workouts: list[Workout] = workouts_from_json(_raw) if _raw else []
active_workout = workouts[0].id if workouts else None


def save_workouts() -> None:
    localStorage.setItem(ls_workouts_key, workouts_to_json(workouts))


def is_authenticated() -> bool:
    try:
        if (
            hasattr(window, "flexaryAuth")
            and window.flexaryAuth
            and window.flexaryAuth.state
            and window.flexaryAuth.state.user
        ):
            return True
    except Exception:
        pass
    return bool(localStorage.getItem(ls_auth_session_key))


def strip_custom_video_overrides() -> bool:
    changed = False
    for workout in workouts:
        for exercise in workout.exercises:
            if getattr(exercise, "custom_video_id", ""):
                exercise.custom_video_id = ""
                changed = True
    if changed:
        save_workouts()
    return changed


def flush_workout_inputs() -> None:
    """Read name/date inputs directly from the DOM so pending unsaved edits are captured
    before a download, bypassing change-event timing issues."""
    import datetime
    changed = False
    for w in workouts:
        name_el = document.getElementById(f"workout-name-{w.id}")
        if name_el:
            val = str(name_el.value).strip()
            if val != w.name:
                w.name = val
                changed = True
        date_el = document.getElementById(f"workout-date-{w.id}")
        if date_el and date_el.value:
            try:
                new_date = datetime.datetime.strptime(str(date_el.value), "%Y-%m-%d").date()
                if new_date != w.execution_date:
                    w.execution_date = new_date
                    changed = True
            except Exception:
                pass
    save_workouts()


active_category_filters: set[str] = set()
active_body_part_filters: set[str] = set()
active_primary_muscle_filters: set[str] = set()

_filters_raw = localStorage.getItem(ls_filters_key)
if _filters_raw:
    try:
        _f = json.loads(_filters_raw)
        active_category_filters = set(c for c in _f.get("categories", []) if c is not None)
        active_body_part_filters = set(c for c in _f.get("body_parts", []) if c is not None)
        active_primary_muscle_filters = set(c for c in _f.get("primary_muscles", []) if c is not None)
    except Exception:
        pass

data: list[dict] = []
base_data: list[dict] = []
category_count: dict[str, int] = {}
body_parts_list: list[str] = []
primary_muscles_list: list[str] = []

custom_exercises: list[dict] = []
_custom_raw = localStorage.getItem(ls_custom_exercises_key)
if _custom_raw:
    try:
        custom_exercises = catalog.parse_custom_exercises(_custom_raw)
    except Exception:
        pass


def save_custom_exercises() -> None:
    localStorage.setItem(ls_custom_exercises_key, json.dumps(custom_exercises))


def next_custom_id() -> int:
    if not custom_exercises:
        return -1
    return min(int(ex["id"]) for ex in custom_exercises) - 1


if workouts and not is_authenticated():
    strip_custom_video_overrides()
