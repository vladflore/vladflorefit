from dataclasses import dataclass, field
from datetime import datetime, date
import json
from datetime import timedelta
import requests
from config import GH_PAGES_ROOT
import time


@dataclass
class FitnessClassRenderConfig:
    text_color: str = "black"
    background_color: str = "white"


@dataclass
class FitnessClass:
    name: str
    start: datetime
    end: datetime
    instructor: str
    render_config: FitnessClassRenderConfig = field(
        default_factory=FitnessClassRenderConfig
    )

    @staticmethod
    def from_dict(item: dict) -> "FitnessClass":
        return FitnessClass(
            name=item["name"],
            start=datetime.fromisoformat(item["start"]),
            end=datetime.fromisoformat(item["end"]),
            instructor=item["instructor"],
            render_config=FitnessClassRenderConfig(
                text_color=item.get("render_config", {}).get("text_color", "#000000"),
                background_color=item.get("render_config", {}).get(
                    "background_color", "#FFFFFF"
                ),
            ),
        )


def read_data(data) -> list[FitnessClass]:
    classes: list[FitnessClass] = []
    for fitness_class in data["fitness_classes"]:
        start = datetime.fromisoformat(fitness_class["start"])
        end = datetime.fromisoformat(fitness_class["end"])
        render_config = FitnessClassRenderConfig(
            text_color=fitness_class["render_config"].get("text_color", "#000000"),
            background_color=fitness_class["render_config"].get(
                "background_color", "#FFFFFF"
            ),
        )
        fitness_class = FitnessClass(
            name=fitness_class["name"],
            start=start,
            end=end,
            instructor=fitness_class["instructor"],
            render_config=render_config,
        )
        classes.append(fitness_class)
    return classes


def load_classes_from_file(lang: str) -> list[FitnessClass]:
    with open("classes_{lang}.json".format(lang=lang), "r") as file:
        data = json.load(file)
        return read_data(data)


def load_classes_from_gh(lang: str) -> list[FitnessClass]:
    response = requests.get(
        f"{GH_PAGES_ROOT}/classes_{lang}.json?v={str(int(time.time()))}"
    )
    data = response.json()
    return read_data(data)


def load_classes_from_url(url: str) -> list[FitnessClass]:
    response = requests.get(url)
    text = response.text
    class_blocks = [block.strip() for block in text.split("+++") if block.strip()]
    fitness_classes = []

    for block in class_blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        class_dict = {}
        render_config = {}
        for line in lines:
            if line.startswith("Class Name Is "):
                class_dict["name"] = line.replace("Class Name Is ", "")
            elif line.startswith("Class Instructor Is "):
                class_dict["instructor"] = line.replace("Class Instructor Is ", "")
            elif line.startswith("Class Starts On "):
                class_dict["start_date"] = line.replace("Class Starts On ", "")
            elif line.startswith("Class Starts At "):
                class_dict["start_time"] = line.replace("Class Starts At ", "")
            elif line.startswith("Class Ends On "):
                class_dict["end_date"] = line.replace("Class Ends On ", "")
            elif line.startswith("Class Ends At "):
                class_dict["end_time"] = line.replace("Class Ends At ", "")
            elif line.startswith("Text Color Is "):
                render_config["text_color"] = line.replace("Text Color Is ", "")
            elif line.startswith("Background Color Is "):
                render_config["background_color"] = line.replace(
                    "Background Color Is ", ""
                )
        start = datetime.strptime(
            f"{class_dict['start_date']} {class_dict['start_time']}", "%d.%m.%Y %H:%M"
        ).isoformat()
        end = datetime.strptime(
            f"{class_dict['end_date']} {class_dict['end_time']}", "%d.%m.%Y %H:%M"
        ).isoformat()
        fitness_classes.append(
            {
                "name": class_dict["name"],
                "instructor": class_dict["instructor"],
                "start": start,
                "end": end,
                "render_config": render_config,
            }
        )

    data = {"fitness_classes": fitness_classes}
    return read_data(data)


def load_dummy_classes() -> list[FitnessClass]:
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    return [
        FitnessClass(
            name="Dummy Yoga Flow",
            start=datetime.combine(start_of_week, datetime.min.time()).replace(hour=9),
            end=datetime.combine(start_of_week, datetime.min.time()).replace(hour=10),
            instructor="Alice Smith",
            render_config=FitnessClassRenderConfig(
                text_color="#FFFFFF",
                background_color="#800080",
            ),
        ),
        FitnessClass(
            name="Dummy Power Yoga",
            start=datetime.combine(start_of_week, datetime.min.time()).replace(hour=17),
            end=datetime.combine(start_of_week, datetime.min.time()).replace(hour=18),
            instructor="Alice Smith",
            render_config=FitnessClassRenderConfig(
                text_color="#FFFFFF",
                background_color="#4B0082",
            ),
        ),
        FitnessClass(
            name="Dummy HIIT Blast",
            start=datetime.combine(
                start_of_week + timedelta(days=1), datetime.min.time()
            ).replace(hour=18),
            end=datetime.combine(
                start_of_week + timedelta(days=1), datetime.min.time()
            ).replace(hour=19),
            instructor="Bob Johnson",
            render_config=FitnessClassRenderConfig(
                text_color="#000000",
                background_color="#FFFF00",
            ),
        ),
        FitnessClass(
            name="Dummy Morning HIIT",
            start=datetime.combine(
                start_of_week + timedelta(days=1), datetime.min.time()
            ).replace(hour=7),
            end=datetime.combine(
                start_of_week + timedelta(days=1), datetime.min.time()
            ).replace(hour=8),
            instructor="Bob Johnson",
            render_config=FitnessClassRenderConfig(
                text_color="#000000",
                background_color="#FFD700",
            ),
        ),
        FitnessClass(
            name="Dummy Pilates Core",
            start=datetime.combine(
                start_of_week + timedelta(days=2), datetime.min.time()
            ).replace(hour=7),
            end=datetime.combine(
                start_of_week + timedelta(days=2), datetime.min.time()
            ).replace(hour=8),
            instructor="Carol Lee",
            render_config=FitnessClassRenderConfig(
                text_color="#000000",
                background_color="#ADD8E6",
            ),
        ),
        FitnessClass(
            name="Dummy Pilates Stretch",
            start=datetime.combine(
                start_of_week + timedelta(days=2), datetime.min.time()
            ).replace(hour=19),
            end=datetime.combine(
                start_of_week + timedelta(days=2), datetime.min.time()
            ).replace(hour=20),
            instructor="Carol Lee",
            render_config=FitnessClassRenderConfig(
                text_color="#000000",
                background_color="#B0E0E6",
            ),
        ),
        FitnessClass(
            name="Dummy Spin Class",
            start=datetime.combine(
                start_of_week + timedelta(days=4), datetime.min.time()
            ).replace(hour=17),
            end=datetime.combine(
                start_of_week + timedelta(days=4), datetime.min.time()
            ).replace(hour=18),
            instructor="Dan Miller",
            render_config=FitnessClassRenderConfig(
                text_color="#FFFFFF",
                background_color="#00008B",
            ),
        ),
        FitnessClass(
            name="Dummy Morning Spin",
            start=datetime.combine(
                start_of_week + timedelta(days=4), datetime.min.time()
            ).replace(hour=7),
            end=datetime.combine(
                start_of_week + timedelta(days=4), datetime.min.time()
            ).replace(hour=8),
            instructor="Dan Miller",
            render_config=FitnessClassRenderConfig(
                text_color="#FFFFFF",
                background_color="#4682B4",
            ),
        ),
        FitnessClass(
            name="Dummy Zumba",
            start=datetime.combine(
                start_of_week + timedelta(days=5), datetime.min.time()
            ).replace(hour=11),
            end=datetime.combine(
                start_of_week + timedelta(days=5), datetime.min.time()
            ).replace(hour=12),
            instructor="Eva Gomez",
            render_config=FitnessClassRenderConfig(
                text_color="#000000",
                background_color="#FFC0CB",
            ),
        ),
        FitnessClass(
            name="Dummy Zumba Party",
            start=datetime.combine(
                start_of_week + timedelta(days=5), datetime.min.time()
            ).replace(hour=18),
            end=datetime.combine(
                start_of_week + timedelta(days=5), datetime.min.time()
            ).replace(hour=19),
            instructor="Eva Gomez",
            render_config=FitnessClassRenderConfig(
                text_color="#000000",
                background_color="#FF69B4",
            ),
        ),
        FitnessClass(
            name="Dummy Stretch & Relax",
            start=datetime.combine(
                start_of_week + timedelta(days=6), datetime.min.time()
            ).replace(hour=10),
            end=datetime.combine(
                start_of_week + timedelta(days=6), datetime.min.time()
            ).replace(hour=11),
            instructor="Grace Lin",
            render_config=FitnessClassRenderConfig(
                text_color="#000000",
                background_color="#E0FFFF",
            ),
        ),
        FitnessClass(
            name="Dummy Sunday Bootcamp",
            start=datetime.combine(
                start_of_week + timedelta(days=6), datetime.min.time()
            ).replace(hour=16),
            end=datetime.combine(
                start_of_week + timedelta(days=6), datetime.min.time()
            ).replace(hour=17),
            instructor="Mike Brown",
            render_config=FitnessClassRenderConfig(
                text_color="#FFFFFF",
                background_color="#228B22",
            ),
        ),
    ]
