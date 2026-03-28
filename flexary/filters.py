from pyodide.ffi import create_proxy
from pyscript import document, when
from pyweb import pydom

import state
from models import category_to_badge
from exercises import create_card_exercise


def build_category_badges() -> str:
    html = ""
    for category in state.category_count:
        badge_class = category_to_badge.get(category.lower())
        active_class = " category-filter-active" if category in state.active_category_filters else ""
        html += (
            f'<span class="badge {badge_class}{active_class} me-1"'
            f' data-category="{category}" style="cursor: pointer">{category}</span>'
        )
    return html


def build_body_part_badges() -> str:
    html = ""
    for bp in state.body_parts_list:
        active_class = " body-part-filter-active" if bp in state.active_body_part_filters else ""
        html += (
            f'<span class="badge bg-secondary{active_class} me-1"'
            f' data-body-part="{bp}" style="cursor: pointer">{bp}</span>'
        )
    return html


def attach_category_filter_listeners() -> None:
    container = document.getElementById("exercises-per-category-badges-row")
    badges = container.querySelectorAll("[data-category]")
    for i in range(badges.length):
        badges.item(i).addEventListener("click", create_proxy(filter_by_category))


def attach_body_part_filter_listeners() -> None:
    container = document.getElementById("exercises-per-body-part-badges-row")
    badges = container.querySelectorAll("[data-body-part]")
    for i in range(badges.length):
        badges.item(i).addEventListener("click", create_proxy(filter_by_body_part))


def filter_by_category(event) -> None:
    category = event.target.getAttribute("data-category")
    if category in state.active_category_filters:
        state.active_category_filters.discard(category)
    else:
        state.active_category_filters.add(category)
    update(pydom["#search-input"][0]._js.value)


def filter_by_body_part(event) -> None:
    bp = event.target.getAttribute("data-body-part")
    if bp in state.active_body_part_filters:
        state.active_body_part_filters.discard(bp)
    else:
        state.active_body_part_filters.add(bp)
    update(pydom["#search-input"][0]._js.value)


def update_exercise_stats(display_count: int, total: int) -> None:
    parts = sorted(state.active_category_filters) + sorted(state.active_body_part_filters)
    stats = f"{display_count} · {' & '.join(parts)}" if parts else f"{total} exercises"
    pydom["#exercise-stats"][0]._js.textContent = stats


def update(search_str: str) -> None:
    search_str = search_str.strip().lower()
    search_filtered = [ex for ex in state.data if search_str in ex["name"].lower()]

    display_data = search_filtered
    if state.active_category_filters:
        display_data = [
            ex for ex in display_data
            if state.active_category_filters & {c.strip() for c in ex["category"].split(",")}
        ]
    if state.active_body_part_filters:
        display_data = [
            ex for ex in display_data
            if state.active_body_part_filters & {bp.strip() for bp in ex["body_parts"].split(",")}
        ]

    state.exercises_row._js.innerHTML = ""
    empty_state = pydom["#empty-state"][0]
    if display_data:
        empty_state._js.classList.add("d-none")
        for i, exercise_data in enumerate(display_data):
            card = create_card_exercise(state.exercise_template, exercise_data)
            card._js.classList.add("card-animate")
            card._js.style.animationDelay = f"{min(i * 30, 300)}ms"
            state.exercises_row.append(card)
    else:
        empty_state._js.classList.remove("d-none")

    pydom[state.exercises_per_category_badges_row_id][0]._js.innerHTML = build_category_badges()
    attach_category_filter_listeners()
    pydom[state.exercises_per_body_part_badges_row_id][0]._js.innerHTML = build_body_part_badges()
    attach_body_part_filter_listeners()
    update_exercise_stats(len(display_data), len(search_filtered))


def filter_library(event) -> None:
    update(event.target.parentElement.children[0].value)


def clear_filters(event) -> None:
    state.active_category_filters.clear()
    state.active_body_part_filters.clear()
    update(state.q("#search-input").value)


@when("input", "#search-input")
def handle_search_input(event):
    update(event.target.value)
