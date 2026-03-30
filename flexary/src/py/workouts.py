import asyncio
import datetime
import json
from html import escape as html_escape
from uuid import UUID, uuid4

from js import localStorage, window
from pyodide.ffi import create_proxy
from pyodide.http import pyfetch
from pyscript import document
from pyweb import pydom

import state
from models import Exercise, Workout, workouts_to_json


# ── DOM helpers ────────────────────────────────────────────────────────────────

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


def _find_exercise(workout_id: str, workout_ex_id: str):
    """Return (workout, exercise, index) or (None, None, -1)."""
    for w in state.workouts:
        if str(w.id) == workout_id:
            for j, ex in enumerate(w.exercises):
                if ex.internal_id == workout_ex_id:
                    return w, ex, j
    return None, None, -1


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
    """Returns (container_el, input_el). The input_el fires 'input' events normally."""
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
    label.textContent = "Sets"
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
    """Returns (container_el, input_el, set_value_fn). Steps in 15-second increments."""

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
    label.textContent = "Rest between sets"
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
    """Three spinning-wheel columns (h / m / s). Returns (container_el, get_value_fn).
    get_value_fn() returns 'HH:MM:SS' or '' when all zeros."""
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
        sep.style.marginBottom = "14px"  # nudge up to align with digit display
        return sep

    field_lbl = document.createElement("label")
    field_lbl.textContent = "Time"
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
    """Returns (container_el, get_value_fn). get_value_fn() -> '' or str(int)."""
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
    lbl.textContent = "Reps"
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
    """Returns (container_el, get_value_fn). get_value_fn() -> '' or 'Xm'/'Xkm'."""
    unit = ["m"]
    val = [0]
    s = initial_value.strip().lower()
    if s.endswith("km"):
        try:
            val[0] = int(float(s[:-2]))
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

    STEPS = {"m": 1, "km": 1}

    display = document.createElement("span")
    display.textContent = str(val[0])
    display.style.minWidth = "32px"
    display.style.textAlign = "center"
    display.style.fontSize = "0.95rem"
    display.style.fontWeight = "600"
    display.style.color = "#fff"
    display.style.userSelect = "none"

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
        step = STEPS[unit[0]]
        val[0] = max(0, val[0] - step)
        display.textContent = str(val[0])

    def _on_plus(evt):
        evt.preventDefault()
        val[0] += STEPS[unit[0]]
        display.textContent = str(val[0])

    def _on_unit_toggle(evt):
        evt.preventDefault()
        unit[0] = "km" if unit[0] == "m" else "m"
        unit_btn.textContent = unit[0]
        val[0] = 0
        display.textContent = "0"

    minus_btn.addEventListener("click", create_proxy(_on_minus))
    plus_btn.addEventListener("click", create_proxy(_on_plus))
    unit_btn.addEventListener("click", create_proxy(_on_unit_toggle))

    lbl = document.createElement("label")
    lbl.textContent = "Distance"
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
    """Creates a navigable per-set reps/time/distance section.
    Returns (wrapper_el, get_values_fn) where get_values_fn() -> (reps_csv, time_csv, dist_csv).
    """
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
        set_label.textContent = f"Set {idx + 1} / {sets}"
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
    existing = document.querySelector(".break-popup-overlay")
    if existing:
        existing.remove()

    overlay = document.createElement("div")
    overlay.className = "break-popup-overlay confirm-popup-overlay"

    popup = document.createElement("div")
    popup.className = "confirm-popup"

    title_el = document.createElement("p")
    title_el.className = "confirm-popup-message"
    title_el.textContent = f"Rest before {ex_below.name}"
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
    inp.placeholder = "sec"
    inp.style.width = "64px"
    inp.style.fontSize = "0.8rem"
    inp.style.padding = "2px 6px"
    inp.style.borderRadius = "4px"
    inp.style.border = "1px solid rgba(255,255,255,0.2)"
    inp.style.backgroundColor = "rgba(255,255,255,0.1)"
    inp.style.color = "#fff"

    unit_label = document.createElement("span")
    unit_label.textContent = "sec"
    unit_label.style.fontSize = "0.8rem"
    unit_label.style.color = "rgba(255,255,255,0.7)"

    input_row.appendChild(inp)
    input_row.appendChild(unit_label)
    popup.appendChild(input_row)

    btn_row = document.createElement("div")
    btn_row.className = "confirm-popup-actions"

    save_btn = document.createElement("button")
    save_btn.textContent = "Set"
    save_btn.className = "confirm-popup-confirm"

    clear_btn = document.createElement("button")
    clear_btn.textContent = "Clear"
    clear_btn.className = "confirm-popup-cancel"

    cancel_btn = document.createElement("button")
    cancel_btn.textContent = "Cancel"
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


def _validate_exercise_inputs(sets_val, reps_val, time_val, sets, warning_el) -> bool:
    if not sets_val:
        _show_warning(warning_el, "Number of sets is required.")
        return False
    if reps_val:
        reps = [v for r in reps_val.split(",") if (v := r.strip()) and v.isdigit()]
        if len(reps) != sets:
            _show_warning(warning_el, f"Reps count ({len(reps)}) must match number of sets ({sets}).")
            return False
    if time_val:
        time_parts = time_val.split(":")
        if len(time_parts) != 3 or not all(part.isdigit() for part in time_parts):
            _show_warning(warning_el, "Time must be in hh:mm:ss format.")
            return False
        if any(int(part) < 0 for part in time_parts):
            _show_warning(warning_el, "Time values cannot be negative.")
            return False
    return True


# ── Sidebar visibility ─────────────────────────────────────────────────────────

def show_sidebar() -> None:
    pydom[state.workout_sidebar_el_id][0]._js.classList.remove("d-none")
    icon = pydom["#toggle-workout-sidebar"][0]._js.querySelector("i")
    if icon:
        icon.className = "bi bi-x-lg"
    pydom["#toggle-workout-sidebar"][0]._js.title = "Hide Workouts"


def hide_sidebar() -> None:
    pydom[state.workout_sidebar_el_id][0]._js.classList.add("d-none")
    icon = pydom["#toggle-workout-sidebar"][0]._js.querySelector("i")
    if icon:
        icon.className = "bi bi-list"
    pydom["#toggle-workout-sidebar"][0]._js.title = "Show Workouts"
    update_workout_badge()


def update_workout_badge() -> None:
    count = len(state.workouts)
    btn = pydom["#toggle-workout-sidebar"][0]._js
    existing = btn.querySelector(".workout-count-badge")
    if existing:
        existing.remove()
    if count > 0:
        badge = document.createElement("span")
        badge.className = "workout-count-badge"
        badge.textContent = str(count)
        btn.appendChild(badge)


# ── Workout rendering ──────────────────────────────────────────────────────────

def _make_superset_connector(workout, idx_above, idx_below):
    ex_above = workout.exercises[idx_above]
    ex_below = workout.exercises[idx_below]
    is_linked = bool(ex_above.superset_id and ex_above.superset_id == ex_below.superset_id)

    el = document.createElement("div")
    el.className = "superset-connector " + ("superset-connector--linked" if is_linked else "superset-connector--unlinked")
    el.setAttribute("data-workout-exercise-id", ex_below.internal_id)
    el.setAttribute("data-workout-id", str(workout.id))
    el.title = "Split superset here" if is_linked else "Add to superset"

    icon = document.createElement("i")
    icon.className = "bi bi-scissors" if is_linked else "bi bi-link-45deg"
    icon.setAttribute("data-workout-exercise-id", ex_below.internal_id)
    icon.setAttribute("data-workout-id", str(workout.id))

    el.appendChild(icon)
    el.addEventListener("click", create_proxy(toggle_superset))

    if not is_linked:
        id_above = ex_above.internal_id
        id_below = ex_below.internal_id

        def _on_mouseenter(evt):
            for ex_id in [id_above, id_below]:
                node = document.querySelector(f'[data-exercise-item-id="{ex_id}"]')
                if node:
                    node.classList.add("superset-hover-stay")

        def _on_mouseleave(evt):
            for node in document.querySelectorAll(".superset-hover-stay"):
                node.classList.remove("superset-hover-stay")

        el.addEventListener("mouseenter", create_proxy(_on_mouseenter))
        el.addEventListener("mouseleave", create_proxy(_on_mouseleave))

    return el


def _make_break_row(workout, ex_below):
    break_mins = workout.breaks.get(ex_below.internal_id, 0)

    row = document.createElement("div")
    row.className = "connector-break-row" + (" connector-break-row--set" if break_mins else "")

    clock = document.createElement("i")
    clock.className = "bi bi-hourglass-split"
    row.appendChild(clock)

    lbl = document.createElement("span")
    lbl.textContent = f"{_format_break(break_mins)} rest" if break_mins else "add rest"
    row.appendChild(lbl)

    def _make_break_handler(w, ex_b):
        def _on_click(evt):
            _show_break_popup(row, w, ex_b)
        return _on_click

    row.addEventListener("click", create_proxy(_make_break_handler(workout, ex_below)))
    return row

def workout_edit(event) -> None:
    state.active_workout = UUID(event.target.getAttribute("data-workout-id"))
    for w in state.workouts:
        layover = pydom[f"#workout-layover-{w.id}"][0]
        if w.id == state.active_workout:
            layover._js.classList.add("d-none")
        else:
            layover._js.classList.remove("d-none")


def render_workouts(workouts: list) -> None:
    ws_container = pydom["#workout-list-container"][0]
    while ws_container._js.firstChild:
        ws_container._js.removeChild(ws_container._js.firstChild)

    for w in workouts:
        w_div = state.w_template.clone()
        w_div._js.removeAttribute("id")

        workout_layover = w_div.find("#workout-layover")[0]
        workout_layover._js.setAttribute("id", f"workout-layover-{w.id}")
        if w.id != state.active_workout:
            workout_layover._js.classList.remove("d-none")
        else:
            workout_layover._js.classList.add("d-none")

        workout_edit_btn = workout_layover.find("#workout-edit")[0]
        workout_edit_btn._js.onclick = workout_edit
        workout_edit_btn._js.setAttribute("data-workout-id", str(w.id))
        workout_edit_btn._js.removeAttribute("id")

        workout_edit_btn_icon = workout_layover.find("#workout-edit-icon")[0]
        workout_edit_btn_icon._js.onclick = workout_edit
        workout_edit_btn_icon._js.setAttribute("data-workout-id", str(w.id))
        workout_edit_btn_icon._js.removeAttribute("id")

        w_name = w_div.find("#workout-name")[0]
        w_name._js.value = w.name or ""
        w_name._js.setAttribute("id", f"workout-name-{w.id}")
        w_name._js.setAttribute("data-workout-id", str(w.id))

        def on_name_change(evt):
            w_id = UUID(evt.target.getAttribute("data-workout-id"))
            for workout in state.workouts:
                if workout.id == w_id:
                    workout.name = evt.target.value.strip()
                    break
            state.save_workouts()

        w_name._js.addEventListener("change", create_proxy(on_name_change))

        w_date = w_div.find("#workout-date")[0]
        w_date._js.value = w.execution_date.strftime("%Y-%m-%d")
        w_date._js.setAttribute("id", f"workout-date-{w.id}")
        w_date._js.setAttribute("data-workout-id", str(w.id))

        def on_date_change(evt):
            if not evt.target.value:
                return
            new_date = datetime.datetime.strptime(evt.target.value, "%Y-%m-%d").date()
            w_id = UUID(evt.target.getAttribute("data-workout-id"))
            for w in state.workouts:
                if w.id == w_id:
                    w.execution_date = new_date
                    break
            state.save_workouts()

        w_date._js.addEventListener("change", create_proxy(on_date_change))

        w_remove_btn = w_div.find("#workout-remove")[0]
        w_remove_btn._js.onclick = remove_workout
        w_remove_btn._js.setAttribute("data-workout-id", str(w.id))
        w_remove_btn._js.removeAttribute("id")

        w_remove_icon = w_div.find("#workout-remove-icon")[0]
        w_remove_icon._js.onclick = remove_workout
        w_remove_icon._js.setAttribute("data-workout-id", str(w.id))
        w_remove_icon._js.removeAttribute("id")

        w_ul = w_div.find("#workout-items")[0]
        li = w_ul.find("#workout-item")[0]
        current_superset_wrapper = None
        for ei, exercise in enumerate(w.exercises):
            w_li = li if ei == 0 else li.clone()
            w_li._js.removeAttribute("id")
            w_li._js.setAttribute("data-exercise-item-id", exercise.internal_id)

            name_el = document.createElement("div")
            name_el.className = "exercise-item-name"
            name_el.textContent = exercise.name

            rounds = w.superset_rounds.get(exercise.superset_id, 1) if exercise.superset_id else 1
            details_el = document.createElement("div")
            details_el.className = "exercise-item-details"
            details_el.textContent = exercise.detail_str(in_superset=bool(exercise.superset_id))
            if exercise.superset_id and exercise.execution_mismatch(rounds):
                warn = document.createElement("div")
                warn.className = "superset-reps-warning"
                def _mismatch_count(raw):
                    return len([v for v in raw.split(",") if v.strip()]) if raw else 0
                ex_count = max(_mismatch_count(exercise.reps), _mismatch_count(exercise.time), _mismatch_count(exercise.distance))
                warn.textContent = f"⚠ Exercise configured with {ex_count} executions but the superset has {rounds} rounds — edit either the exercise's configuration or the superset's number of rounds so that they match"
                details_el.appendChild(warn)

            item_name_span = w_li.find("#workout-item-name")[0]._js
            item_name_span.innerHTML = ""
            item_name_span.appendChild(name_el)
            item_name_span.appendChild(details_el)
            if exercise.notes:
                notes_el = document.createElement("div")
                notes_el.className = "exercise-item-notes"
                notes_el.textContent = exercise.notes[:60] + "…" if len(exercise.notes) > 60 else exercise.notes
                item_name_span.appendChild(notes_el)

            w_item_move_up = w_li.find("#workout-item-move-up")[0]
            w_item_move_up._js.onclick = move_exercise_up
            w_item_move_up._js.setAttribute("data-workout-exercise-id", exercise.internal_id)
            w_item_move_up._js.setAttribute("data-workout-id", str(w.id))
            if not _can_move(w.exercises, ei, -1):
                w_item_move_up._js.classList.add("disabled")
            else:
                w_item_move_up._js.classList.remove("disabled")

            w_item_move_down = w_li.find("#workout-item-move-down")[0]
            w_item_move_down._js.onclick = move_exercise_down
            w_item_move_down._js.setAttribute("data-workout-exercise-id", exercise.internal_id)
            w_item_move_down._js.setAttribute("data-workout-id", str(w.id))
            if not _can_move(w.exercises, ei, +1):
                w_item_move_down._js.classList.add("disabled")
            else:
                w_item_move_down._js.classList.remove("disabled")

            w_item_edit_icon = w_li.find("#workout-item-edit")[0]
            w_item_edit_icon._js.onclick = edit_exercise_in_workout
            w_item_edit_icon._js.setAttribute("data-exercise-id", str(exercise.id))
            w_item_edit_icon._js.setAttribute("data-workout-exercise-id", exercise.internal_id)
            w_item_edit_icon._js.setAttribute("data-workout-id", str(w.id))

            w_item_remove_icon = w_li.find("#workout-item-remove")[0]
            w_item_remove_icon._js.onclick = remove_exercise_from_workout
            w_item_remove_icon._js.setAttribute("data-exercise-id", str(exercise.id))
            w_item_remove_icon._js.setAttribute("data-workout-exercise-id", exercise.internal_id)
            w_item_remove_icon._js.setAttribute("data-workout-id", str(w.id))

            if exercise.superset_id:
                is_group_start = ei == 0 or w.exercises[ei - 1].superset_id != exercise.superset_id
                if is_group_start:
                    if ei > 0:
                        w_ul._js.appendChild(_make_superset_connector(w, ei - 1, ei))
                        w_ul._js.appendChild(_make_break_row(w, exercise))

                    sid = exercise.superset_id
                    current_superset_wrapper = document.createElement("div")
                    current_superset_wrapper.className = "superset-group"

                    header = document.createElement("div")
                    header.className = "superset-group-header"

                    ss_label = document.createElement("span")
                    ss_label.textContent = "Superset"
                    header.appendChild(ss_label)

                    rounds = w.superset_rounds.get(sid, 1)
                    rounds_input = document.createElement("input")
                    rounds_input.type = "number"
                    rounds_input.min = "1"
                    rounds_input.value = str(rounds)
                    rounds_input.className = "superset-rounds-input"
                    rounds_input.title = "Superset rounds"

                    rounds_label = document.createElement("span")
                    rounds_label.textContent = "× rounds"

                    header.appendChild(rounds_input)
                    header.appendChild(rounds_label)
                    current_superset_wrapper.appendChild(header)
                    w_ul._js.appendChild(current_superset_wrapper)

                    def _make_rounds_handler(workout, superset_id):
                        def _on_change(evt):
                            val = evt.target.value
                            if val and int(val) > 0:
                                workout.superset_rounds[superset_id] = int(val)
                                state.save_workouts()
                                render_workouts(state.workouts)
                        return _on_change

                    rounds_input.addEventListener("change", create_proxy(_make_rounds_handler(w, sid)))
                else:
                    current_superset_wrapper.appendChild(_make_superset_connector(w, ei - 1, ei))

                current_superset_wrapper.appendChild(w_li._js)
            else:
                if ei > 0:
                    w_ul._js.appendChild(_make_superset_connector(w, ei - 1, ei))
                    w_ul._js.appendChild(_make_break_row(w, exercise))
                current_superset_wrapper = None
                w_ul.append(w_li)

        count_badge = w_div._js.querySelector(".workout-exercise-count")
        count = len(w.exercises)
        count_badge.textContent = f"{count} ex" if count > 0 else ""

        hint = w_div._js.querySelector(".add-exes-hint")
        if w.exercises:
            w_ul._js.classList.remove("d-none")
            hint.classList.add("d-none")
        else:
            w_ul._js.classList.add("d-none")
            hint.classList.remove("d-none")

        describe_btn = document.createElement("button")
        describe_btn.className = "describe-workout-btn" + ("" if w.exercises else " d-none")
        describe_btn.setAttribute("data-workout-id", str(w.id))
        describe_btn.innerHTML = '<i class="bi bi-stars"></i><span>Describe workout</span>'

        def _make_describe_handler(wid):
            def _on_click(evt):
                w = next((x for x in state.workouts if x.id == wid), None)
                if w and w.description:
                    anchor = evt.target.closest("button") or evt.target
                    _show_confirm_popup(
                        anchor,
                        "Regenerate description?",
                        lambda: asyncio.ensure_future(_fetch_description(wid)),
                        confirm_label="Yes",
                        cancel_label="No",
                    )
                else:
                    asyncio.ensure_future(_fetch_description(wid))
            return _on_click

        describe_btn.addEventListener("click", create_proxy(_make_describe_handler(w.id)))
        w_div._js.appendChild(describe_btn)

        ws_container.append(w_div)

    has_mismatch = any(
        ex.superset_id and ex.execution_mismatch(w.superset_rounds.get(ex.superset_id, 1))
        for w in workouts
        for ex in w.exercises
    )
    mismatch_title = "Fix reps/rounds mismatches before downloading" if has_mismatch else ""
    for btn_id in ("download-workouts", "download-ics"):
        btn = document.getElementById(btn_id)
        if btn:
            btn.disabled = has_mismatch
            btn.title = mismatch_title


# ── Add / configure exercise ───────────────────────────────────────────────────

def add_exercise_to_workout(event) -> None:
    event.stopPropagation()
    card = event.target.closest("[data-exercise-id]")
    exercise_id = card.getAttribute("data-exercise-id")
    exercise_name = card.getAttribute("data-exercise-name")
    configure_exercise(exercise_id, exercise_name)


def configure_exercise(exercise_id: str, exercise_name: str) -> None:
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
    rest_group.style.display = "none"  # hidden when sets == 1

    input_notes = document.createElement("textarea")
    input_notes.placeholder = "Notes…"
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
    inputs_container.appendChild(_make_input_group("Notes", input_notes))

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
    confirm_btn.textContent = "Add"
    confirm_btn.classList.add("btn", "btn-outline-gold", "btn-sm")
    confirm_btn.style.flex = "1"
    confirm_btn.style.fontSize = "0.8rem"

    close_btn = document.createElement("button")
    close_btn.textContent = "Cancel"
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
                    _invalidate_description(w)
                    break

        state.save_workouts()
        update_workout_badge()
        render_workouts(state.workouts)
        overlay.remove()

    confirm_btn.onclick = on_confirm_click


# ── Superset linking ──────────────────────────────────────────────────────────

def toggle_superset(event) -> None:
    workout_ex_id = event.target.getAttribute("data-workout-exercise-id")
    workout_id = event.target.getAttribute("data-workout-id")
    w, ex, j = _find_exercise(workout_id, workout_ex_id)
    if w is None or j == 0:
        return
    prev_ex = w.exercises[j - 1]
    if ex.superset_id and ex.superset_id == prev_ex.superset_id:
        # Unlink: split the superset at this boundary.
        # Exercises from j onwards that share the same sid form a new superset (if ≥2).
        old_sid = ex.superset_id
        tail = [e for i, e in enumerate(w.exercises) if i >= j and e.superset_id == old_sid]
        if len(tail) >= 2:
            new_sid = str(uuid4())
            w.superset_rounds[new_sid] = w.superset_rounds.get(old_sid, 1)
            for e in tail:
                e.superset_id = new_sid
        else:
            ex.superset_id = ""
        _cleanup_supersets(w)
    else:
        # Prefer the existing superset id from whichever side already belongs to one.
        # Priority: lower exercise's group > upper exercise's group > new id.
        # This ensures adding ex1 above an existing ex2+ex3 superset extends it
        # rather than creating a new one that orphans ex3.
        sid = ex.superset_id or prev_ex.superset_id or str(uuid4())
        if sid not in w.superset_rounds:
            w.superset_rounds[sid] = 1
        # If the upper exercise was in a different superset, migrate all its members.
        if prev_ex.superset_id and prev_ex.superset_id != sid:
            old_sid = prev_ex.superset_id
            for e in w.exercises:
                if e.superset_id == old_sid:
                    e.superset_id = sid
            w.superset_rounds.pop(old_sid, None)
        prev_ex.superset_id = sid
        ex.superset_id = sid
        # Clear per-set rest for all exercises now in this superset — rest belongs at superset level.
        for e in w.exercises:
            if e.superset_id == sid:
                e.rest_between_sets = 0
    state.save_workouts()
    render_workouts(state.workouts)


# ── Move exercises ─────────────────────────────────────────────────────────────

def _cleanup_supersets(w) -> None:
    """Clear superset_id from exercises no longer adjacent to a partner, then
    remove orphaned superset_rounds entries. Iterates until stable."""
    changed = True
    while changed:
        changed = False
        n = len(w.exercises)
        for i, ex in enumerate(w.exercises):
            if not ex.superset_id:
                continue
            sid = ex.superset_id
            above = i > 0 and w.exercises[i - 1].superset_id == sid
            below = i < n - 1 and w.exercises[i + 1].superset_id == sid
            if not above and not below:
                ex.superset_id = ""
                changed = True
    active = {ex.superset_id for ex in w.exercises if ex.superset_id}
    for sid in list(w.superset_rounds.keys()):
        if sid not in active:
            del w.superset_rounds[sid]


def _can_move(exercises, j, delta) -> bool:
    """Superset exercises: only within their group. Standalones: always (jump over groups)."""
    k = j + delta
    if not (0 <= k < len(exercises)):
        return False
    if exercises[j].superset_id:
        return exercises[k].superset_id == exercises[j].superset_id
    return True


def _do_move(exercises, j, delta) -> None:
    """Perform the move. Standalones jump over entire superset groups as a unit."""
    ex = exercises[j]
    k = j + delta
    if ex.superset_id or not exercises[k].superset_id:
        exercises[j], exercises[k] = exercises[k], exercises[j]
    else:
        # Standalone jumping over a superset group — find the far boundary.
        sid = exercises[k].superset_id
        if delta == +1:
            end = k
            while end + 1 < len(exercises) and exercises[end + 1].superset_id == sid:
                end += 1
            exercises.insert(end, exercises.pop(j))
        else:
            start = k
            while start - 1 >= 0 and exercises[start - 1].superset_id == sid:
                start -= 1
            exercises.insert(start, exercises.pop(j))


def move_exercise_up(event) -> None:
    workout_ex_id = event.target.getAttribute("data-workout-exercise-id")
    workout_id = event.target.getAttribute("data-workout-id")
    w, _, j = _find_exercise(workout_id, workout_ex_id)
    if w and _can_move(w.exercises, j, -1):
        _do_move(w.exercises, j, -1)
        state.save_workouts()
        render_workouts(state.workouts)


def move_exercise_down(event) -> None:
    workout_ex_id = event.target.getAttribute("data-workout-exercise-id")
    workout_id = event.target.getAttribute("data-workout-id")
    w, _, j = _find_exercise(workout_id, workout_ex_id)
    if w and _can_move(w.exercises, j, +1):
        _do_move(w.exercises, j, +1)
        state.save_workouts()
        render_workouts(state.workouts)


# ── Edit exercise ──────────────────────────────────────────────────────────────

def edit_exercise_in_workout(event) -> None:
    workout_ex_id = event.target.getAttribute("data-workout-exercise-id")
    workout_id = event.target.getAttribute("data-workout-id")

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
    title.textContent = f"Edit: {target_ex.name}"
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
    input_notes.placeholder = "Notes…"
    input_notes.rows = "3"
    input_notes.style.resize = "vertical"
    input_notes.value = target_ex.notes or ""

    initial_sets = initial_sets_val

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

    _rebuild_per_set(initial_sets, target_ex.reps or "", target_ex.time or "", target_ex.distance or "")

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
    modal.appendChild(_make_input_group("Notes", input_notes))

    buttons_container = document.createElement("div")
    buttons_container.style.display = "flex"
    buttons_container.style.gap = "8px"
    buttons_container.style.marginTop = "4px"

    confirm_btn = document.createElement("button")
    confirm_btn.textContent = "Save"
    confirm_btn.classList.add("btn", "btn-outline-gold", "btn-sm")
    confirm_btn.style.flex = "1"
    confirm_btn.style.fontSize = "0.8rem"

    cancel_btn = document.createElement("button")
    cancel_btn.textContent = "Cancel"
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

        _invalidate_description(target_workout)
        state.save_workouts()
        render_workouts(state.workouts)
        overlay.remove()

    confirm_btn.onclick = on_save


# ── Remove exercise / workout ──────────────────────────────────────────────────

def remove_exercise_from_workout(event) -> None:
    workout_ex_id = event.target.getAttribute("data-workout-exercise-id")
    workout_id = event.target.getAttribute("data-workout-id")
    w, ex, j = _find_exercise(workout_id, workout_ex_id)
    if not w or j < 0:
        return

    anchor = event.target.closest("i") or event.target

    def _do():
        ex_id = w.exercises[j].internal_id
        del w.exercises[j]
        w.breaks.pop(ex_id, None)
        _cleanup_supersets(w)
        _invalidate_description(w)
        state.save_workouts()
        render_workouts(state.workouts)
        if not state.workouts:
            state.active_workout = None
            hide_sidebar()

    _show_confirm_popup(anchor, f"Remove {ex.name}?", _do, confirm_label="Yes", cancel_label="No")


def remove_workout(event) -> None:
    event.stopPropagation()
    anchor = event.target.closest("button") or event.target
    workout_id = event.target.getAttribute("data-workout-id")

    def _do():
        for i, w in enumerate(state.workouts):
            if str(w.id) == workout_id:
                del state.workouts[i]
                break
        state.active_workout = None if not state.workouts else state.workouts[-1].id
        state.save_workouts()
        render_workouts(state.workouts)
        update_workout_badge()
        if not state.workouts:
            hide_sidebar()

    target = next((w for w in state.workouts if str(w.id) == workout_id), None)
    if target and target.exercises:
        _show_confirm_popup(anchor, "Remove this workout?", _do)
    else:
        _do()


def remove_workouts(event) -> None:
    event.stopPropagation()
    anchor = event.target.closest("button") or event.target

    def _do():
        state.workouts.clear()
        state.active_workout = None
        localStorage.removeItem(state.ls_workouts_key)
        ws_container = pydom["#workout-list-container"][0]
        while ws_container._js.firstChild:
            ws_container._js.removeChild(ws_container._js.firstChild)
        update_workout_badge()
        hide_sidebar()

    if any(w.exercises for w in state.workouts):
        _show_confirm_popup(anchor, "Remove all workouts?", _do)
    else:
        _do()


def add_workout(event) -> None:
    state.active_workout = uuid4()
    w = Workout(state.active_workout, datetime.datetime.now().date(), [])
    state.workouts.append(w)
    state.save_workouts()
    render_workouts(state.workouts)
    update_workout_badge()


# ── AI workout description ─────────────────────────────────────────────────────

def _invalidate_description(workout) -> None:
    if workout and workout.description:
        workout.description = ""

async def _fetch_description(workout_id) -> None:
    modal = document.getElementById("describe-modal")
    modal_body = document.getElementById("describe-modal-body")
    btn = document.querySelector(f'.describe-workout-btn[data-workout-id="{workout_id}"]')

    workout = next((w for w in state.workouts if w.id == workout_id), None)
    if not workout:
        return

    if btn:
        btn.disabled = True
        btn.classList.add("describe-workout-btn--loading")

    try:
        body = json.loads(workouts_to_json([workout]))[0]
        print(json.dumps(body, indent=2))
        resp = await pyfetch(
            f"{window.API_BASE}/api/describe_workout",
            method="POST",
            body=json.dumps(body),
            headers={"Content-Type": "application/json"},
        )
        data = await resp.json()
        if "description" in data:
            workout.description = data["description"]
            state.save_workouts()
            paragraphs = "".join(
                f"<p>{html_escape(p.strip())}</p>"
                for p in data["description"].split("\n\n")
                if p.strip()
            )
            modal_body.innerHTML = paragraphs
        else:
            modal_body.innerHTML = f'<p style="color:#e05252;">Error: {html_escape(data.get("error", "Unknown error"))}</p>'
    except Exception as e:
        modal_body.innerHTML = f'<p style="color:#e05252;">Request failed: {html_escape(str(e))}</p>'
    finally:
        if btn:
            btn.disabled = False
            btn.classList.remove("describe-workout-btn--loading")

    modal.showModal()
