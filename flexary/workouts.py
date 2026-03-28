import datetime
from uuid import UUID, uuid4

from js import localStorage
from pyodide.ffi import create_proxy
from pyscript import document
from pyweb import pydom

import state
from models import Exercise, Workout


def show_sidebar() -> None:
    pydom[state.workout_sidebar_el_id][0]._js.classList.remove("d-none")
    pydom["#toggle-workout-sidebar"][0]._js.innerHTML = '<i class="bi bi-x-lg"></i>'
    pydom["#toggle-workout-sidebar"][0]._js.title = "Hide Workouts"


def hide_sidebar() -> None:
    pydom[state.workout_sidebar_el_id][0]._js.classList.add("d-none")
    pydom["#toggle-workout-sidebar"][0]._js.innerHTML = '<i class="bi bi-list"></i>'
    pydom["#toggle-workout-sidebar"][0]._js.title = "Show Workouts"


def workout_edit(event) -> None:
    state.active_workout = UUID(event.target.getAttribute("data-workout-id"))
    for w in state.workouts:
        layover = pydom[f"#workout-layover-{w.id}"][0]
        if w.id == state.active_workout:
            layover._js.classList.add("d-none")
        else:
            layover._js.classList.remove("d-none")


def render_workouts(workouts: list) -> None:
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

        w_date = w_div.find("#workout-date")[0]
        w_date._js.value = w.execution_date.strftime("%Y-%m-%d")
        w_date._js.setAttribute("id", f"workout-date-{w.id}")
        w_date._js.setAttribute("data-workout-id", str(w.id))

        def on_date_change(evt):
            new_date = datetime.datetime.strptime(evt.target.value, "%Y-%m-%d").date()
            w_id = UUID(evt.target.getAttribute("data-workout-id"))
            for w in state.workouts:
                if w.id == w_id:
                    w.execution_date = new_date
                    break
            localStorage.setItem(state.ls_workouts_key, state.workouts)

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
        for ei, exercise in enumerate(w.exercises):
            w_li = li if ei == 0 else li.clone()
            w_li._js.removeAttribute("id")
            details_str = exercise.detail_str()
            notes_html = (
                f'<div class="exercise-item-notes">{exercise.notes}</div>'
                if exercise.notes else ""
            )
            w_li.find("#workout-item-name")[0]._js.innerHTML = (
                f'<div class="exercise-item-name">{exercise.name}</div>'
                f'<div class="exercise-item-details">{details_str}</div>'
                f'{notes_html}'
            )
            w_item_move_up = w_li.find("#workout-item-move-up")[0]
            w_item_move_up._js.onclick = move_exercise_up
            w_item_move_up._js.setAttribute("data-workout-exercise-id", exercise.internal_id)
            w_item_move_up._js.setAttribute("data-workout-id", str(w.id))
            if ei == 0:
                w_item_move_up._js.classList.add("disabled")
            else:
                w_item_move_up._js.classList.remove("disabled")

            w_item_move_down = w_li.find("#workout-item-move-down")[0]
            w_item_move_down._js.onclick = move_exercise_down
            w_item_move_down._js.setAttribute("data-workout-exercise-id", exercise.internal_id)
            w_item_move_down._js.setAttribute("data-workout-id", str(w.id))
            if ei == len(w.exercises) - 1:
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
            w_item_remove_icon._js.setAttribute("data-exercise-id", exercise.id)
            w_item_remove_icon._js.setAttribute("data-workout-exercise-id", exercise.internal_id)
            w_item_remove_icon._js.setAttribute("data-workout-id", str(w.id))
            w_ul.append(w_li)

        count_badge = w_div._js.querySelector(".workout-exercise-count")
        count = len(w.exercises)
        count_badge.textContent = f"{count} ex" if count > 0 else ""

        hint = w_div._js.querySelector(".add-exes-hint")
        if w.exercises:
            w_ul._js.classList.remove("d-none")
            hint.classList.add("d-none")
        else:
            w_ul._js.classList.add("d-none")
            hint.classList.remove("d-none")

        ws_container.append(w_div)


def add_exercise_to_workout(event) -> None:
    event.stopPropagation()
    card = event.target.parentElement.parentElement.parentElement.parentElement
    exercise_id = card.getAttribute("data-exercise-id")
    exercise_name = card.getAttribute("data-exercise-name")
    configure_exercise(exercise_id, exercise_name)


def configure_exercise(exercise_id: str, exercise_name: str) -> None:
    overlay = document.createElement("div")
    overlay.classList.add("exercise-overlay")
    overlay.setAttribute("onclick", "event.stopPropagation()")
    overlay.style.position = "fixed"
    overlay.style.top = "0"
    overlay.style.left = "0"
    overlay.style.width = "100%"
    overlay.style.height = "100%"
    overlay.style.backgroundColor = "rgba(0,0,0,0.7)"
    overlay.style.display = "flex"
    overlay.style.alignItems = "center"
    overlay.style.justifyContent = "center"
    overlay.style.zIndex = "1000"

    modal = document.createElement("div")
    modal.style.backgroundColor = "#1a1a1a"
    modal.style.border = "1px solid #444"
    modal.style.borderRadius = "8px"
    modal.style.padding = "20px"
    modal.style.width = "320px"
    modal.style.display = "flex"
    modal.style.flexDirection = "column"
    modal.style.gap = "12px"
    modal.style.color = "white"

    title = document.createElement("div")
    title.textContent = exercise_name
    title.style.fontWeight = "bold"
    title.style.fontSize = "0.95rem"
    title.style.color = "#ba945e"
    title.style.marginBottom = "4px"
    modal.appendChild(title)

    inputs_container = document.createElement("div")
    inputs_container.style.display = "flex"
    inputs_container.style.flexDirection = "column"
    inputs_container.style.gap = "8px"
    inputs_container.style.width = "100%"

    def make_group(label_text, input_el):
        group = document.createElement("div")
        group.style.display = "flex"
        group.style.flexDirection = "column"
        group.style.gap = "2px"
        label = document.createElement("label")
        label.textContent = label_text
        label.style.fontSize = "0.75rem"
        label.style.color = "rgba(255,255,255,0.75)"
        input_el.style.width = "100%"
        input_el.style.fontSize = "0.8rem"
        input_el.style.height = "26px"
        input_el.style.padding = "2px 6px"
        input_el.style.borderRadius = "4px"
        input_el.style.border = "1px solid rgba(255,255,255,0.2)"
        input_el.style.backgroundColor = "rgba(255,255,255,0.1)"
        input_el.style.color = "#fff"
        group.appendChild(label)
        group.appendChild(input_el)
        return group

    input_sets = document.createElement("input")
    input_sets.type = "number"
    input_sets.min = "1"
    input_sets.value = "1"

    input_reps_per_set = document.createElement("input")
    input_reps_per_set.type = "text"
    input_reps_per_set.placeholder = "e.g. 10,12,15"

    input_time_per_set = document.createElement("input")
    input_time_per_set.type = "text"
    input_time_per_set.placeholder = "e.g. 00:01:30"

    input_distance = document.createElement("input")
    input_distance.type = "text"
    input_distance.placeholder = "e.g. 400m, 5km"

    input_notes = document.createElement("textarea")
    input_notes.placeholder = "Optional notes…"
    input_notes.rows = "2"
    input_notes.style.resize = "none"
    input_notes.style.height = "auto"

    inputs_container.appendChild(make_group("Sets", input_sets))
    inputs_container.appendChild(make_group("Reps per set (comma separated, optional)", input_reps_per_set))
    inputs_container.appendChild(make_group("Time per set — hh:mm:ss (optional)", input_time_per_set))
    inputs_container.appendChild(make_group("Distance (optional)", input_distance))
    inputs_container.appendChild(make_group("Notes (optional)", input_notes))

    warning_el = document.createElement("div")
    warning_el.style.display = "none"
    warning_el.style.color = "#f87171"
    warning_el.style.fontSize = "0.75rem"
    warning_el.style.marginTop = "-4px"

    buttons_container = document.createElement("div")
    buttons_container.style.display = "flex"
    buttons_container.style.gap = "8px"
    buttons_container.style.marginTop = "4px"

    confirm_btn = document.createElement("button")
    confirm_btn.textContent = "Add"
    confirm_btn.classList.add("btn", "btn-outline-gold", "btn-sm")
    confirm_btn.style.flex = "1"
    confirm_btn.style.fontSize = "0.8rem"

    close_btn = document.createElement("button")
    close_btn.textContent = "Cancel"
    close_btn.classList.add("btn", "btn-outline-secondary", "btn-sm")
    close_btn.style.flex = "1"
    close_btn.style.fontSize = "0.8rem"
    close_btn.onclick = lambda evt: overlay.remove()

    buttons_container.appendChild(confirm_btn)
    buttons_container.appendChild(close_btn)
    modal.appendChild(inputs_container)
    modal.appendChild(warning_el)
    modal.appendChild(buttons_container)
    overlay.appendChild(modal)
    document.body.appendChild(overlay)

    def on_confirm_click(evt):
        sets_val = input_sets.value
        reps_val = input_reps_per_set.value
        time_val = input_time_per_set.value
        distance_val = input_distance.value.strip()
        notes_val = input_notes.value.strip()

        warning_el.style.display = "none"

        if not sets_val:
            return
        sets = int(sets_val)

        if reps_val:
            reps = [v for r in reps_val.split(",") if (v := r.strip()) and v.isdigit()]
            if len(reps) != sets:
                warning_el.textContent = f"Reps count ({len(reps)}) must match number of sets ({sets})."
                warning_el.style.display = "block"
                return

        if time_val:
            time_parts = time_val.split(":")
            if len(time_parts) != 3 or not all(part.isdigit() for part in time_parts):
                return
            if any(int(part) < 0 for part in time_parts):
                return

        ex = Exercise(int(exercise_id), str(uuid4()), exercise_name, sets, reps_val, time_val, distance_val, notes_val)

        if state.active_workout is None:
            state.active_workout = uuid4()
            w = Workout(state.active_workout, datetime.datetime.now().date(), [ex])
            state.workouts.append(w)
        else:
            for w in state.workouts:
                if w.id == state.active_workout:
                    w.exercises.append(ex)
                    break

        localStorage.setItem(state.ls_workouts_key, state.workouts)
        show_sidebar()
        render_workouts(state.workouts)
        overlay.remove()

    confirm_btn.onclick = on_confirm_click


def move_exercise_up(event) -> None:
    workout_ex_id = event.target.getAttribute("data-workout-exercise-id")
    workout_id = event.target.getAttribute("data-workout-id")
    for w in state.workouts:
        if str(w.id) == workout_id:
            for j, ex in enumerate(w.exercises):
                if ex.internal_id == workout_ex_id and j > 0:
                    w.exercises[j], w.exercises[j - 1] = w.exercises[j - 1], w.exercises[j]
                    break
            break
    localStorage.setItem(state.ls_workouts_key, state.workouts)
    render_workouts(state.workouts)


def move_exercise_down(event) -> None:
    workout_ex_id = event.target.getAttribute("data-workout-exercise-id")
    workout_id = event.target.getAttribute("data-workout-id")
    for w in state.workouts:
        if str(w.id) == workout_id:
            for j, ex in enumerate(w.exercises):
                if ex.internal_id == workout_ex_id and j < len(w.exercises) - 1:
                    w.exercises[j], w.exercises[j + 1] = w.exercises[j + 1], w.exercises[j]
                    break
            break
    localStorage.setItem(state.ls_workouts_key, state.workouts)
    render_workouts(state.workouts)


def edit_exercise_in_workout(event) -> None:
    workout_ex_id = event.target.getAttribute("data-workout-exercise-id")
    workout_id = event.target.getAttribute("data-workout-id")

    target_ex = None
    target_workout = None
    for w in state.workouts:
        if str(w.id) == workout_id:
            target_workout = w
            for ex in w.exercises:
                if ex.internal_id == workout_ex_id:
                    target_ex = ex
                    break
            break

    if target_ex is None or target_workout is None:
        return

    overlay = document.createElement("div")
    overlay.classList.add("exercise-edit-overlay")
    overlay.setAttribute("onclick", "event.stopPropagation()")
    overlay.style.position = "fixed"
    overlay.style.top = "0"
    overlay.style.left = "0"
    overlay.style.width = "100%"
    overlay.style.height = "100%"
    overlay.style.backgroundColor = "rgba(0,0,0,0.7)"
    overlay.style.display = "flex"
    overlay.style.alignItems = "center"
    overlay.style.justifyContent = "center"
    overlay.style.zIndex = "1000"

    modal = document.createElement("div")
    modal.style.backgroundColor = "#1a1a1a"
    modal.style.border = "1px solid #444"
    modal.style.borderRadius = "8px"
    modal.style.padding = "20px"
    modal.style.width = "320px"
    modal.style.display = "flex"
    modal.style.flexDirection = "column"
    modal.style.gap = "12px"
    modal.style.color = "white"

    title = document.createElement("div")
    title.textContent = f"Edit: {target_ex.name}"
    title.style.fontWeight = "bold"
    title.style.fontSize = "0.95rem"
    title.style.color = "#ba945e"
    title.style.marginBottom = "4px"
    modal.appendChild(title)

    def make_group(label_text, input_el):
        group = document.createElement("div")
        group.style.display = "flex"
        group.style.flexDirection = "column"
        group.style.gap = "2px"
        label = document.createElement("label")
        label.textContent = label_text
        label.style.fontSize = "0.75rem"
        label.style.color = "rgba(255,255,255,0.75)"
        input_el.style.width = "100%"
        input_el.style.fontSize = "0.8rem"
        input_el.style.height = "26px"
        input_el.style.padding = "2px 6px"
        input_el.style.borderRadius = "4px"
        input_el.style.border = "1px solid rgba(255,255,255,0.2)"
        input_el.style.backgroundColor = "rgba(255,255,255,0.1)"
        input_el.style.color = "#fff"
        group.appendChild(label)
        group.appendChild(input_el)
        return group

    input_sets = document.createElement("input")
    input_sets.type = "number"
    input_sets.min = "1"
    input_sets.value = str(target_ex.sets)

    input_reps = document.createElement("input")
    input_reps.type = "text"
    input_reps.placeholder = "e.g. 10,12,15"
    input_reps.value = target_ex.reps or ""

    input_time = document.createElement("input")
    input_time.type = "text"
    input_time.placeholder = "e.g. 00:01:30"
    input_time.value = target_ex.time or ""

    input_distance = document.createElement("input")
    input_distance.type = "text"
    input_distance.placeholder = "e.g. 400m, 5km"
    input_distance.value = target_ex.distance or ""

    input_notes = document.createElement("textarea")
    input_notes.placeholder = "Optional notes…"
    input_notes.rows = "2"
    input_notes.style.resize = "none"
    input_notes.style.height = "auto"
    input_notes.value = target_ex.notes or ""

    modal.appendChild(make_group("Sets", input_sets))
    modal.appendChild(make_group("Reps per set (comma separated, optional)", input_reps))
    modal.appendChild(make_group("Time per set — hh:mm:ss (optional)", input_time))
    modal.appendChild(make_group("Distance (optional)", input_distance))

    notes_group = make_group("Notes (optional)", input_notes)
    input_notes.style.height = "auto"
    modal.appendChild(notes_group)

    buttons_container = document.createElement("div")
    buttons_container.style.display = "flex"
    buttons_container.style.gap = "8px"
    buttons_container.style.marginTop = "4px"

    confirm_btn = document.createElement("button")
    confirm_btn.textContent = "Save"
    confirm_btn.classList.add("btn", "btn-outline-gold", "btn-sm")
    confirm_btn.style.flex = "1"
    confirm_btn.style.fontSize = "0.8rem"

    cancel_btn = document.createElement("button")
    cancel_btn.textContent = "Cancel"
    cancel_btn.classList.add("btn", "btn-outline-secondary", "btn-sm")
    cancel_btn.style.flex = "1"
    cancel_btn.style.fontSize = "0.8rem"
    cancel_btn.onclick = lambda evt: overlay.remove()

    warning_el = document.createElement("div")
    warning_el.style.display = "none"
    warning_el.style.color = "#f87171"
    warning_el.style.fontSize = "0.75rem"
    warning_el.style.marginTop = "-4px"

    buttons_container.appendChild(confirm_btn)
    buttons_container.appendChild(cancel_btn)
    modal.appendChild(warning_el)
    modal.appendChild(buttons_container)
    overlay.appendChild(modal)
    document.body.appendChild(overlay)

    def on_save(evt):
        sets_val = input_sets.value
        reps_val = input_reps.value
        time_val = input_time.value
        distance_val = input_distance.value.strip()
        notes_val = input_notes.value.strip()

        warning_el.style.display = "none"

        if not sets_val:
            return
        sets = int(sets_val)

        if reps_val:
            reps = [v for r in reps_val.split(",") if (v := r.strip()) and v.isdigit()]
            if len(reps) != sets:
                warning_el.textContent = f"Reps count ({len(reps)}) must match number of sets ({sets})."
                warning_el.style.display = "block"
                return

        if time_val:
            time_parts = time_val.split(":")
            if len(time_parts) != 3 or not all(part.isdigit() for part in time_parts):
                return
            if any(int(part) < 0 for part in time_parts):
                return

        target_ex.sets = sets
        target_ex.reps = reps_val
        target_ex.time = time_val
        target_ex.distance = distance_val
        target_ex.notes = notes_val

        localStorage.setItem(state.ls_workouts_key, state.workouts)
        render_workouts(state.workouts)
        overlay.remove()

    confirm_btn.onclick = on_save


def remove_exercise_from_workout(event) -> None:
    ex_id = event.target.getAttribute("data-exercise-id")
    workout_ex_id = event.target.getAttribute("data-workout-exercise-id")
    workout_id = event.target.getAttribute("data-workout-id")

    for w in state.workouts:
        if str(w.id) == workout_id:
            for j, ex in enumerate(w.exercises):
                if ex.id == int(ex_id) and ex.internal_id == workout_ex_id:
                    del w.exercises[j]
                    break
            break

    localStorage.setItem(state.ls_workouts_key, state.workouts)
    render_workouts(state.workouts)
    if not state.workouts:
        state.active_workout = None
        hide_sidebar()


def remove_workout(event) -> None:
    workout_id = event.target.getAttribute("data-workout-id")
    for i, w in enumerate(state.workouts):
        if str(w.id) == workout_id:
            del state.workouts[i]
            break
    state.active_workout = None if not state.workouts else state.workouts[-1].id
    localStorage.setItem(state.ls_workouts_key, state.workouts)
    render_workouts(state.workouts)
    if not state.workouts:
        hide_sidebar()


def remove_workouts(event) -> None:
    state.workouts.clear()
    state.active_workout = None
    localStorage.removeItem(state.ls_workouts_key)
    ws_container = pydom["#workout-list-container"][0]
    while ws_container._js.firstChild:
        ws_container._js.removeChild(ws_container._js.firstChild)
    hide_sidebar()


def add_workout(event) -> None:
    state.active_workout = uuid4()
    w = Workout(state.active_workout, datetime.datetime.now().date(), [])
    state.workouts.append(w)
    localStorage.setItem(state.ls_workouts_key, state.workouts)
    render_workouts(state.workouts)
