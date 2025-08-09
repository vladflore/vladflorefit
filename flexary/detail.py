from pyscript import window
from common import csv_to_json
from pyweb import pydom
from common import copyright, current_version

category_to_badge = {
    "strength": "bg-dark",
    "conditioning": "bg-danger",
    "mobility": "bg-info",
}

current_link = window.location.href
exercise_id = current_link.split("?")[1].split("=")[1]

data = csv_to_json("exercises.csv", exercise_id=exercise_id)

pydom["#exercise-name"][0]._js.textContent = data["name"]
pydom["#category-badge"][0]._js.textContent = data["category"]
pydom["#category-badge"][0]._js.classList.add(
    category_to_badge.get(data["category"].lower())
)


def open_exercise(event):
    exercise_id = event.target.getAttribute("data-id")
    window.open(f"detail.html?exercise_id={exercise_id}", "_blank")


body_parts_badges = data["body_parts"].split(",")
for i, badge in enumerate(body_parts_badges):
    new_badge = (
        pydom["#body-parts-badge"][0].clone()
        if i > 0
        else pydom["#body-parts-badge"][0]
    )
    new_badge._js.textContent = badge
    new_badge._js.classList.add("bg-secondary")
    pydom["#badges-container"][0]._js.append(new_badge._js)

yt_video_link = f"https://www.youtube.com/embed/{data['yt_video_id']}"
pydom["#exercise-video"][0]._js.src = yt_video_link
pydom["#exercise-instructions"][0]._js.textContent = data["instructions"]

primary_muscles = data["primary_muscles"]
if primary_muscles:
    pydom["#primary-muscles"][0]._js.textContent = f"Primary: {primary_muscles}"

secondary_muscles = data["secondary_muscles"]
if secondary_muscles:
    pydom["#secondary-muscles"][0]._js.textContent = f"Secondary: {secondary_muscles}"

cues = data["key_cues"]
if cues:
    for i, cue in enumerate(cues.split(",")):
        new_cue = pydom["#key-cue"][0].clone() if i > 0 else pydom["#key-cue"][0]
        new_cue._js.textContent = cue.strip()
        pydom["#key-cues-container"][0]._js.append(new_cue._js)
    pydom["#key-cues-container"][0]._js.classList.remove("d-none")
else:
    pydom["#cues-not-available"][0]._js.classList.remove("d-none")

alternatives = data["alternatives"]
if alternatives:
    for i, alternative_id in enumerate(alternatives.split(",")):
        alt_data = csv_to_json("exercises.csv", exercise_id=alternative_id)
        new_alternative = pydom["#alt-ex"][0].clone() if i > 0 else pydom["#alt-ex"][0]
        new_alternative._js.setAttribute("data-id", alt_data["id"])
        new_alternative._js.textContent = alt_data["name"]
        new_alternative._js.onclick = open_exercise
        pydom["#alt-ex-container"][0]._js.append(new_alternative._js)
    pydom["#alt-ex-container"][0]._js.classList.remove("d-none")
else:
    pydom["#alt-not-available"][0]._js.classList.remove("d-none")


copyright_element = pydom["#copyright"][0]
copyright_element._js.innerHTML = copyright()

version_element = pydom["#version"][0]
version_element._js.innerHTML = current_version()

pydom["#footer"][0]._js.classList.remove("d-none")
