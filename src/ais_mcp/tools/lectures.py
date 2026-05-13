"""
Tools: ais_lectures_sheet, ais_course_progress
"""
import re

from bs4 import BeautifulSoup

from ais_mcp.context import resolve_studium_obdobi
from ais_mcp.parsers import clean_page_text, text_of
from ais_mcp.session import get_session, BASE_URL

LIST_URL = f"{BASE_URL}/auth/student/list.pl"

_DOCH = {
    "doch-pritomen":  "present",
    "doch-neomluven": "absent",
    "doch-omluven":   "excused",
    "doch-pozde":     "late",
    "doch-vyloucen":  "disqualified",
    "doch-jinya":     "other_seminar",
    "doch-odchod":    "early_leave",
}


def _parse_sheet(soup: BeautifulSoup) -> list[dict]:
    """Parse the main lectures sheet HTML into a per-course list."""
    # Find table that has prubezne links (the attendance table)
    main_table = None
    for table in soup.find_all("table"):
        if table.find("a", href=re.compile(r"prubezne=1")):
            main_table = table
            break
    if not main_table:
        return []

    courses: dict[str, dict] = {}
    current_code: str | None = None

    for row in main_table.find_all("tr"):
        prubezne_a = row.find("a", href=re.compile(r"prubezne=1"))
        test_a = row.find("a", href=re.compile(r"test=1"))

        if prubezne_a:
            # Course header row — extract code and name
            code = name = None
            for td in row.find_all("td"):
                t = text_of(td).strip()
                m = re.match(r'^([A-Z][\w-]{2,10})\s+(.*)', t)
                if m:
                    code, name = m.group(1), m.group(2).strip()
                    break

            pred_m = re.search(r"predmet=(\d+)", prubezne_a.get("href", ""))
            predmet_id = pred_m.group(1) if pred_m else None

            def _full(a_tag):
                if not a_tag:
                    return None
                h = a_tag.get("href", "")
                return (BASE_URL + h) if h.startswith("/") else h

            current_code = code
            if code and code not in courses:
                courses[code] = {
                    "code": code,
                    "name": name,
                    "predmet_id": predmet_id,
                    "progress_url": _full(prubezne_a),
                    "tests_url": _full(test_a),
                    "attendance": [],
                }

        # Collect per-session attendance from td[title] with doch-* spans
        if current_code and current_code in courses:
            for td in row.find_all("td", title=True):
                td_title = td.get("title", "")
                if not re.search(r'\d{2}[./]\d{2}[./]\d{4}', td_title):
                    continue
                span = td.find("span", attrs={"data-sysid": re.compile(r"^doch-")})
                if not span:
                    continue
                sysid = span.get("data-sysid", "")
                courses[current_code]["attendance"].append({
                    "session_info": td_title,
                    "status": _DOCH.get(sysid, sysid),
                })

    return list(courses.values())


def _summary(records: list[dict]) -> dict:
    s: dict[str, int] = {}
    for r in records:
        s[r["status"]] = s.get(r["status"], 0) + 1
    return s


def tool_lectures_sheet(studium: str = None, obdobi: str = None) -> dict:
    """
    Return attendance overview for all courses this period.
    Each course: code, name, predmet_id, attendance_summary {present/absent/excused/...},
    and the full per-session attendance list.
    Use ais_course_progress(predmet_id) for grades and test scores.
    """
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    sess = get_session()
    resp = sess.get(f"{LIST_URL}?studium={studium};obdobi={obdobi}&lang=en")
    soup = BeautifulSoup(resp.text, "lxml")

    raw = _parse_sheet(soup)
    courses = [
        {
            "code": c["code"],
            "name": c["name"],
            "predmet_id": c["predmet_id"],
            "attendance_summary": _summary(c["attendance"]),
            "attendance": c["attendance"],
        }
        for c in raw
    ]

    return {"studium": studium, "obdobi": obdobi, "courses": courses}


def _parse_progress(soup: BeautifulSoup) -> list[dict]:
    results = []
    for table in soup.find_all("table"):
        headers = [text_of(th) for th in table.find_all("th")]
        if not headers or "Grouping" not in headers[0]:
            continue
        for row in table.find_all("tr"):
            cells = [text_of(td) for td in row.find_all("td")]
            if cells:
                results.append(dict(zip(headers, cells)))
    return results


def _parse_tests(soup: BeautifulSoup) -> list[dict]:
    results = []
    for table in soup.find_all("table"):
        headers = [text_of(th) for th in table.find_all("th")]
        if "Score attained" not in " ".join(headers):
            continue
        detail_col = next((i for i, h in enumerate(headers) if h == "Details"), None)
        for row in table.find_all("tr"):
            tds = row.find_all("td")
            cells = [text_of(td) for td in tds]
            if cells and cells[0]:
                entry = dict(zip(headers, cells))
                entry.pop("Details", None)
                # Extract detail_id from the Details link
                if detail_col is not None and detail_col < len(tds):
                    a = tds[detail_col].find("a", href=True)
                    if a:
                        m = re.search(r"detail=(\d+)", a.get("href", ""))
                        if m:
                            entry["detail_id"] = m.group(1)
                results.append(entry)
    return results


def _parse_test_detail(soup: BeautifulSoup) -> list[dict]:
    results = []
    for table in soup.find_all("table"):
        headers = [text_of(th) for th in table.find_all("th")]
        if "Question" not in " ".join(headers) or "Points" not in " ".join(headers):
            continue
        tbody = table.find("tbody") or table
        for row in tbody.find_all("tr", recursive=False):
            tds = row.find_all("td", recursive=False)
            if len(tds) < 3:
                continue
            q_num = tds[0].get_text(" ", strip=True)
            # Middle td has nested table rows: [question text, type note, student answer]
            inner = [r.get_text(" ", strip=True) for r in tds[1].find_all("tr") if r.get_text(strip=True)]
            points = tds[2].get_text(" ", strip=True)
            if not q_num:
                continue
            entry = {
                "question_no": q_num,
                "question": inner[0] if len(inner) > 0 else "",
                "type_note": inner[1] if len(inner) > 1 else "",
                "answer": inner[2] if len(inner) > 2 else "",
                "points": points,
            }
            results.append(entry)
    return results


def tool_course_progress(
    predmet_id: str,
    studium: str = None,
    obdobi: str = None,
) -> dict:
    """
    Return progress grades and test results for a specific course.
    predmet_id: numeric course ID — get it from ais_lectures_sheet courses[].predmet_id.
    Returns:
      progress: running score groupings (activities A 1-5, tests T 1, etc.) with totals.
      tests: list of individual tests with score, max, percentage, date.
    """
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    sess = get_session()

    base = f"{LIST_URL}?studium={studium};obdobi={obdobi};predmet={predmet_id}"

    resp_p = sess.get(f"{base};prubezne=1;lang=en")
    soup_p = BeautifulSoup(resp_p.text, "lxml")
    progress = _parse_progress(soup_p)

    # Course name from page title area
    heading = clean_page_text(soup_p)
    course_name = ""
    m = re.search(r"Course - (.+?)(?:\n|$)", heading)
    if m:
        course_name = m.group(1).strip()

    resp_t = sess.get(f"{base};test=1;lang=en")
    soup_t = BeautifulSoup(resp_t.text, "lxml")
    tests = _parse_tests(soup_t)

    return {
        "studium": studium,
        "obdobi": obdobi,
        "predmet_id": predmet_id,
        "course_name": course_name,
        "progress": progress,
        "tests": tests,
    }


def tool_test_detail(
    detail_id: str,
    predmet_id: str,
    studium: str = None,
    obdobi: str = None,
) -> dict:
    """
    Return per-question breakdown for a specific test.
    detail_id: from ais_course_progress tests[].detail_id.
    predmet_id: numeric course ID.
    Returns list of questions with question text, student answer, and points earned.
    """
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    sess = get_session()
    url = (f"{LIST_URL}?studium={studium};obdobi={obdobi}"
           f";predmet={predmet_id};vysledky=1;detail={detail_id};lang=en")
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "lxml")
    questions = _parse_test_detail(soup)
    return {
        "studium": studium,
        "obdobi": obdobi,
        "predmet_id": predmet_id,
        "detail_id": detail_id,
        "questions": questions,
    }
