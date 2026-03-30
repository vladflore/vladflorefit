import datetime
import json
from dataclasses import dataclass, field
from uuid import UUID


category_to_badge: dict[str, str] = {
    "strength": "bg-dark",
    "conditioning": "bg-danger",
    "mobility": "bg-info",
}

category_to_rgb: dict[str, tuple] = {
    "strength": (50, 50, 50),
    "conditioning": (220, 53, 69),
    "mobility": (13, 202, 240),
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
    description: str = ""


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
        }

    def _w(w):
        return {
            "id": str(w.id),
            "execution_date": w.execution_date.isoformat(),
            "exercises": [_ex(ex) for ex in w.exercises],
            "superset_rounds": w.superset_rounds,
            "name": w.name,
            "breaks": w.breaks,
            "description": w.description,
        }

    return json.dumps([_w(w) for w in workouts])


def workouts_from_json(raw: str) -> list:
    try:
        data = json.loads(raw)
        result = []
        for w_data in data:
            exercises = [Exercise(
                id=ex_data["id"],
                internal_id=ex_data["internal_id"],
                name=ex_data["name"],
                sets=ex_data["sets"],
                reps=ex_data["reps"],
                time=ex_data.get("time", ""),
                distance=ex_data.get("distance", ""),
                notes=ex_data.get("notes", ""),
                superset_id=ex_data.get("superset_id", ""),
                rest_between_sets=int(ex_data.get("rest_between_sets", 0)),
            ) for ex_data in w_data["exercises"]]
            result.append(Workout(
                id=UUID(w_data["id"]),
                execution_date=datetime.date.fromisoformat(w_data["execution_date"]),
                exercises=exercises,
                superset_rounds=w_data.get("superset_rounds", {}),
                name=w_data.get("name", ""),
                breaks={k: int(v) for k, v in w_data.get("breaks", {}).items()},
                description=w_data.get("description", ""),
            ))
        return result
    except Exception:
        try:
            return eval(raw)
        except Exception:
            return []
