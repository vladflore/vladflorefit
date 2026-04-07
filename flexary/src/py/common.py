import csv
import datetime

from exercise_records import normalize_exercise_record, normalize_exercise_records


def csv_to_json(csv_file_path, exercise_id=None):
    with open(csv_file_path, mode="r", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if exercise_id:
            for row in reader:
                if row.get("id") == exercise_id:
                    return normalize_exercise_record(row, is_custom=False)
            return {}
        else:
            return normalize_exercise_records([row for row in reader], is_custom=False)


def copyright():
    current_year = datetime.date.today().year
    return f"""
    © {current_year} <a href="https://vladflore.fit/">vladflore.fit</a> · All rights reserved."""


def current_version():
    return "<i>Version: 07.04.2026</i>"
