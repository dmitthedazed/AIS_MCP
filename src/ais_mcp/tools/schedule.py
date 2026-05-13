"""
Tools: ais_schedule, ais_academic_calendar, ais_year_schedule
"""
import re

from bs4 import BeautifulSoup

from ais_mcp.context import get_context, resolve_studium_obdobi
from ais_mcp.parsers import clean_page_text, text_of
from ais_mcp.session import get_session, BASE_URL

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_MAP = {
    "Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday",
    "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday",
}


def _parse_timetable(html):
    soup = BeautifulSoup(html, "lxml")
    schedule = {}
    notes_raw = []

    for table in soup.find_all("table"):
        headers = [text_of(th) for th in table.find_all("th")]
        if not headers or "Day" not in headers[0]:
            continue
        time_slots = [h for h in headers[1:] if h]

        current_day = None
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            first = text_of(cells[0])
            if first in DAYS:
                current_day = DAY_MAP.get(first, first)
                if current_day not in schedule:
                    schedule[current_day] = []
            if current_day is None:
                continue
            for cell in cells[1:]:
                cell_text = cell.get_text("\n", strip=True)
                if not cell_text:
                    continue
                # Each cell may contain multiple events (line-separated)
                lines = [l.strip() for l in cell_text.splitlines() if l.strip()]
                if not lines:
                    continue
                # Typical format: room, course_name + (note_refs), teacher
                entry = {
                    "room": lines[0] if lines else "",
                    "course": lines[1] if len(lines) > 1 else "",
                    "teacher": lines[2] if len(lines) > 2 else "",
                    "raw": " | ".join(lines),
                }
                schedule[current_day].append(entry)

    # Extract footnotes table (usually small table with (N) Explanation)
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        for row in rows:
            cells = [text_of(td) for td in row.find_all("td")]
            if cells and re.match(r"^\(\d+\)", cells[0]):
                notes_raw.append(" ".join(cells))

    return {
        "schedule": schedule,
        "notes": notes_raw,
    }


def tool_schedule(rozvrh_student: str = None) -> dict:
    """
    Return personal weekly timetable as {Monday: [...], Tuesday: [...], ...}.
    Each event has: room, course, teacher.
    """
    ctx = get_context()
    rs = rozvrh_student or ctx.get("rozvrh_student")
    if not rs:
        raise RuntimeError("rozvrh_student ID not found. Pass it explicitly.")
    sess = get_session()
    url = (f"{BASE_URL}/auth/katalog/rozvrhy_view.pl"
           f"?rozvrh_student_obec=1;zobraz=1;format=html;rozvrh_student={rs}&lang=en")
    resp = sess.get(url)
    result = _parse_timetable(resp.text)
    result["rozvrh_student"] = rs
    result["url"] = resp.url
    return result


def tool_academic_calendar(studium: str = None, obdobi: str = None) -> dict:
    """Return academic calendar weeks overview for the current study period."""
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    sess = get_session()
    url = f"{BASE_URL}/auth/ca/prehled_tydnu.pl?studium={studium};obdobi={obdobi};&lang=en"
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "lxml")
    return {
        "studium": studium,
        "obdobi": obdobi,
        "text": clean_page_text(soup),
    }


def tool_year_schedule(obdobi: str = None, fakulta: str = "30") -> dict:
    """Return academic year schedule (key dates, exam periods, holidays)."""
    _, obdobi = resolve_studium_obdobi(None, obdobi)
    sess = get_session()
    url = (f"{BASE_URL}/auth/student/harmonogram.pl"
           f"?obdobi={obdobi};fakulta={fakulta}&lang=en")
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "lxml")
    return {
        "obdobi": obdobi,
        "fakulta": fakulta,
        "text": clean_page_text(soup),
    }
