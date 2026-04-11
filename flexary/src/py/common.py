import datetime

from pyscript import document


def copyright():
    current_year = datetime.date.today().year
    return f"""
    © {current_year} <a href="https://vladflore.fit/">vladflore.fit</a> · All rights reserved."""


def current_version():
    return "<i>Version: 12.04.2026</i>"


def is_valid_yt_url(value: str) -> bool:
    """Return True if value is empty (optional) or a recognised YouTube URL."""
    value = (value or "").strip()
    if not value:
        return True
    is_yt_host = "youtube.com/" in value or "youtu.be/" in value
    return is_yt_host and bool(extract_yt_id(value))


def yt_id_to_url(video_id: str) -> str:
    video_id = (video_id or "").strip()
    if not video_id:
        return ""
    return f"https://www.youtube.com/watch?v={video_id}"


def extract_yt_id(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if "youtu.be/" in value:
        return value.split("youtu.be/")[-1].split("?")[0].split("&")[0]
    if "/shorts/" in value:
        return value.split("/shorts/")[-1].split("?")[0].split("&")[0]
    if "embed/" in value:
        return value.split("embed/")[-1].split("?")[0].split("&")[0]
    if "v=" in value:
        return value.split("v=")[-1].split("&")[0]
    return value


def make_input_group(label_text: str, input_el):
    is_textarea = input_el.tagName.lower() == "textarea"
    group = document.createElement("div")
    group.style.display = "flex"
    group.style.flexDirection = "column"
    group.style.gap = "2px"
    label = document.createElement("label")
    label.textContent = label_text
    label.style.fontSize = "0.75rem"
    label.style.color = "rgba(255,255,255,0.6)"
    input_el.style.width = "100%"
    input_el.style.fontSize = "0.8rem"
    if not is_textarea:
        input_el.style.height = "30px"
    else:
        input_el.style.resize = "vertical"
    input_el.style.padding = "4px 8px"
    input_el.style.borderRadius = "4px"
    input_el.style.border = "1px solid rgba(186,148,94,0.3)"
    input_el.style.backgroundColor = "rgba(255,255,255,0.07)"
    input_el.style.color = "#fff"
    input_el.style.outline = "none"
    group.appendChild(label)
    group.appendChild(input_el)
    return group


def make_warning_el():
    el = document.createElement("div")
    el.style.display = "none"
    el.style.color = "#f87171"
    el.style.fontSize = "0.75rem"
    return el


def show_warning(el, msg: str) -> None:
    el.textContent = msg
    el.style.display = "block"
