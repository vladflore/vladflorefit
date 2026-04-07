import asyncio
import datetime
import json
from uuid import uuid4

from js import window
from pyodide.ffi import create_proxy
from pyscript import document

import state
from i18n import t
from models import Exercise, Workout
from workout_domain import _cleanup_supersets, _event_attr, _find_exercise


def _inject_no_spinner_style():
    _id = "no-number-spinner-style"
    if not document.getElementById(_id):
        style = document.createElement("style")
        style.id = _id
        style.textContent = (
            "input.no-spinner::-webkit-inner-spin-button,"
            "input.no-spinner::-webkit-outer-spin-button{-webkit-appearance:none;margin:0;}"
            "input.no-spinner{-moz-appearance:textfield;}"
        )
        document.head.appendChild(style)


def _make_input_group(label_text: str, input_el):
    group = document.createElement("div")
    group.style.display = "flex"
    group.style.flexDirection = "column"
    group.style.gap = "2px"
    label = document.createElement("label")
    label.textContent = label_text
    label.style.fontSize = "0.75rem"
    label.style.color = "rgba(255,255,255,0.75)"
    input_el.style.width = "100%"
    input_el.style.fontSize = "0.8rem"
    if input_el.tagName.lower() != "textarea":
        input_el.style.height = "26px"
    input_el.style.padding = "2px 6px"
    input_el.style.borderRadius = "4px"
    input_el.style.border = "1px solid rgba(255,255,255,0.2)"
    input_el.style.backgroundColor = "rgba(255,255,255,0.1)"
    input_el.style.color = "#fff"
    group.appendChild(label)
    group.appendChild(input_el)
    return group


def _make_warning_el():
    el = document.createElement("div")
    el.style.display = "none"
    el.style.color = "#f87171"
    el.style.fontSize = "0.75rem"
    el.style.marginTop = "-4px"
    return el


def _show_warning(el, msg: str) -> None:
    el.textContent = msg
    el.style.display = "block"


def _make_sets_stepper(initial_value: int = 1):
    input_el = document.createElement("input")
    input_el.type = "hidden"
    input_el.value = str(initial_value)

    display = document.createElement("span")
    display.textContent = str(initial_value)
    display.style.minWidth = "32px"
    display.style.textAlign = "center"
    display.style.fontSize = "0.95rem"
    display.style.fontWeight = "600"
    display.style.color = "#fff"
    display.style.userSelect = "none"

    def _make_step_btn(symbol):
        btn = document.createElement("button")
        btn.type = "button"
        btn.textContent = symbol
        btn.classList.add("btn", "btn-outline-gold", "btn-sm")
        btn.style.width = "32px"
        btn.style.height = "32px"
        btn.style.padding = "0"
        btn.style.fontSize = "1.1rem"
        btn.style.lineHeight = "1"
        btn.style.flexShrink = "0"
        btn.style.borderRadius = "50%"
        return btn

    minus_btn = _make_step_btn("\u2212")
    plus_btn = _make_step_btn("+")

    def _on_minus(evt):
        evt.preventDefault()
        cur = int(input_el.value) if input_el.value.strip().isdigit() else 1
        if cur > 1:
            input_el.value = str(cur - 1)
            display.textContent = input_el.value
            input_el.dispatchEvent(window.Event.new("input", {"bubbles": True}))

    def _on_plus(evt):
        evt.preventDefault()
        cur = int(input_el.value) if input_el.value.strip().isdigit() else 1
        input_el.value = str(cur + 1)
        display.textContent = input_el.value
        input_el.dispatchEvent(window.Event.new("input", {"bubbles": True}))

    minus_btn.addEventListener("click", create_proxy(_on_minus))
    plus_btn.addEventListener("click", create_proxy(_on_plus))

    label = document.createElement("label")
    label.textContent = t("sets_label")
    label.style.fontSize = "0.75rem"
    label.style.color = "rgba(255,255,255,0.75)"
    label.style.textAlign = "center"

    row = document.createElement("div")
    row.style.display = "flex"
    row.style.alignItems = "center"
    row.style.justifyContent = "center"
    row.style.gap = "6px"
    row.appendChild(minus_btn)
    row.appendChild(display)
    row.appendChild(plus_btn)
    row.appendChild(input_el)

    container = document.createElement("div")
    container.style.display = "flex"
    container.style.flexDirection = "column"
    container.style.gap = "2px"
    container.appendChild(label)
    container.appendChild(row)

    return container, input_el


def _make_rest_stepper(initial_value: int = 0):
    def _fmt(v):
        if v == 0:
            return "0"
        m, s = divmod(v, 60)
        if m and s:
            return f"{m}m {s}s"
        return f"{m}m" if m else f"{s}s"

    input_el = document.createElement("input")
    input_el.type = "hidden"
    input_el.value = str(initial_value)

    display = document.createElement("span")
    display.textContent = _fmt(initial_value)
    display.style.minWidth = "48px"
    display.style.textAlign = "center"
    display.style.fontSize = "0.95rem"
    display.style.fontWeight = "600"
    display.style.color = "#fff"
    display.style.userSelect = "none"

    def _make_step_btn(symbol):
        btn = document.createElement("button")
        btn.type = "button"
        btn.textContent = symbol
        btn.classList.add("btn", "btn-outline-gold", "btn-sm")
        btn.style.width = "32px"
        btn.style.height = "32px"
        btn.style.padding = "0"
        btn.style.fontSize = "1.1rem"
        btn.style.lineHeight = "1"
        btn.style.flexShrink = "0"
        btn.style.borderRadius = "50%"
        return btn

    minus_btn = _make_step_btn("\u2212")
    plus_btn = _make_step_btn("+")

    def _set_value(v):
        input_el.value = str(v)
        display.textContent = _fmt(v)

    def _on_minus(evt):
        evt.preventDefault()
        cur = int(input_el.value) if input_el.value.strip().isdigit() else 0
        if cur >= 15:
            _set_value(cur - 15)

    def _on_plus(evt):
        evt.preventDefault()
        cur = int(input_el.value) if input_el.value.strip().isdigit() else 0
        _set_value(cur + 15)

    minus_btn.addEventListener("click", create_proxy(_on_minus))
    plus_btn.addEventListener("click", create_proxy(_on_plus))

    label = document.createElement("label")
    label.textContent = t("rest_label")
    label.style.fontSize = "0.75rem"
    label.style.color = "rgba(255,255,255,0.75)"
    label.style.textAlign = "center"

    row = document.createElement("div")
    row.style.display = "flex"
    row.style.alignItems = "center"
    row.style.justifyContent = "center"
    row.style.gap = "6px"
    row.appendChild(minus_btn)
    row.appendChild(display)
    row.appendChild(plus_btn)
    row.appendChild(input_el)

    container = document.createElement("div")
    container.style.display = "flex"
    container.style.flexDirection = "column"
    container.style.gap = "2px"
    container.appendChild(label)
    container.appendChild(row)

    return container, input_el, _set_value


def _make_time_wheel(initial_value: str = ""):
    h, m, s = 0, 0, 0
    if initial_value:
        parts_t = initial_value.split(":")
        if len(parts_t) == 3:
            try:
                h = max(0, min(23, int(parts_t[0])))
                m = max(0, min(59, int(parts_t[1])))
                s = max(0, min(59, int(parts_t[2])))
            except (ValueError, IndexError):
                pass

    vals = [h, m, s]
    maxvals = [23, 59, 59]

    def _make_col(idx, col_label):
        col = document.createElement("div")
        col.style.display = "flex"
        col.style.flexDirection = "column"
        col.style.alignItems = "center"
        col.style.gap = "3px"

        def _btn(icon_cls):
            b = document.createElement("button")
            b.type = "button"
            b.innerHTML = f'<i class="bi {icon_cls}"></i>'
            b.classList.add("btn", "btn-outline-gold", "btn-sm")
            b.style.width = "26px"
            b.style.height = "26px"
            b.style.padding = "0"
            b.style.fontSize = "0.65rem"
            b.style.lineHeight = "1"
            b.style.borderRadius = "50%"
            b.style.flexShrink = "0"
            return b

        up = _btn("bi-chevron-up")
        down = _btn("bi-chevron-down")

        disp = document.createElement("span")
        disp.textContent = f"{vals[idx]:02d}"
        disp.style.fontSize = "1.05rem"
        disp.style.fontWeight = "600"
        disp.style.color = "#fff"
        disp.style.minWidth = "28px"
        disp.style.textAlign = "center"
        disp.style.userSelect = "none"

        unit_lbl = document.createElement("span")
        unit_lbl.textContent = col_label
        unit_lbl.style.fontSize = "0.6rem"
        unit_lbl.style.color = "rgba(255,255,255,0.45)"
        unit_lbl.style.textAlign = "center"

        def _up(evt, i=idx):
            evt.preventDefault()
            vals[i] = 0 if vals[i] >= maxvals[i] else vals[i] + 1
            disp.textContent = f"{vals[i]:02d}"

        def _down(evt, i=idx):
            evt.preventDefault()
            vals[i] = maxvals[i] if vals[i] <= 0 else vals[i] - 1
            disp.textContent = f"{vals[i]:02d}"

        up.addEventListener("click", create_proxy(_up))
        down.addEventListener("click", create_proxy(_down))

        col.appendChild(up)
        col.appendChild(disp)
        col.appendChild(down)
        col.appendChild(unit_lbl)
        return col

    def _colon():
        sep = document.createElement("span")
        sep.textContent = ":"
        sep.style.color = "#ba945e"
        sep.style.fontWeight = "700"
        sep.style.fontSize = "1.1rem"
        sep.style.alignSelf = "center"
        sep.style.marginBottom = "14px"
        return sep

    field_lbl = document.createElement("label")
    field_lbl.textContent = t("time_label")
    field_lbl.style.fontSize = "0.75rem"
    field_lbl.style.color = "rgba(255,255,255,0.75)"
    field_lbl.style.textAlign = "center"

    wheel_row = document.createElement("div")
    wheel_row.style.display = "flex"
    wheel_row.style.alignItems = "stretch"
    wheel_row.style.justifyContent = "center"
    wheel_row.style.gap = "4px"
    wheel_row.appendChild(_make_col(0, "h"))
    wheel_row.appendChild(_colon())
    wheel_row.appendChild(_make_col(1, "m"))
    wheel_row.appendChild(_colon())
    wheel_row.appendChild(_make_col(2, "s"))

    container = document.createElement("div")
    container.style.display = "flex"
    container.style.flexDirection = "column"
    container.style.alignItems = "center"
    container.style.gap = "4px"
    container.appendChild(field_lbl)
    container.appendChild(wheel_row)

    def get_value():
        if vals[0] == 0 and vals[1] == 0 and vals[2] == 0:
            return ""
        return f"{vals[0]:02d}:{vals[1]:02d}:{vals[2]:02d}"

    return container, get_value


def _make_reps_stepper(initial_value: str = ""):
    try:
        v = int(initial_value.strip()) if initial_value.strip().isdigit() else 0
    except ValueError:
        v = 0
    val = [max(0, v)]

    display = document.createElement("span")
    display.textContent = str(val[0])
    display.style.minWidth = "32px"
    display.style.textAlign = "center"
    display.style.fontSize = "0.95rem"
    display.style.fontWeight = "600"
    display.style.color = "#fff"
    display.style.userSelect = "none"

    def _btn(symbol):
        b = document.createElement("button")
        b.type = "button"
        b.textContent = symbol
        b.classList.add("btn", "btn-outline-gold", "btn-sm")
        b.style.width = "26px"
        b.style.height = "26px"
        b.style.padding = "0"
        b.style.fontSize = "1rem"
        b.style.lineHeight = "1"
        b.style.borderRadius = "50%"
        b.style.flexShrink = "0"
        return b

    minus_btn = _btn("\u2212")
    plus_btn = _btn("+")

    def _on_minus(evt):
        evt.preventDefault()
        if val[0] > 0:
            val[0] -= 1
            display.textContent = str(val[0])

    def _on_plus(evt):
        evt.preventDefault()
        val[0] += 1
        display.textContent = str(val[0])

    minus_btn.addEventListener("click", create_proxy(_on_minus))
    plus_btn.addEventListener("click", create_proxy(_on_plus))

    lbl = document.createElement("label")
    lbl.textContent = t("reps_label")
    lbl.style.fontSize = "0.75rem"
    lbl.style.color = "rgba(255,255,255,0.75)"
    lbl.style.textAlign = "center"

    row = document.createElement("div")
    row.style.display = "flex"
    row.style.alignItems = "center"
    row.style.justifyContent = "center"
    row.style.gap = "10px"
    row.appendChild(minus_btn)
    row.appendChild(display)
    row.appendChild(plus_btn)

    container = document.createElement("div")
    container.style.display = "flex"
    container.style.flexDirection = "column"
    container.style.alignItems = "center"
    container.style.gap = "4px"
    container.appendChild(lbl)
    container.appendChild(row)

    def get_value():
        return str(val[0]) if val[0] > 0 else ""

    return container, get_value


def _make_distance_stepper(initial_value: str = ""):
    unit = ["m"]
    val = [0]
    s = initial_value.strip().lower()
    if s.endswith("km"):
        try:
            val[0] = float(s[:-2])
            unit[0] = "km"
        except ValueError:
            pass
    elif s.endswith("m"):
        try:
            val[0] = int(s[:-1])
        except ValueError:
            pass
    elif s:
        try:
            val[0] = int(s)
        except ValueError:
            pass

    steps = {"m": 1, "km": 1}

    _inject_no_spinner_style()

    display = document.createElement("input")
    display.type = "number"
    display.min = "0"
    display.value = str(val[0])
    display.classList.add("no-spinner")
    display.style.width = "64px"
    display.style.textAlign = "center"
    display.style.fontSize = "0.95rem"
    display.style.fontWeight = "600"
    display.style.color = "#fff"
    display.style.background = "transparent"
    display.style.border = "1px solid rgba(255,255,255,0.3)"
    display.style.borderRadius = "6px"
    display.style.padding = "2px 4px"

    unit_btn = document.createElement("button")
    unit_btn.type = "button"
    unit_btn.textContent = unit[0]
    unit_btn.classList.add("btn", "btn-outline-gold", "btn-sm")
    unit_btn.style.padding = "0 6px"
    unit_btn.style.height = "26px"
    unit_btn.style.fontSize = "0.7rem"
    unit_btn.style.borderRadius = "12px"
    unit_btn.style.flexShrink = "0"

    def _btn(symbol):
        b = document.createElement("button")
        b.type = "button"
        b.textContent = symbol
        b.classList.add("btn", "btn-outline-gold", "btn-sm")
        b.style.width = "26px"
        b.style.height = "26px"
        b.style.padding = "0"
        b.style.fontSize = "1rem"
        b.style.lineHeight = "1"
        b.style.borderRadius = "50%"
        b.style.flexShrink = "0"
        return b

    minus_btn = _btn("\u2212")
    plus_btn = _btn("+")

    def _on_minus(evt):
        evt.preventDefault()
        step = steps[unit[0]]
        val[0] = round(max(0, val[0] - step), 3)
        display.value = str(val[0])

    def _on_plus(evt):
        evt.preventDefault()
        val[0] = round(val[0] + steps[unit[0]], 3)
        display.value = str(val[0])

    def _on_unit_toggle(evt):
        evt.preventDefault()
        if unit[0] == "m":
            unit[0] = "km"
            val[0] = round(val[0] / 1000, 3)
        else:
            unit[0] = "m"
            val[0] = int(round(val[0] * 1000))
        unit_btn.textContent = unit[0]
        display.value = str(val[0])

    def _on_input(evt):
        try:
            v = float(display.value or "0")
            val[0] = max(0, v) if unit[0] == "km" else max(0, int(v))
        except (ValueError, TypeError):
            pass

    minus_btn.addEventListener("click", create_proxy(_on_minus))
    plus_btn.addEventListener("click", create_proxy(_on_plus))
    unit_btn.addEventListener("click", create_proxy(_on_unit_toggle))
    display.addEventListener("input", create_proxy(_on_input))

    lbl = document.createElement("label")
    lbl.textContent = t("distance_label")
    lbl.style.fontSize = "0.75rem"
    lbl.style.color = "rgba(255,255,255,0.75)"
    lbl.style.textAlign = "center"

    row = document.createElement("div")
    row.style.display = "flex"
    row.style.alignItems = "center"
    row.style.justifyContent = "center"
    row.style.gap = "10px"
    row.appendChild(minus_btn)
    row.appendChild(display)
    row.appendChild(unit_btn)
    row.appendChild(plus_btn)

    container = document.createElement("div")
    container.style.display = "flex"
    container.style.flexDirection = "column"
    container.style.alignItems = "center"
    container.style.gap = "4px"
    container.appendChild(lbl)
    container.appendChild(row)

    def get_value():
        return f"{val[0]}{unit[0]}" if val[0] > 0 else ""

    return container, get_value


def _make_per_set_group(sets: int, reps_list=None, time_list=None, dist_list=None):
    reps_list = list(reps_list or [])
    time_list = list(time_list or [])
    dist_list = list(dist_list or [])

    def _pad(lst, n):
        last = lst[-1] if lst else ""
        while len(lst) < n:
            lst.append(last)
        return lst[:n]

    reps_list = _pad(reps_list, sets)
    time_list = _pad(time_list, sets)
    dist_list = _pad(dist_list, sets)

    set_panels = []
    all_inputs = []
    for i in range(sets):
        reps_container, reps_get = _make_reps_stepper(reps_list[i])
        time_container, time_get = _make_time_wheel(time_list[i])
        dist_container, dist_get = _make_distance_stepper(dist_list[i])
        all_inputs.append((reps_get, time_get, dist_get))

        def _divider():
            hr = document.createElement("div")
            hr.style.borderTop = "1px solid rgba(255,255,255,0.08)"
            hr.style.margin = "2px 0"
            return hr

        panel = document.createElement("div")
        panel.style.display = "none"
        panel.style.flexDirection = "column"
        panel.style.gap = "10px"
        panel.style.paddingTop = "4px"
        panel.appendChild(reps_container)
        panel.appendChild(_divider())
        panel.appendChild(time_container)
        panel.appendChild(_divider())
        panel.appendChild(dist_container)
        set_panels.append(panel)

    current_set = [0]
    wrapper = document.createElement("div")
    wrapper.style.display = "flex"
    wrapper.style.flexDirection = "column"
    wrapper.style.gap = "6px"
    wrapper.style.border = "1px solid rgba(255,255,255,0.1)"
    wrapper.style.borderRadius = "6px"
    wrapper.style.padding = "8px"

    nav = document.createElement("div")
    nav.style.display = "flex" if sets > 1 else "none"
    nav.style.alignItems = "center"
    nav.style.gap = "6px"
    nav.style.marginBottom = "2px"

    prev_btn = document.createElement("button")
    prev_btn.type = "button"
    prev_btn.textContent = "\u2039"
    prev_btn.classList.add("btn", "btn-outline-gold", "btn-sm")
    prev_btn.style.padding = "0"
    prev_btn.style.width = "24px"
    prev_btn.style.height = "24px"
    prev_btn.style.fontSize = "1.1rem"
    prev_btn.style.lineHeight = "1"
    prev_btn.style.borderRadius = "50%"
    prev_btn.style.flexShrink = "0"

    next_btn = document.createElement("button")
    next_btn.type = "button"
    next_btn.textContent = "\u203a"
    next_btn.classList.add("btn", "btn-outline-gold", "btn-sm")
    next_btn.style.padding = "0"
    next_btn.style.width = "24px"
    next_btn.style.height = "24px"
    next_btn.style.fontSize = "1.1rem"
    next_btn.style.lineHeight = "1"
    next_btn.style.borderRadius = "50%"
    next_btn.style.flexShrink = "0"

    set_label = document.createElement("span")
    set_label.style.flex = "1"
    set_label.style.textAlign = "center"
    set_label.style.fontSize = "0.8rem"
    set_label.style.color = "#ba945e"
    set_label.style.fontWeight = "600"

    nav.appendChild(prev_btn)
    nav.appendChild(set_label)
    nav.appendChild(next_btn)

    content = document.createElement("div")
    for panel in set_panels:
        content.appendChild(panel)

    def _show(idx):
        current_set[0] = idx
        set_label.textContent = t("set_of", current=idx + 1, total=sets)
        prev_btn.disabled = idx == 0
        next_btn.disabled = idx == sets - 1
        for k, panel in enumerate(set_panels):
            panel.style.display = "flex" if k == idx else "none"

    def _on_prev(evt):
        evt.preventDefault()
        if current_set[0] > 0:
            _show(current_set[0] - 1)

    def _on_next(evt):
        evt.preventDefault()
        if current_set[0] < sets - 1:
            _show(current_set[0] + 1)

    prev_btn.addEventListener("click", create_proxy(_on_prev))
    next_btn.addEventListener("click", create_proxy(_on_next))
    _show(0)

    wrapper.appendChild(nav)
    wrapper.appendChild(content)

    def get_values():
        reps_parts = [rg() for rg, _, _ in all_inputs]
        time_parts = [tg() for _, tg, _ in all_inputs]
        dist_parts = [dg() for _, _, dg in all_inputs]
        reps_csv = ",".join(reps_parts) if any(reps_parts) else ""
        time_csv = ",".join(time_parts) if any(time_parts) else ""
        dist_csv = ",".join(dist_parts) if any(dist_parts) else ""
        return reps_csv, time_csv, dist_csv

    return wrapper, get_values


def _show_confirm_popup(anchor_el, message, on_confirm, confirm_label="Remove", cancel_label="Cancel") -> None:
    existing = document.querySelector(".confirm-popup-overlay")
    if existing:
        existing.remove()

    overlay = document.createElement("div")
    overlay.className = "confirm-popup-overlay"

    popup = document.createElement("div")
    popup.className = "confirm-popup"

    msg_el = document.createElement("p")
    msg_el.className = "confirm-popup-message"
    msg_el.textContent = message
    popup.appendChild(msg_el)

    btn_row = document.createElement("div")
    btn_row.className = "confirm-popup-actions"

    cancel_btn = document.createElement("button")
    cancel_btn.textContent = cancel_label
    cancel_btn.className = "confirm-popup-cancel"

    confirm_btn = document.createElement("button")
    confirm_btn.textContent = confirm_label
    confirm_btn.className = "confirm-popup-confirm"

    def _confirm(evt):
        evt.stopPropagation()
        overlay.remove()
        on_confirm()

    def _cancel(evt):
        evt.stopPropagation()
        overlay.remove()

    def _dismiss(evt):
        if evt.target == overlay:
            overlay.remove()

    confirm_btn.addEventListener("click", create_proxy(_confirm))
    cancel_btn.addEventListener("click", create_proxy(_cancel))
    overlay.addEventListener("click", create_proxy(_dismiss))

    btn_row.appendChild(cancel_btn)
    btn_row.appendChild(confirm_btn)
    popup.appendChild(btn_row)
    overlay.appendChild(popup)
    document.body.appendChild(overlay)

    rect = anchor_el.getBoundingClientRect()
    popup_w = 210
    left = rect.left + rect.width / 2 - popup_w / 2
    left = max(8, min(left, document.documentElement.clientWidth - popup_w - 8))
    popup.style.width = f"{popup_w}px"
    popup.style.left = f"{left}px"
    popup.style.top = f"{rect.top - 8}px"
    popup.style.transform = "translateY(-100%)"


def _format_break(secs: int) -> str:
    if secs < 60:
        return f"{secs}s"
    m, s = divmod(secs, 60)
    return f"{m}m {s}s" if s else f"{m}m"


def _show_break_popup(anchor_el, workout, ex_below) -> None:
    from workout_rendering import render_workouts

    existing = document.querySelector(".break-popup-overlay")
    if existing:
        existing.remove()

    overlay = document.createElement("div")
    overlay.className = "break-popup-overlay confirm-popup-overlay"

    popup = document.createElement("div")
    popup.className = "confirm-popup"

    title_el = document.createElement("p")
    title_el.className = "confirm-popup-message"
    title_el.textContent = t("rest_before", name=ex_below.name)
    popup.appendChild(title_el)

    input_row = document.createElement("div")
    input_row.style.display = "flex"
    input_row.style.alignItems = "center"
    input_row.style.gap = "6px"
    input_row.style.margin = "4px 0 8px"

    inp = document.createElement("input")
    inp.type = "number"
    inp.min = "1"
    inp.max = "3600"
    current = workout.breaks.get(ex_below.internal_id, 0)
    inp.value = str(current) if current else ""
    inp.placeholder = t("sec_placeholder")
    inp.style.width = "64px"
    inp.style.fontSize = "0.8rem"
    inp.style.padding = "2px 6px"
    inp.style.borderRadius = "4px"
    inp.style.border = "1px solid rgba(255,255,255,0.2)"
    inp.style.backgroundColor = "rgba(255,255,255,0.1)"
    inp.style.color = "#fff"

    unit_label = document.createElement("span")
    unit_label.textContent = t("sec_unit")
    unit_label.style.fontSize = "0.8rem"
    unit_label.style.color = "rgba(255,255,255,0.7)"

    input_row.appendChild(inp)
    input_row.appendChild(unit_label)
    popup.appendChild(input_row)

    btn_row = document.createElement("div")
    btn_row.className = "confirm-popup-actions"

    save_btn = document.createElement("button")
    save_btn.textContent = t("set_btn")
    save_btn.className = "confirm-popup-confirm"

    clear_btn = document.createElement("button")
    clear_btn.textContent = t("clear_btn")
    clear_btn.className = "confirm-popup-cancel"

    cancel_btn = document.createElement("button")
    cancel_btn.textContent = t("cancel_btn")
    cancel_btn.className = "confirm-popup-cancel"

    def _save(evt):
        evt.stopPropagation()
        val = inp.value.strip()
        if val and int(val) > 0:
            workout.breaks[ex_below.internal_id] = int(val)
        else:
            workout.breaks.pop(ex_below.internal_id, None)
        overlay.remove()
        state.save_workouts()
        render_workouts(state.workouts)

    def _clear(evt):
        evt.stopPropagation()
        inp.value = ""

    def _cancel(evt):
        evt.stopPropagation()
        overlay.remove()

    def _dismiss(evt):
        if evt.target == overlay:
            overlay.remove()

    save_btn.addEventListener("click", create_proxy(_save))
    clear_btn.addEventListener("click", create_proxy(_clear))
    cancel_btn.addEventListener("click", create_proxy(_cancel))
    overlay.addEventListener("click", create_proxy(_dismiss))

    btn_row.appendChild(clear_btn)
    btn_row.appendChild(cancel_btn)
    btn_row.appendChild(save_btn)
    popup.appendChild(btn_row)
    overlay.appendChild(popup)
    document.body.appendChild(overlay)

    rect = anchor_el.getBoundingClientRect()
    popup_w = 210
    left = rect.left + rect.width / 2 - popup_w / 2
    left = max(8, min(left, document.documentElement.clientWidth - popup_w - 8))
    popup.style.width = f"{popup_w}px"
    popup.style.left = f"{left}px"
    popup.style.top = f"{rect.top - 8}px"
    popup.style.transform = "translateY(-100%)"


def configure_exercise(exercise_id: str, exercise_name: str) -> None:
    from workout_persistence import update_workout_badge
    from workout_rendering import render_workouts

    overlay = document.createElement("div")
    overlay.classList.add("exercise-overlay")
    overlay.setAttribute("onclick", "event.stopPropagation()")
    overlay.style.position = "fixed"
    overlay.style.top = "0"
    overlay.style.left = "0"
    overlay.style.width = "100%"
    overlay.style.height = "100%"
    overlay.style.backgroundColor = "rgba(0,0,0,0.7)"
    overlay.style.display = "flex"
    overlay.style.alignItems = "center"
    overlay.style.justifyContent = "center"
    overlay.style.zIndex = "1000"

    modal = document.createElement("div")
    modal.style.backgroundColor = "#1a1a1a"
    modal.style.border = "1px solid #444"
    modal.style.borderRadius = "8px"
    modal.style.padding = "20px"
    modal.style.width = "320px"
    modal.style.display = "flex"
    modal.style.flexDirection = "column"
    modal.style.gap = "12px"
    modal.style.color = "white"

    title = document.createElement("div")
    title.textContent = exercise_name
    title.style.fontWeight = "bold"
    title.style.fontSize = "0.95rem"
    title.style.color = "#ba945e"
    title.style.marginBottom = "4px"
    modal.appendChild(title)

    inputs_container = document.createElement("div")
    inputs_container.style.display = "flex"
    inputs_container.style.flexDirection = "column"
    inputs_container.style.gap = "8px"
    inputs_container.style.width = "100%"

    sets_stepper, input_sets = _make_sets_stepper(1)
    rest_group, input_rest, reset_rest = _make_rest_stepper(0)
    rest_group.style.display = "none"

    input_notes = document.createElement("textarea")
    input_notes.placeholder = t("notes_placeholder")
    input_notes.rows = "3"
    input_notes.style.resize = "vertical"

    per_set_wrapper = document.createElement("div")
    per_set_wrapper.style.width = "100%"
    get_per_set_values = [None]

    def _rebuild_per_set(n, reps_csv="", time_csv="", dist_csv=""):
        reps_list = [v.strip() for v in reps_csv.split(",") if v.strip()] if reps_csv else []
        time_list = [v.strip() for v in time_csv.split(",") if v.strip()] if time_csv else []
        dist_list = [v.strip() for v in dist_csv.split(",") if v.strip()] if dist_csv else []
        while per_set_wrapper.firstChild:
            per_set_wrapper.removeChild(per_set_wrapper.firstChild)
        group_el, get_vals = _make_per_set_group(n, reps_list, time_list, dist_list)
        per_set_wrapper.appendChild(group_el)
        get_per_set_values[0] = get_vals

    _rebuild_per_set(1)

    inputs_container.appendChild(sets_stepper)
    inputs_container.appendChild(per_set_wrapper)
    inputs_container.appendChild(rest_group)
    inputs_container.appendChild(_make_input_group(t("notes_label"), input_notes))

    def _on_sets_change(evt):
        val = input_sets.value.strip()
        rest_group.style.display = "flex" if val and val.isdigit() and int(val) > 1 else "none"
        if rest_group.style.display == "none":
            reset_rest(0)
        if val and val.isdigit() and int(val) >= 1:
            reps_csv, time_csv, dist_csv = get_per_set_values[0]() if get_per_set_values[0] else ("", "", "")
            _rebuild_per_set(int(val), reps_csv, time_csv, dist_csv)

    input_sets.addEventListener("change", create_proxy(_on_sets_change))
    input_sets.addEventListener("input", create_proxy(_on_sets_change))

    buttons_container = document.createElement("div")
    buttons_container.style.display = "flex"
    buttons_container.style.gap = "8px"
    buttons_container.style.marginTop = "4px"

    confirm_btn = document.createElement("button")
    confirm_btn.textContent = t("add_btn")
    confirm_btn.classList.add("btn", "btn-outline-gold", "btn-sm")
    confirm_btn.style.flex = "1"
    confirm_btn.style.fontSize = "0.8rem"

    close_btn = document.createElement("button")
    close_btn.textContent = t("cancel_btn")
    close_btn.classList.add("btn", "btn-outline-secondary", "btn-sm")
    close_btn.style.flex = "1"
    close_btn.style.fontSize = "0.8rem"
    close_btn.onclick = lambda evt: overlay.remove()

    buttons_container.appendChild(confirm_btn)
    buttons_container.appendChild(close_btn)
    modal.appendChild(inputs_container)
    modal.appendChild(buttons_container)
    overlay.appendChild(modal)
    document.body.appendChild(overlay)

    def on_confirm_click(evt):
        sets = int(input_sets.value) if input_sets.value.strip() else 1
        reps_val, time_val, distance_val = get_per_set_values[0]()
        rest_val = int(input_rest.value) if input_rest.value.strip() else 0
        notes_val = input_notes.value.strip()

        ex = Exercise(int(exercise_id), str(uuid4()), exercise_name, sets, reps_val, time_val, distance_val, notes_val, rest_between_sets=rest_val)
        if state.active_workout is None:
            state.active_workout = uuid4()
            w = Workout(state.active_workout, datetime.datetime.now().date(), [ex])
            state.workouts.append(w)
        else:
            for w in state.workouts:
                if w.id == state.active_workout:
                    w.exercises.append(ex)
                    break

        state.save_workouts()
        update_workout_badge()
        render_workouts(state.workouts)
        overlay.remove()

    confirm_btn.onclick = on_confirm_click


def edit_exercise_in_workout(event) -> None:
    from workout_rendering import render_workouts

    workout_ex_id = _event_attr(event, "data-workout-exercise-id")
    workout_id = _event_attr(event, "data-workout-id")
    if not workout_ex_id or not workout_id:
        return

    target_workout, target_ex, _ = _find_exercise(workout_id, workout_ex_id)
    if target_ex is None:
        return

    overlay = document.createElement("div")
    overlay.classList.add("exercise-edit-overlay")
    overlay.setAttribute("onclick", "event.stopPropagation()")
    overlay.style.position = "fixed"
    overlay.style.top = "0"
    overlay.style.left = "0"
    overlay.style.width = "100%"
    overlay.style.height = "100%"
    overlay.style.backgroundColor = "rgba(0,0,0,0.7)"
    overlay.style.display = "flex"
    overlay.style.alignItems = "center"
    overlay.style.justifyContent = "center"
    overlay.style.zIndex = "1000"

    modal = document.createElement("div")
    modal.style.backgroundColor = "#1a1a1a"
    modal.style.border = "1px solid #444"
    modal.style.borderRadius = "8px"
    modal.style.padding = "20px"
    modal.style.width = "320px"
    modal.style.display = "flex"
    modal.style.flexDirection = "column"
    modal.style.gap = "12px"
    modal.style.color = "white"

    title = document.createElement("div")
    title.textContent = t("edit_exercise_title", name=target_ex.name)
    title.style.fontWeight = "bold"
    title.style.fontSize = "0.95rem"
    title.style.color = "#ba945e"
    title.style.marginBottom = "4px"
    modal.appendChild(title)

    initial_sets_val = int(target_ex.sets) if str(target_ex.sets).isdigit() else 1
    sets_stepper, input_sets = _make_sets_stepper(initial_sets_val)
    initial_rest = int(target_ex.rest_between_sets) if target_ex.rest_between_sets else 0
    edit_rest_group, input_rest, reset_rest = _make_rest_stepper(initial_rest)
    edit_rest_group.style.display = "flex" if initial_sets_val > 1 else "none"

    input_notes = document.createElement("textarea")
    input_notes.placeholder = t("notes_placeholder")
    input_notes.rows = "3"
    input_notes.style.resize = "vertical"
    input_notes.value = target_ex.notes or ""

    per_set_wrapper = document.createElement("div")
    per_set_wrapper.style.width = "100%"
    get_per_set_values = [None]

    def _rebuild_per_set(n, reps_csv="", time_csv="", dist_csv=""):
        reps_list = [v.strip() for v in reps_csv.split(",") if v.strip()] if reps_csv else []
        time_list = [v.strip() for v in time_csv.split(",") if v.strip()] if time_csv else []
        dist_list = [v.strip() for v in dist_csv.split(",") if v.strip()] if dist_csv else []
        while per_set_wrapper.firstChild:
            per_set_wrapper.removeChild(per_set_wrapper.firstChild)
        group_el, get_vals = _make_per_set_group(n, reps_list, time_list, dist_list)
        per_set_wrapper.appendChild(group_el)
        get_per_set_values[0] = get_vals

    _rebuild_per_set(initial_sets_val, target_ex.reps or "", target_ex.time or "", target_ex.distance or "")

    def _on_edit_sets_change(evt):
        val = input_sets.value.strip()
        edit_rest_group.style.display = "flex" if val and val.isdigit() and int(val) > 1 else "none"
        if edit_rest_group.style.display == "none":
            reset_rest(0)
        if val and val.isdigit() and int(val) >= 1:
            reps_csv, time_csv, dist_csv = get_per_set_values[0]() if get_per_set_values[0] else ("", "", "")
            _rebuild_per_set(int(val), reps_csv, time_csv, dist_csv)

    input_sets.addEventListener("change", create_proxy(_on_edit_sets_change))
    input_sets.addEventListener("input", create_proxy(_on_edit_sets_change))

    modal.appendChild(sets_stepper)
    modal.appendChild(per_set_wrapper)
    modal.appendChild(edit_rest_group)
    modal.appendChild(_make_input_group(t("notes_label"), input_notes))

    buttons_container = document.createElement("div")
    buttons_container.style.display = "flex"
    buttons_container.style.gap = "8px"
    buttons_container.style.marginTop = "4px"

    confirm_btn = document.createElement("button")
    confirm_btn.textContent = t("save_btn")
    confirm_btn.classList.add("btn", "btn-outline-gold", "btn-sm")
    confirm_btn.style.flex = "1"
    confirm_btn.style.fontSize = "0.8rem"

    cancel_btn = document.createElement("button")
    cancel_btn.textContent = t("cancel_btn")
    cancel_btn.classList.add("btn", "btn-outline-secondary", "btn-sm")
    cancel_btn.style.flex = "1"
    cancel_btn.style.fontSize = "0.8rem"
    cancel_btn.onclick = lambda evt: overlay.remove()

    buttons_container.appendChild(confirm_btn)
    buttons_container.appendChild(cancel_btn)
    modal.appendChild(buttons_container)
    overlay.appendChild(modal)
    document.body.appendChild(overlay)

    def on_save(evt):
        sets = int(input_sets.value) if input_sets.value.strip() else 1
        reps_val, time_val, distance_val = get_per_set_values[0]()
        rest_val = int(input_rest.value) if input_rest.value.strip() else 0
        notes_val = input_notes.value.strip()

        target_ex.sets = sets
        target_ex.reps = reps_val
        target_ex.time = time_val
        target_ex.distance = distance_val
        target_ex.rest_between_sets = rest_val
        target_ex.notes = notes_val

        state.save_workouts()
        render_workouts(state.workouts)
        overlay.remove()

    confirm_btn.onclick = on_save


def remove_exercise_from_workout(event) -> None:
    from workout_persistence import hide_sidebar
    from workout_rendering import render_workouts

    workout_ex_id = _event_attr(event, "data-workout-exercise-id")
    workout_id = _event_attr(event, "data-workout-id")
    if not workout_ex_id or not workout_id:
        return
    w, ex, j = _find_exercise(workout_id, workout_ex_id)
    if not w or j < 0:
        return

    anchor = event.target.closest("i") or event.target

    def _do():
        ex_id = w.exercises[j].internal_id
        del w.exercises[j]
        w.breaks.pop(ex_id, None)
        _cleanup_supersets(w)
        state.save_workouts()
        render_workouts(state.workouts)
        if not state.workouts:
            state.active_workout = None
            hide_sidebar()

    _show_confirm_popup(anchor, t("remove_exercise_confirm", name=ex.name), _do, confirm_label=t("yes_btn"), cancel_label=t("no_btn"))
