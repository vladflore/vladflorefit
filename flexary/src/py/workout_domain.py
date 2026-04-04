from uuid import UUID, uuid4

import state


def _find_exercise(workout_id: str, workout_ex_id: str):
    for w in state.workouts:
        if str(w.id) == workout_id:
            for j, ex in enumerate(w.exercises):
                if ex.internal_id == workout_ex_id:
                    return w, ex, j
    return None, None, -1


def _event_attr(event, attr_name: str):
    current_target = getattr(event, "currentTarget", None)
    if current_target:
        value = current_target.getAttribute(attr_name)
        if value:
            return value

    target = getattr(event, "target", None)
    if target:
        value = target.getAttribute(attr_name)
        if value:
            return value

        closest = getattr(target, "closest", None)
        if closest:
            container = closest(f"[{attr_name}]")
            if container:
                value = container.getAttribute(attr_name)
                if value:
                    return value

    return None


def _cleanup_supersets(w) -> None:
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
    k = j + delta
    if not (0 <= k < len(exercises)):
        return False
    if exercises[j].superset_id:
        return exercises[k].superset_id == exercises[j].superset_id
    return True


def _do_move(exercises, j, delta) -> None:
    ex = exercises[j]
    k = j + delta
    if ex.superset_id or not exercises[k].superset_id:
        exercises[j], exercises[k] = exercises[k], exercises[j]
    else:
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


def toggle_superset(event) -> None:
    from workout_rendering import render_workouts

    workout_ex_id = _event_attr(event, "data-workout-exercise-id")
    workout_id = _event_attr(event, "data-workout-id")
    if not workout_ex_id or not workout_id:
        return
    w, ex, j = _find_exercise(workout_id, workout_ex_id)
    if w is None or j == 0:
        return
    prev_ex = w.exercises[j - 1]
    if ex.superset_id and ex.superset_id == prev_ex.superset_id:
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
        sid = ex.superset_id or prev_ex.superset_id or str(uuid4())
        if sid not in w.superset_rounds:
            w.superset_rounds[sid] = 1
        if prev_ex.superset_id and prev_ex.superset_id != sid:
            old_sid = prev_ex.superset_id
            for e in w.exercises:
                if e.superset_id == old_sid:
                    e.superset_id = sid
            w.superset_rounds.pop(old_sid, None)
        prev_ex.superset_id = sid
        ex.superset_id = sid
        for e in w.exercises:
            if e.superset_id == sid:
                e.rest_between_sets = 0
    state.save_workouts()
    render_workouts(state.workouts)


def move_exercise_up(event) -> None:
    from workout_rendering import render_workouts

    workout_ex_id = _event_attr(event, "data-workout-exercise-id")
    workout_id = _event_attr(event, "data-workout-id")
    if not workout_ex_id or not workout_id:
        return
    w, _, j = _find_exercise(workout_id, workout_ex_id)
    if w and _can_move(w.exercises, j, -1):
        _do_move(w.exercises, j, -1)
        state.save_workouts()
        render_workouts(state.workouts)


def move_exercise_down(event) -> None:
    from workout_rendering import render_workouts

    workout_ex_id = _event_attr(event, "data-workout-exercise-id")
    workout_id = _event_attr(event, "data-workout-id")
    if not workout_ex_id or not workout_id:
        return
    w, _, j = _find_exercise(workout_id, workout_ex_id)
    if w and _can_move(w.exercises, j, +1):
        _do_move(w.exercises, j, +1)
        state.save_workouts()
        render_workouts(state.workouts)
