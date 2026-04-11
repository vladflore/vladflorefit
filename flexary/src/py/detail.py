import catalog
from js import URLSearchParams, localStorage
from pyscript import window
from pyweb import pydom
from common import copyright, current_version, extract_yt_id
from i18n import t, apply_html_translations

category_to_badge = {
    "strength": "bg-dark",
    "conditioning": "bg-danger",
    "mobility": "bg-info",
    "stretching": "bg-primary",
}

query = URLSearchParams.new(window.location.search)
exercise_id = query.get("exercise_id") or ""
custom_video_id = query.get("custom_video_id") or ""


def _is_authenticated() -> bool:
    try:
        if (
            hasattr(window, "flexaryAuth")
            and window.flexaryAuth
            and window.flexaryAuth.state
            and (window.flexaryAuth.state.user or window.flexaryAuth.state.session)
        ):
            return True
    except Exception:
        pass
    return bool(localStorage.getItem("flexary_auth_session"))


customs = catalog.parse_custom_exercises(localStorage.getItem("custom_exercises"))
catalog.initialize(customs)
data = catalog.get_exercise(exercise_id)

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


equipment = data.get("equipment", "").strip()
if equipment:
    all_equipment = equipment.split(",")
    for i, item in enumerate(all_equipment):
        new_item = pydom["#equipment-item"][0].clone() if i > 0 else pydom["#equipment-item"][0]
        new_item._js.textContent = item.strip()
        pydom["#equipment-container"][0]._js.append(new_item._js)
    pydom["#equipment-container"][0]._js.classList.remove("d-none")
else:
    pydom["#equipment-not-available"][0]._js.classList.remove("d-none")

yt_id = (
    extract_yt_id(custom_video_id) if _is_authenticated() else ""
) or extract_yt_id(data.get("yt_video_id", ""))
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
    label.textContent = t("no_video")
    placeholder.appendChild(icon)
    placeholder.appendChild(label)
    ratio_div.replaceWith(placeholder)

instructions = data.get("instructions", "")
if instructions:
    pydom["#exercise-instructions"][0]._js.textContent = instructions
else:
    pydom["#instructions-not-available"][0]._js.classList.remove("d-none")

primary_muscles = data.get("primary_muscles", "")
secondary_muscles = data.get("secondary_muscles", "")
if primary_muscles:
    pydom["#primary-muscles-section"][0]._js.classList.remove("d-none")
    chips = pydom["#primary-muscles-chips"][0]._js
    for muscle in primary_muscles.split(","):
        chip = window.document.createElement("span")
        chip.className = "muscle-chip"
        chip.textContent = muscle.strip()
        chips.appendChild(chip)
if secondary_muscles:
    pydom["#secondary-muscles-section"][0]._js.classList.remove("d-none")
    chips = pydom["#secondary-muscles-chips"][0]._js
    for muscle in secondary_muscles.split(","):
        chip = window.document.createElement("span")
        chip.className = "muscle-chip muscle-chip--secondary"
        chip.textContent = muscle.strip()
        chips.appendChild(chip)
if not primary_muscles and not secondary_muscles:
    pydom["#muscles-not-available"][0]._js.classList.remove("d-none")

cues = data.get("key_cues", "")
if cues:
    if "\\," in cues:
        cues = cues.replace("\\,", "|")
    all_cues = cues.split(",")
    for i, cue in enumerate(all_cues):
        if "|" in cue:
            cue = cue.replace("|", ", ")
        new_cue = pydom["#key-cue"][0].clone() if i > 0 else pydom["#key-cue"][0]
        new_cue._js.textContent = cue.strip()
        pydom["#key-cues-container"][0]._js.append(new_cue._js)
    pydom["#key-cues-container"][0]._js.classList.remove("d-none")
else:
    pydom["#cues-not-available"][0]._js.classList.remove("d-none")

alternatives = data.get("alternatives", "")
if alternatives:
    for i, alternative_id in enumerate(alternatives.split(",")):
        alt_data = catalog.get_exercise(alternative_id.strip())
        if not alt_data:
            continue
        new_alternative = pydom["#alt-ex"][0].clone() if i > 0 else pydom["#alt-ex"][0]
        new_alternative._js.setAttribute("data-id", alt_data["id"])
        new_alternative._js.textContent = alt_data["name"]
        new_alternative._js.onclick = open_exercise
        pydom["#alt-ex-container"][0]._js.append(new_alternative._js)
    pydom["#alt-ex-container"][0]._js.classList.remove("d-none")
else:
    pydom["#alt-not-available"][0]._js.classList.remove("d-none")

apply_html_translations()

pydom["#copyright"][0]._js.innerHTML = copyright()
pydom["#version"][0]._js.innerHTML = current_version()
pydom["#footer"][0]._js.classList.remove("d-none")
