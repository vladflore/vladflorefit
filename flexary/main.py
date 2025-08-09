import datetime
import io
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


# Identifiers
exercises_row_id = "#exercises-row"
exercise_card_template_id = "#exercise-card-template"
copyright_el_id = "#copyright"
version_el_id = "#version"
footer_el_id = "#footer"
workout_sidebar_el_id = "#workout-sidebar"
exercise_count_id = "#exercise-count"
exercises_per_category_badges_row_id = "#exercises-per-category-badges-row"

download_pdf_btn_id = "download-workouts"

# DOM elements
exercises_row = pydom[exercises_row_id][0]
exercise_template = pydom.Element(
    q(exercise_card_template_id).content.querySelector("#card-exercise")
)


def create_pdf():
    class PDF(FPDF):
        def header(self):
            self.set_font("times", "B", 16)
            self.cell(0, 10, "Your Workouts", new_x="LMARGIN", new_y="NEXT", align="C")
            self.ln(5)

        def footer(self):
            self.set_y(-20)
            self.set_font("times", "I", 10)
            self.set_draw_color(180, 180, 180)
            self.set_line_width(0.3)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.ln(2)
            self.cell(0, 10, f"Page {self.page_no()}", align="C")

        def add_watermark(self, image_path):
            x, y = self.get_x(), self.get_y()
            page_w = self.w
            page_h = self.h

            with Image.open(image_path) as img:
                img_w, img_h = img.size

            scale = min(page_w / img_w, page_h / img_h)
            new_w = img_w * scale
            new_h = img_h * scale

            x_img = (page_w - new_w) / 2
            y_img = (page_h - new_h) / 2

            self.image(image_path, x=x_img, y=y_img, w=new_w, h=new_h)
            self.set_xy(x, y)

    pdf = PDF()
    pdf.set_font("times", style="", size=13)

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
            for i in range(0, len(exercises), chunk_size):
                chunk = exercises[i : i + chunk_size]
                pdf.add_page()
                pdf.add_watermark("logo-for-pdf.png")

                table_width = (
                    exercise_name_column_width
                    + sets_column_width
                    + reps_time_column_width
                    + weight_column_width
                )
                page_width = pdf.w - 2 * pdf.l_margin
                x_start = (page_width - table_width) / 2 + pdf.l_margin

                pdf.set_x(x_start)
                formatted_date = workout.execution_date.strftime("%d.%m.%Y")

                pdf.set_font("times", style="I", size=12)

                pdf.cell(
                    table_width,
                    10,
                    f"Workout {idx} of {total_workouts} for {formatted_date}",
                    new_x="LMARGIN",
                    new_y="NEXT",
                    align="L",
                )

                pdf.set_font("times", style="", size=13)

                pdf.set_x(x_start)
                row_height = 12

                pdf.set_fill_color(220, 220, 220)
                pdf.cell(
                    exercise_name_column_width,
                    row_height,
                    "Exercise",
                    border=1,
                    fill=True,
                    align="C",
                )
                pdf.cell(
                    sets_column_width,
                    row_height,
                    "Sets",
                    border=1,
                    fill=True,
                    align="C",
                )
                pdf.cell(
                    reps_time_column_width,
                    row_height,
                    "Reps / Time",
                    border=1,
                    fill=True,
                    align="C",
                )
                pdf.cell(
                    weight_column_width,
                    row_height,
                    "Weight",
                    border=1,
                    fill=True,
                    align="C",
                )
                pdf.ln()
                for exercise in chunk:
                    pdf.set_x(x_start)
                    detailed_page_link = next(
                        (
                            f"https://vladflore.fit/detail.html?exercise_id={exercise.id}"
                            for d in data
                            if int(d["id"]) == exercise.id
                        ),
                        "",
                    )
                    pdf.set_text_color(0, 0, 255)
                    pdf.set_font(style="U")
                    pdf.cell(
                        exercise_name_column_width,
                        row_height,
                        exercise.name,
                        border=1,
                        align="L",
                        link=detailed_page_link,
                    )
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font(style="")
                    pdf.cell(
                        sets_column_width,
                        row_height,
                        str(exercise.sets),
                        border=1,
                        align="C",
                    )

                    # Reps / Time
                    reps_time_cell_content = ""
                    if exercise.reps:
                        reps_time_cell_content = exercise.reps
                    if exercise.time:
                        if reps_time_cell_content:
                            reps_time_cell_content += " / "
                        reps_time_cell_content += exercise.time
                    pdf.cell(
                        reps_time_column_width,
                        row_height,
                        reps_time_cell_content,
                        border=1,
                        align="C",
                    )

                    try:
                        sets = int(exercise.sets)
                    except Exception:
                        sets = 1
                    placeholders = "|".join([" ___ "] * sets)
                    pdf.cell(
                        weight_column_width,
                        row_height,
                        placeholders,
                        border=1,
                        align="C",
                    )
                    pdf.ln(row_height)
            pdf.ln(10)
            pdf.set_font("times", style="I", size=12)
            pdf.set_x(x_start)
            pdf.cell(
                table_width,
                10,
                "Executed on:",
                align="L",
            )
            pdf.ln(8)
            pdf.set_x(x_start)
            pdf.cell(table_width, 10, "Notes:", align="L")

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
    exercise_id = event.target.parentElement.parentElement.parentElement.getAttribute(
        "data-exercise-id"
    )
    window.open(f"detail.html?exercise_id={exercise_id}", "_blank")


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
    overlay.style.position = "absolute"
    overlay.style.top = "0"
    overlay.style.left = "0"
    overlay.style.width = "100%"
    overlay.style.height = "100%"
    overlay.style.backgroundColor = "rgba(0, 0, 0, 0.8)"
    overlay.style.display = "flex"
    overlay.style.flexDirection = "column"
    overlay.style.alignItems = "center"
    overlay.style.justifyContent = "space-between"
    overlay.style.color = "white"
    overlay.style.fontSize = "1.2rem"
    overlay.style.zIndex = "10"
    overlay.style.gap = "0"
    overlay.style.padding = "16px 0 24px 0"

    inputs_container = document.createElement("div")
    inputs_container.style.display = "flex"
    inputs_container.style.flexDirection = "column"
    inputs_container.style.alignItems = "flex-start"
    inputs_container.style.width = "100%"
    inputs_container.style.marginTop = "0"

    left_indent = "24px"

    # Sets
    input_sets = document.createElement("input")
    input_sets.type = "number"
    input_sets.min = "1"
    input_sets.value = "1"
    input_sets.style.marginLeft = left_indent
    input_sets.style.width = "48px"
    input_sets.style.marginTop = "2px"
    input_sets.style.fontSize = "0.85rem"
    input_sets.style.display = "block"
    input_sets.style.height = "24px"
    input_sets.style.padding = "2px 6px"

    label_sets = document.createElement("label")
    label_sets.textContent = "Sets:"
    label_sets.style.marginLeft = left_indent
    label_sets.style.fontSize = "0.85rem"
    label_sets.style.fontWeight = "400"
    label_sets.style.color = "#fff"
    label_sets.style.letterSpacing = "0.01em"

    sets_group = document.createElement("div")
    sets_group.style.display = "flex"
    sets_group.style.flexDirection = "column"
    sets_group.style.marginBottom = "16px"
    sets_group.appendChild(label_sets)
    sets_group.appendChild(input_sets)

    # Reps per set
    label_reps_per_set = document.createElement("label")
    label_reps_per_set.textContent = (
        "Reps per set (comma separated, leave empty if not needed):"
    )
    label_reps_per_set.style.marginLeft = left_indent
    label_reps_per_set.style.fontSize = "0.85rem"
    label_reps_per_set.style.fontWeight = "400"
    label_reps_per_set.style.color = "#fff"
    label_reps_per_set.style.letterSpacing = "0.01em"

    input_reps_per_set = document.createElement("input")
    input_reps_per_set.type = "text"
    input_reps_per_set.placeholder = "e.g. 10,12,15"
    input_reps_per_set.style.marginLeft = left_indent
    input_reps_per_set.style.width = "96px"
    input_reps_per_set.style.marginTop = "2px"
    input_reps_per_set.style.fontSize = "0.85rem"
    input_reps_per_set.style.display = "block"
    input_reps_per_set.style.height = "24px"
    input_reps_per_set.style.padding = "2px 6px"

    reps_group = document.createElement("div")
    reps_group.style.display = "flex"
    reps_group.style.flexDirection = "column"
    reps_group.style.marginBottom = "16px"
    reps_group.appendChild(label_reps_per_set)
    reps_group.appendChild(input_reps_per_set)

    # Time per set
    label_time_per_set = document.createElement("label")
    label_time_per_set.textContent = (
        "Time per set (hh:mm:ss, leave empty if not needed):"
    )
    label_time_per_set.style.marginLeft = left_indent
    label_time_per_set.style.fontSize = "0.85rem"
    label_time_per_set.style.fontWeight = "400"
    label_time_per_set.style.color = "#fff"
    label_time_per_set.style.letterSpacing = "0.01em"

    input_time_per_set = document.createElement("input")
    input_time_per_set.type = "text"
    input_time_per_set.placeholder = "e.g. 00:01:30"
    input_time_per_set.style.marginLeft = left_indent
    input_time_per_set.style.width = "100px"
    input_time_per_set.style.marginTop = "2px"
    input_time_per_set.style.fontSize = "0.85rem"
    input_time_per_set.style.display = "block"
    input_time_per_set.style.height = "24px"
    input_time_per_set.style.padding = "2px 6px"

    time_group = document.createElement("div")
    time_group.style.display = "flex"
    time_group.style.flexDirection = "column"
    time_group.appendChild(label_time_per_set)
    time_group.appendChild(input_time_per_set)

    inputs_container.appendChild(sets_group)
    inputs_container.appendChild(reps_group)
    inputs_container.appendChild(time_group)

    buttons_container = document.createElement("div")
    buttons_container.style.display = "flex"
    buttons_container.style.flexDirection = "row"
    buttons_container.style.justifyContent = "center"
    buttons_container.style.alignItems = "center"
    buttons_container.style.gap = "10px"
    buttons_container.style.width = "100%"
    buttons_container.style.marginBottom = "0"

    confirm_btn = document.createElement("button")
    confirm_btn.textContent = "Add to Workout"
    confirm_btn.classList.add("btn", "btn-outline-gold", "btn-sm")
    confirm_btn.style.padding = "4px 10px"
    confirm_btn.style.fontSize = "0.85rem"
    confirm_btn.style.borderRadius = "4px"

    close_btn = document.createElement("button")
    close_btn.textContent = "Cancel"
    close_btn.classList.add("btn", "btn-outline-secondary", "btn-sm")
    close_btn.style.padding = "4px 10px"
    close_btn.style.fontSize = "0.85rem"
    close_btn.style.borderRadius = "4px"
    close_btn.onclick = lambda evt: overlay.remove()

    buttons_container.appendChild(confirm_btn)
    buttons_container.appendChild(close_btn)

    overlay.appendChild(inputs_container)
    overlay.appendChild(document.createElement("div"))
    overlay.appendChild(buttons_container)

    ex_card._js.style.position = "relative"
    ex_card._js.appendChild(overlay)

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
    # TODO revisit this when there are multiple workouts
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
            # if len(w.exercises) == 0:
            #     del workouts[i]
            break
    localStorage.setItem(ls_workouts_key, workouts)
    event.target.parentElement.remove()
    if not workouts:
        active_workout = None
        hide_sidebar()


def remove_workout(event):
    # TODO revisit this when there are multiple workouts
    global active_workout
    workout_id = event.target.getAttribute("data-workout-id")
    for i, w in enumerate(workouts):
        if str(w.id) == workout_id:
            del workouts[i]
            break
    # last workout becomes active
    active_workout = None if not workouts else workouts[-1].id
    localStorage.setItem(ls_workouts_key, workouts)
    render_workouts(workouts)
    if not workouts:
        hide_sidebar()


def remove_workouts(event):
    # TODO revisit this when there are multiple workouts
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
    (exercise_html.find("#card-title")[0])._js.onclick = open_exercise

    category_badge_element = exercise_html.find("#category-badge")[0]
    category_badge_element._js.textContent = data["category"]
    category_badge_element._js.classList.add(
        category_to_badge.get(data["category"].lower())
    )

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
    (exercise_html.find("#video-link")[0])._js.href = yt_video_link

    (exercise_html.find("#add-ex-to-workout")[0])._js.onclick = add_exercise_to_workout

    return exercise_html


def build_category_badges(category_count: dict[str, int]) -> str:
    html = ""
    for category, count in category_count.items():
        badge_class = category_to_badge.get(category.lower())
        html += f"""
                <div class="d-flex align-items-center">
                  <span class="badge {badge_class} me-2">{category}</span>
                  <span class="golden-text">{count}</span>
                </div>
        """
    return html


def update(search_str: str) -> None:
    # >>> empty_string = ""
    # >>> target_string = "Hello"
    # >>> empty_string in target_string
    # True
    search_str = search_str.strip().lower()
    filtered_data = [
        exercise for exercise in data if search_str in exercise["name"].lower()
    ]
    exercises_row._js.innerHTML = ""
    filtered_category_count: dict[str, int] = {}
    for exercise_data in filtered_data:
        category = exercise_data["category"]
        filtered_category_count[category] = filtered_category_count.get(category, 0) + 1
        exercise_html = create_card_exercise(exercise_template, exercise_data)
        exercises_row.append(exercise_html)

    pydom[exercise_count_id][0]._js.innerHTML = f"Total exercises: {len(filtered_data)}"
    pydom[exercises_per_category_badges_row_id][
        0
    ]._js.innerHTML = build_category_badges(filtered_category_count)


def filter_library(event) -> None:
    search_str = event.target.parentElement.children[0].value
    update(search_str)


@when("input", "#search-input")
def handle_search_input(event):
    search_str = event.target.value
    update(search_str)


data = csv_to_json("exercises.csv")
data = sorted(data, key=lambda x: x["name"])

category_count: dict[str, int] = {}
for exercise_data in data:
    category = exercise_data["category"]
    category_count[category] = category_count.get(category, 0) + 1
    exercise_html = create_card_exercise(exercise_template, exercise_data)
    exercises_row.append(exercise_html)

pydom[exercise_count_id][0]._js.innerHTML = f"Total exercises: {len(data)}"
pydom[exercises_per_category_badges_row_id][0]._js.innerHTML = build_category_badges(
    category_count
)

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
