from pyodide.ffi import create_proxy
from pyscript import document
from pyweb import pydom

import state
from filters import update as update_filters
from i18n import t
from workouts import render_workouts


def _inject_modal_css() -> None:
    if document.getElementById("custom-modal-styles"):
        return
    style = document.createElement("style")
    style.id = "custom-modal-styles"
    style.textContent = (
        ".cm-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);"
        "display:flex;align-items:center;justify-content:center;z-index:2000}"
        ".cm-box{background:#1a1a1a;border:1px solid #ba945e;border-radius:10px;"
        "padding:20px;width:min(420px,92vw);max-height:90vh;overflow-y:auto;"
        "display:flex;flex-direction:column;gap:12px;color:#fff}"
        "@media(max-width:576px){"
        ".cm-overlay{align-items:flex-end}"
        ".cm-box{width:100%;max-height:85vh;border-radius:12px 12px 0 0}}"
    )
    document.head.appendChild(style)


def _make_input_group(label_text: str, input_el, is_textarea: bool = False):
    group = document.createElement("div")
    group.style.display = "flex"
    group.style.flexDirection = "column"
    group.style.gap = "2px"
    label = document.createElement("label")
    label.textContent = label_text
    label.style.fontSize = "0.75rem"
    label.style.color = "rgba(255,255,255,0.6)"
    input_el.style.width = "100%"
    input_el.style.fontSize = "0.8rem"
    if not is_textarea:
        input_el.style.height = "30px"
    input_el.style.padding = "4px 8px"
    input_el.style.borderRadius = "4px"
    input_el.style.border = "1px solid rgba(186,148,94,0.3)"
    input_el.style.backgroundColor = "rgba(255,255,255,0.07)"
    input_el.style.color = "#fff"
    input_el.style.outline = "none"
    if is_textarea:
        input_el.style.resize = "vertical"
    group.appendChild(label)
    group.appendChild(input_el)
    return group


def _make_warning_el():
    el = document.createElement("div")
    el.style.display = "none"
    el.style.color = "#f87171"
    el.style.fontSize = "0.75rem"
    return el


def _show_warning(el, msg: str) -> None:
    el.textContent = msg
    el.style.display = "block"


def _extract_yt_id(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if "youtu.be/" in value:
        return value.split("youtu.be/")[-1].split("?")[0].split("&")[0]
    if "v=" in value:
        return value.split("v=")[-1].split("&")[0]
    return value


def _rebuild_data() -> None:
    state.data = sorted(state.custom_exercises, key=lambda x: x["name"]) + state.base_data
    state.category_count.clear()
    state.body_parts_list.clear()
    seen_bp: set[str] = set()
    for ex in state.data:
        for cat in ex["category"].split(","):
            cat = cat.strip()
            if cat:
                state.category_count[cat] = state.category_count.get(cat, 0) + 1
        for bp in ex["body_parts"].split(","):
            bp = bp.strip()
            if bp and bp not in seen_bp:
                seen_bp.add(bp)
                state.body_parts_list.append(bp)
    state.body_parts_list.sort()
    search_val = pydom["#search-input"][0]._js.value
    update_filters(search_val)


def _open_custom_modal(ex: dict | None = None) -> None:
    """Two-step wizard modal for add (ex=None) and edit (ex=dict)."""
    _inject_modal_css()
    is_edit = ex is not None
    exercise_id = str(ex["id"]) if is_edit else None

    overlay = document.createElement("div")
    overlay.className = "cm-overlay"

    modal = document.createElement("div")
    modal.className = "cm-box"

    header = document.createElement("div")
    header.style.display = "flex"
    header.style.alignItems = "center"
    header.style.justifyContent = "space-between"

    title_el = document.createElement("span")
    title_el.textContent = t("edit_exercise_modal") if is_edit else t("new_exercise_modal")
    title_el.style.fontWeight = "700"
    title_el.style.fontSize = "0.95rem"
    title_el.style.color = "#ba945e"
    title_el.style.letterSpacing = "0.03em"

    step_el = document.createElement("span")
    step_el.textContent = t("step_indicator", step=1, total=2)
    step_el.style.fontSize = "0.75rem"
    step_el.style.color = "rgba(255,255,255,0.4)"

    header.appendChild(title_el)
    header.appendChild(step_el)
    modal.appendChild(header)

    step1 = document.createElement("div")
    step1.style.display = "flex"
    step1.style.flexDirection = "column"
    step1.style.gap = "12px"

    if not is_edit:
        notice = document.createElement("div")
        notice.style.display = "flex"
        notice.style.gap = "8px"
        notice.style.alignItems = "flex-start"
        notice.style.background = "rgba(245,158,11,0.08)"
        notice.style.border = "1px solid rgba(245,158,11,0.2)"
        notice.style.borderRadius = "6px"
        notice.style.padding = "8px 10px"
        notice_icon = document.createElement("i")
        notice_icon.className = "bi bi-info-circle"
        notice_icon.style.color = "#f59e0b"
        notice_icon.style.fontSize = "0.85rem"
        notice_icon.style.flexShrink = "0"
        notice_icon.style.marginTop = "1px"
        notice_text = document.createElement("span")
        notice_text.textContent = t("local_storage_notice")
        notice_text.style.fontSize = "0.74rem"
        notice_text.style.color = "rgba(255,255,255,0.55)"
        notice_text.style.lineHeight = "1.4"
        notice.appendChild(notice_icon)
        notice.appendChild(notice_text)
        step1.appendChild(notice)

    name_input = document.createElement("input")
    name_input.type = "text"
    name_input.placeholder = t("name_placeholder")
    if is_edit:
        name_input.value = ex["name"]
    step1.appendChild(_make_input_group(t("name_label"), name_input))

    category_select = document.createElement("select")
    category_select.style.height = "30px"
    for value in ("Strength", "Conditioning", "Mobility"):
        opt = document.createElement("option")
        opt.value = value
        opt.textContent = value
        if is_edit and value == ex["category"]:
            opt.selected = True
        category_select.appendChild(opt)
    step1.appendChild(_make_input_group(t("category_label"), category_select))

    body_parts_input = document.createElement("input")
    body_parts_input.type = "text"
    body_parts_input.placeholder = t("body_parts_placeholder")
    if is_edit:
        body_parts_input.value = ex.get("body_parts", "")
    step1.appendChild(_make_input_group(t("body_parts_label"), body_parts_input))

    image_input = document.createElement("input")
    image_input.type = "url"
    image_input.placeholder = t("image_url_placeholder")
    if is_edit:
        image_input.value = ex.get("thumbnail_url", "")
    step1.appendChild(_make_input_group(t("image_url_label"), image_input))

    video_input = document.createElement("input")
    video_input.type = "text"
    video_input.placeholder = t("video_placeholder")
    if is_edit:
        video_input.value = ex.get("yt_video_id", "")
    step1.appendChild(_make_input_group(t("video_label"), video_input))

    warning1 = _make_warning_el()
    step1.appendChild(warning1)

    footer1 = document.createElement("div")
    footer1.style.display = "flex"
    footer1.style.justifyContent = "flex-end"
    footer1.style.gap = "8px"
    footer1.style.marginTop = "4px"

    cancel_btn = document.createElement("button")
    cancel_btn.type = "button"
    cancel_btn.textContent = t("cancel_btn")
    cancel_btn.style.borderRadius = "4px"
    cancel_btn.style.fontSize = "0.8rem"
    cancel_btn.style.border = "1px solid #555"
    cancel_btn.style.color = "#aaa"
    cancel_btn.style.background = "transparent"
    cancel_btn.style.cursor = "pointer"
    cancel_btn.style.padding = "4px 14px"

    next_btn = document.createElement("button")
    next_btn.type = "button"
    next_btn.textContent = t("next_btn")
    next_btn.className = "btn btn-outline-gold btn-sm"
    next_btn.style.padding = "4px 14px"

    footer1.appendChild(cancel_btn)
    footer1.appendChild(next_btn)
    step1.appendChild(footer1)
    modal.appendChild(step1)

    step2 = document.createElement("div")
    step2.style.display = "none"
    step2.style.flexDirection = "column"
    step2.style.gap = "12px"

    instructions_input = document.createElement("textarea")
    instructions_input.rows = 3
    instructions_input.placeholder = t("instructions_placeholder")
    if is_edit:
        instructions_input.value = ex.get("instructions", "")
    step2.appendChild(_make_input_group(t("instructions_label"), instructions_input, is_textarea=True))

    primary_muscles_input = document.createElement("input")
    primary_muscles_input.type = "text"
    primary_muscles_input.placeholder = t("primary_muscles_placeholder")
    if is_edit:
        primary_muscles_input.value = ex.get("primary_muscles", "")
    step2.appendChild(_make_input_group(t("primary_muscles_label"), primary_muscles_input))

    secondary_muscles_input = document.createElement("input")
    secondary_muscles_input.type = "text"
    secondary_muscles_input.placeholder = t("secondary_muscles_placeholder")
    if is_edit:
        secondary_muscles_input.value = ex.get("secondary_muscles", "")
    step2.appendChild(_make_input_group(t("secondary_muscles_label"), secondary_muscles_input))

    key_cues_input = document.createElement("input")
    key_cues_input.type = "text"
    key_cues_input.placeholder = t("key_cues_placeholder")
    if is_edit:
        key_cues_input.value = ex.get("key_cues", "")
    step2.appendChild(_make_input_group(t("key_cues_label"), key_cues_input))

    alternatives_input = document.createElement("input")
    alternatives_input.type = "text"
    alternatives_input.placeholder = t("alternatives_placeholder")
    if is_edit:
        alternatives_input.value = ex.get("alternatives", "")
    step2.appendChild(_make_input_group(t("alternatives_label"), alternatives_input))

    footer2 = document.createElement("div")
    footer2.style.display = "flex"
    footer2.style.justifyContent = "space-between"
    footer2.style.gap = "8px"
    footer2.style.marginTop = "4px"

    back_btn = document.createElement("button")
    back_btn.type = "button"
    back_btn.textContent = t("back_btn")
    back_btn.style.borderRadius = "4px"
    back_btn.style.fontSize = "0.8rem"
    back_btn.style.border = "1px solid #555"
    back_btn.style.color = "#aaa"
    back_btn.style.background = "transparent"
    back_btn.style.cursor = "pointer"
    back_btn.style.padding = "4px 14px"

    confirm_btn = document.createElement("button")
    confirm_btn.type = "button"
    confirm_btn.textContent = t("save_btn") if is_edit else t("add_btn")
    confirm_btn.className = "btn btn-outline-gold btn-sm"
    confirm_btn.style.padding = "4px 14px"

    footer2.appendChild(back_btn)
    footer2.appendChild(confirm_btn)
    step2.appendChild(footer2)
    modal.appendChild(step2)

    overlay.appendChild(modal)
    document.body.appendChild(overlay)
    name_input.focus()

    def on_cancel(evt):
        overlay.remove()

    def on_overlay_click(evt):
        if evt.target == overlay:
            overlay.remove()

    def on_next(evt):
        name = name_input.value.strip()
        if not name:
            _show_warning(warning1, t("name_required"))
            name_input.focus()
            return
        body_parts = body_parts_input.value.strip()
        if not body_parts:
            _show_warning(warning1, t("body_parts_required"))
            body_parts_input.focus()
            return
        warning1.style.display = "none"
        step1.style.display = "none"
        step2.style.display = "flex"
        step_el.textContent = t("step_indicator", step=2, total=2)

    def on_back(evt):
        step2.style.display = "none"
        step1.style.display = "flex"
        step_el.textContent = t("step_indicator", step=1, total=2)

    def on_confirm(evt):
        name = name_input.value.strip()
        category = category_select.value
        body_parts = body_parts_input.value.strip()

        if is_edit:
            ex["name"] = name
            ex["category"] = category
            ex["body_parts"] = body_parts
            ex["thumbnail_url"] = image_input.value.strip()
            ex["yt_video_id"] = _extract_yt_id(video_input.value)
            ex["instructions"] = instructions_input.value.strip()
            ex["primary_muscles"] = primary_muscles_input.value.strip()
            ex["secondary_muscles"] = secondary_muscles_input.value.strip()
            ex["key_cues"] = key_cues_input.value.strip()
            ex["alternatives"] = alternatives_input.value.strip()
            state.save_custom_exercises()
            for w in state.workouts:
                for wex in w.exercises:
                    if str(wex.id) == exercise_id:
                        wex.name = name
            state.save_workouts()
            render_workouts(state.workouts)
        else:
            new_id = state.next_custom_id()
            new_ex = {
                "id": str(new_id),
                "name": name,
                "category": category,
                "body_parts": body_parts,
                "thumbnail_url": image_input.value.strip(),
                "yt_video_id": _extract_yt_id(video_input.value),
                "instructions": instructions_input.value.strip(),
                "primary_muscles": primary_muscles_input.value.strip(),
                "secondary_muscles": secondary_muscles_input.value.strip(),
                "key_cues": key_cues_input.value.strip(),
                "alternatives": alternatives_input.value.strip(),
                "is_custom": "true",
            }
            state.custom_exercises.append(new_ex)
            state.save_custom_exercises()

        _rebuild_data()
        overlay.remove()

    cancel_btn.onclick = create_proxy(on_cancel)
    next_btn.onclick = create_proxy(on_next)
    back_btn.onclick = create_proxy(on_back)
    confirm_btn.onclick = create_proxy(on_confirm)
    overlay.addEventListener("click", create_proxy(on_overlay_click))


def delete_custom_exercise(event) -> None:
    event.stopPropagation()
    card = event.target.closest("[data-exercise-id]")
    if not card:
        return
    exercise_id = card.getAttribute("data-exercise-id")
    state.custom_exercises[:] = [
        ex for ex in state.custom_exercises if str(ex["id"]) != exercise_id
    ]
    state.save_custom_exercises()
    for w in state.workouts:
        w.exercises[:] = [ex for ex in w.exercises if str(ex.id) != exercise_id]
    state.save_workouts()
    render_workouts(state.workouts)
    _rebuild_data()


def open_add_custom_modal(event) -> None:
    _open_custom_modal(ex=None)


def open_edit_custom_modal(event) -> None:
    event.stopPropagation()
    card = event.target.closest("[data-exercise-id]")
    if not card:
        return
    exercise_id = card.getAttribute("data-exercise-id")
    ex = next((e for e in state.custom_exercises if str(e["id"]) == exercise_id), None)
    if not ex:
        return
    _open_custom_modal(ex=ex)
