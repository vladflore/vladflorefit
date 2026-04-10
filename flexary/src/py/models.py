import ast
import datetime
import json
from dataclasses import dataclass, field
from uuid import UUID


category_to_badge: dict[str, str] = {
    "strength": "bg-dark",
    "conditioning": "bg-danger",
    "mobility": "bg-info",
    "stretching": "bg-primary",
}

category_to_rgb: dict[str, tuple] = {
    "strength": (50, 50, 50),
    "conditioning": (220, 53, 69),
    "mobility": (13, 202, 240),
    "stretching": (13, 110, 253),
}


def _reps_display(raw: str, sets: int) -> str:
    values = [v.strip() for v in raw.split(",") if v.strip()]
    if len(set(values)) == 1:
        return f"{values[0]} reps each" if sets > 1 else f"{values[0]} reps"
    return "/".join(values) + " reps"


def _time_display(raw: str, sets: int) -> str:
    values = [v.strip() for v in raw.split(",") if v.strip()]
    if len(set(values)) == 1:
        return f"{values[0]} each" if sets > 1 else values[0]
    return "/".join(values)


def _dist_display(raw: str, sets: int = 0) -> str:
    values = [v.strip() for v in raw.split(",") if v.strip()]
    if len(set(values)) == 1:
        return f"{values[0]} each" if sets > 1 else values[0]
    return "/".join(values)


@dataclass
class Exercise:
    id: int
    internal_id: str
    name: str
    sets: int
    reps: str
    time: str = ""
    distance: str = ""
    notes: str = ""
    superset_id: str = ""
    rest_between_sets: int = 0
    custom_video_id: str = ""

    def execution_mismatch(self, rounds: int) -> bool:
        """True when any per-set field has multiple values that don't match the superset rounds count."""
        def _check(raw):
            if not raw:
                return False
            values = [v.strip() for v in raw.split(",") if v.strip()]
            return len(values) > 1 and len(values) != rounds
        return _check(self.reps) or _check(self.time) or _check(self.distance)

    def detail_str(self, in_superset: bool = False) -> str:
        sets = int(self.sets) if str(self.sets).isdigit() else 1
        parts = []
        if in_superset:
            if self.reps:
                parts.append(_reps_display(self.reps, 1))
            elif self.time:
                parts.append(_time_display(self.time, 1))
            elif self.distance:
                parts.append(_dist_display(self.distance))
            if self.reps and self.time:
                parts.append(_time_display(self.time, 1))
            if self.distance and (self.reps or self.time):
                parts.append(_dist_display(self.distance))
        else:
            sets_label = f"{sets} set{'s' if sets != 1 else ''}"
            if self.reps:
                parts.append(f"{sets_label} × {_reps_display(self.reps, sets)}")
            elif self.time:
                parts.append(f"{sets_label} × {_time_display(self.time, sets)}")
            elif self.distance:
                parts.append(f"{sets_label} × {_dist_display(self.distance, sets)}")
            else:
                parts.append(sets_label)
            if self.reps and self.time:
                parts.append(_time_display(self.time, sets))
            if self.distance and (self.reps or self.time):
                parts.append(_dist_display(self.distance, sets))
        if self.rest_between_sets:
            m, s = divmod(self.rest_between_sets, 60)
            rest_str = (f"{m}m {s}s" if s else f"{m}m") if m else f"{s}s"
            parts.append(f"{rest_str} rest between sets")
        return " · ".join(parts)


@dataclass
class Workout:
    id: UUID
    execution_date: datetime.date
    exercises: list
    superset_rounds: dict = field(default_factory=dict)
    name: str = ""
    breaks: dict = field(default_factory=dict)


def workouts_to_json(workouts: list) -> str:
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

    def _w(w):
        return {
            "id": str(w.id),
            "execution_date": w.execution_date.isoformat(),
            "exercises": [_ex(ex) for ex in w.exercises],
            "superset_rounds": w.superset_rounds,
            "name": w.name,
            "breaks": w.breaks,
        }

    return json.dumps([_w(w) for w in workouts])


def _coerce_str(value, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _coerce_int(value, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return int(stripped)
    return default


def _parse_exercise(ex_data) -> Exercise:
    if not isinstance(ex_data, dict):
        raise ValueError("Exercise must be an object")

    return Exercise(
        id=_coerce_int(ex_data["id"]),
        internal_id=_coerce_str(ex_data["internal_id"]),
        name=_coerce_str(ex_data["name"]),
        sets=_coerce_int(ex_data.get("sets", 1), default=1),
        reps=_coerce_str(ex_data.get("reps", "")),
        time=_coerce_str(ex_data.get("time", "")),
        distance=_coerce_str(ex_data.get("distance", "")),
        notes=_coerce_str(ex_data.get("notes", "")),
        superset_id=_coerce_str(ex_data.get("superset_id", "")),
        rest_between_sets=_coerce_int(ex_data.get("rest_between_sets", 0)),
        custom_video_id=_coerce_str(ex_data.get("custom_video_id", "")),
    )


def _parse_int_mapping(raw_mapping) -> dict[str, int]:
    if not raw_mapping:
        return {}
    if not isinstance(raw_mapping, dict):
        raise ValueError("Expected an object mapping")
    parsed: dict[str, int] = {}
    for key, value in raw_mapping.items():
        parsed[_coerce_str(key)] = _coerce_int(value)
    return parsed


def _parse_workout(w_data) -> Workout:
    if not isinstance(w_data, dict):
        raise ValueError("Workout must be an object")

    exercises_raw = w_data.get("exercises", [])
    if not isinstance(exercises_raw, list):
        raise ValueError("Workout exercises must be a list")

    return Workout(
        id=UUID(_coerce_str(w_data["id"])),
        execution_date=datetime.date.fromisoformat(_coerce_str(w_data["execution_date"])),
        exercises=[_parse_exercise(ex_data) for ex_data in exercises_raw],
        superset_rounds=_parse_int_mapping(w_data.get("superset_rounds", {})),
        name=_coerce_str(w_data.get("name", "")),
        breaks=_parse_int_mapping(w_data.get("breaks", {})),
    )


def _parse_workouts_payload(raw: str):
    try:
        return json.loads(raw)
    except Exception:
        return ast.literal_eval(raw)


def _migrate_done_breaks(workout: "Workout") -> None:
    """Migrate _done_{sid} break keys to the internal_id of the first exercise after that superset."""
    to_delete = []
    to_add = {}
    exs = workout.exercises
    for i, ex in enumerate(exs):
        if ex.superset_id:
            continue
        prev = exs[i - 1] if i > 0 else None
        if prev and prev.superset_id:
            done_key = f"_done_{prev.superset_id}"
            if done_key in workout.breaks:
                to_add[ex.internal_id] = workout.breaks[done_key]
                to_delete.append(done_key)
    for k in to_delete:
        del workout.breaks[k]
    workout.breaks.update(to_add)


def workouts_from_json(raw: str) -> list:
    try:
        payload = _parse_workouts_payload(raw)
        if isinstance(payload, dict):
            version = payload.get("version", 1)
            if version != 1:
                return []
            data = payload.get("workouts", [])
        else:
            data = payload

        if not isinstance(data, list):
            return []

        result = [_parse_workout(w_data) for w_data in data]
        for w in result:
            _migrate_done_breaks(w)
        return result
    except Exception:
        return []
