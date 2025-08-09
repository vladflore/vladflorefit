import csv
import json
import datetime


def csv_to_json(csv_file_path, exercise_id=None):
    """
    Reads a CSV file and converts its data to a JSON object. If exercise_id is provided,
    filters the CSV data to return only the row with the matching exercise_id.

    Args:
        csv_file_path (str): Path to the CSV file.
        exercise_id (str, optional): ID of the exercise to filter.

    Returns:
        dict or list: JSON object containing the filtered CSV data or all data.
    """
    with open(csv_file_path, mode="r", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if exercise_id:
            for row in reader:
                if row.get("id") == exercise_id:
                    return json.loads(json.dumps(row))
            return {}
        else:
            data = [row for row in reader]
            return json.loads(json.dumps(data))


def copyright():
    current_year = datetime.date.today().year
    return f"""
    © {current_year} <a href="https://vladflore.fit/">vladflore.fit</a> · All rights reserved."""


def current_version():
    return "<i>Version: 06.07.2025</i>"


if __name__ == "__main__":
    csv_file_path = "exercises_library.csv"

    json_data = csv_to_json(csv_file_path, exercise_id="4")
    print(json.dumps(json_data, indent=4))

    json_data = csv_to_json(csv_file_path)
    print(json.dumps(json_data, indent=4))
