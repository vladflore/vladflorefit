"""
Workout recurrence – RRULE-style implementation.

Stored dict keys (all optional, sensible defaults):
  freq          – DAILY | WEEKLY | MONTHLY | YEARLY
  interval      – int >= 1
  byday         – list of RRULE weekday codes (WEEKLY only): MO TU WE TH FR SA SU
  monthly_mode  – "bymonthday" | "byday"  (MONTHLY only)
  bymonthday    – int day-of-month (1-31, MONTHLY bymonthday)
  bysetpos      – int 1-4 or -1=last (MONTHLY byday)
  byday_monthly – weekday code (MONTHLY byday)
  end_type      – "never" | "on" | "after"
  until         – ISO date string (end_type "on")
  count         – int occurrences (end_type "after")
"""

import calendar
import copy
import datetime
from uuid import UUID, uuid4

from pyodide.ffi import create_proxy
from pyscript import document

import state
from i18n import t
from models import Workout
from workout_domain import _event_attr

# ── Weekday constants ────────────────────────────────────────────────────────
# Display order: Sunday first (Google Calendar convention)
WEEKDAYS = ["SU", "MO", "TU", "WE", "TH", "FR", "SA"]
# Python weekday() → RRULE code  (Mon=0 … Sun=6 in Python)
PY_TO_BYDAY = {0: "MO", 1: "TU", 2: "WE", 3: "TH", 4: "FR", 5: "SA", 6: "SU"}
BYDAY_TO_PY = {v: k for k, v in PY_TO_BYDAY.items()}
_ORD_KEYS = ["", "rec_ord_1", "rec_ord_2", "rec_ord_3", "rec_ord_4"]  # index by bysetpos


# ── Date helpers ─────────────────────────────────────────────────────────────

def _add_months(date, n):
    m = date.month + n
    y = date.year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    return date.replace(year=y, month=m, day=min(date.day, calendar.monthrange(y, m)[1]))


def _add_years(date, n):
    try:
        return date.replace(year=date.year + n)
    except ValueError:
        return date.replace(year=date.year + n, day=28)


def _nth_weekday_of_month(date):
    """Return (n, byday) for the date's occurrence: n is 1-4 or -1 (last)."""
    byday = PY_TO_BYDAY[date.weekday()]
    n = (date.day - 1) // 7 + 1
    if date.day + 7 > calendar.monthrange(date.year, date.month)[1]:
        n = -1
    return n, byday


def _nth_weekday_date(year, month, n, byday):
    """Date of the Nth occurrence of byday in year/month; n=-1 means last."""
    py_wd = BYDAY_TO_PY[byday]
    if n > 0:
        first = datetime.date(year, month, 1)
        delta = (py_wd - first.weekday()) % 7
        result = first + datetime.timedelta(days=delta + 7 * (n - 1))
        return result if result.month == month else None
    else:
        last = datetime.date(year, month, calendar.monthrange(year, month)[1])
        return last - datetime.timedelta(days=(last.weekday() - py_wd) % 7)


# ── Date generation ──────────────────────────────────────────────────────────

_NEVER_CAPS = {"DAILY": 30, "WEEKLY": 26, "MONTHLY": 24, "YEARLY": 10}


def _generate_dates(rec, start_date):
    """Return list of occurrence dates from RRULE-style rec dict."""
    MAX = 200
    freq = rec.get("freq", "DAILY")
    interval = max(1, int(rec.get("interval", 1)))
    end_type = rec.get("end_type", "never")

    until = None
    count = None
    if end_type == "on":
        try:
            until = datetime.date.fromisoformat(rec.get("until", ""))
        except Exception:
            pass
    elif end_type == "after":
        count = max(1, int(rec.get("count", 10)))

    cap = None if (until or count) else _NEVER_CAPS.get(freq, 30)

    dates = []

    if freq == "DAILY":
        cur = start_date
        while len(dates) < MAX:
            if until and cur > until:
                break
            if count and len(dates) >= count:
                break
            if cap and len(dates) >= cap:
                break
            dates.append(cur)
            cur += datetime.timedelta(days=interval)

    elif freq == "WEEKLY":
        active = rec.get("byday") or [PY_TO_BYDAY[start_date.weekday()]]
        by_py = sorted(active, key=lambda d: BYDAY_TO_PY[d])
        # Anchor to the Monday of start_date's week
        week = start_date - datetime.timedelta(days=start_date.weekday())
        done = False
        while not done and len(dates) < MAX:
            for wd in by_py:
                candidate = week + datetime.timedelta(days=BYDAY_TO_PY[wd])
                if candidate < start_date:
                    continue
                if until and candidate > until:
                    done = True
                    break
                if count and len(dates) >= count:
                    done = True
                    break
                if cap and len(dates) >= cap:
                    done = True
                    break
                dates.append(candidate)
            week += datetime.timedelta(weeks=interval)

    elif freq == "MONTHLY":
        mode = rec.get("monthly_mode", "bymonthday")
        bymonthday = int(rec.get("bymonthday", start_date.day))
        bysetpos = int(rec.get("bysetpos", 1))
        byday_m = rec.get("byday_monthly", PY_TO_BYDAY[start_date.weekday()])
        cursor = start_date.replace(day=1)
        done = False
        while not done and len(dates) < MAX:
            y, m = cursor.year, cursor.month
            if mode == "bymonthday":
                candidate = datetime.date(y, m, min(bymonthday, calendar.monthrange(y, m)[1]))
            else:
                candidate = _nth_weekday_date(y, m, bysetpos, byday_m)
                if candidate is None:
                    cursor = _add_months(cursor, interval)
                    continue
            if candidate >= start_date:
                if until and candidate > until:
                    break
                if count and len(dates) >= count:
                    break
                if cap and len(dates) >= cap:
                    break
                dates.append(candidate)
            cursor = _add_months(cursor, interval)

    elif freq == "YEARLY":
        cur = start_date
        while len(dates) < MAX:
            if until and cur > until:
                break
            if count and len(dates) >= count:
                break
            if cap and len(dates) >= cap:
                break
            dates.append(cur)
            cur = _add_years(cur, interval)

    return dates


# ── Human-readable summary ───────────────────────────────────────────────────

def recurrence_summary(rec):
    """Return a short translated summary string, e.g. 'Every 2 weeks on Mon, Wed · 10×'."""
    if not rec:
        return ""

    freq = rec.get("freq", "DAILY")
    interval = max(1, int(rec.get("interval", 1)))
    end_type = rec.get("end_type", "never")

    # Main part
    if freq == "DAILY":
        main = t("rec_sum_daily") if interval == 1 else t("rec_sum_every_n", n=interval, unit=t("rec_unit_days"))

    elif freq == "WEEKLY":
        active = rec.get("byday") or []
        day_names = ", ".join(t(f"rec_day_{d.lower()}") for d in sorted(active, key=lambda d: BYDAY_TO_PY[d]))
        if interval == 1:
            main = t("rec_sum_weekly_on", days=day_names) if day_names else t("rec_sum_weekly")
        else:
            if day_names:
                main = t("rec_sum_every_n_on", n=interval, unit=t("rec_unit_weeks"), days=day_names)
            else:
                main = t("rec_sum_every_n", n=interval, unit=t("rec_unit_weeks"))

    elif freq == "MONTHLY":
        mode = rec.get("monthly_mode", "bymonthday")
        if mode == "byday":
            bysetpos = int(rec.get("bysetpos", 1))
            byday_m = rec.get("byday_monthly", "MO")
            ord_str = t("rec_ord_last") if bysetpos == -1 else t(_ORD_KEYS[max(1, min(bysetpos, 4))])
            day_long = t(f"rec_day_{byday_m.lower()}_long")
            base = t("rec_sum_monthly_byday", ord=ord_str, day=day_long)
        else:
            bmd = int(rec.get("bymonthday", 1))
            base = t("rec_sum_monthly_day", day=bmd)
        main = base if interval == 1 else t("rec_sum_every_n", n=interval, unit=t("rec_unit_months")) + " — " + base

    elif freq == "YEARLY":
        main = t("rec_sum_yearly") if interval == 1 else t("rec_sum_every_n", n=interval, unit=t("rec_unit_years"))

    else:
        main = freq

    # End qualifier
    if end_type == "on":
        s = rec.get("until", "")
        if s:
            try:
                d = datetime.date.fromisoformat(s)
                main += " · " + t("rec_summary_until", date=d.strftime("%d %b %Y"))
            except Exception:
                pass
    elif end_type == "after":
        main += " · " + t("rec_summary_times", count=int(rec.get("count", 1)))

    return main


# ── Apply / Clear ────────────────────────────────────────────────────────────

def _apply_recurrence(workout, rec):
    from workout_rendering import render_workouts
    from workout_persistence import update_workout_badge

    dates = _generate_dates(rec, workout.execution_date)
    rec_id = workout.recurrence_id or str(uuid4())

    # Replace all existing copies in the group (keep source)
    state.workouts[:] = [w for w in state.workouts if w.recurrence_id != rec_id or w.id == workout.id]

    workout.recurrence = rec
    workout.recurrence_id = rec_id

    src_idx = next((i for i, w in enumerate(state.workouts) if w.id == workout.id), None)
    if src_idx is None:
        return

    for offset, d in enumerate(dates[1:], start=1):
        copy_w = Workout(
            id=uuid4(),
            execution_date=d,
            exercises=copy.deepcopy(workout.exercises),
            superset_rounds=copy.deepcopy(workout.superset_rounds),
            name=workout.name,
            breaks=copy.deepcopy(workout.breaks),
            recurrence=rec,
            recurrence_id=rec_id,
        )
        state.workouts.insert(src_idx + offset, copy_w)

    state.save_workouts()
    render_workouts(state.workouts)
    update_workout_badge()


def clear_recurrence(workout):
    from workout_rendering import render_workouts
    from workout_persistence import update_workout_badge

    rec_id = workout.recurrence_id
    if rec_id:
        state.workouts[:] = [w for w in state.workouts if w.recurrence_id != rec_id or w.id == workout.id]

    workout.recurrence = {}
    workout.recurrence_id = ""

    state.save_workouts()
    render_workouts(state.workouts)
    update_workout_badge()


# ── Popup UI ─────────────────────────────────────────────────────────────────

def _show_recurrence_popup(workout):
    existing = document.getElementById("recurrence-popup-overlay")
    if existing:
        existing.remove()

    start_date = workout.execution_date
    rec = workout.recurrence or {}

    # Resolved current values (from rec or defaults derived from start_date)
    freq = rec.get("freq", "DAILY")
    interval = max(1, int(rec.get("interval", 1)))
    active_byday = set(rec.get("byday") or ([PY_TO_BYDAY[start_date.weekday()]] if freq == "WEEKLY" else []))
    monthly_mode = rec.get("monthly_mode", "bymonthday")
    bymonthday = int(rec.get("bymonthday", start_date.day))
    default_setpos, default_byday_m = _nth_weekday_of_month(start_date)
    bysetpos = int(rec.get("bysetpos", default_setpos))
    byday_monthly = rec.get("byday_monthly", default_byday_m)
    end_type = rec.get("end_type", "never")

    # ── Shell ────────────────────────────────────────────────────────────────
    overlay = document.createElement("div")
    overlay.id = "recurrence-popup-overlay"
    overlay.className = "recurrence-overlay"

    modal = document.createElement("div")
    modal.className = "recurrence-modal"
    modal.setAttribute("role", "dialog")

    def _label(text):
        el = document.createElement("div")
        el.className = "recurrence-section-label"
        el.textContent = text
        return el

    def _divider():
        el = document.createElement("hr")
        el.className = "recurrence-divider"
        return el

    # ── Header ────────────────────────────────────────────────────────────────
    header = document.createElement("div")
    header.className = "recurrence-modal-header"

    title_el = document.createElement("span")
    title_el.className = "recurrence-modal-title"
    title_el.textContent = t("rec_repeat_btn")

    close_x = document.createElement("button")
    close_x.type = "button"
    close_x.className = "recurrence-modal-close"
    close_x.innerHTML = '<i class="bi bi-x-lg"></i>'
    close_x.addEventListener("click", create_proxy(lambda evt: overlay.remove()))

    header.appendChild(title_el)
    header.appendChild(close_x)
    modal.appendChild(header)

    # ── Body ──────────────────────────────────────────────────────────────────
    body = document.createElement("div")
    body.className = "recurrence-modal-body"

    # "Repeat every [N] [Freq]"
    body.appendChild(_label(t("rec_repeats_every")))

    interval_row = document.createElement("div")
    interval_row.className = "recurrence-interval-row"

    interval_input = document.createElement("input")
    interval_input.type = "number"
    interval_input.min = "1"
    interval_input.max = "99"
    interval_input.value = str(interval)
    interval_input.className = "recurrence-number-input recurrence-input"

    freq_select = document.createElement("select")
    freq_select.className = "recurrence-select recurrence-input"
    for fval, flbl in [
        ("DAILY",   t("rec_freq_day")),
        ("WEEKLY",  t("rec_freq_week")),
        ("MONTHLY", t("rec_freq_month")),
        ("YEARLY",  t("rec_freq_year")),
    ]:
        opt = document.createElement("option")
        opt.value = fval
        opt.textContent = flbl
        if freq == fval:
            opt.selected = True
        freq_select.appendChild(opt)

    interval_row.appendChild(interval_input)
    interval_row.appendChild(freq_select)
    body.appendChild(interval_row)

    # ── Weekly: day-of-week pills ─────────────────────────────────────────────
    body.appendChild(_divider())
    weekly_section = document.createElement("div")
    weekly_section.className = "recurrence-weekly-section"
    if freq != "WEEKLY":
        weekly_section.style.display = "none"

    weekly_section.appendChild(_label(t("rec_repeat_on")))

    pills_row = document.createElement("div")
    pills_row.className = "recurrence-day-pills"

    day_btns = {}
    for wd in WEEKDAYS:
        btn = document.createElement("button")
        btn.type = "button"
        btn.textContent = t(f"rec_day_{wd.lower()}")
        btn.className = "recurrence-day-pill" + (" recurrence-day-pill--active" if wd in active_byday else "")
        btn.setAttribute("data-wd", wd)

        def _make_toggle(b, code):
            def _toggle(evt):
                if "recurrence-day-pill--active" in b.className:
                    b.className = "recurrence-day-pill"
                    active_byday.discard(code)
                else:
                    b.className = "recurrence-day-pill recurrence-day-pill--active"
                    active_byday.add(code)
            return _toggle

        btn.addEventListener("click", create_proxy(_make_toggle(btn, wd)))
        day_btns[wd] = btn
        pills_row.appendChild(btn)

    weekly_section.appendChild(pills_row)
    body.appendChild(weekly_section)

    # ── Monthly: mode selection ───────────────────────────────────────────────
    monthly_section = document.createElement("div")
    monthly_section.className = "recurrence-monthly-section"
    if freq != "MONTHLY":
        monthly_section.style.display = "none"

    monthly_section.appendChild(_label(t("rec_monthly_on")))

    # Labels derived from stored values
    bmd_label = t("rec_monthly_day_label", day=bymonthday)
    if bysetpos == -1:
        ord_str = t("rec_ord_last")
    else:
        ord_str = t(_ORD_KEYS[max(1, min(bysetpos, 4))])
    byd_label = t("rec_monthly_byday_label", ord=ord_str, day=t(f"rec_day_{byday_monthly.lower()}_long"))

    def _monthly_radio(val, label_text, checked):
        row = document.createElement("div")
        row.className = "recurrence-radio-row"
        radio = document.createElement("input")
        radio.type = "radio"
        radio.name = "monthly-mode"
        radio.value = val
        radio.id = f"rec-monthly-{val}"
        radio.checked = checked
        lbl = document.createElement("label")
        lbl.setAttribute("for", f"rec-monthly-{val}")
        lbl.textContent = label_text
        row.appendChild(radio)
        row.appendChild(lbl)
        return row, radio

    m_bmd_row, m_bmd_radio = _monthly_radio("bymonthday", bmd_label, monthly_mode == "bymonthday")
    m_byd_row, m_byd_radio = _monthly_radio("byday", byd_label, monthly_mode == "byday")
    monthly_section.appendChild(m_bmd_row)
    monthly_section.appendChild(m_byd_row)
    body.appendChild(monthly_section)

    # ── Starts (read-only display) ────────────────────────────────────────────
    body.appendChild(_divider())
    body.appendChild(_label(t("rec_starts")))
    starts_el = document.createElement("div")
    starts_el.className = "recurrence-date-display"
    starts_el.textContent = start_date.strftime("%d %B %Y")
    body.appendChild(starts_el)

    # ── Ends ─────────────────────────────────────────────────────────────────
    body.appendChild(_divider())
    body.appendChild(_label(t("rec_ends")))

    ends_wrap = document.createElement("div")
    ends_wrap.className = "recurrence-ends-container"

    default_until = _add_months(start_date, 1).isoformat()

    def _end_radio(val, label_text, extra=None):
        row = document.createElement("div")
        row.className = "recurrence-radio-row"
        radio = document.createElement("input")
        radio.type = "radio"
        radio.name = "recurrence-end"
        radio.value = val
        radio.id = f"rec-end-{val}"
        radio.checked = (end_type == val)
        lbl = document.createElement("label")
        lbl.setAttribute("for", f"rec-end-{val}")
        lbl.textContent = label_text
        row.appendChild(radio)
        row.appendChild(lbl)
        if extra:
            row.appendChild(extra)
        return row, radio

    _, never_radio = _end_radio("never", t("rec_end_never"))
    ends_wrap.appendChild(_)

    until_input = document.createElement("input")
    until_input.type = "date"
    until_input.className = "recurrence-date-input recurrence-input"
    until_input.value = rec.get("until", default_until)
    until_input.disabled = (end_type != "on")
    _, on_radio = _end_radio("on", t("rec_end_on"), until_input)
    ends_wrap.appendChild(_)

    count_input = document.createElement("input")
    count_input.type = "number"
    count_input.min = "1"
    count_input.max = "365"
    count_input.className = "recurrence-count-input recurrence-input"
    count_input.value = str(rec.get("count", 10))
    count_input.disabled = (end_type != "after")
    occ_span = document.createElement("span")
    occ_span.className = "recurrence-occ-label"
    occ_span.textContent = t("rec_occurrences")
    after_wrap = document.createElement("span")
    after_wrap.className = "recurrence-after-wrapper"
    after_wrap.appendChild(count_input)
    after_wrap.appendChild(occ_span)
    _, after_radio = _end_radio("after", t("rec_end_after"), after_wrap)
    ends_wrap.appendChild(_)

    body.appendChild(ends_wrap)
    modal.appendChild(body)

    # ── Event handlers ────────────────────────────────────────────────────────
    def _on_freq_change(evt):
        f = freq_select.value
        weekly_section.style.display = "flex" if f == "WEEKLY" else "none"
        monthly_section.style.display = "flex" if f == "MONTHLY" else "none"

    freq_select.addEventListener("change", create_proxy(_on_freq_change))

    def _on_end_change(evt):
        v = evt.target.value
        until_input.disabled = (v != "on")
        count_input.disabled = (v != "after")

    for r in [never_radio, on_radio, after_radio]:
        r.addEventListener("change", create_proxy(_on_end_change))

    # ── Footer: [clear (left)] [spacer] [Done] [Cancel] ──────────────────────
    footer = document.createElement("div")
    footer.className = "recurrence-modal-footer"

    if rec:
        clear_btn = document.createElement("button")
        clear_btn.type = "button"
        clear_btn.className = "recurrence-btn--clear"
        clear_btn.textContent = t("rec_clear")

        def _on_clear(evt, _w=workout):
            overlay.remove()
            clear_recurrence(_w)

        clear_btn.addEventListener("click", create_proxy(_on_clear))
        footer.appendChild(clear_btn)

    spacer = document.createElement("div")
    spacer.style.flex = "1"
    footer.appendChild(spacer)

    done_btn = document.createElement("button")
    done_btn.type = "button"
    done_btn.className = "btn btn-sm btn-outline-gold"
    done_btn.textContent = t("rec_done")

    def _on_done(evt, _w=workout):
        f = freq_select.value
        iv = max(1, int(interval_input.value) if str(interval_input.value).strip().isdigit() else 1)
        sel_byday = sorted(active_byday, key=lambda d: BYDAY_TO_PY[d]) or [PY_TO_BYDAY[start_date.weekday()]]
        mm = "byday" if m_byd_radio.checked else "bymonthday"
        if on_radio.checked:
            et = "on"
        elif after_radio.checked:
            et = "after"
        else:
            et = "never"
        cnt = max(1, int(count_input.value) if str(count_input.value).strip().isdigit() else 10)

        new_rec = {
            "freq": f,
            "interval": iv,
            "byday": sel_byday,
            "monthly_mode": mm,
            "bymonthday": bymonthday,
            "bysetpos": bysetpos,
            "byday_monthly": byday_monthly,
            "end_type": et,
            "until": until_input.value,
            "count": cnt,
        }
        overlay.remove()
        _apply_recurrence(_w, new_rec)

    done_btn.addEventListener("click", create_proxy(_on_done))
    footer.appendChild(done_btn)

    cancel_btn = document.createElement("button")
    cancel_btn.type = "button"
    cancel_btn.className = "recurrence-btn--cancel"
    cancel_btn.textContent = t("cancel_btn")
    cancel_btn.addEventListener("click", create_proxy(lambda evt: overlay.remove()))
    footer.appendChild(cancel_btn)

    modal.appendChild(footer)
    overlay.appendChild(modal)
    document.body.appendChild(overlay)

    def _on_overlay_click(evt):
        if evt.target == overlay:
            overlay.remove()

    overlay.addEventListener("click", create_proxy(_on_overlay_click))


def open_recurrence_popup(event):
    event.stopPropagation()
    workout_id = _event_attr(event, "data-workout-id")
    if not workout_id:
        return
    w_id = UUID(workout_id)
    workout = next((w for w in state.workouts if w.id == w_id), None)
    if not workout:
        return
    _show_recurrence_popup(workout)
