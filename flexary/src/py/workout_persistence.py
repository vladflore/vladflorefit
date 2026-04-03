import datetime
from uuid import uuid4

from js import localStorage, window
from pyscript import document
from pyweb import pydom

import state
from i18n import t
from models import Workout
from workout_domain import _event_attr


def show_sidebar() -> None:
    if hasattr(window, "flexarySidebar") and window.flexarySidebar:
        window.flexarySidebar.setHidden(False)
        return
    pydom[state.workout_sidebar_el_id][0]._js.classList.remove("d-none")


def hide_sidebar() -> None:
    if hasattr(window, "flexarySidebar") and window.flexarySidebar:
        window.flexarySidebar.setHidden(True)
    else:
        pydom[state.workout_sidebar_el_id][0]._js.classList.add("d-none")
    update_workout_badge()


def update_workout_badge() -> None:
    count = len(state.workouts)
    btn = pydom["#toggle-workout-sidebar"][0]._js
    existing = btn.querySelector(".workout-count-badge")
    if existing:
        existing.remove()
    if count > 0:
        badge = document.createElement("span")
        badge.className = "workout-count-badge"
        badge.textContent = str(count)
        btn.appendChild(badge)


def remove_workout(event) -> None:
    from workout_modal import _show_confirm_popup
    from workout_rendering import render_workouts

    event.stopPropagation()
    anchor = event.target.closest("button") or event.target
    workout_id = _event_attr(event, "data-workout-id")
    if not workout_id:
        return

    def _do():
        for i, w in enumerate(state.workouts):
            if str(w.id) == workout_id:
                del state.workouts[i]
                break
        state.active_workout = None if not state.workouts else state.workouts[-1].id
        state.save_workouts()
        render_workouts(state.workouts)
        update_workout_badge()
        if not state.workouts:
            hide_sidebar()

    target = next((w for w in state.workouts if str(w.id) == workout_id), None)
    if target and target.exercises:
        _show_confirm_popup(anchor, t("remove_workout_confirm"), _do, confirm_label=t("remove_btn"), cancel_label=t("cancel_btn"))
    else:
        _do()


def remove_workouts(event) -> None:
    from workout_modal import _show_confirm_popup

    event.stopPropagation()
    anchor = event.target.closest("button") or event.target

    def _do():
        state.workouts.clear()
        state.active_workout = None
        localStorage.removeItem(state.ls_workouts_key)
        ws_container = pydom["#workout-list-container"][0]
        while ws_container._js.firstChild:
            ws_container._js.removeChild(ws_container._js.firstChild)
        update_workout_badge()
        hide_sidebar()

    if any(w.exercises for w in state.workouts):
        _show_confirm_popup(anchor, t("remove_all_confirm"), _do, confirm_label=t("remove_btn"), cancel_label=t("cancel_btn"))
    else:
        _do()


def add_workout(event) -> None:
    from workout_rendering import render_workouts

    state.active_workout = uuid4()
    w = Workout(state.active_workout, datetime.datetime.now().date(), [])
    state.workouts.append(w)
    state.save_workouts()
    render_workouts(state.workouts)
    update_workout_badge()
