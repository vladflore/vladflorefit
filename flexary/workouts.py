import datetime
from html import escape as html_escape
from uuid import UUID, uuid4

from js import localStorage
from pyodide.ffi import create_proxy
from pyscript import document
from pyweb import pydom

import state
from models import Exercise, Workout


# ── DOM helpers ────────────────────────────────────────────────────────────────

def _make_input_group(label_text: str, input_el):
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
    if input_el.tagName.lower() != "textarea":
        input_el.style.height = "26px"
    input_el.style.padding = "2px 6px"
    input_el.style.borderRadius = "4px"
    input_el.style.border = "1px solid rgba(255,255,255,0.2)"
    input_el.style.backgroundColor = "rgba(255,255,255,0.1)"
    input_el.style.color = "#fff"
    group.appendChild(label)
    group.appendChild(input_el)
    return group


def _find_exercise(workout_id: str, workout_ex_id: str):
    """Return (workout, exercise, index) or (None, None, -1)."""
    for w in state.workouts:
        if str(w.id) == workout_id:
            for j, ex in enumerate(w.exercises):
                if ex.internal_id == workout_ex_id:
                    return w, ex, j
    return None, None, -1


def _make_warning_el():
    el = document.createElement("div")
    el.style.display = "none"
    el.style.color = "#f87171"
    el.style.fontSize = "0.75rem"
    el.style.marginTop = "-4px"
    return el


def _show_warning(el, msg: str) -> None:
    el.textContent = msg
    el.style.display = "block"


def _show_confirm_popup(anchor_el, message, on_confirm) -> None:
    existing = document.querySelector(".confirm-popup-overlay")
    if existing:
        existing.remove()

    overlay = document.createElement("div")
    overlay.className = "confirm-popup-overlay"

    popup = document.createElement("div")
    popup.className = "confirm-popup"

    msg_el = document.createElement("p")
    msg_el.className = "confirm-popup-message"
    msg_el.textContent = message
    popup.appendChild(msg_el)

    btn_row = document.createElement("div")
    btn_row.className = "confirm-popup-actions"

    cancel_btn = document.createElement("button")
    cancel_btn.textContent = "Cancel"
    cancel_btn.className = "confirm-popup-cancel"

    confirm_btn = document.createElement("button")
    confirm_btn.textContent = "Remove"
    confirm_btn.className = "confirm-popup-confirm"

    def _confirm(evt):
        evt.stopPropagation()
        overlay.remove()
        on_confirm()

    def _cancel(evt):
        evt.stopPropagation()
        overlay.remove()

    def _dismiss(evt):
        if evt.target == overlay:
            overlay.remove()

    confirm_btn.addEventListener("click", create_proxy(_confirm))
    cancel_btn.addEventListener("click", create_proxy(_cancel))
    overlay.addEventListener("click", create_proxy(_dismiss))

    btn_row.appendChild(cancel_btn)
    btn_row.appendChild(confirm_btn)
    popup.appendChild(btn_row)
    overlay.appendChild(popup)
    document.body.appendChild(overlay)

    rect = anchor_el.getBoundingClientRect()
    popup_w = 210
    left = rect.left + rect.width / 2 - popup_w / 2
    left = max(8, min(left, document.documentElement.clientWidth - popup_w - 8))
    popup.style.width = f"{popup_w}px"
    popup.style.left = f"{left}px"
    popup.style.top = f"{rect.top - 8}px"
    popup.style.transform = "translateY(-100%)"


def _validate_exercise_inputs(sets_val, reps_val, time_val, sets, warning_el) -> bool:
    if not sets_val:
        _show_warning(warning_el, "Number of sets is required.")
        return False
    if reps_val:
        reps = [v for r in reps_val.split(",") if (v := r.strip()) and v.isdigit()]
        if len(reps) != sets:
            _show_warning(warning_el, f"Reps count ({len(reps)}) must match number of sets ({sets}).")
            return False
    if time_val:
        time_parts = time_val.split(":")
        if len(time_parts) != 3 or not all(part.isdigit() for part in time_parts):
            _show_warning(warning_el, "Time must be in hh:mm:ss format.")
            return False
        if any(int(part) < 0 for part in time_parts):
            _show_warning(warning_el, "Time values cannot be negative.")
            return False
    return True


# ── Sidebar visibility ─────────────────────────────────────────────────────────

def show_sidebar() -> None:
    pydom[state.workout_sidebar_el_id][0]._js.classList.remove("d-none")
    pydom["#toggle-workout-sidebar"][0]._js.innerHTML = '<i class="bi bi-x-lg"></i>'
    pydom["#toggle-workout-sidebar"][0]._js.title = "Hide Workouts"


def hide_sidebar() -> None:
    pydom[state.workout_sidebar_el_id][0]._js.classList.add("d-none")
    pydom["#toggle-workout-sidebar"][0]._js.innerHTML = '<i class="bi bi-list"></i>'
    pydom["#toggle-workout-sidebar"][0]._js.title = "Show Workouts"


# ── Workout rendering ──────────────────────────────────────────────────────────

def _make_superset_connector(workout, idx_above, idx_below):
    ex_above = workout.exercises[idx_above]
    ex_below = workout.exercises[idx_below]
    is_linked = bool(ex_above.superset_id and ex_above.superset_id == ex_below.superset_id)

    el = document.createElement("div")
    el.className = "superset-connector " + ("superset-connector--linked" if is_linked else "superset-connector--unlinked")
    el.setAttribute("data-workout-exercise-id", ex_below.internal_id)
    el.setAttribute("data-workout-id", str(workout.id))
    el.title = "Split superset here" if is_linked else "Add to superset"

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
            if not evt.target.value:
                return
            new_date = datetime.datetime.strptime(evt.target.value, "%Y-%m-%d").date()
            w_id = UUID(evt.target.getAttribute("data-workout-id"))
            for w in state.workouts:
                if w.id == w_id:
                    w.execution_date = new_date
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
            if exercise.superset_id and exercise.reps_mismatch(rounds):
                warn = document.createElement("div")
                warn.className = "superset-reps-warning"
                reps_count = len([v for v in exercise.reps.split(",") if v.strip()])
                warn.textContent = f"⚠ Exercise configured with {reps_count} executions but the superset has {rounds} rounds — edit either the exercise's configuration or the superset's number of rounds so that they match"
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

                    sid = exercise.superset_id
                    current_superset_wrapper = document.createElement("div")
                    current_superset_wrapper.className = "superset-group"

                    header = document.createElement("div")
                    header.className = "superset-group-header"

                    ss_label = document.createElement("span")
                    ss_label.textContent = "Superset"
                    header.appendChild(ss_label)

                    rounds = w.superset_rounds.get(sid, 1)
                    rounds_input = document.createElement("input")
                    rounds_input.type = "number"
                    rounds_input.min = "1"
                    rounds_input.value = str(rounds)
                    rounds_input.className = "superset-rounds-input"
                    rounds_input.title = "Superset rounds"

                    rounds_label = document.createElement("span")
                    rounds_label.textContent = "× rounds"

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
                current_superset_wrapper = None
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

    has_mismatch = any(
        ex.superset_id and ex.reps_mismatch(w.superset_rounds.get(ex.superset_id, 1))
        for w in workouts
        for ex in w.exercises
    )
    mismatch_title = "Fix reps/rounds mismatches before downloading" if has_mismatch else ""
    for btn_id in ("download-workouts", "download-ics"):
        btn = document.getElementById(btn_id)
        if btn:
            btn.disabled = has_mismatch
            btn.title = mismatch_title


# ── Add / configure exercise ───────────────────────────────────────────────────

def add_exercise_to_workout(event) -> None:
    event.stopPropagation()
    card = event.target.closest("[data-exercise-id]")
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

    input_sets = document.createElement("input")
    input_sets.type = "number"
    input_sets.min = "1"
    input_sets.value = "1"

    input_reps = document.createElement("input")
    input_reps.type = "text"
    input_reps.placeholder = "e.g. 10,12,15"

    input_time = document.createElement("input")
    input_time.type = "text"
    input_time.placeholder = "e.g. 00:01:30"

    input_distance = document.createElement("input")
    input_distance.type = "text"
    input_distance.placeholder = "e.g. 400m, 5km"

    input_notes = document.createElement("textarea")
    input_notes.placeholder = "Optional notes…"
    input_notes.rows = "3"
    input_notes.style.resize = "vertical"

    inputs_container.appendChild(_make_input_group("Sets", input_sets))
    inputs_container.appendChild(_make_input_group("Reps per set (comma separated, optional)", input_reps))
    inputs_container.appendChild(_make_input_group("Time per set — hh:mm:ss (optional)", input_time))
    inputs_container.appendChild(_make_input_group("Distance per set (optional)", input_distance))
    inputs_container.appendChild(_make_input_group("Notes (optional)", input_notes))

    warning_el = _make_warning_el()

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
        reps_val = input_reps.value
        time_val = input_time.value
        distance_val = input_distance.value.strip()
        notes_val = input_notes.value.strip()

        warning_el.style.display = "none"

        if not sets_val:
            _show_warning(warning_el, "Number of sets is required.")
            return
        sets = int(sets_val)

        if not _validate_exercise_inputs(sets_val, reps_val, time_val, sets, warning_el):
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

        state.save_workouts()
        show_sidebar()
        render_workouts(state.workouts)
        overlay.remove()

    confirm_btn.onclick = on_confirm_click


# ── Superset linking ──────────────────────────────────────────────────────────

def toggle_superset(event) -> None:
    workout_ex_id = event.target.getAttribute("data-workout-exercise-id")
    workout_id = event.target.getAttribute("data-workout-id")
    w, ex, j = _find_exercise(workout_id, workout_ex_id)
    if w is None or j == 0:
        return
    prev_ex = w.exercises[j - 1]
    if ex.superset_id and ex.superset_id == prev_ex.superset_id:
        # Unlink: split the superset at this boundary.
        # Exercises from j onwards that share the same sid form a new superset (if ≥2).
        old_sid = ex.superset_id
        tail = [e for i, e in enumerate(w.exercises) if i >= j and e.superset_id == old_sid]
        if len(tail) >= 2:
            new_sid = str(uuid4())
            w.superset_rounds[new_sid] = w.superset_rounds.get(old_sid, 1)
            for e in tail:
                e.superset_id = new_sid
        else:
            ex.superset_id = ""
        _cleanup_supersets(w)
    else:
        # Prefer the existing superset id from whichever side already belongs to one.
        # Priority: lower exercise's group > upper exercise's group > new id.
        # This ensures adding ex1 above an existing ex2+ex3 superset extends it
        # rather than creating a new one that orphans ex3.
        sid = ex.superset_id or prev_ex.superset_id or str(uuid4())
        if sid not in w.superset_rounds:
            w.superset_rounds[sid] = 1
        # If the upper exercise was in a different superset, migrate all its members.
        if prev_ex.superset_id and prev_ex.superset_id != sid:
            old_sid = prev_ex.superset_id
            for e in w.exercises:
                if e.superset_id == old_sid:
                    e.superset_id = sid
            w.superset_rounds.pop(old_sid, None)
        prev_ex.superset_id = sid
        ex.superset_id = sid
    state.save_workouts()
    render_workouts(state.workouts)


# ── Move exercises ─────────────────────────────────────────────────────────────

def _cleanup_supersets(w) -> None:
    """Clear superset_id from exercises no longer adjacent to a partner, then
    remove orphaned superset_rounds entries. Iterates until stable."""
    changed = True
    while changed:
        changed = False
        n = len(w.exercises)
        for i, ex in enumerate(w.exercises):
            if not ex.superset_id:
                continue
            sid = ex.superset_id
            above = i > 0 and w.exercises[i - 1].superset_id == sid
            below = i < n - 1 and w.exercises[i + 1].superset_id == sid
            if not above and not below:
                ex.superset_id = ""
                changed = True
    active = {ex.superset_id for ex in w.exercises if ex.superset_id}
    for sid in list(w.superset_rounds.keys()):
        if sid not in active:
            del w.superset_rounds[sid]


def _can_move(exercises, j, delta) -> bool:
    """Superset exercises: only within their group. Standalones: always (jump over groups)."""
    k = j + delta
    if not (0 <= k < len(exercises)):
        return False
    if exercises[j].superset_id:
        return exercises[k].superset_id == exercises[j].superset_id
    return True


def _do_move(exercises, j, delta) -> None:
    """Perform the move. Standalones jump over entire superset groups as a unit."""
    ex = exercises[j]
    k = j + delta
    if ex.superset_id or not exercises[k].superset_id:
        exercises[j], exercises[k] = exercises[k], exercises[j]
    else:
        # Standalone jumping over a superset group — find the far boundary.
        sid = exercises[k].superset_id
        if delta == +1:
            end = k
            while end + 1 < len(exercises) and exercises[end + 1].superset_id == sid:
                end += 1
            exercises.insert(end, exercises.pop(j))
        else:
            start = k
            while start - 1 >= 0 and exercises[start - 1].superset_id == sid:
                start -= 1
            exercises.insert(start, exercises.pop(j))


def move_exercise_up(event) -> None:
    workout_ex_id = event.target.getAttribute("data-workout-exercise-id")
    workout_id = event.target.getAttribute("data-workout-id")
    w, _, j = _find_exercise(workout_id, workout_ex_id)
    if w and _can_move(w.exercises, j, -1):
        _do_move(w.exercises, j, -1)
        state.save_workouts()
        render_workouts(state.workouts)


def move_exercise_down(event) -> None:
    workout_ex_id = event.target.getAttribute("data-workout-exercise-id")
    workout_id = event.target.getAttribute("data-workout-id")
    w, _, j = _find_exercise(workout_id, workout_ex_id)
    if w and _can_move(w.exercises, j, +1):
        _do_move(w.exercises, j, +1)
        state.save_workouts()
        render_workouts(state.workouts)


# ── Edit exercise ──────────────────────────────────────────────────────────────

def edit_exercise_in_workout(event) -> None:
    workout_ex_id = event.target.getAttribute("data-workout-exercise-id")
    workout_id = event.target.getAttribute("data-workout-id")

    _, target_ex, _ = _find_exercise(workout_id, workout_ex_id)
    if target_ex is None:
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
    input_notes.rows = "3"
    input_notes.style.resize = "vertical"
    input_notes.value = target_ex.notes or ""

    modal.appendChild(_make_input_group("Sets", input_sets))
    modal.appendChild(_make_input_group("Reps per set (comma separated, optional)", input_reps))
    modal.appendChild(_make_input_group("Time per set — hh:mm:ss (optional)", input_time))
    modal.appendChild(_make_input_group("Distance per set (optional)", input_distance))
    modal.appendChild(_make_input_group("Notes (optional)", input_notes))

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

    warning_el = _make_warning_el()

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
            _show_warning(warning_el, "Number of sets is required.")
            return
        sets = int(sets_val)

        if not _validate_exercise_inputs(sets_val, reps_val, time_val, sets, warning_el):
            return

        target_ex.sets = sets
        target_ex.reps = reps_val
        target_ex.time = time_val
        target_ex.distance = distance_val
        target_ex.notes = notes_val

        state.save_workouts()
        render_workouts(state.workouts)
        overlay.remove()

    confirm_btn.onclick = on_save


# ── Remove exercise / workout ──────────────────────────────────────────────────

def remove_exercise_from_workout(event) -> None:
    workout_ex_id = event.target.getAttribute("data-workout-exercise-id")
    workout_id = event.target.getAttribute("data-workout-id")
    w, _, j = _find_exercise(workout_id, workout_ex_id)
    if w and j >= 0:
        del w.exercises[j]
        _cleanup_supersets(w)
    state.save_workouts()
    render_workouts(state.workouts)
    if not state.workouts:
        state.active_workout = None
        hide_sidebar()


def remove_workout(event) -> None:
    event.stopPropagation()
    anchor = event.target.closest("button") or event.target
    workout_id = event.target.getAttribute("data-workout-id")

    def _do():
        for i, w in enumerate(state.workouts):
            if str(w.id) == workout_id:
                del state.workouts[i]
                break
        state.active_workout = None if not state.workouts else state.workouts[-1].id
        state.save_workouts()
        render_workouts(state.workouts)
        if not state.workouts:
            hide_sidebar()

    _show_confirm_popup(anchor, "Remove this workout?", _do)


def remove_workouts(event) -> None:
    event.stopPropagation()
    anchor = event.target.closest("button") or event.target

    def _do():
        state.workouts.clear()
        state.active_workout = None
        localStorage.removeItem(state.ls_workouts_key)
        ws_container = pydom["#workout-list-container"][0]
        while ws_container._js.firstChild:
            ws_container._js.removeChild(ws_container._js.firstChild)
        hide_sidebar()

    _show_confirm_popup(anchor, "Remove all workouts?", _do)


def add_workout(event) -> None:
    state.active_workout = uuid4()
    w = Workout(state.active_workout, datetime.datetime.now().date(), [])
    state.workouts.append(w)
    state.save_workouts()
    render_workouts(state.workouts)
