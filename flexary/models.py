import datetime
from dataclasses import dataclass
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


def _reps_display(raw: str) -> str:
    values = [v.strip() for v in raw.split(",") if v.strip()]
    if len(set(values)) == 1:
        return f"{values[0]} reps each"
    return "/".join(values) + " reps"


def _dist_display(raw: str) -> str:
    values = [v.strip() for v in raw.split(",") if v.strip()]
    if len(set(values)) == 1:
        return f"{values[0]} each"
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

    def detail_str(self) -> str:
        sets = int(self.sets) if str(self.sets).isdigit() else 1
        sets_label = f"{sets} set{'s' if sets != 1 else ''}"
        parts = []
        if self.reps:
            parts.append(f"{sets_label} × {_reps_display(self.reps)}")
        elif self.time:
            parts.append(f"{sets_label} × {self.time} each")
        elif self.distance:
            parts.append(f"{sets_label} × {_dist_display(self.distance)}")
        else:
            parts.append(sets_label)
        if self.reps and self.time:
            parts.append(f"{self.time} each")
        if self.distance and (self.reps or self.time):
            parts.append(_dist_display(self.distance))
        return " · ".join(parts)


@dataclass
class Workout:
    id: UUID
    execution_date: datetime.datetime
    exercises: list
