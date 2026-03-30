import json

from js import localStorage
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

# Fall back to localStorage for custom exercises (negative IDs)
if not data:
    try:
        raw = localStorage.getItem("custom_exercises")
        if raw:
            customs = json.loads(raw)
            data = next((ex for ex in customs if str(ex["id"]) == exercise_id), {})
    except Exception:
        pass

pydom["#exercise-name"][0]._js.textContent = data.get("name", "")
pydom["#breadcrumb-exercise-name"][0]._js.textContent = data.get("name", "")

categories = data.get("category", "").split(",")
category_badge_element = pydom["#category-badge"][0]
clean_cat_badge = category_badge_element.clone()
for i, category in enumerate(categories):
    category = category.strip()
    cat_badge = category_badge_element if i == 0 else clean_cat_badge.clone()
    cat_badge._js.textContent = category
    cat_badge._js.classList.add(category_to_badge.get(category.lower(), "bg-secondary"))
    if i > 0:
        pydom["#badges-container"][0]._js.append(cat_badge._js)

body_parts_badges = data.get("body_parts", "").split(",")
for i, badge in enumerate(body_parts_badges):
    new_badge = (
        pydom["#body-parts-badge"][0].clone()
        if i > 0
        else pydom["#body-parts-badge"][0]
    )
    new_badge._js.textContent = badge
    new_badge._js.classList.add("bg-secondary")
    pydom["#badges-container"][0]._js.append(new_badge._js)


def open_exercise(event):
    exercise_id = event.target.getAttribute("data-id")
    window.open(f"detail.html?exercise_id={exercise_id}", "_blank")


# ── Video ──────────────────────────────────────────────────────────────────────
yt_id = data.get("yt_video_id", "")
iframe = pydom["#exercise-video"][0]._js
ratio_div = iframe.closest(".ratio")

if yt_id:
    iframe.src = f"https://www.youtube.com/embed/{yt_id}"
else:
    placeholder = window.document.createElement("div")
    placeholder.className = "video-placeholder"
    icon = window.document.createElement("i")
    icon.className = "bi bi-camera-video-off"
    label = window.document.createElement("span")
    label.textContent = "No video available"
    placeholder.appendChild(icon)
    placeholder.appendChild(label)
    ratio_div.replaceWith(placeholder)

# ── Instructions ───────────────────────────────────────────────────────────────
instructions = data.get("instructions", "")
if instructions:
    pydom["#exercise-instructions"][0]._js.textContent = instructions
else:
    pydom["#instructions-not-available"][0]._js.classList.remove("d-none")

# ── Muscles ────────────────────────────────────────────────────────────────────
primary_muscles = data.get("primary_muscles", "")
secondary_muscles = data.get("secondary_muscles", "")
if primary_muscles:
    pydom["#primary-muscles"][0]._js.textContent = f"Primary: {primary_muscles}"
if secondary_muscles:
    pydom["#secondary-muscles"][0]._js.textContent = f"Secondary: {secondary_muscles}"
if not primary_muscles and not secondary_muscles:
    pydom["#muscles-not-available"][0]._js.classList.remove("d-none")

# ── Key cues ───────────────────────────────────────────────────────────────────
cues = data.get("key_cues", "")
if cues:
    for i, cue in enumerate(cues.split(",")):
        new_cue = pydom["#key-cue"][0].clone() if i > 0 else pydom["#key-cue"][0]
        new_cue._js.textContent = cue.strip()
        pydom["#key-cues-container"][0]._js.append(new_cue._js)
    pydom["#key-cues-container"][0]._js.classList.remove("d-none")
else:
    pydom["#cues-not-available"][0]._js.classList.remove("d-none")

# ── Alternatives ───────────────────────────────────────────────────────────────
alternatives = data.get("alternatives", "")
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

# ── Footer ─────────────────────────────────────────────────────────────────────
pydom["#copyright"][0]._js.innerHTML = copyright()
pydom["#version"][0]._js.innerHTML = current_version()
pydom["#footer"][0]._js.classList.remove("d-none")
