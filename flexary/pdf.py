import datetime
import io
import math

import qrcode
from fpdf import FPDF
from js import Uint8Array, File, URL, document, localStorage

import state
from models import category_to_rgb
from models import Exercise, Workout  # noqa: F401 — required in eval() scope
import datetime  # noqa: F401 — required in eval() scope
from uuid import UUID  # noqa: F401 — required in eval() scope


def create_pdf(black_and_white: bool = False):
    gold = (80, 80, 80) if black_and_white else (186, 148, 94)
    header_fill = (220, 220, 220) if black_and_white else (240, 228, 208)
    cat_colors = {
        "strength": (60, 60, 60),
        "conditioning": (120, 120, 120),
        "mobility": (170, 170, 170),
    } if black_and_white else category_to_rgb

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
    sets_column_width = 15
    reps_time_column_width = 40
    weight_column_width = 35

    raw = localStorage.getItem(state.ls_workouts_key)
    if not raw:
        return pdf
    workouts = eval(raw)

    for workout in workouts:
        exercises = workout.exercises
        if not exercises:
            continue

        chunk_size = 15
        workout_total_pages = math.ceil(len(exercises) / chunk_size)
        for i in range(0, len(exercises), chunk_size):
            chunk = exercises[i: i + chunk_size]
            is_last_chunk = (i + chunk_size >= len(exercises))
            pdf.add_page()
            pdf.workout_page_num = i // chunk_size + 1
            pdf.workout_total_pages = workout_total_pages

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

            def render_table_header():
                pdf.set_fill_color(*header_fill)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("opensans", style="B", size=10)
                pdf.set_draw_color(*gold)
                pdf.set_x(x_start)
                pdf.cell(exercise_name_column_width, row_height, "Exercise", border=1, fill=True, align="C")
                pdf.cell(sets_column_width, row_height, "Sets", border=1, fill=True, align="C")
                pdf.cell(reps_time_column_width, row_height, "Reps/Time/Dist", border=1, fill=True, align="C")
                pdf.cell(weight_column_width, row_height, "Weight", border=1, fill=True, align="C")
                pdf.ln()
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("opensans", style="", size=10)
                pdf.set_draw_color(*gold)

            render_table_header()

            for row_num, exercise in enumerate(chunk):
                pdf.set_x(x_start)
                row_fill = row_num % 2 == 1
                detailed_page_link = next(
                    (
                        f"https://vladflore.fit/flexary/detail.html?exercise_id={exercise.id}"
                        for d in state.data
                        if int(d["id"]) == exercise.id
                    ),
                    "",
                )
                try:
                    sets = int(exercise.sets)
                except Exception:
                    sets = 1

                sub_row_h = 7
                ex_data = next((d for d in state.data if int(d["id"]) == exercise.id), None)
                categories = [c.strip() for c in ex_data["category"].split(",")] if ex_data else []

                badge_h = 4
                badge_pad_v = 1.5
                badge_area_h = badge_h + badge_pad_v * 2
                notes_line_h = 4
                if exercise.notes:
                    # Pre-calculate available text width (mirrors values computed later)
                    _tri_size = 2.2
                    _text_w = exercise_name_column_width - 12 - 2 - 3 - _tri_size * 1.6 - 2 - 2
                    pdf.set_font("opensans", style="I", size=7)
                    _lines, _line_w = 1, 0
                    for _word in exercise.notes.split():
                        _word_w = pdf.get_string_width(_word + " ")
                        if _line_w + _word_w > _text_w:
                            _lines += 1
                            _line_w = _word_w
                        else:
                            _line_w += _word_w
                    notes_h = _lines * notes_line_h + 1
                    pdf.set_font("opensans", style="", size=10)
                else:
                    notes_h = 0
                min_cell_h = badge_area_h + row_height + notes_h + 1
                total_h = max(min_cell_h, sets * sub_row_h)

                if pdf.get_y() + total_h > pdf.h - 25:
                    workout_total_pages += 1
                    pdf.workout_total_pages = workout_total_pages
                    next_page_num = pdf.workout_page_num + 1
                    pdf.add_page()
                    pdf.workout_page_num = next_page_num
                    render_table_header()

                row_y = pdf.get_y()
                rect_style = "FD" if row_fill else "D"
                if row_fill:
                    pdf.set_fill_color(245, 245, 245)

                pdf.rect(x_start, row_y, exercise_name_column_width, total_h, style=rect_style)

                pdf.set_font("opensans", style="B", size=6)
                badge_x = x_start + 3
                badge_y = row_y + badge_pad_v
                for cat in categories:
                    bg = cat_colors.get(cat.lower(), gold)
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
                pdf.set_fill_color(*gold)
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

                if exercise.notes:
                    pdf.set_font("opensans", style="I", size=7)
                    pdf.set_text_color(100, 100, 100)
                    pdf.set_xy(text_x, name_y + row_height)
                    pdf.multi_cell(text_w, notes_line_h, exercise.notes, border=0, align="L")
                    pdf.set_text_color(0, 0, 0)
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
                if exercise.distance:
                    if reps_time_cell_content:
                        reps_time_cell_content += " / "
                    reps_time_cell_content += exercise.distance
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
                    v_offset = (total_h - sets * sub_row_h) / 2
                    for s in range(sets):
                        pdf.set_xy(weight_x, row_y + v_offset + s * sub_row_h + (sub_row_h - 9) / 2)
                        pdf.cell(weight_column_width, 9, f"set {s + 1}:  _________", border=0, align="C")

                pdf.set_text_color(0, 0, 0)
                pdf.set_font("opensans", style="", size=10)
                pdf.set_y(row_y + total_h)

            if is_last_chunk:
                field_h = 18
                box_padding = 4
                needed_h = 8 + field_h + 4

                if pdf.get_y() + needed_h > pdf.h - pdf.b_margin:
                    workout_total_pages += 1
                    pdf.workout_total_pages = workout_total_pages
                    next_page_num = pdf.workout_page_num + 1
                    pdf.add_page()
                    pdf.workout_page_num = next_page_num

                pdf.ln(8)
                pdf.set_font("opensans", style="I", size=10)
                pdf.set_text_color(100, 100, 100)
                pdf.set_draw_color(*gold)

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


def _perform_download(black_and_white: bool = False) -> None:
    pdf = create_pdf(black_and_white=black_and_white)
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


def download_file(*args) -> None:
    if not any(w.exercises for w in state.workouts):
        return
    document.getElementById(state.pdf_color_modal_id).showModal()


def make_pdf_download_handler(black_and_white: bool):
    def handler(*args):
        document.getElementById(state.pdf_color_modal_id).close()
        _perform_download(black_and_white=black_and_white)
    return handler
