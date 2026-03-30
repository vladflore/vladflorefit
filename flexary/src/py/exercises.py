from pyscript import document, window

import state
from i18n import t
from models import category_to_badge
from workouts import add_exercise_to_workout


def open_exercise(event) -> None:
    card = event.target.closest("[data-exercise-id]")
    if card:
        window.open(f"detail.html?exercise_id={card.getAttribute('data-exercise-id')}", "_blank")


def stop_propagation(event) -> None:
    event.stopPropagation()


def create_card_exercise(template, exercise_data: dict):
    from custom_exercises import delete_custom_exercise

    is_custom = exercise_data.get("is_custom") == "true"

    exercise_html = template.clone()
    exercise_html.id = f"ex-{exercise_data['id']}"
    exercise_html._js.setAttribute("data-exercise-name", exercise_data["name"])
    exercise_html._js.setAttribute("data-exercise-id", exercise_data["id"])

    card_img = exercise_html.find("#card-img")[0]
    if is_custom:
        thumbnail = exercise_data.get("thumbnail_url", "")
        card_img._js.src = thumbnail if thumbnail else "./assets/exercises/placeholder.png"
        card_img._js.alt = exercise_data["name"]
    else:
        card_img._js.src = f"./assets/exercises/{exercise_data['thumbnail_url']}"
        card_img._js.alt = exercise_data["name"]

    exercise_html.find("#card-title")[0]._js.textContent = exercise_data["name"]

    card_el = exercise_html.find(".exercise-card")[0]
    card_el._js.style.cursor = "pointer"
    card_el._js.onclick = open_exercise
    if is_custom:
        card_el._js.classList.add("exercise-card--custom")

    categories = exercise_data["category"].split(",")
    body_parts_badge_element = exercise_html.find("#body-parts-badge")[0]
    category_badge_element = exercise_html.find("#category-badge")[0]
    clean_cat_badge = category_badge_element.clone()
    for i, category in enumerate(categories):
        category = category.strip()
        cat_badge = category_badge_element if i == 0 else clean_cat_badge.clone()
        cat_badge._js.textContent = category
        cat_badge._js.classList.add(category_to_badge.get(category.lower(), "bg-secondary"))
        if i > 0:
            body_parts_badge_element._js.before(cat_badge._js)

    badges_container_element = exercise_html.find("#badges")[0]
    for i, badge in enumerate(exercise_data["body_parts"].split(",")):
        new_badge = (
            exercise_html.find("#body-parts-badge")[0].clone()
            if i > 0
            else exercise_html.find("#body-parts-badge")[0]
        )
        new_badge._js.textContent = badge
        new_badge._js.classList.add("bg-secondary")
        badges_container_element._js.append(new_badge._js)

    yt_id = exercise_data.get("yt_video_id", "")
    video_link = exercise_html.find("#video-link")[0]
    if yt_id:
        video_link._js.href = f"https://www.youtube.com/embed/{yt_id}"
    else:
        video_link._js.removeAttribute("href")
        video_link._js.classList.add("card-action-icon--disabled")
        video_link._js.setAttribute("aria-disabled", "true")
        video_link._js.setAttribute("tabindex", "-1")

    add_btn = exercise_html.find("#add-ex-to-workout")[0]
    add_btn._js.onclick = add_exercise_to_workout

    if is_custom:
        from custom_exercises import open_edit_custom_modal

        card_body = exercise_html.find(".card-body")[0]._js
        card_actions = exercise_html.find(".card-actions")[0]._js

        custom_actions_row = document.createElement("div")
        custom_actions_row.className = "custom-actions-row"

        edit_icon = document.createElement("i")
        edit_icon.className = "bi bi-pencil card-action-icon custom-action-icon"
        edit_icon.title = t("edit_exercise")
        edit_icon.onclick = open_edit_custom_modal

        delete_icon = document.createElement("i")
        delete_icon.className = "bi bi-trash card-action-icon card-action-icon--danger custom-action-icon"
        delete_icon.title = t("remove_btn")
        delete_icon.onclick = delete_custom_exercise

        custom_actions_row.appendChild(edit_icon)
        custom_actions_row.appendChild(delete_icon)

        card_body.insertBefore(custom_actions_row, card_actions)

    return exercise_html
