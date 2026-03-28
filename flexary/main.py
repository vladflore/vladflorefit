import datetime
import io
import qrcode
from dataclasses import dataclass
from uuid import UUID, uuid4
from PIL import Image
from fpdf import FPDF
from js import Uint8Array, File, URL, document, localStorage
from pyodide.ffi.wrappers import add_event_listener
from pyodide.ffi import create_proxy
from pyscript import document, window, when, display
from pyweb import pydom

from common import copyright, current_version, csv_to_json

category_to_badge = {
    "strength": "bg-dark",
    "conditioning": "bg-danger",
    "mobility": "bg-info",
}

category_to_rgb = {
    "strength": (50, 50, 50),
    "conditioning": (220, 53, 69),
    "mobility": (13, 202, 240),
}


@dataclass
class Exercise:
    id: int
    internal_id: str
    name: str
    sets: int
    reps: str
    time: str = ""


@dataclass
class Workout:
    id: UUID
    execution_date: datetime.datetime
    exercises: list[Exercise]


ls_workouts_key = "workouts"
current_workouts = eval(
    localStorage.getItem(ls_workouts_key)
    if localStorage.getItem(ls_workouts_key)
    else "[]"
)

workouts: list[Workout] = current_workouts

active_workout: UUID | None = workouts[0].id if workouts else None


def q(selector, root=document):
    return root.querySelector(selector)


exercises_row_id = "#exercises-row"
exercise_card_template_id = "#exercise-card-template"
copyright_el_id = "#copyright"
version_el_id = "#version"
footer_el_id = "#footer"
workout_sidebar_el_id = "#workout-sidebar"
exercises_per_category_badges_row_id = "#exercises-per-category-badges-row"
exercises_per_body_part_badges_row_id = "#exercises-per-body-part-badges-row"

active_category_filter: str | None = None
active_body_part_filter: str | None = None

download_pdf_btn_id = "download-workouts"

exercises_row = pydom[exercises_row_id][0]
exercise_template = pydom.Element(
    q(exercise_card_template_id).content.querySelector("#card-exercise")
)


def create_pdf():
    class PDF(FPDF):
        def header(self):
            logo_size = 14
            self.image("logo-nobg.png", x=self.w - self.r_margin - logo_size, y=3, w=logo_size, h=logo_size)
            self.ln(logo_size - 4)

        def footer(self):
            self.set_y(-20)
            self.set_font("opensans", "I", 10)
            self.set_draw_color(180, 180, 180)
            self.set_line_width(0.3)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.ln(2)
            self.set_text_color(120, 120, 120)
            self.cell(0, 10, "vladflore.fit", align="L")
            self.set_text_color(0, 0, 0)
            self.set_y(self.get_y() - 10)
            page_label = f"Page {getattr(self, 'workout_page_num', 1)} of {getattr(self, 'workout_total_pages', 1)}"
            self.cell(0, 10, page_label, align="C")

    pdf = PDF()
    pdf.set_top_margin(5)
    pdf.add_font("opensans", style="", fname="OpenSans-Regular.ttf")
    pdf.add_font("opensans", style="B", fname="OpenSans-Bold.ttf")
    pdf.add_font("opensans", style="I", fname="OpenSans-Italic.ttf")
    pdf.add_font("opensans", style="BI", fname="OpenSans-BoldItalic.ttf")
    pdf.set_font("opensans", style="", size=10)

    exercise_name_column_width = 90
    sets_column_width = 20
    reps_time_column_width = 30
    weight_column_width = 40

    workouts = localStorage.getItem(ls_workouts_key)
    if workouts:
        workouts = eval(workouts)
        total_workouts = len([w for w in workouts if w.exercises])
        for idx, workout in enumerate(workouts, start=1):
            exercises = workout.exercises
            if not exercises:
                continue

            chunk_size = 15
            import math
            workout_total_pages = math.ceil(len(exercises) / chunk_size)
            for i in range(0, len(exercises), chunk_size):
                chunk = exercises[i : i + chunk_size]
                pdf.workout_page_num = i // chunk_size + 1
                pdf.workout_total_pages = workout_total_pages
                pdf.add_page()

                table_width = (
                    exercise_name_column_width
                    + sets_column_width
                    + reps_time_column_width
                    + weight_column_width
                )
                page_width = pdf.w - 2 * pdf.l_margin
                x_start = (page_width - table_width) / 2 + pdf.l_margin

                pdf.ln(2)
                formatted_date = workout.execution_date.strftime("%d.%m.%Y")

                pdf.set_font("opensans", style="I", size=10)
                exercise_count = len(exercises)
                ex_label = "exercise" if exercise_count == 1 else "exercises"
                prefix = "Do on: "
                prefix_w = pdf.get_string_width(prefix)
                pdf.set_x(x_start)
                pdf.cell(prefix_w, 8, prefix, new_x="END", new_y="LAST")
                pdf.set_font("opensans", style="BI", size=10)
                date_w = pdf.get_string_width(formatted_date)
                pdf.cell(date_w, 8, formatted_date, new_x="END", new_y="LAST")
                pdf.set_font("opensans", style="I", size=10)
                suffix = f"  ·  {exercise_count} {ex_label}"
                pdf.cell(pdf.get_string_width(suffix), 8, suffix, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(4)

                pdf.set_font("opensans", style="", size=10)

                pdf.set_x(x_start)
                row_height = 8

                pdf.set_fill_color(240, 228, 208)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("opensans", style="B", size=10)
                pdf.set_draw_color(186, 148, 94)
                pdf.set_x(x_start)
                pdf.cell(exercise_name_column_width, row_height, "Exercise", border=1, fill=True, align="C")
                pdf.cell(sets_column_width, row_height, "Sets", border=1, fill=True, align="C")
                pdf.cell(reps_time_column_width, row_height, "Reps / Time", border=1, fill=True, align="C")
                pdf.cell(weight_column_width, row_height, "Weight", border=1, fill=True, align="C")
                pdf.ln()
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("opensans", style="", size=10)
                pdf.set_draw_color(186, 148, 94)
                for row_num, exercise in enumerate(chunk):
                    pdf.set_x(x_start)
                    row_fill = row_num % 2 == 1
                    detailed_page_link = next(
                        (
                            f"https://vladflore.fit/flexary/detail.html?exercise_id={exercise.id}"
                            for d in data
                            if int(d["id"]) == exercise.id
                        ),
                        "",
                    )
                    try:
                        sets = int(exercise.sets)
                    except Exception:
                        sets = 1

                    sub_row_h = 7
                    ex_data = next((d for d in data if int(d["id"]) == exercise.id), None)
                    categories = [c.strip() for c in ex_data["category"].split(",")] if ex_data else []

                    badge_h = 4
                    badge_pad_v = 1.5
                    badge_area_h = badge_h + badge_pad_v * 2
                    min_cell_h = badge_area_h + row_height + 1
                    total_h = max(min_cell_h, sets * sub_row_h)
                    row_y = pdf.get_y()
                    rect_style = "FD" if row_fill else "D"
                    if row_fill:
                        pdf.set_fill_color(245, 245, 245)

                    pdf.rect(x_start, row_y, exercise_name_column_width, total_h, style=rect_style)

                    pdf.set_font("opensans", style="B", size=6)
                    badge_x = x_start + 3
                    badge_y = row_y + badge_pad_v
                    for cat in categories:
                        bg = category_to_rgb.get(cat.lower(), (186, 148, 94))
                        badge_text_w = pdf.get_string_width(cat) + 4
                        pdf.set_fill_color(*bg)
                        pdf.rect(badge_x, badge_y, badge_text_w, badge_h, style="F", round_corners=True, corner_radius=1.5)
                        pdf.set_text_color(255, 255, 255)
                        text_y = badge_y + (badge_h - pdf.font_size) / 2
                        pdf.set_xy(badge_x, text_y)
                        pdf.cell(badge_text_w, pdf.font_size, cat, border=0, align="C")
                        badge_x += badge_text_w + 1.5

                    if row_fill:
                        pdf.set_fill_color(245, 245, 245)

                    name_y = row_y + badge_area_h
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font("opensans", style="", size=10)
                    tri_size = 2.2
                    icon_x = x_start + 3
                    icon_y_center = name_y + row_height / 2
                    pdf.set_fill_color(186, 148, 94)
                    pdf.polygon([
                        (icon_x, icon_y_center - tri_size),
                        (icon_x, icon_y_center + tri_size),
                        (icon_x + tri_size * 1.6, icon_y_center),
                    ], style="F")
                    if row_fill:
                        pdf.set_fill_color(245, 245, 245)
                    qr_size = 12
                    qr = qrcode.QRCode(version=1, box_size=3, border=1, error_correction=qrcode.constants.ERROR_CORRECT_L)
                    qr.add_data(detailed_page_link)
                    qr.make(fit=True)
                    qr_img = qr.make_image(fill_color="black", back_color="white")
                    qr_buf = io.BytesIO()
                    qr_img.save(qr_buf, format="PNG")
                    qr_buf.seek(0)
                    qr_x = x_start + exercise_name_column_width - qr_size - 2
                    qr_y = row_y + (total_h - qr_size) / 2

                    text_x = icon_x + tri_size * 1.6 + 2
                    text_w = qr_x - text_x - 2
                    pdf.set_xy(text_x, name_y)
                    pdf.set_font("opensans", style="B", size=10)
                    pdf.cell(text_w, row_height, exercise.name, border=0, align="L", link=detailed_page_link)
                    pdf.set_font("opensans", style="", size=10)

                    pdf.image(qr_buf, x=qr_x, y=qr_y, w=qr_size, h=qr_size, link=detailed_page_link)

                    sets_x = x_start + exercise_name_column_width
                    pdf.rect(sets_x, row_y, sets_column_width, total_h, style=rect_style)
                    pdf.set_xy(sets_x, row_y + (total_h - row_height) / 2)
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font(style="")
                    pdf.cell(sets_column_width, row_height, str(exercise.sets), border=0, align="C")

                    reps_time_cell_content = ""
                    if exercise.reps:
                        reps_time_cell_content = exercise.reps
                    if exercise.time:
                        if reps_time_cell_content:
                            reps_time_cell_content += " / "
                        reps_time_cell_content += exercise.time
                    reps_x = sets_x + sets_column_width
                    pdf.rect(reps_x, row_y, reps_time_column_width, total_h, style=rect_style)
                    pdf.set_xy(reps_x, row_y + (total_h - row_height) / 2)
                    pdf.cell(reps_time_column_width, row_height, reps_time_cell_content, border=0, align="C")

                    weight_x = reps_x + reps_time_column_width
                    pdf.rect(weight_x, row_y, weight_column_width, total_h, style=rect_style)
                    is_time_based = exercise.time and not exercise.reps
                    is_mobility = ex_data and "mobility" in [c.strip().lower() for c in ex_data["category"].split(",")]
                    if not is_time_based and not is_mobility:
                        pdf.set_font("opensans", "I", 9)
                        pdf.set_text_color(120, 120, 120)
                        for s in range(sets):
                            pdf.set_xy(weight_x + 2, row_y + s * sub_row_h + (sub_row_h - 9) / 2)
                            pdf.cell(weight_column_width - 4, 9, f"set {s + 1}:  _________", border=0, align="L")

                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font("opensans", style="", size=10)
                    pdf.set_y(row_y + total_h)
            pdf.ln(8)
            field_h = 18
            box_padding = 4

            pdf.set_font("opensans", style="I", size=10)
            pdf.set_text_color(100, 100, 100)
            pdf.set_draw_color(186, 148, 94)

            pdf.set_x(x_start)
            pdf.rect(x_start, pdf.get_y(), table_width / 2 - 2, field_h, round_corners=True, corner_radius=3)
            pdf.set_xy(x_start + box_padding, pdf.get_y() + box_padding)
            pdf.cell(0, 0, "Done on:", border=0, align="L")
            executed_y = pdf.get_y() - box_padding

            notes_x = x_start + table_width / 2 + 2
            pdf.rect(notes_x, executed_y, table_width / 2 - 2, field_h, round_corners=True, corner_radius=3)
            pdf.set_xy(notes_x + box_padding, executed_y + box_padding)
            pdf.cell(0, 0, "Notes:", border=0, align="L")

            pdf.set_text_color(0, 0, 0)
            pdf.set_y(executed_y + field_h + 4)

    return pdf


def download_file(*args):
    valid_workouts = len([w for w in workouts if w.exercises])
    if not valid_workouts:
        return

    pdf = create_pdf()
    encoded_data = pdf.output()
    my_stream = io.BytesIO(encoded_data)

    js_array = Uint8Array.new(len(encoded_data))
    js_array.assign(my_stream.getbuffer())

    file = File.new([js_array], "unused_file_name.pdf", {type: "application/pdf"})
    url = URL.createObjectURL(file)

    hidden_link = document.createElement("a")
    hidden_link.setAttribute(
        "download",
        f"workouts_{datetime.datetime.now().strftime('%d%m%Y_%H%M%S')}.pdf",
    )
    hidden_link.setAttribute("href", url)
    hidden_link.click()


w_template = pydom.Element(
    q("#workout-template").content.querySelector("#workout")  # div element
)


def show_info(event):
    info_box = document.createElement("div")
    info_box.style.position = "fixed"
    info_box.style.top = "50%"
    info_box.style.left = "50%"
    info_box.style.width = "80%"
    info_box.style.maxWidth = "600px"
    info_box.style.height = "auto"
    info_box.style.maxHeight = "80%"
    info_box.style.transform = "translate(-50%, -50%)"
    info_box.style.backgroundColor = "rgba(0, 0, 0, 0.9)"
    info_box.style.color = "white"
    info_box.style.padding = "20px"
    info_box.style.borderRadius = "10px"
    info_box.style.boxShadow = "0 4px 8px rgba(0, 0, 0, 0.2)"
    info_box.style.overflowY = "auto"
    info_box.style.zIndex = "1000"

    with open("info.txt", "r") as info_file:
        info_content = info_file.read()
    info_box.innerHTML = info_content

    close_button = document.createElement("button")
    close_button.textContent = "Close"
    close_button.style.marginTop = "20px"
    close_button.style.padding = "10px 20px"
    close_button.classList.add("btn", "btn-outline-gold", "btn-sm")
    close_button.style.cursor = "pointer"
    close_button.onclick = lambda event: info_box.remove()

    info_box.appendChild(close_button)
    document.body.appendChild(info_box)


def open_exercise(event):
    card = event.target.closest("[data-exercise-id]")
    if card:
        window.open(f"detail.html?exercise_id={card.getAttribute('data-exercise-id')}", "_blank")


def stop_propagation(event):
    event.stopPropagation()


def workout_edit(event):
    global active_workout
    active_workout = UUID(event.target.getAttribute("data-workout-id"))

    for w in workouts:
        workout_layover = pydom[f"#workout-layover-{w.id}"][0]
        if w.id == active_workout:
            workout_layover._js.classList.add("d-none")
        else:
            workout_layover._js.classList.remove("d-none")


def render_workouts(workouts: list[Workout]):
    ws_container = pydom["#workout-list-container"][0]
    while ws_container._js.firstChild:
        ws_container._js.removeChild(ws_container._js.firstChild)

    for _, w in enumerate(workouts):
        w_div = w_template.clone()
        w_div._js.removeAttribute("id")

        workout_layover = w_div.find("#workout-layover")[0]
        workout_layover._js.setAttribute("id", f"workout-layover-{w.id}")

        if w.id != active_workout:
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

        w_date = w_div.find("#workout-date")[0]
        w_date._js.value = w.execution_date.strftime("%Y-%m-%d")
        w_date._js.setAttribute("id", f"workout-date-{w.id}")
        w_date._js.setAttribute("data-workout-id", str(w.id))

        def on_date_change(evt):
            new_date = datetime.datetime.strptime(evt.target.value, "%Y-%m-%d").date()
            w_id = UUID(evt.target.getAttribute("data-workout-id"))
            for w in workouts:
                if w.id == w_id:
                    w.execution_date = new_date
                    break
            localStorage.setItem(ls_workouts_key, workouts)

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
        for ei, exercise in enumerate(w.exercises):
            w_li = li if ei == 0 else li.clone()
            w_li._js.removeAttribute("id")
            details = []
            if exercise.reps:
                details.append(f"of {exercise.reps}")
            if exercise.time:
                details.append(f"for {exercise.time}")
            details_str = (
                f" ({exercise.sets} {' '.join(details)})"
                if details
                else f" ({exercise.sets})"
            )
            w_li.find("#workout-item-name")[0]._js.innerHTML = (
                f"{exercise.name} "
                f'<span style="font-size:0.8em; color:#888;">'
                f"{details_str}"
                f"</span>"
            )
            w_item_remove_icon = w_li.find("#workout-item-remove")[0]
            w_item_remove_icon._js.onclick = remove_exercise_from_workout
            w_item_remove_icon._js.setAttribute("data-exercise-id", exercise.id)
            w_item_remove_icon._js.setAttribute(
                "data-workout-exercise-id", exercise.internal_id
            )
            w_item_remove_icon._js.setAttribute("data-workout-id", str(w.id))
            w_ul.append(w_li)

        if not w.exercises:
            w_ul._js.classList.add("d-none")

        ws_container.append(w_div)


def add_exercise_to_workout(event):
    event.stopPropagation()
    exercise_id = event.target.parentElement.parentElement.parentElement.parentElement.getAttribute(
        "data-exercise-id"
    )
    exercise_name = event.target.parentElement.parentElement.parentElement.parentElement.getAttribute(
        "data-exercise-name"
    )
    configure_exercise(exercise_id, exercise_name)


def configure_exercise(exercise_id, exercise_name):
    ex_card = pydom["#ex-" + exercise_id][0]

    overlay = document.createElement("div")
    overlay.classList.add("exercise-overlay")
    overlay.setAttribute("onclick", "event.stopPropagation()")
    overlay.style.position = "absolute"
    overlay.style.top = "0"
    overlay.style.left = "0"
    overlay.style.width = "100%"
    overlay.style.height = "100%"
    overlay.style.backgroundColor = "rgba(0, 0, 0, 0.85)"
    overlay.style.display = "flex"
    overlay.style.flexDirection = "column"
    overlay.style.alignItems = "stretch"
    overlay.style.justifyContent = "center"
    overlay.style.color = "white"
    overlay.style.zIndex = "10"
    overlay.style.padding = "12px 16px"
    overlay.style.gap = "8px"

    inputs_container = document.createElement("div")
    inputs_container.style.display = "flex"
    inputs_container.style.flexDirection = "column"
    inputs_container.style.gap = "8px"
    inputs_container.style.width = "100%"

    def make_group(label_text, input_el):
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
        input_el.style.height = "26px"
        input_el.style.padding = "2px 6px"
        input_el.style.borderRadius = "4px"
        input_el.style.border = "1px solid rgba(255,255,255,0.2)"
        input_el.style.backgroundColor = "rgba(255,255,255,0.1)"
        input_el.style.color = "#fff"

        group.appendChild(label)
        group.appendChild(input_el)
        return group

    input_sets = document.createElement("input")
    input_sets.type = "number"
    input_sets.min = "1"
    input_sets.value = "1"

    input_reps_per_set = document.createElement("input")
    input_reps_per_set.type = "text"
    input_reps_per_set.placeholder = "e.g. 10,12,15"

    input_time_per_set = document.createElement("input")
    input_time_per_set.type = "text"
    input_time_per_set.placeholder = "e.g. 00:01:30"

    inputs_container.appendChild(make_group("Sets", input_sets))
    inputs_container.appendChild(make_group("Reps per set (comma separated, optional)", input_reps_per_set))
    inputs_container.appendChild(make_group("Time per set — hh:mm:ss (optional)", input_time_per_set))

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

    overlay.appendChild(inputs_container)
    overlay.appendChild(buttons_container)

    exercise_card_el = ex_card._js.querySelector(".exercise-card")
    exercise_card_el.style.position = "relative"
    exercise_card_el.appendChild(overlay)

    def on_confirm_click(evt):
        global active_workout
        sets_val = input_sets.value
        reps_val = input_reps_per_set.value
        time_val = input_time_per_set.value

        if not sets_val:
            return

        sets = int(sets_val)

        if reps_val:
            reps = [v for r in reps_val.split(",") if (v := r.strip()) and v.isdigit()]
            if len(reps) != sets:
                return

        if time_val:
            time_parts = time_val.split(":")
            if len(time_parts) != 3 or not all(part.isdigit() for part in time_parts):
                return
            if any(int(part) < 0 for part in time_parts):
                return

        ex = Exercise(
            int(exercise_id), str(uuid4()), exercise_name, sets, reps_val, time_val
        )

        if active_workout is None:
            active_workout = uuid4()
            w = Workout(active_workout, datetime.datetime.now().date(), [ex])
            workouts.append(w)
        else:
            for w in workouts:
                if w.id == active_workout:
                    w.exercises.append(ex)
                    break
        localStorage.setItem(ls_workouts_key, workouts)
        show_sidebar()
        render_workouts(workouts)
        overlay.remove()

    confirm_btn.onclick = on_confirm_click


def remove_exercise_from_workout(event):
    global active_workout
    ex_id = event.target.getAttribute("data-exercise-id")
    workout_ex_id = event.target.getAttribute("data-workout-exercise-id")
    workout_id = event.target.getAttribute("data-workout-id")
    for i, w in enumerate(workouts):
        if str(w.id) == workout_id:
            for j, ex in enumerate(w.exercises):
                if ex.id == int(ex_id) and ex.internal_id == workout_ex_id:
                    del w.exercises[j]
                    break
            break
    localStorage.setItem(ls_workouts_key, workouts)
    event.target.parentElement.remove()
    if not workouts:
        active_workout = None
        hide_sidebar()


def remove_workout(event):
    global active_workout
    workout_id = event.target.getAttribute("data-workout-id")
    for i, w in enumerate(workouts):
        if str(w.id) == workout_id:
            del workouts[i]
            break
    active_workout = None if not workouts else workouts[-1].id
    localStorage.setItem(ls_workouts_key, workouts)
    render_workouts(workouts)
    if not workouts:
        hide_sidebar()


def remove_workouts(event):
    global active_workout
    workouts.clear()
    active_workout = None
    localStorage.removeItem(ls_workouts_key)
    workouts_container = pydom["#workout-list-container"][0]
    while workouts_container._js.firstChild:
        workouts_container._js.removeChild(workouts_container._js.firstChild)
    hide_sidebar()


def add_workout(event):
    global active_workout
    active_workout = uuid4()
    w = Workout(active_workout, datetime.datetime.now().date(), [])
    workouts.append(w)
    localStorage.setItem(ls_workouts_key, workouts)
    render_workouts(workouts)


def create_card_exercise(template, data):
    exercise_html = template.clone()
    exercise_html.id = f"ex-{data['id']}"
    exercise_html._js.setAttribute("data-exercise-name", data["name"])
    exercise_html._js.setAttribute("data-exercise-id", data["id"])

    (
        exercise_html.find("#card-img")[0]
    )._js.src = f"./assets/exercises/{data['thumbnail_url']}"
    (exercise_html.find("#card-img")[0])._js.alt = data["name"]

    (exercise_html.find("#card-title")[0])._js.textContent = data["name"]

    card_el = exercise_html.find(".exercise-card")[0]
    card_el._js.style.cursor = "pointer"
    card_el._js.onclick = open_exercise

    categories = data["category"].split(",")
    body_parts_badge_element = exercise_html.find("#body-parts-badge")[0]
    category_badge_element = exercise_html.find("#category-badge")[0]
    clean_cat_badge = category_badge_element.clone()
    for i, category in enumerate(categories):
        category = category.strip()
        cat_badge = category_badge_element if i == 0 else clean_cat_badge.clone()
        cat_badge._js.textContent = category
        cat_badge._js.classList.add(category_to_badge.get(category.lower()))
        if i > 0:
            body_parts_badge_element._js.before(cat_badge._js)

    body_parts_badges = data["body_parts"].split(",")
    badges_container_element = exercise_html.find("#badges")[0]
    for i, badge in enumerate(body_parts_badges):
        new_badge_element = (
            exercise_html.find("#body-parts-badge")[0].clone()
            if i > 0
            else exercise_html.find("#body-parts-badge")[0]
        )
        new_badge_element._js.textContent = badge
        new_badge_element._js.classList.add("bg-secondary")
        badges_container_element._js.append(new_badge_element._js)

    yt_video_link = f"https://www.youtube.com/embed/{data['yt_video_id']}"
    video_link_el = exercise_html.find("#video-link")[0]
    video_link_el._js.href = yt_video_link

    add_btn_el = exercise_html.find("#add-ex-to-workout")[0]
    add_btn_el._js.onclick = add_exercise_to_workout

    return exercise_html


def build_category_badges(category_count: dict[str, int]) -> str:
    html = ""
    for category, count in category_count.items():
        badge_class = category_to_badge.get(category.lower())
        active_class = " category-filter-active" if category == active_category_filter else ""
        html += f'<span class="badge {badge_class}{active_class} me-1" data-category="{category}" style="cursor: pointer">{category}</span>'
    return html


def update_exercise_stats(display_count: int, total: int) -> None:
    parts = []
    if active_category_filter:
        parts.append(active_category_filter)
    if active_body_part_filter:
        parts.append(active_body_part_filter)
    if parts:
        stats = f"{display_count} · {' & '.join(parts)}"
    else:
        stats = f"{total} exercises"
    pydom["#exercise-stats"][0]._js.textContent = stats


def attach_category_filter_listeners():
    container = document.getElementById("exercises-per-category-badges-row")
    badges = container.querySelectorAll("[data-category]")
    for i in range(badges.length):
        badges.item(i).addEventListener("click", create_proxy(filter_by_category))


def filter_by_category(event):
    global active_category_filter
    category = event.target.getAttribute("data-category")
    active_category_filter = None if active_category_filter == category else category
    search_str = pydom["#search-input"][0]._js.value
    update(search_str)


def build_body_part_badges() -> str:
    html = ""
    for bp in body_parts_list:
        active_class = " body-part-filter-active" if bp == active_body_part_filter else ""
        html += f'<span class="badge bg-secondary{active_class} me-1" data-body-part="{bp}" style="cursor: pointer">{bp}</span>'
    return html


def attach_body_part_filter_listeners():
    container = document.getElementById("exercises-per-body-part-badges-row")
    badges = container.querySelectorAll("[data-body-part]")
    for i in range(badges.length):
        badges.item(i).addEventListener("click", create_proxy(filter_by_body_part))


def filter_by_body_part(event):
    global active_body_part_filter
    bp = event.target.getAttribute("data-body-part")
    active_body_part_filter = None if active_body_part_filter == bp else bp
    search_str = pydom["#search-input"][0]._js.value
    update(search_str)


def update(search_str: str) -> None:
    search_str = search_str.strip().lower()
    search_filtered = [
        exercise for exercise in data if search_str in exercise["name"].lower()
    ]

    display_data = search_filtered
    if active_category_filter:
        display_data = [
            exercise for exercise in display_data
            if active_category_filter in [c.strip() for c in exercise["category"].split(",")]
        ]
    if active_body_part_filter:
        display_data = [
            exercise for exercise in display_data
            if active_body_part_filter in [bp.strip() for bp in exercise["body_parts"].split(",")]
        ]

    exercises_row._js.innerHTML = ""
    empty_state = pydom["#empty-state"][0]
    if display_data:
        empty_state._js.classList.add("d-none")
        for i, exercise_data in enumerate(display_data):
            exercise_html = create_card_exercise(exercise_template, exercise_data)
            exercise_html._js.classList.add("card-animate")
            exercise_html._js.style.animationDelay = f"{min(i * 30, 300)}ms"
            exercises_row.append(exercise_html)
    else:
        empty_state._js.classList.remove("d-none")

    pydom[exercises_per_category_badges_row_id][
        0
    ]._js.innerHTML = build_category_badges(category_count)
    attach_category_filter_listeners()
    pydom[exercises_per_body_part_badges_row_id][
        0
    ]._js.innerHTML = build_body_part_badges()
    attach_body_part_filter_listeners()
    update_exercise_stats(len(display_data), len(search_filtered))


def filter_library(event) -> None:
    search_str = event.target.parentElement.children[0].value
    update(search_str)


def clear_filters(event) -> None:
    global active_category_filter, active_body_part_filter
    active_category_filter = None
    active_body_part_filter = None
    search_str = q("#search-input").value
    update(search_str)


@when("input", "#search-input")
def handle_search_input(event):
    search_str = event.target.value
    update(search_str)


data = csv_to_json("exercises.csv")
data = sorted(data, key=lambda x: x["name"])

category_count: dict[str, int] = {}
body_parts_set: set[str] = set()
body_parts_list: list[str] = []

for i, exercise_data in enumerate(data):
    for category in exercise_data["category"].split(","):
        category = category.strip()
        category_count[category] = category_count.get(category, 0) + 1
    for bp in exercise_data["body_parts"].split(","):
        bp = bp.strip()
        if bp and bp not in body_parts_set:
            body_parts_set.add(bp)
            body_parts_list.append(bp)
    exercise_html = create_card_exercise(exercise_template, exercise_data)
    exercise_html._js.classList.add("card-animate")
    exercise_html._js.style.animationDelay = f"{min(i * 30, 300)}ms"
    exercises_row.append(exercise_html)

body_parts_list.sort()

pydom[exercises_per_category_badges_row_id][0]._js.innerHTML = build_category_badges(
    category_count
)
attach_category_filter_listeners()
pydom[exercises_per_body_part_badges_row_id][0]._js.innerHTML = build_body_part_badges()
attach_body_part_filter_listeners()
update_exercise_stats(len(data), len(data))

pydom["#skeleton-row"][0]._js.classList.add("d-none")
pydom["#filter-row"][0]._js.classList.remove("d-none")

copyright_element = pydom[copyright_el_id][0]
copyright_element._js.innerHTML = copyright()

version_element = pydom[version_el_id][0]
version_element._js.innerHTML = current_version()

pydom[footer_el_id][0]._js.classList.remove("d-none")

add_event_listener(document.getElementById(download_pdf_btn_id), "click", download_file)


def show_sidebar():
    pydom[workout_sidebar_el_id][0]._js.classList.remove("d-none")
    pydom["#toggle-workout-sidebar"][0]._js.innerHTML = '<i class="bi bi-x-lg"></i>'
    pydom["#toggle-workout-sidebar"][0]._js.title = "Hide Workouts"


def hide_sidebar():
    pydom[workout_sidebar_el_id][0]._js.classList.add("d-none")
    pydom["#toggle-workout-sidebar"][0]._js.innerHTML = '<i class="bi bi-list"></i>'
    pydom["#toggle-workout-sidebar"][0]._js.title = "Show Workouts"


if workouts:
    show_sidebar()
    render_workouts(workouts)
else:
    hide_sidebar()
