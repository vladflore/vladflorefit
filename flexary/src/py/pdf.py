import asyncio
import datetime
import io
import importlib
import math
from pathlib import Path

import catalog
from js import Uint8Array, File, URL, document, localStorage
from pyodide_js import loadPackage
from pyodide.http import pyfetch

import state
from models import category_to_rgb, workouts_from_json, _reps_display, _time_display, _dist_display

_PDF_ASSET_DIR = Path(".pdf-assets")
_PDF_FONT_SOURCES = {
    "OpenSans-Regular.ttf": "./assets/fonts/OpenSans-Regular.ttf",
    "OpenSans-Bold.ttf": "./assets/fonts/OpenSans-Bold.ttf",
    "OpenSans-Italic.ttf": "./assets/fonts/OpenSans-Italic.ttf",
    "OpenSans-BoldItalic.ttf": "./assets/fonts/OpenSans-BoldItalic.ttf",
}
_PDF_IMAGE_SOURCES = {
    "logo-nobg.png": "./assets/logo-nobg.png",
}
_PDF_PACKAGES = ["fpdf2==2.8.3", "pillow==10.0.0", "qrcode==7.4.2"]
_pdf_runtime_ready = False
_pdf_runtime_loading = None
FPDF = None
qrcode = None

async def _ensure_pdf_runtime() -> None:
    global _pdf_runtime_ready
    global _pdf_runtime_loading
    global FPDF
    global qrcode

    if _pdf_runtime_ready:
        return

    if _pdf_runtime_loading is None:
        async def _load() -> None:
            await loadPackage("micropip")
            micropip = importlib.import_module("micropip")
            await micropip.install(_PDF_PACKAGES)

            from fpdf import FPDF as _FPDF
            import qrcode as _qrcode

            FPDF = _FPDF
            qrcode = _qrcode
            globals()["FPDF"] = FPDF
            globals()["qrcode"] = qrcode

        _pdf_runtime_loading = asyncio.ensure_future(_load())

    await _pdf_runtime_loading
    _pdf_runtime_ready = True

async def _ensure_pdf_assets() -> None:
    _PDF_ASSET_DIR.mkdir(exist_ok=True)

    for filename, source in {**_PDF_FONT_SOURCES, **_PDF_IMAGE_SOURCES}.items():
        target = _PDF_ASSET_DIR / filename
        if target.exists():
            continue
        response = await pyfetch(source)
        data = await response.bytes()
        target.write_bytes(data)

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
            self.image(str(_PDF_ASSET_DIR / "logo-nobg.png"), x=self.w - self.r_margin - logo_size, y=3, w=logo_size, h=logo_size)
            self.ln(logo_size - 4)

        def footer(self):
            self.set_y(-20)
            self.set_font("opensans", "I", 10)
            self.set_draw_color(180, 180, 180)
            self.set_line_width(0.3)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.ln(2)
            self.set_text_color(120, 120, 120)
            self.cell(0, 10, "vladflore.fit", align="C")
            self.set_text_color(0, 0, 0)
            self.set_y(self.get_y() - 10)
            page_label = f"Page {getattr(self, 'workout_page_num', 1)} of {getattr(self, 'workout_total_pages', 1)}"
            self.cell(0, 10, page_label, align="R")

    pdf = PDF()
    pdf.set_top_margin(5)
    pdf.add_font("opensans", style="", fname=str(_PDF_ASSET_DIR / "OpenSans-Regular.ttf"))
    pdf.add_font("opensans", style="B", fname=str(_PDF_ASSET_DIR / "OpenSans-Bold.ttf"))
    pdf.add_font("opensans", style="I", fname=str(_PDF_ASSET_DIR / "OpenSans-Italic.ttf"))
    pdf.add_font("opensans", style="BI", fname=str(_PDF_ASSET_DIR / "OpenSans-BoldItalic.ttf"))
    pdf.set_font("opensans", style="", size=10)

    exercise_name_column_width = 80
    sets_column_width = 15
    reps_time_column_width = 40
    obs_column_width = 50

    raw = localStorage.getItem(state.ls_workouts_key)
    if not raw:
        return pdf
    workouts = workouts_from_json(raw)

    ss_palette = [
        (80, 80, 80),
        (130, 130, 130),
        (50, 50, 50),
        (160, 160, 160),
        (100, 100, 100),
        (40, 40, 40),
        (145, 145, 145),
        (115, 115, 115),
    ] if black_and_white else [
        (186, 148, 94),
        (70, 130, 180),
        (80, 170, 100),
        (160, 90, 200),
        (210, 110, 40),
        (30, 170, 170),
        (200, 75, 75),
        (190, 80, 145),
    ]

    for workout in workouts:
        exercises = workout.exercises
        if not exercises:
            continue

        ss_color_map: dict = {}

        def _ss_color(sid):
            if sid not in ss_color_map:
                ss_color_map[sid] = ss_palette[len(ss_color_map) % len(ss_palette)]
            return ss_color_map[sid]

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
                + obs_column_width
            )
            page_width = pdf.w - 2 * pdf.l_margin
            x_start = (page_width - table_width) / 2 + pdf.l_margin

            pdf.ln(2)
            formatted_date = workout.execution_date.strftime("%d.%m.%Y")

            if workout.name:
                pdf.set_font("opensans", style="B", size=13)
                pdf.set_text_color(*gold)
                pdf.set_x(x_start)
                pdf.cell(0, 9, workout.name, new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(0, 0, 0)
                pdf.ln(1)

            pdf.set_font("opensans", style="I", size=10)
            exercise_count = len(exercises)
            ex_label = "exercise" if exercise_count == 1 else "exercises"
            prefix = "Scheduled for: "
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
                pdf.cell(obs_column_width, row_height, "Observations", border=1, fill=True, align="C")
                pdf.ln()
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("opensans", style="", size=10)
                pdf.set_draw_color(*gold)

            render_table_header()

            line_x = x_start - 4
            line_w = 2.5
            ss_open = {}

            def _close_ss_line(sid):
                st = ss_open.pop(sid, None)
                if st is None:
                    return
                y_top = st["y_top"]
                y_bot = st["y_bottom"]
                mid_y = (y_top + y_bot) / 2
                rounds = workout.superset_rounds.get(sid, 1)
                label = str(rounds)
                color = _ss_color(sid)
                pdf.set_draw_color(*color)
                pdf.set_line_width(line_w)
                pdf.line(line_x, y_top, line_x, y_bot)
                pdf.set_line_width(0.2)
                pdf.set_font("opensans", "B", 7)
                pdf.set_text_color(255, 255, 255)
                lw, lh = line_w + 1, 5
                pdf.set_xy(line_x - lw / 2, mid_y - lh / 2)
                pdf.cell(lw, lh, label, border=0, align="C")
                pdf.set_text_color(0, 0, 0)
                pdf.set_draw_color(*gold)
                pdf.set_line_width(0.2)

            for row_num, exercise in enumerate(chunk):
                break_mins = workout.breaks.get(exercise.internal_id, 0)
                prev_ex = chunk[row_num - 1] if row_num > 0 else None
                inside_superset = (
                    exercise.superset_id
                    and prev_ex is not None
                    and prev_ex.superset_id == exercise.superset_id
                )
                if break_mins and not inside_superset:
                    break_h = 6
                    if pdf.get_y() + break_h > pdf.h - 25:
                        for _sid in list(ss_open.keys()):
                            _close_ss_line(_sid)
                        workout_total_pages += 1
                        pdf.workout_total_pages = workout_total_pages
                        next_page_num = pdf.workout_page_num + 1
                        pdf.add_page()
                        pdf.workout_page_num = next_page_num
                        render_table_header()
                    pdf.set_x(x_start)
                    pdf.set_font("opensans", style="I", size=7)
                    pdf.set_text_color(120, 120, 120)
                    pdf.set_draw_color(*gold)
                    pdf.rect(x_start, pdf.get_y(), table_width, break_h, style="D")
                    pdf.set_xy(x_start, pdf.get_y())
                    _m, _s = divmod(break_mins, 60)
                    _fmt = (f"{_m}m {_s}s" if _s else f"{_m}m") if _m else f"{_s}s"
                    label = f"rest  {_fmt}"
                    pdf.cell(table_width, break_h, label, border=0, align="C")
                    pdf.set_y(pdf.get_y() + break_h)
                    pdf.set_font("opensans", style="", size=10)
                    pdf.set_text_color(0, 0, 0)

                pdf.set_x(x_start)
                row_fill = row_num % 2 == 1
                is_custom_ex = exercise.id < 0
                ex_data = catalog.get_exercise(exercise.id)
                if is_custom_ex:
                    _yt_id = ex_data.get("yt_video_id", "") if ex_data else ""
                    detailed_page_link = f"https://www.youtube.com/watch?v={_yt_id}" if _yt_id else ""
                else:
                    detailed_page_link = (
                        f"https://vladflore.fit/flexary/detail.html?exercise_id={exercise.id}"
                        if ex_data else ""
                    )
                try:
                    sets = int(exercise.sets)
                except Exception:
                    sets = 1
                row_count = workout.superset_rounds.get(exercise.superset_id, 1) if exercise.superset_id else sets

                sub_row_h = 7
                categories = [c.strip() for c in ex_data["category"].split(",")] if ex_data else []

                badge_h = 4
                badge_pad_v = 1.5
                badge_area_h = badge_h + badge_pad_v * 2
                notes_line_h = 4
                if exercise.notes:
                    _tri_size = 2.2
                    _qr_reserved = (12 + 2) if detailed_page_link else 0
                    _text_w = exercise_name_column_width - _qr_reserved - 3 - _tri_size * 1.6 - 2 - 2
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
                is_time_based = exercise.time and not exercise.reps
                is_mobility = ex_data and "mobility" in [c.strip().lower() for c in ex_data["category"].split(",")]
                has_rest = bool(exercise.rest_between_sets) and not exercise.superset_id
                if has_rest:
                    _m_r, _s_r = divmod(exercise.rest_between_sets, 60)
                    _fmt_r = (f"{_m_r}m {_s_r}s" if _s_r else f"{_m_r}m") if _m_r else f"{_s_r}s"
                    rest_label = f"{_fmt_r} rest between sets"
                    _rest_line_h = 3.5
                    pdf.set_font("opensans", "I", 5.5)
                    _rl_count, _rl_w = 1, 0
                    for _rw in rest_label.split():
                        _rww = pdf.get_string_width(_rw + " ")
                        if _rl_w + _rww > sets_column_width - 1:
                            _rl_count += 1
                            _rl_w = _rww
                        else:
                            _rl_w += _rww
                    rest_row_h = _rl_count * _rest_line_h + 1
                    pdf.set_font("opensans", style="", size=10)
                else:
                    rest_label = ""
                    rest_row_h = 0
                sets_content_h = row_height + rest_row_h
                min_cell_h = badge_area_h + max(row_height + notes_h, sets_content_h) + 1
                total_h = max(min_cell_h, row_count * sub_row_h)

                if pdf.get_y() + total_h > pdf.h - 25:
                    for _sid in list(ss_open.keys()):
                        _close_ss_line(_sid)
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
                if detailed_page_link:
                    pdf.set_fill_color(*gold)
                    pdf.polygon([
                        (icon_x, icon_y_center - tri_size),
                        (icon_x, icon_y_center + tri_size),
                        (icon_x + tri_size * 1.6, icon_y_center),
                    ], style="F")
                    if row_fill:
                        pdf.set_fill_color(245, 245, 245)
                    text_x = icon_x + tri_size * 1.6 + 2
                else:
                    text_x = icon_x

                qr_size = 12
                if detailed_page_link:
                    qr_x = x_start + exercise_name_column_width - qr_size - 2
                    qr_y = row_y + (total_h - qr_size) / 2
                    qr = qrcode.QRCode(version=1, box_size=3, border=1, error_correction=qrcode.constants.ERROR_CORRECT_L)
                    qr.add_data(detailed_page_link)
                    qr.make(fit=True)
                    qr_img = qr.make_image(fill_color="black", back_color="white")
                    qr_buf = io.BytesIO()
                    qr_img.save(qr_buf, format="PNG")
                    qr_buf.seek(0)
                    text_w = qr_x - text_x - 2
                else:
                    text_w = x_start + exercise_name_column_width - 2 - text_x

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

                if detailed_page_link:
                    pdf.image(qr_buf, x=qr_x, y=qr_y, w=qr_size, h=qr_size, link=detailed_page_link)

                sets_x = x_start + exercise_name_column_width
                pdf.rect(sets_x, row_y, sets_column_width, total_h, style=rect_style)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font(style="")
                sets_label = "—" if exercise.superset_id else str(exercise.sets)
                if has_rest:
                    y_sets_block = row_y + (total_h - sets_content_h) / 2
                    pdf.set_xy(sets_x, y_sets_block)
                    pdf.cell(sets_column_width, row_height, sets_label, border=0, align="C")
                    pdf.set_font("opensans", "I", 5.5)
                    pdf.set_text_color(150, 150, 150)
                    pdf.set_xy(sets_x, y_sets_block + row_height)
                    pdf.multi_cell(sets_column_width, _rest_line_h, rest_label, border=0, align="C")
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font("opensans", style="", size=10)
                else:
                    pdf.set_xy(sets_x, row_y + (total_h - row_height) / 2)
                    pdf.cell(sets_column_width, row_height, sets_label, border=0, align="C")

                reps_time_cell_content = ""
                if exercise.reps:
                    reps_time_cell_content = _reps_display(exercise.reps, sets)
                if exercise.time:
                    if reps_time_cell_content:
                        reps_time_cell_content += " / "
                    reps_time_cell_content += _time_display(exercise.time, sets)
                if exercise.distance:
                    if reps_time_cell_content:
                        reps_time_cell_content += " / "
                    reps_time_cell_content += _dist_display(exercise.distance, sets)
                reps_x = sets_x + sets_column_width
                pdf.rect(reps_x, row_y, reps_time_column_width, total_h, style=rect_style)
                pdf.set_xy(reps_x, row_y + (total_h - row_height) / 2)
                pdf.cell(reps_time_column_width, row_height, reps_time_cell_content, border=0, align="C")

                obs_x = reps_x + reps_time_column_width
                pdf.rect(obs_x, row_y, obs_column_width, total_h, style=rect_style)

                pdf.set_text_color(0, 0, 0)
                pdf.set_font("opensans", style="", size=10)
                y_bottom = row_y + total_h
                pdf.set_y(y_bottom)

                if exercise.superset_id:
                    sid = exercise.superset_id
                    if sid not in ss_open:
                        ss_open[sid] = {"y_top": row_y, "y_bottom": y_bottom}
                    else:
                        ss_open[sid]["y_bottom"] = y_bottom
                    next_ex = chunk[row_num + 1] if row_num + 1 < len(chunk) else None
                    if next_ex is None or next_ex.superset_id != sid:
                        _close_ss_line(sid)
                pdf.set_y(y_bottom)

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
                pdf.cell(0, 0, "Executed on:", border=0, align="L")
                executed_y = pdf.get_y() - box_padding

                notes_x = x_start + table_width / 2 + 2
                pdf.rect(notes_x, executed_y, table_width / 2 - 2, field_h, round_corners=True, corner_radius=3)
                pdf.set_xy(notes_x + box_padding, executed_y + box_padding)
                pdf.cell(0, 0, "Notes:", border=0, align="L")

                pdf.set_text_color(0, 0, 0)
                pdf.set_y(executed_y + field_h + 4)

    return pdf

async def _perform_download(black_and_white: bool = False) -> None:
    await _ensure_pdf_runtime()
    await _ensure_pdf_assets()
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

def download_pdf_with_options(*args) -> None:
    bw = document.getElementById("pdf-bw-btn").classList.contains("pdf-toggle-btn--active")
    document.getElementById(state.pdf_color_modal_id).close()
    asyncio.ensure_future(_perform_download(black_and_white=bw))
