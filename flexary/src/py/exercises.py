from pyscript import window

import state
from models import category_to_badge
from workouts import add_exercise_to_workout


def open_exercise(event) -> None:
    card = event.target.closest("[data-exercise-id]")
    if card:
        window.open(f"detail.html?exercise_id={card.getAttribute('data-exercise-id')}", "_blank")


def stop_propagation(event) -> None:
    event.stopPropagation()


def create_card_exercise(template, exercise_data: dict):
    exercise_html = template.clone()
    exercise_html.id = f"ex-{exercise_data['id']}"
    exercise_html._js.setAttribute("data-exercise-name", exercise_data["name"])
    exercise_html._js.setAttribute("data-exercise-id", exercise_data["id"])

    card_img = exercise_html.find("#card-img")[0]
    card_img._js.src = f"./assets/exercises/{exercise_data['thumbnail_url']}"
    card_img._js.alt = exercise_data["name"]

    exercise_html.find("#card-title")[0]._js.textContent = exercise_data["name"]

    card_el = exercise_html.find(".exercise-card")[0]
    card_el._js.style.cursor = "pointer"
    card_el._js.onclick = open_exercise

    categories = exercise_data["category"].split(",")
    body_parts_badge_element = exercise_html.find("#body-parts-badge")[0]
    category_badge_element = exercise_html.find("#category-badge")[0]
    clean_cat_badge = category_badge_element.clone()
    for i, category in enumerate(categories):
        category = category.strip()
        cat_badge = category_badge_element if i == 0 else clean_cat_badge.clone()
        cat_badge._js.textContent = category
        cat_badge._js.classList.add(category_to_badge.get(category.lower()))
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

    yt_video_link = f"https://www.youtube.com/embed/{exercise_data['yt_video_id']}"
    exercise_html.find("#video-link")[0]._js.href = yt_video_link

    exercise_html.find("#add-ex-to-workout")[0]._js.onclick = add_exercise_to_workout

    return exercise_html
