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

    time_intervals = set()
    for cls in classes:
        time_intervals.add((cls.start.time(), cls.end.time()))
    time_intervals = sorted(time_intervals)

    class_lookup = {}
    for day in days:
        for cls in classes_by_day[day]:
            interval = (cls.start.time(), cls.end.time())
            class_lookup[(day, interval)] = cls

    html = []

    html.append('<div class="schedule-grid">')
    html.append(
        f'<div class="schedule-header">{TRANSLATIONS[LANGUAGE]["time"]} / {TRANSLATIONS[LANGUAGE]["date"]}</div>'
    )
    for day in days:
        week_day = day.strftime("%A")
        date_num = day.strftime("%d")
        if day == highlighted_date:
            html.append(
                f'<div class="schedule-header">'
                f"{TRANSLATIONS[LANGUAGE]['week_days'][week_day.lower()]}<br>"
                f'<span class="schedule-today">{date_num}</span>'
                f"</div>"
            )
        else:
            html.append(
                f'<div class="schedule-header">'
                f"{TRANSLATIONS[LANGUAGE]['week_days'][week_day.lower()]}<br>"
                f'<span style="font-size: 1.5em; font-weight: bold;">{date_num}</span>'
                f"</div>"
            )

    for interval in time_intervals:
        start_str = interval[0].strftime("%H:%M")
        end_str = interval[1].strftime("%H:%M")
        html.append(f'<div class="schedule-time">{start_str}-{end_str}</div>')
        for day in days:
            fitness_class: FitnessClass | None = class_lookup.get((day, interval))
            if fitness_class:
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

                if BOOK_VIA_WHATSAPP:
                    book_via_whatsapp = (
                        f'<a class="whatsapp-link" href="{whatsapp_url}" target="_blank">'
                        f"{TRANSLATIONS[LANGUAGE]['book_via_whatsapp']}"
                        f"</a>"
                    )
                else:
                    book_via_whatsapp = (
                        f'<span style="color:gray; font-style:italic; cursor:not-allowed;" '
                        f'title="Feature disabled.">'
                        f"{TRANSLATIONS[LANGUAGE]['book_via_whatsapp']}"
                        f"</span>"
                    )

                if fitness_class.instructor:
                    instructor_text = f"{TRANSLATIONS[LANGUAGE]['instructor']}: {fitness_class.instructor}"
                else:
                    instructor_text = ""

                html.append(
                    f'<div class="schedule-cell" style="color:{config.text_color}; background:{config.background_color};">'
                    f"<strong>{fitness_class.name}</strong><br>"
                    f"{instructor_text}<br>"
                    f"{book_via_whatsapp}<br>"
                    "</div>"
                )
            else:
                html.append('<div class="schedule-cell schedule-cell-empty"></div>')
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

pydom["#whatsapp-btn"][0]._js.href = f"https://wa.me/{WHATSAPP_NUMBER}"
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
