from datetime import datetime, date, timedelta
from collections import defaultdict
from data import FitnessClass
from pyodide.ffi import create_proxy
from data import (
    load_classes_from_file,
    load_classes_from_gh,
    load_classes_from_url,
    convert_to_json,
    load_dummy_classes,
    read_data,
)
from config import (
    TRANSLATIONS,
    DataSourceMode,
    DATA_SOURCE_MODE,
    load_config,
    Config,
)
import io
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from js import Uint8Array, File, URL, document
from pyodide.ffi import create_proxy
from pyscript import document, display, window
from pyweb import pydom
import json

from js import document, window, Uint8Array
from pyodide.ffi.wrappers import add_event_listener


def render_fitness_classes(classes: list[FitnessClass], highlighted_date: date) -> str:
    classes_by_day = defaultdict(list)
    for cls in classes:
        day = cls.start.date()
        classes_by_day[day].append(cls)

    days = sorted(classes_by_day.keys())

    if days:
        if len(days) < 7:
            last_day = days[-1]
            week_start_day = last_day - timedelta(days=last_day.weekday())
            days = [week_start_day + timedelta(days=i) for i in range(7)]
    else:
        week_start_day = highlighted_date - timedelta(days=highlighted_date.weekday())
        days = [week_start_day + timedelta(days=i) for i in range(7)]
    days = sorted(days)

    # Build 15-minute slots covering the full duration of every class
    all_slot_starts = set()
    for cls in classes:
        start_m = cls.start.hour * 60 + cls.start.minute
        end_m = cls.end.hour * 60 + cls.end.minute
        current = start_m
        while current < end_m:
            all_slot_starts.add(current)
            current += 15

    if all_slot_starts:
        # Pad every touched hour to all 4 quarter-slots so the hour label always
        # spans a full 4-row block, making partial coverage visually obvious.
        hour_starts = {s - (s % 60) for s in all_slot_starts}
        extended = {h + q * 15 for h in hour_starts for q in range(4)}
        max_slot = max(hour_starts) + 45
        hour_slots = sorted(s for s in extended if s <= max_slot)
    else:
        hour_slots = []

    # (day, slot_start_minutes) -> (FitnessClass, row_span)
    class_lookup = {}
    # slots that are interior to a multi-hour class (don't render a cell here)
    covered_slots = set()

    for day in days:
        for cls in classes_by_day[day]:
            start_m = cls.start.hour * 60 + cls.start.minute
            end_m = cls.end.hour * 60 + cls.end.minute
            slots_for_class = []
            current = start_m
            while current < end_m:
                slots_for_class.append(current)
                current += 15
            span = len(slots_for_class)
            class_lookup[(day, start_m)] = (cls, span)
            for slot in slots_for_class[1:]:
                covered_slots.add((day, slot))

    html = []
    html.append('<div class="schedule-grid">')

    # Header row — explicit grid-column so skipped cells don't shift anything
    html.append(
        f'<div class="schedule-header" style="grid-column: 1; grid-row: 1;">'
        f'{TRANSLATIONS[LANGUAGE]["time"]} / {TRANSLATIONS[LANGUAGE]["date"]}'
        f'</div>'
    )
    for col, day in enumerate(days, start=2):
        week_day = day.strftime("%A")
        date_num = day.strftime("%d")
        if day == highlighted_date:
            html.append(
                f'<div class="schedule-header" style="grid-column: {col}; grid-row: 1;">'
                f"{TRANSLATIONS[LANGUAGE]['week_days'][week_day.lower()]}<br>"
                f'<span class="schedule-today">{date_num}</span>'
                f"</div>"
            )
        else:
            html.append(
                f'<div class="schedule-header" style="grid-column: {col}; grid-row: 1;">'
                f"{TRANSLATIONS[LANGUAGE]['week_days'][week_day.lower()]}<br>"
                f'<span style="font-size: 1.5em; font-weight: bold;">{date_num}</span>'
                f"</div>"
            )

    for row, slot_start_m in enumerate(hour_slots, start=2):
        slot_h = slot_start_m // 60
        slot_m_min = slot_start_m % 60
        start_str = f"{slot_h:02d}:{slot_m_min:02d}"

        if slot_m_min == 0:
            hour_span = sum(1 for s in hour_slots if slot_start_m <= s < slot_start_m + 60)
            end_label = f"{slot_h + 1:02d}:00"
            row_spec = f"{row} / span {hour_span}" if hour_span > 1 else str(row)
            html.append(
                f'<div class="schedule-time" style="grid-column: 1; grid-row: {row_spec};">'
                f'{start_str}-{end_label}'
                f'</div>'
            )

        for col, day in enumerate(days, start=2):
            if (day, slot_start_m) in covered_slots:
                # interior slot of a multi-hour class — the spanning cell covers this space
                continue

            class_info = class_lookup.get((day, slot_start_m))
            if class_info:
                fitness_class, span = class_info
                config = fitness_class.render_config
                whatsapp_number = WHATSAPP_NUMBER
                message_template: str = TRANSLATIONS[LANGUAGE]["whatsapp_message"]
                message = message_template.format(
                    class_name=fitness_class.name,
                    instructor=fitness_class.instructor,
                    date=day.strftime("%A, %d %B %Y"),
                    time=start_str,
                )
                whatsapp_url = f"https://wa.me/{whatsapp_number}?text={message.replace(' ', '%20')}"

                has_whatsapp = bool(whatsapp_number and whatsapp_number != "n/a")
                if has_whatsapp and BOOK_VIA_WHATSAPP:
                    book_via_whatsapp = (
                        f'<a class="whatsapp-link" href="{whatsapp_url}" target="_blank">'
                        f"{TRANSLATIONS[LANGUAGE]['book_via_whatsapp']}"
                        f"</a>"
                    )
                elif has_whatsapp:
                    book_via_whatsapp = (
                        f'<span style="color:gray; font-style:italic; cursor:not-allowed;" '
                        f'title="Feature disabled.">'
                        f"{TRANSLATIONS[LANGUAGE]['book_via_whatsapp']}"
                        f"</span>"
                    )
                else:
                    book_via_whatsapp = ""

                if fitness_class.instructor:
                    instructor_text = f"{TRANSLATIONS[LANGUAGE]['instructor']}: {fitness_class.instructor}"
                else:
                    instructor_text = ""

                row_span = f"grid-row: {row} / span {span}; " if span > 1 else f"grid-row: {row}; "
                class_time_range = f"{fitness_class.start.strftime('%H:%M')}–{fitness_class.end.strftime('%H:%M')}"

                html.append(
                    f'<div class="schedule-cell" style="{row_span}grid-column: {col}; color:{config.text_color}; background:{config.background_color};">'
                    f"<strong>{fitness_class.name}</strong><br>"
                    f"{instructor_text}<br>"
                    f"{book_via_whatsapp + '<br>' if book_via_whatsapp else ''}"
                    f'<span class="cell-time-range">{class_time_range}</span>'
                    "</div>"
                )

    html.append("</div>")
    return "\n".join(html)


def create_pdf(classes: list[FitnessClass]) -> FPDF:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=10)

    page_width = 297  # A4 landscape width in mm
    page_height = 210  # A4 landscape height in mm
    steps = 100
    for i in range(steps):
        r1, g1, b1 = (
            int(153 * 0.7 + 255 * 0.3),
            int(94 * 0.7 + 255 * 0.3),
            int(10 * 0.7 + 255 * 0.3),
        )
        r2, g2, b2 = (255, 255, 255)
        ratio = i / steps
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        y = (page_height / steps) * i
        pdf.set_fill_color(r, g, b)
        pdf.rect(0, y, page_width, page_height / steps, "F")

    pdf.set_y(4)
    pdf.set_font("Helvetica", "B", 18)
    title = TRANSLATIONS[LANGUAGE].get("schedule_title", "Classes Schedule")
    pdf.set_text_color(40, 40, 80)
    pdf.cell(0, 12, title, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 14)

    classes_by_day = defaultdict(list)
    for cls in classes:
        day = cls.start.date()
        classes_by_day[day].append(cls)
    days = sorted(classes_by_day.keys())
    if days:
        if len(days) < 7:
            last_day = days[-1]
            week_start_day = last_day - timedelta(days=last_day.weekday())
            days = [week_start_day + timedelta(days=i) for i in range(7)]
    else:
        week_start_day = date.today() - timedelta(days=date.today().weekday())
        days = [week_start_day + timedelta(days=i) for i in range(7)]
    days = sorted(days)

    time_intervals = set()
    for cls in classes:
        time_intervals.add((cls.start.time(), cls.end.time()))
    time_intervals = sorted(time_intervals)

    class_lookup = {}
    for day in days:
        for cls in classes_by_day[day]:
            interval = (cls.start.time(), cls.end.time())
            class_lookup[(day, interval)] = cls

    cell_height = 15
    cell_width_time = 35
    cell_width_day = (
        277 - cell_width_time
    ) / 7  # 277mm is printable width in landscape A4

    pdf.set_fill_color(220, 220, 220)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(
        cell_width_time,
        cell_height,
        f"{TRANSLATIONS[LANGUAGE]['time']} / {TRANSLATIONS[LANGUAGE]['date']}",
        border=1,
        align="C",
        fill=True,
    )
    for day in days:
        week_day = day.strftime("%A")
        date_num = day.strftime("%d")
        pdf.set_font("Helvetica", "B", 11)
        week_label = TRANSLATIONS[LANGUAGE]["week_days"][week_day.lower()]
        date_label = date_num
        label = f"{week_label}\n{date_label}"
        x = pdf.get_x()
        y = pdf.get_y()
        pdf.set_fill_color(220, 220, 220)
        pdf.multi_cell(
            cell_width_day, cell_height / 2, label, border=1, align="C", fill=True
        )
        pdf.set_xy(x + cell_width_day, y)
    pdf.ln(cell_height)

    for interval in time_intervals:
        start_str = interval[0].strftime("%H:%M")
        end_str = interval[1].strftime("%H:%M")
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(0, 0, 0)
        pdf.set_fill_color(255, 255, 255)
        pdf.cell(
            cell_width_time,
            cell_height,
            f"{start_str}-{end_str}",
            border=1,
            align="C",
            fill=True,
        )
        for day in days:
            fitness_class = class_lookup.get((day, interval))
            if fitness_class:
                config = fitness_class.render_config
                font_family = (
                    config.font_family
                    if hasattr(config, "font_family")
                    else "Helvetica"
                )
                font_style = config.font_style if hasattr(config, "font_style") else ""
                try:
                    hex_color = config.text_color.lstrip("#")
                    r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
                    pdf.set_text_color(r, g, b)
                except Exception:
                    pdf.set_text_color(0, 0, 0)
                try:
                    hex_bg = config.background_color.lstrip("#")
                    br, bg, bb = tuple(int(hex_bg[i : i + 2], 16) for i in (0, 2, 4))
                    pdf.set_fill_color(br, bg, bb)
                except Exception:
                    pdf.set_fill_color(255, 255, 255)
                text = f"{fitness_class.name}"

                font_size = 11
                pdf.set_font(font_family, font_style, font_size)
                text_width = pdf.get_string_width(text)
                while text_width > (cell_width_day - 2) and font_size > 6:
                    font_size -= 1
                    pdf.set_font(font_family, font_style, font_size)
                    text_width = pdf.get_string_width(text)
                pdf.cell(
                    cell_width_day,
                    cell_height,
                    text,
                    border=1,
                    align="C",
                    fill=True,
                )
            else:
                pdf.set_font("Helvetica", "", 11)
                pdf.set_text_color(0, 0, 0)
                pdf.set_fill_color(255, 255, 255)
                pdf.cell(cell_width_day, cell_height, "", border=1, fill=True)
        pdf.ln(cell_height)

        logo_path = "logo-nobg.png"
        logo_diameter = 15
        x_logo = 0
        y_logo = page_height - logo_diameter
        pdf.image(
            logo_path,
            x=x_logo,
            y=y_logo,
            w=logo_diameter,
            h=logo_diameter,
            type="",
            link="",
        )

    return pdf


def download_pdf(event):
    pdf = create_pdf(filtered_classes)
    encoded_data = pdf.output()
    my_stream = io.BytesIO(encoded_data)

    js_array = Uint8Array.new(len(encoded_data))
    js_array.assign(my_stream.getbuffer())

    file = File.new([js_array], "unused_file_name.pdf", {type: "application/pdf"})
    url = URL.createObjectURL(file)

    hidden_link = document.createElement("a")
    hidden_link.setAttribute(
        "download",
        f"plan_{current_week_start_date.strftime('%d.%m.%Y')}_{current_week_end_date.strftime('%d.%m.%Y')}_{LANGUAGE}.pdf",
    )
    hidden_link.setAttribute("href", url)
    hidden_link.click()


current_link = window.location.href
data_source_url = None
if "data_source=" in current_link:
    data_source_url = current_link.split("data_source=")[1].strip()

classes: list[FitnessClass] = []
config: Config = load_config()

LANGUAGE = config.language
WHATSAPP_NUMBER = config.whatsapp_number
BOOK_VIA_WHATSAPP = config.book_via_whatsapp

if data_source_url:
    classes = load_classes_from_url(data_source_url)
else:
    if DATA_SOURCE_MODE == DataSourceMode.GH_PAGES:
        classes = load_classes_from_gh(lang=LANGUAGE)
    elif DATA_SOURCE_MODE == DataSourceMode.LOCAL:
        classes = load_classes_from_file(lang=LANGUAGE)
    else:
        classes = load_dummy_classes()


if classes:
    min_date = min(cls.start.date() for cls in classes)
    max_date = max(cls.start.date() for cls in classes)
else:
    min_date = date.today()
    max_date = date.today()

current_week_start_date = date.today() - timedelta(days=date.today().weekday())
current_week_end_date = current_week_start_date + timedelta(days=6)
filtered_classes = [
    cls
    for cls in classes
    if current_week_start_date <= cls.start.date() <= current_week_end_date
]

schedule_div = pydom["#schedule"][0]
schedule_div._js.innerHTML = render_fitness_classes(filtered_classes, date.today())
schedule_div._js.classList.remove("d-none")

pydom["#spinner"][0]._js.classList.add("d-none")

schedule_date_input = pydom["#schedule-date"][0]
schedule_date_input._js.value = datetime.now().strftime("%Y-%m-%d")
schedule_date_input._js.min = min_date.strftime("%Y-%m-%d")
schedule_date_input._js.max = max_date.strftime("%Y-%m-%d")

schedule_date_label = pydom["#schedule-date-label"][0]
schedule_date_label._js.innerHTML = TRANSLATIONS[LANGUAGE]["schedule_date_label"]

pydom["#tools"][0]._js.classList.remove("d-none")


def on_date_change(evt):
    global filtered_classes, current_week_start_date, current_week_end_date
    value = evt.target.value
    if not value:
        return
    new_date = datetime.strptime(value, "%Y-%m-%d").date()
    current_week_start_date = new_date - timedelta(days=new_date.weekday())
    current_week_end_date = current_week_start_date + timedelta(days=6)
    filtered_classes = [
        cls
        for cls in classes
        if current_week_start_date <= cls.start.date() <= current_week_end_date
    ]
    pydom["#schedule"][0]._js.innerHTML = render_fitness_classes(
        filtered_classes, new_date
    )


schedule_date_input._js.addEventListener("change", create_proxy(on_date_change))

if WHATSAPP_NUMBER and WHATSAPP_NUMBER != "n/a":
    pydom["#whatsapp-btn"][0]._js.href = f"https://wa.me/{WHATSAPP_NUMBER}"
else:
    pydom["#whatsapp-btn"][0]._js.style.display = "none"
modal = pydom["#infoModalLabel"][0]
modal._js.innerHTML = TRANSLATIONS[LANGUAGE]["info_modal_title"]

info_modal_body = pydom["#info-modal-body"][0]
version_element = pydom["#version"][0]


def load_modal_content():
    return TRANSLATIONS[LANGUAGE].get("info_modal_content", "No information available.")


info_modal_body._js.innerHTML = load_modal_content()
version_element._js.innerHTML = "Version: 18.08.2025"


async def upload_file_and_show(e):
    global classes, filtered_classes

    file_list = e.target.files
    first_item = file_list.item(0)

    my_bytes: bytes = await get_bytes_from_file(first_item)
    classes = read_data(convert_to_json(my_bytes.decode("utf-8")))
    min_date = min(cls.start.date() for cls in classes)
    max_date = max(cls.start.date() for cls in classes)

    today = date.today()
    current_week_start_date = today - timedelta(days=today.weekday())
    current_week_end_date = current_week_start_date + timedelta(days=6)
    filtered_classes = [
        cls
        for cls in classes
        if current_week_start_date <= cls.start.date() <= current_week_end_date
    ]
    pydom["#schedule"][0]._js.innerHTML = render_fitness_classes(
        filtered_classes, today
    )
    schedule_date_input = pydom["#schedule-date"][0]
    schedule_date_input._js.value = datetime.now().strftime("%Y-%m-%d")
    schedule_date_input._js.min = min_date.strftime("%Y-%m-%d")
    schedule_date_input._js.max = max_date.strftime("%Y-%m-%d")


async def get_bytes_from_file(file):
    array_buf = await file.arrayBuffer()
    return array_buf.to_bytes()


add_event_listener(
    document.getElementById("file-upload"), "change", upload_file_and_show
)
