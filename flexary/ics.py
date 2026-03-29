import datetime
import io

from js import Uint8Array, File, URL, document, localStorage
from models import workouts_from_json

import state


def _fold(line: str) -> str:
    """Fold long lines per RFC 5545 (max 75 octets, continuation with CRLF + space)."""
    result = []
    while len(line.encode("utf-8")) > 75:
        chunk = line[:75]
        while len(chunk.encode("utf-8")) > 75:
            chunk = chunk[:-1]
        result.append(chunk)
        line = " " + line[len(chunk):]
    result.append(line)
    return "\r\n".join(result)


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _build_ics() -> str:
    raw = localStorage.getItem(state.ls_workouts_key)
    if not raw:
        return ""
    workouts = workouts_from_json(raw)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//vladflore.fit//Flexary//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    now = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    for workout in workouts:
        if not workout.exercises:
            continue

        date_str = workout.execution_date.strftime("%Y%m%d")
        uid = f"flexary-{workout.id}@vladflore.fit"

        exercise_lines = []
        exs = workout.exercises
        i = 0
        prev_was_superset = False

        while i < len(exs):
            ex = exs[i]
            if exercise_lines:
                if prev_was_superset or ex.superset_id:
                    exercise_lines += ["", ""]   # larger gap around supersets
                else:
                    exercise_lines += [""]        # single blank line between standalone exercises
            break_secs = workout.breaks.get(ex.internal_id, 0)
            if break_secs:
                _m, _s = divmod(break_secs, 60)
                _fmt = (f"{_m}m {_s}s" if _s else f"{_m}m") if _m else f"{_s}s"
                exercise_lines.append(f"  \u23f1 {_fmt} rest")
                exercise_lines.append("")
            if ex.superset_id:
                sid = ex.superset_id
                group = []
                while i < len(exs) and exs[i].superset_id == sid:
                    group.append(exs[i])
                    i += 1
                rounds = workout.superset_rounds.get(sid, 1)
                rounds_label = f"{rounds} round{'s' if rounds != 1 else ''}"
                exercise_lines.append(f"Superset ({rounds_label}):")
                for g_ex in group:
                    entry = f"  • {g_ex.name} — {g_ex.detail_str(in_superset=True)}"
                    if g_ex.notes:
                        entry += f" ({g_ex.notes})"
                    exercise_lines.append(entry)
                prev_was_superset = True
            else:
                entry = f"• {ex.name} — {ex.detail_str()}"
                if ex.notes:
                    entry += f" ({ex.notes})"
                exercise_lines.append(entry)
                prev_was_superset = False
                i += 1

        count = len(workout.exercises)
        workout_label = workout.name if workout.name else "Workout"
        summary = f"{workout_label} — {count} exercise{'s' if count != 1 else ''}"
        description = "\\n".join(_escape(l) for l in exercise_lines)

        lines += [
            "BEGIN:VEVENT",
            _fold(f"UID:{uid}"),
            f"DTSTAMP:{now}",
            f"DTSTART;VALUE=DATE:{date_str}",
            f"DTEND;VALUE=DATE:{date_str}",
            _fold(f"SUMMARY:{_escape(summary)}"),
            _fold(f"DESCRIPTION:{description}"),
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def download_ics(*args) -> None:
    if not any(w.exercises for w in state.workouts):
        return

    content = _build_ics()
    if not content:
        return

    encoded = content.encode("utf-8")
    js_array = Uint8Array.new(len(encoded))
    js_array.assign(io.BytesIO(encoded).getbuffer())

    file = File.new([js_array], "workouts.ics", {type: "text/calendar"})
    url = URL.createObjectURL(file)

    hidden_link = document.createElement("a")
    hidden_link.setAttribute(
        "download",
        f"workouts_{datetime.datetime.now().strftime('%d%m%Y_%H%M%S')}.ics",
    )
    hidden_link.setAttribute("href", url)
    hidden_link.click()
