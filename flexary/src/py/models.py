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

    def reps_mismatch(self, rounds: int) -> bool:
        """True when varying reps values don't match the superset rounds count."""
        if not self.reps:
            return False
        values = [v.strip() for v in self.reps.split(",") if v.strip()]
        return len(values) > 1 and len(values) != rounds

    def detail_str(self, in_superset: bool = False) -> str:
        sets = int(self.sets) if str(self.sets).isdigit() else 1
        parts = []
        if in_superset:
            # Rounds are controlled at the superset level — show only per-round details.
            if self.reps:
                parts.append(_reps_display(self.reps, 1))
            elif self.time:
                parts.append(self.time)
            elif self.distance:
                parts.append(_dist_display(self.distance))
            if self.reps and self.time:
                parts.append(self.time)
            if self.distance and (self.reps or self.time):
                parts.append(_dist_display(self.distance))
        else:
            sets_label = f"{sets} set{'s' if sets != 1 else ''}"
            each = sets > 1
            if self.reps:
                parts.append(f"{sets_label} × {_reps_display(self.reps, sets)}")
            elif self.time:
                parts.append(f"{sets_label} × {self.time}{' each' if each else ''}")
            elif self.distance:
                parts.append(f"{sets_label} × {_dist_display(self.distance, sets)}")
            else:
                parts.append(sets_label)
            if self.reps and self.time:
                parts.append(f"{self.time}{' each' if each else ''}")
            if self.distance and (self.reps or self.time):
                parts.append(_dist_display(self.distance, sets))
        return " · ".join(parts)


@dataclass
class Workout:
    id: UUID
    execution_date: datetime.date
    exercises: list
    superset_rounds: dict = field(default_factory=dict)  # superset_id -> rounds
    name: str = ""
    breaks: dict = field(default_factory=dict)  # exercise internal_id -> seconds


# ── Serialisation ──────────────────────────────────────────────────────────────

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
            ) for ex_data in w_data["exercises"]]
            result.append(Workout(
                id=UUID(w_data["id"]),
                execution_date=datetime.date.fromisoformat(w_data["execution_date"]),
                exercises=exercises,
                superset_rounds=w_data.get("superset_rounds", {}),
                name=w_data.get("name", ""),
                breaks={k: int(v) for k, v in w_data.get("breaks", {}).items()},
            ))
        return result
    except Exception:
        # Fallback: legacy eval-based storage format
        try:
            return eval(raw)  # noqa: S307
        except Exception:
            return []
