import asyncio
import datetime
import io
import json

from js import JSON, File, URL, Uint8Array, document, localStorage as _ls, window

import catalog
import state
from common import yt_id_to_url


def _split_csv(value: str) -> list:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _split_key_cues(value: str) -> list:
    """Split key_cues respecting \\, as an escaped comma within a single cue."""
    if not value:
        return []
    normalized = value.replace("\\,", "\x00")
    parts = [p.strip().replace("\x00", ", ") for p in normalized.split(",") if p.strip()]
    return parts


def _expand_per_set(raw: str, sets: int) -> list:
    """Return a list of per-set values, always expanded to `sets` entries."""
    values = [v.strip() for v in raw.split(",") if v.strip()] if raw else []
    if not values:
        return []
    if len(values) == 1:
        return values * sets
    return values


def _export_workout(workout) -> dict:
    # Collect unique supersets with their rest values
    seen_supersets: dict = {}
    for ex in workout.exercises:
        if ex.superset_id and ex.superset_id not in seen_supersets:
            seen_supersets[ex.superset_id] = {
                "id": ex.superset_id,
                "rounds": workout.superset_rounds.get(ex.superset_id, 1),
                "rest_before_seconds": workout.breaks.get(f"_before_{ex.superset_id}", 0),
                "rest_after_seconds": workout.breaks.get(f"_after_{ex.superset_id}", 0),
            }

    exercises = []
    for ex in workout.exercises:
        sets = int(ex.sets) if str(ex.sets).isdigit() else 1
        ex_data = catalog.get_exercise(ex.id) or {}
        is_custom = ex_data.get("is_custom") == "true"

        # Custom video takes priority; fall back to catalog default
        video_url = (
            yt_id_to_url(ex.custom_video_id)
            if ex.custom_video_id
            else yt_id_to_url(ex_data.get("yt_video_id", ""))
        )

        exercises.append({
            "id": ex.id,
            "name": ex.name,
            "sets": sets,
            "reps": _expand_per_set(ex.reps, sets),
            "time": _expand_per_set(ex.time, sets),
            "distance": _expand_per_set(ex.distance, sets),
            "notes": ex.notes,
            "rest_between_sets_seconds": ex.rest_between_sets,
            "rest_before_seconds": workout.breaks.get(ex.internal_id, 0),
            "superset_id": ex.superset_id,
            "video_url": video_url,
            "category": _split_csv(ex_data.get("category", "")),
            "equipment": _split_csv(ex_data.get("equipment", "")),
            "instructions": ex_data.get("instructions", ""),
            "key_cues": _split_key_cues(ex_data.get("key_cues", "")),
            "is_custom": is_custom,
        })

    return {
        "id": str(workout.id),
        "name": workout.name,
        "scheduled_date": workout.execution_date.isoformat(),
        "exercises": exercises,
        "supersets": list(seen_supersets.values()),
    }


def sync_export() -> None:
    """Rebuild flexary_export from the current in-memory workouts state.

    Call this after any mutation (remove exercise, remove workout, clear all)
    so the export stays in sync without requiring a manual Save click.
    When no workout has any exercises left the export key is removed entirely.
    """
    if not any(w.exercises for w in state.workouts):
        _ls.removeItem("flexary_export")
        return
    _ls.setItem("flexary_export", json.dumps(_build_payload(), ensure_ascii=False))


def _build_payload() -> dict:
    return {
        "version": 1,
        "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
        "workouts": [_export_workout(w) for w in state.workouts],
    }


def _workout_to_dict(w) -> dict:
    def _ex(ex):
        return {
            "id": ex.id,
            "internal_id": ex.internal_id,
            "name": ex.name,
            "sets": ex.sets,
            "reps": ex.reps,
            "time": ex.time,
            "distance": ex.distance,
            "notes": ex.notes,
            "superset_id": ex.superset_id,
            "rest_between_sets": ex.rest_between_sets,
            "custom_video_id": ex.custom_video_id,
        }
    return {
        "id": str(w.id),
        "execution_date": w.execution_date.isoformat(),
        "exercises": [_ex(ex) for ex in w.exercises],
        "superset_rounds": w.superset_rounds,
        "name": w.name,
        "breaks": w.breaks,
        "recurrence": w.recurrence,
        "recurrence_id": w.recurrence_id,
    }


def _set_save_btn_state(btn, btn_state: str) -> None:
    if not btn:
        return
    icon = btn.querySelector("i")
    span = btn.querySelector("span")
    disabled, icon_cls, label = {
        "saving": (True,  "bi bi-arrow-clockwise", "Saving..."),
        "saved":  (False, "bi bi-check-lg",        "Saved"),
        "error":  (False, "bi bi-exclamation-triangle", "Failed"),
        "idle":   (False, "bi bi-floppy",           "Save"),
    }.get(btn_state, (False, "bi bi-floppy", "Save"))
    btn.disabled = disabled
    if icon:
        icon.className = icon_cls
    if span:
        span.textContent = label


async def _reset_save_btn_after(btn, delay: float) -> None:
    await asyncio.sleep(delay)
    _set_save_btn_state(btn, "idle")


async def _save_workouts_async() -> None:
    state.flush_workout_inputs()
    if not any(w.exercises for w in state.workouts):
        return

    _ls.setItem("flexary_export", json.dumps(_build_payload(), ensure_ascii=False))

    if not state.is_authenticated():
        return

    btn = document.getElementById("save-workouts")
    _set_save_btn_state(btn, "saving")
    try:
        for w in state.workouts:
            workout_js = JSON.parse(json.dumps(_workout_to_dict(w)))
            await window.flexaryWorkoutApi.saveWorkout(workout_js)
        _set_save_btn_state(btn, "saved")
        asyncio.ensure_future(_reset_save_btn_after(btn, 2.0))
    except Exception:
        _set_save_btn_state(btn, "error")
        asyncio.ensure_future(_reset_save_btn_after(btn, 3.0))


def save_workouts(*args) -> None:
    """Persist workouts to localStorage and, for authenticated users, to the API."""
    asyncio.ensure_future(_save_workouts_async())


def download_workouts_json(*args) -> None:
    state.flush_workout_inputs()
    if not any(w.exercises for w in state.workouts):
        return

    payload = _build_payload()
    _ls.setItem("flexary_export", json.dumps(payload, ensure_ascii=False))

    json_str = json.dumps(payload, indent=2, ensure_ascii=False)

    encoded = json_str.encode("utf-8")
    js_array = Uint8Array.new(len(encoded))
    js_array.assign(io.BytesIO(encoded).getbuffer())

    file = File.new([js_array], "workouts.json", {"type": "application/json"})
    url = URL.createObjectURL(file)

    link = document.createElement("a")
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    link.setAttribute("download", f"workouts_{ts}.json")
    link.setAttribute("href", url)
    link.click()
