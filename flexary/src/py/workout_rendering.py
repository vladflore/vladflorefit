import asyncio
import datetime
from uuid import UUID

from pyodide.ffi import create_proxy
from pyscript import document
from pyweb import pydom

import state
from i18n import t
from workout_domain import _can_move, _event_attr, toggle_superset
from workout_modal import _fetch_description, _format_break, _show_break_popup, _show_confirm_popup
from workout_persistence import remove_workout


def workout_edit(event) -> None:
    workout_id = _event_attr(event, "data-workout-id")
    if not workout_id:
        return
    state.active_workout = UUID(workout_id)
    for w in state.workouts:
        layover = pydom[f"#workout-layover-{w.id}"][0]
        if w.id == state.active_workout:
            layover._js.classList.add("d-none")
        else:
            layover._js.classList.remove("d-none")


def _make_superset_connector(workout, idx_above, idx_below):
    ex_above = workout.exercises[idx_above]
    ex_below = workout.exercises[idx_below]
    is_linked = bool(ex_above.superset_id and ex_above.superset_id == ex_below.superset_id)

    el = document.createElement("div")
    el.className = "superset-connector " + ("superset-connector--linked" if is_linked else "superset-connector--unlinked")
    el.setAttribute("data-workout-exercise-id", ex_below.internal_id)
    el.setAttribute("data-workout-id", str(workout.id))
    el.title = t("split_superset") if is_linked else t("add_to_superset")

    icon = document.createElement("i")
    icon.className = "bi bi-scissors" if is_linked else "bi bi-link-45deg"
    icon.setAttribute("data-workout-exercise-id", ex_below.internal_id)
    icon.setAttribute("data-workout-id", str(workout.id))

    el.appendChild(icon)
    el.addEventListener("click", create_proxy(toggle_superset))

    if not is_linked:
        id_above = ex_above.internal_id
        id_below = ex_below.internal_id

        def _on_mouseenter(evt):
            for ex_id in [id_above, id_below]:
                node = document.querySelector(f'[data-exercise-item-id="{ex_id}"]')
                if node:
                    node.classList.add("superset-hover-stay")

        def _on_mouseleave(evt):
            for node in document.querySelectorAll(".superset-hover-stay"):
                node.classList.remove("superset-hover-stay")

        el.addEventListener("mouseenter", create_proxy(_on_mouseenter))
        el.addEventListener("mouseleave", create_proxy(_on_mouseleave))

    return el


def _make_break_row(workout, ex_below):
    break_mins = workout.breaks.get(ex_below.internal_id, 0)

    row = document.createElement("div")
    row.className = "connector-break-row" + (" connector-break-row--set" if break_mins else "")

    clock = document.createElement("i")
    clock.className = "bi bi-hourglass-split"
    row.appendChild(clock)

    lbl = document.createElement("span")
    lbl.textContent = f"{_format_break(break_mins)} {t('rest_unit')}" if break_mins else t("add_rest")
    row.appendChild(lbl)

    def _make_break_handler(w, ex_b):
        def _on_click(evt):
            _show_break_popup(row, w, ex_b)
        return _on_click

    row.addEventListener("click", create_proxy(_make_break_handler(workout, ex_below)))
    return row


def render_workouts(workouts: list) -> None:
    from workout_modal import edit_exercise_in_workout, remove_exercise_from_workout

    ws_container = pydom["#workout-list-container"][0]
    while ws_container._js.firstChild:
        ws_container._js.removeChild(ws_container._js.firstChild)

    for w in workouts:
        w_div = state.w_template.clone()
        w_div._js.removeAttribute("id")

        workout_layover = w_div.find("#workout-layover")[0]
        workout_layover._js.setAttribute("id", f"workout-layover-{w.id}")
        if w.id != state.active_workout:
            workout_layover._js.classList.remove("d-none")
        else:
            workout_layover._js.classList.add("d-none")

        workout_edit_btn = workout_layover.find("#workout-edit")[0]
        workout_edit_btn._js.onclick = workout_edit
        workout_edit_btn._js.setAttribute("data-workout-id", str(w.id))
        workout_edit_btn._js.removeAttribute("id")

        workout_edit_btn_icon = workout_layover.find("#workout-edit-icon")[0]
        workout_edit_btn_icon._js.onclick = workout_edit
        workout_edit_btn_icon._js.setAttribute("data-workout-id", str(w.id))
        workout_edit_btn_icon._js.removeAttribute("id")

        w_name = w_div.find("#workout-name")[0]
        w_name._js.value = w.name or ""
        w_name._js.setAttribute("id", f"workout-name-{w.id}")
        w_name._js.setAttribute("data-workout-id", str(w.id))

        def on_name_change(evt):
            workout_id = _event_attr(evt, "data-workout-id")
            if not workout_id:
                return
            w_id = UUID(workout_id)
            for workout in state.workouts:
                if workout.id == w_id:
                    workout.name = evt.target.value.strip()
                    break
            state.save_workouts()

        w_name._js.addEventListener("change", create_proxy(on_name_change))

        w_date = w_div.find("#workout-date")[0]
        w_date._js.value = w.execution_date.strftime("%Y-%m-%d")
        w_date._js.setAttribute("id", f"workout-date-{w.id}")
        w_date._js.setAttribute("data-workout-id", str(w.id))

        def on_date_change(evt):
            if not evt.target.value:
                return
            new_date = datetime.datetime.strptime(evt.target.value, "%Y-%m-%d").date()
            workout_id = _event_attr(evt, "data-workout-id")
            if not workout_id:
                return
            w_id = UUID(workout_id)
            for item in state.workouts:
                if item.id == w_id:
                    item.execution_date = new_date
                    break
            state.save_workouts()

        w_date._js.addEventListener("change", create_proxy(on_date_change))

        w_remove_btn = w_div.find("#workout-remove")[0]
        w_remove_btn._js.onclick = remove_workout
        w_remove_btn._js.setAttribute("data-workout-id", str(w.id))
        w_remove_btn._js.removeAttribute("id")

        w_remove_icon = w_div.find("#workout-remove-icon")[0]
        w_remove_icon._js.onclick = remove_workout
        w_remove_icon._js.setAttribute("data-workout-id", str(w.id))
        w_remove_icon._js.removeAttribute("id")

        w_ul = w_div.find("#workout-items")[0]
        li = w_ul.find("#workout-item")[0]
        current_superset_wrapper = None
        for ei, exercise in enumerate(w.exercises):
            w_li = li if ei == 0 else li.clone()
            w_li._js.removeAttribute("id")
            w_li._js.setAttribute("data-exercise-item-id", exercise.internal_id)

            name_el = document.createElement("div")
            name_el.className = "exercise-item-name"
            name_el.textContent = exercise.name

            rounds = w.superset_rounds.get(exercise.superset_id, 1) if exercise.superset_id else 1
            details_el = document.createElement("div")
            details_el.className = "exercise-item-details"
            details_el.textContent = exercise.detail_str(in_superset=bool(exercise.superset_id))
            if exercise.superset_id and exercise.execution_mismatch(rounds):
                warn = document.createElement("div")
                warn.className = "superset-reps-warning"

                def _mismatch_count(raw):
                    return len([v for v in raw.split(",") if v.strip()]) if raw else 0

                ex_count = max(_mismatch_count(exercise.reps), _mismatch_count(exercise.time), _mismatch_count(exercise.distance))
                warn.textContent = t("mismatch_warning", count=ex_count, rounds=rounds)
                details_el.appendChild(warn)

            item_name_span = w_li.find("#workout-item-name")[0]._js
            item_name_span.innerHTML = ""
            item_name_span.appendChild(name_el)
            item_name_span.appendChild(details_el)
            if exercise.notes:
                notes_el = document.createElement("div")
                notes_el.className = "exercise-item-notes"
                notes_el.textContent = exercise.notes[:60] + "…" if len(exercise.notes) > 60 else exercise.notes
                item_name_span.appendChild(notes_el)

            w_item_move_up = w_li.find("#workout-item-move-up")[0]
            from workout_domain import move_exercise_up, move_exercise_down
            w_item_move_up._js.onclick = move_exercise_up
            w_item_move_up._js.setAttribute("data-workout-exercise-id", exercise.internal_id)
            w_item_move_up._js.setAttribute("data-workout-id", str(w.id))
            if not _can_move(w.exercises, ei, -1):
                w_item_move_up._js.classList.add("disabled")
            else:
                w_item_move_up._js.classList.remove("disabled")

            w_item_move_down = w_li.find("#workout-item-move-down")[0]
            w_item_move_down._js.onclick = move_exercise_down
            w_item_move_down._js.setAttribute("data-workout-exercise-id", exercise.internal_id)
            w_item_move_down._js.setAttribute("data-workout-id", str(w.id))
            if not _can_move(w.exercises, ei, +1):
                w_item_move_down._js.classList.add("disabled")
            else:
                w_item_move_down._js.classList.remove("disabled")

            w_item_edit_icon = w_li.find("#workout-item-edit")[0]
            w_item_edit_icon._js.onclick = edit_exercise_in_workout
            w_item_edit_icon._js.setAttribute("data-exercise-id", str(exercise.id))
            w_item_edit_icon._js.setAttribute("data-workout-exercise-id", exercise.internal_id)
            w_item_edit_icon._js.setAttribute("data-workout-id", str(w.id))

            w_item_remove_icon = w_li.find("#workout-item-remove")[0]
            w_item_remove_icon._js.onclick = remove_exercise_from_workout
            w_item_remove_icon._js.setAttribute("data-exercise-id", str(exercise.id))
            w_item_remove_icon._js.setAttribute("data-workout-exercise-id", exercise.internal_id)
            w_item_remove_icon._js.setAttribute("data-workout-id", str(w.id))

            if exercise.superset_id:
                is_group_start = ei == 0 or w.exercises[ei - 1].superset_id != exercise.superset_id
                if is_group_start:
                    if ei > 0:
                        w_ul._js.appendChild(_make_superset_connector(w, ei - 1, ei))
                        w_ul._js.appendChild(_make_break_row(w, exercise))

                    sid = exercise.superset_id
                    current_superset_wrapper = document.createElement("div")
                    current_superset_wrapper.className = "superset-group"

                    header = document.createElement("div")
                    header.className = "superset-group-header"

                    ss_label = document.createElement("span")
                    ss_label.textContent = t("superset_label")
                    header.appendChild(ss_label)

                    rounds = w.superset_rounds.get(sid, 1)
                    rounds_input = document.createElement("input")
                    rounds_input.type = "number"
                    rounds_input.min = "1"
                    rounds_input.value = str(rounds)
                    rounds_input.className = "superset-rounds-input"
                    rounds_input.title = t("superset_rounds")

                    rounds_label = document.createElement("span")
                    rounds_label.textContent = t("rounds_label")

                    header.appendChild(rounds_input)
                    header.appendChild(rounds_label)
                    current_superset_wrapper.appendChild(header)
                    w_ul._js.appendChild(current_superset_wrapper)

                    def _make_rounds_handler(workout, superset_id):
                        def _on_change(evt):
                            val = evt.target.value
                            if val and int(val) > 0:
                                workout.superset_rounds[superset_id] = int(val)
                                state.save_workouts()
                                render_workouts(state.workouts)
                        return _on_change

                    rounds_input.addEventListener("change", create_proxy(_make_rounds_handler(w, sid)))
                else:
                    current_superset_wrapper.appendChild(_make_superset_connector(w, ei - 1, ei))

                current_superset_wrapper.appendChild(w_li._js)
            else:
                if ei > 0:
                    w_ul._js.appendChild(_make_superset_connector(w, ei - 1, ei))
                    w_ul._js.appendChild(_make_break_row(w, exercise))
                current_superset_wrapper = None
                w_ul.append(w_li)

        count_badge = w_div._js.querySelector(".workout-exercise-count")
        count = len(w.exercises)
        count_badge.textContent = t("ex_count", count=count) if count > 0 else ""

        hint = w_div._js.querySelector(".add-exes-hint")
        if w.exercises:
            w_ul._js.classList.remove("d-none")
            hint.classList.add("d-none")
        else:
            w_ul._js.classList.add("d-none")
            hint.classList.remove("d-none")

        describe_btn = document.createElement("button")
        describe_btn.className = "describe-workout-btn" + ("" if w.exercises else " d-none")
        describe_btn.setAttribute("data-workout-id", str(w.id))
        describe_btn.innerHTML = f'<i class="bi bi-stars"></i><span>{t("describe_workout")}</span>'

        def _make_describe_handler(wid):
            def _on_click(evt):
                target = next((x for x in state.workouts if x.id == wid), None)
                if target and target.description:
                    anchor = evt.target.closest("button") or evt.target
                    _show_confirm_popup(
                        anchor,
                        t("regenerate_confirm"),
                        lambda: asyncio.ensure_future(_fetch_description(wid)),
                        confirm_label=t("yes_btn"),
                        cancel_label=t("no_btn"),
                    )
                else:
                    asyncio.ensure_future(_fetch_description(wid))
            return _on_click

        describe_btn.addEventListener("click", create_proxy(_make_describe_handler(w.id)))
        w_div._js.appendChild(describe_btn)

        ws_container.append(w_div)

    has_mismatch = any(
        ex.superset_id and ex.execution_mismatch(w.superset_rounds.get(ex.superset_id, 1))
        for w in workouts
        for ex in w.exercises
    )
    mismatch_title = t("fix_mismatch") if has_mismatch else ""
    for btn_id in ("download-workouts", "download-ics"):
        btn = document.getElementById(btn_id)
        if btn:
            btn.disabled = has_mismatch
            btn.title = mismatch_title


def add_exercise_to_workout(event) -> None:
    from workout_modal import configure_exercise

    event.stopPropagation()
    card = event.target.closest("[data-exercise-id]")
    exercise_id = card.getAttribute("data-exercise-id")
    exercise_name = card.getAttribute("data-exercise-name")
    configure_exercise(exercise_id, exercise_name)
