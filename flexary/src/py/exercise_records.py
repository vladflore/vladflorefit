from typing import NotRequired, TypedDict


class ExerciseRecord(TypedDict):
    id: str
    name: str
    category: str
    body_parts: str
    primary_muscles: str
    secondary_muscles: str
    thumbnail_url: str
    yt_video_id: str
    instructions: str
    key_cues: str
    alternatives: str
    equipment: str
    is_custom: NotRequired[str]


def _coerce_str(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_csv_list(value) -> str:
    parts = [_coerce_str(item) for item in _coerce_str(value).split(",")]
    return ",".join(part for part in parts if part)


def normalize_exercise_record(raw: dict, *, is_custom: bool | None = None) -> ExerciseRecord:
    normalized: ExerciseRecord = {
        "id": _coerce_str(raw.get("id")),
        "name": _coerce_str(raw.get("name")),
        "category": _normalize_csv_list(raw.get("category")),
        "body_parts": _normalize_csv_list(raw.get("body_parts")),
        "primary_muscles": _normalize_csv_list(raw.get("primary_muscles")),
        "secondary_muscles": _normalize_csv_list(raw.get("secondary_muscles")),
        "thumbnail_url": _coerce_str(raw.get("thumbnail_url")),
        "yt_video_id": _coerce_str(raw.get("yt_video_id")),
        "instructions": _coerce_str(raw.get("instructions")),
        "key_cues": _normalize_csv_list(raw.get("key_cues")),
        "alternatives": _normalize_csv_list(raw.get("alternatives")),
        "equipment": _coerce_str(raw.get("equipment")),
    }
    custom_flag = _coerce_str(raw.get("is_custom")).lower()
    if is_custom is True or custom_flag == "true":
        normalized["is_custom"] = "true"
    return normalized


def normalize_exercise_records(raw_records: list[dict], *, is_custom: bool | None = None) -> list[ExerciseRecord]:
    return [
        normalize_exercise_record(record, is_custom=is_custom)
        for record in raw_records
        if isinstance(record, dict)
    ]
