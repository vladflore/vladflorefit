import csv
import json
from pathlib import Path


_base_exercises: list[dict] | None = None
_all_exercises: list[dict] = []
_exercise_by_id: dict[str, dict] = {}
_category_count: dict[str, int] = {}
_body_parts_list: list[str] = []


def _load_base_exercises(csv_file_path: str = "exercises.csv") -> list[dict]:
    candidates = [
        Path(csv_file_path),
        Path("data/exercises_library.csv"),
        Path(__file__).resolve().parents[2] / "data" / "exercises_library.csv",
    ]
    for path in candidates:
        if path.exists():
            with path.open(mode="r", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                return sorted(list(reader), key=lambda ex: ex["name"])
    raise FileNotFoundError(csv_file_path)


def _split_csv_field(value: str) -> list[str]:
    return [item.strip() for item in str(value).split(",") if item.strip()]


def parse_custom_exercises(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def initialize(custom_exercises: list[dict] | None = None) -> None:
    global _base_exercises
    if _base_exercises is None:
        _base_exercises = _load_base_exercises()
    refresh(custom_exercises or [])


def refresh(custom_exercises: list[dict] | None = None) -> None:
    global _all_exercises, _exercise_by_id, _category_count, _body_parts_list

    if _base_exercises is None:
        initialize(custom_exercises)
        return

    merged = sorted(custom_exercises or [], key=lambda ex: ex["name"]) + _base_exercises
    exercise_by_id: dict[str, dict] = {}
    category_count: dict[str, int] = {}
    body_parts_seen: set[str] = set()
    body_parts_list: list[str] = []

    for exercise in merged:
        exercise_by_id[str(exercise["id"])] = exercise

        for category in _split_csv_field(exercise.get("category", "")):
            category_count[category] = category_count.get(category, 0) + 1

        for body_part in _split_csv_field(exercise.get("body_parts", "")):
            if body_part not in body_parts_seen:
                body_parts_seen.add(body_part)
                body_parts_list.append(body_part)

    body_parts_list.sort()

    _all_exercises = merged
    _exercise_by_id = exercise_by_id
    _category_count = category_count
    _body_parts_list = body_parts_list

    try:
        import state

        state.base_data = list(_base_exercises)
        state.data = merged
        state.category_count.clear()
        state.category_count.update(category_count)
        state.body_parts_list[:] = body_parts_list
    except Exception:
        pass


def all_exercises() -> list[dict]:
    return _all_exercises


def get_exercise(exercise_id) -> dict:
    return _exercise_by_id.get(str(exercise_id), {})


def category_count() -> dict[str, int]:
    return _category_count


def body_parts_list() -> list[str]:
    return _body_parts_list
