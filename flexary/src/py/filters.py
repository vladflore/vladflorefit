import json

import catalog
from js import localStorage
from pyodide.ffi import create_proxy
from pyscript import document, when
from pyweb import pydom

import state
from i18n import t
from models import category_to_badge
from exercises import create_card_exercise


def _save_filters() -> None:
    localStorage.setItem(
        state.ls_filters_key,
        json.dumps({
            "categories": list(state.active_category_filters),
            "body_parts": list(state.active_body_part_filters),
        }),
    )
    _update_filter_badge()


def _update_filter_badge() -> None:
    count = len(state.active_category_filters) + len(state.active_body_part_filters)
    badge = document.getElementById("filter-active-count")
    if badge is None:
        return
    if count:
        badge.textContent = str(count)
        badge.classList.remove("d-none")
    else:
        badge.classList.add("d-none")


def build_category_badges(counts: dict) -> str:
    html = ""
    for category in catalog.category_count():
        badge_class = category_to_badge.get(category.lower())
        active_class = " category-filter-active" if category in state.active_category_filters else ""
        count = counts.get(category, 0)
        html += (
            f'<span class="badge {badge_class}{active_class} me-1"'
            f' data-category="{category}" style="cursor: pointer">{category} ({count})</span>'
        )
    return html


def build_body_part_badges(counts: dict) -> str:
    html = ""
    for bp in catalog.body_parts_list():
        active_class = " body-part-filter-active" if bp in state.active_body_part_filters else ""
        count = counts.get(bp, 0)
        html += (
            f'<span class="badge bg-secondary{active_class} me-1"'
            f' data-body-part="{bp}" style="cursor: pointer">{bp} ({count})</span>'
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
    _save_filters()
    update(pydom["#search-input"][0]._js.value)


def filter_by_body_part(event) -> None:
    bp = event.target.getAttribute("data-body-part")
    if bp in state.active_body_part_filters:
        state.active_body_part_filters.discard(bp)
    else:
        state.active_body_part_filters.add(bp)
    _save_filters()
    update(pydom["#search-input"][0]._js.value)


def update_exercise_stats(display_count: int, total: int) -> None:
    dims = []
    if state.active_category_filters:
        dims.append(" or ".join(sorted(state.active_category_filters)))
    if state.active_body_part_filters:
        dims.append(" or ".join(sorted(state.active_body_part_filters)))
    stats = f"{display_count} · {' & '.join(dims)}" if dims else t("exercises_count", count=total)
    pydom["#exercise-stats"][0]._js.textContent = stats


def update(search_str: str) -> None:
    search_str = search_str.strip().lower()
    search_filtered = [
        ex for ex in catalog.all_exercises()
        if search_str in ex["name"].lower()
        or search_str in ex["category"].lower()
        or search_str in ex["body_parts"].lower()
    ]

    display_data = search_filtered
    if state.active_category_filters:
        display_data = [
            ex for ex in display_data
            if any(c.strip() in state.active_category_filters for c in ex["category"].split(","))
        ]
    if state.active_body_part_filters:
        display_data = [
            ex for ex in display_data
            if any(bp.strip() in state.active_body_part_filters for bp in ex["body_parts"].split(","))
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

    bp_filtered = [
        ex for ex in search_filtered
        if not state.active_body_part_filters
        or any(bp.strip() in state.active_body_part_filters for bp in ex["body_parts"].split(","))
    ]
    cat_counts: dict = {}
    for ex in bp_filtered:
        for c in ex["category"].split(","):
            c = c.strip()
            if c:
                cat_counts[c] = cat_counts.get(c, 0) + 1

    cat_filtered = [
        ex for ex in search_filtered
        if not state.active_category_filters
        or any(c.strip() in state.active_category_filters for c in ex["category"].split(","))
    ]
    bp_counts: dict = {}
    for ex in cat_filtered:
        for bp in ex["body_parts"].split(","):
            bp = bp.strip()
            if bp:
                bp_counts[bp] = bp_counts.get(bp, 0) + 1

    pydom[state.exercises_per_category_badges_row_id][0]._js.innerHTML = build_category_badges(cat_counts)
    attach_category_filter_listeners()
    pydom[state.exercises_per_body_part_badges_row_id][0]._js.innerHTML = build_body_part_badges(bp_counts)
    attach_body_part_filter_listeners()
    update_exercise_stats(len(display_data), len(search_filtered))
    _update_filter_badge()


def clear_filters(event) -> None:
    state.active_category_filters.clear()
    state.active_body_part_filters.clear()
    _save_filters()
    search_input = document.getElementById("search-input")
    search_input.value = ""
    update("")


@when("input", "#search-input")
def handle_search_input(event):
    update(event.target.value)
