import datetime
import io

from js import Uint8Array, File, URL, document, localStorage
from models import Exercise, Workout  # noqa: F401 — required in eval() scope
from uuid import UUID  # noqa: F401 — required in eval() scope

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
    workouts = eval(raw)

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
        for ex in workout.exercises:
            entry = f"• {ex.name} — {ex.detail_str()}"
            if ex.notes:
                entry += f" ({ex.notes})"
            exercise_lines.append(entry)

        count = len(workout.exercises)
        summary = f"Workout — {count} exercise{'s' if count != 1 else ''}"
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
