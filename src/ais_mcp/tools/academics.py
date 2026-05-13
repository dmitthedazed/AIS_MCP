"""
Tools: ais_grades, ais_grades_all, ais_plan_progress, ais_course_eplans,
       ais_study_details, ais_schoolmates, ais_excuse_notes
"""
import re

from bs4 import BeautifulSoup

from ais_mcp.context import resolve_studium_obdobi
from ais_mcp.parsers import clean_page_text, parse_grades_table, text_of
from ais_mcp.session import get_session, BASE_URL


def tool_grades(studium: str = None, obdobi: str = None) -> dict:
    """
    Return current-period courses and exam results from E-study record.
    Includes course code, name, completion type, attempt count, result, credits.
    """
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    sess = get_session()
    url = f"{BASE_URL}/auth/student/pruchod_studiem.pl?studium={studium};obdobi={obdobi}&lang=en"
    resp = sess.get(url)
    courses = parse_grades_table(resp.text)

    # Also extract period stats from page text
    soup = BeautifulSoup(resp.text, "lxml")
    stats_text = ""
    for p in soup.find_all(text=True):
        if "Number of credits" in p:
            stats_text = p.strip()
            break

    return {
        "studium": studium,
        "obdobi": obdobi,
        "courses": courses,
        "raw_text": clean_page_text(soup)[:2000],
    }


def tool_grades_all(studium: str = None) -> dict:
    """
    Return complete study record across all periods.
    Fetches the 'Detailed overview of the whole study' view.
    """
    studium, _ = resolve_studium_obdobi(studium, None)
    sess = get_session()
    # tab=3 is "Detailed overview of the whole study"
    url = (f"{BASE_URL}/auth/student/pruchod_studiem.pl"
           f"?studium={studium}&lang=en&zalozka=4")
    resp = sess.get(url)
    courses = parse_grades_table(resp.text)
    soup = BeautifulSoup(resp.text, "lxml")
    return {
        "studium": studium,
        "courses": courses,
        "raw_text": clean_page_text(soup)[:4000],
    }


def tool_plan_progress(studium: str = None, obdobi: str = None) -> dict:
    """
    Return study plan progress check (obligatory/optional/elective credits).
    """
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    sess = get_session()
    url = (f"{BASE_URL}/auth/studijni/studijni_povinnosti.pl"
           f"?studium={studium};obdobi={obdobi}&lang=en")
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "lxml")
    return {
        "studium": studium,
        "obdobi": obdobi,
        "text": clean_page_text(soup),
    }


def tool_course_eplans(studium: str = None, obdobi: str = None) -> dict:
    """
    Return list of course e-plans (syllabi) for current period.
    """
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    sess = get_session()
    url = (f"{BASE_URL}/auth/elis/student/seznam_osnov.pl"
           f"?studium={studium};obdobi={obdobi}&lang=en")
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "lxml")

    plans = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "osnova_predmetu" in href or "syllabus" in href or "osnov" in href:
            plans.append({"title": text_of(a), "url": BASE_URL + href if href.startswith("/") else href})

    return {
        "studium": studium,
        "obdobi": obdobi,
        "plans": plans,
        "raw_text": clean_page_text(soup)[:3000],
    }


def tool_study_details(studium: str = None, obdobi: str = None) -> dict:
    """
    Return detailed study information: programme, credits enrolled/obtained,
    degree, start date, financing, thesis topic/supervisor, card number,
    study interruptions, trips abroad.
    """
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    sess = get_session()
    url = f"{BASE_URL}/auth/student/studium.pl?studium={studium};obdobi={obdobi}&lang=en"
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "lxml")

    details = {}
    interruptions = []
    trips = []

    for table in soup.find_all("table"):
        headers = [text_of(th) for th in table.find_all("th")]
        if headers:
            header_str = " ".join(headers)
            rows = []
            for row in table.find_all("tr"):
                cells = [text_of(td) for td in row.find_all("td")]
                if cells and "No suitable" not in " ".join(cells):
                    rows.append(dict(zip(headers, cells)))
            if "Since" in headers and "Until" in headers:
                interruptions = rows
            elif "Institution" in header_str or "Past from" in header_str:
                trips = rows
        else:
            # Key-value info table
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) == 2:
                    key = text_of(cells[0]).rstrip(":")
                    val = text_of(cells[1])
                    if key:
                        details[key] = val

    return {
        "studium": studium,
        "details": details,
        "interruptions": interruptions,
        "trips_abroad": trips,
    }


def tool_schoolmates(
    studium: str = None,
    obdobi: str = None,
    course_code: str = None,
    group: str = "all",
) -> dict:
    """
    List courses and classmates.
    Without course_code: return list of courses you share with other students this period.
    With course_code (e.g. 'B-MAT2'): return students in that course.
    group: 'all' (default) | 'seminar' (your seminar group) | 'teacher' (same teacher group).
    Students over 40 are paginated — all pages are fetched automatically.
    Each student: name, person_id (usable with ais_get_person), study_info.
    """
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    sess = get_session()
    url = f"{BASE_URL}/auth/student/spoluzaci.pl?studium={studium};obdobi={obdobi}&lang=en"
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "lxml")

    # Each course row: code | name | icon(all) | icon(teacher-group) | icon(seminar) | email
    # Links use predmet=NNNN, with optional vyucujici=1 and skupina=NNNN
    courses = []
    for row in soup.find_all("tr"):
        tds = row.find_all("td")
        if len(tds) < 3:
            continue
        code = text_of(tds[0]).strip()
        if not code or not re.match(r'^[A-Z][\w-]{1,12}$', code):
            continue
        name = text_of(tds[1]).strip()
        links: dict[str, str] = {}
        for a in row.find_all("a", href=True):
            href = a["href"]
            if "predmet=" not in href:
                continue
            full = (BASE_URL + href) if href.startswith("/") else href
            if "email=1" in href:
                continue
            if "vyucujici=1" in href:
                links["teacher"] = full
            elif "skupina=" in href:
                links["seminar"] = full
            else:
                links["all"] = full
        if links:
            courses.append({"code": code, "name": name, "predmet_links": links})

    if not course_code:
        return {
            "studium": studium,
            "obdobi": obdobi,
            "courses": [{"code": c["code"], "name": c["name"]} for c in courses],
        }

    target = next((c for c in courses if c["code"].upper() == course_code.upper()), None)
    if not target:
        return {
            "error": f"Course {course_code} not found",
            "available": [c["code"] for c in courses],
        }

    base_url = target["predmet_links"].get(group) or target["predmet_links"].get("all") or next(iter(target["predmet_links"].values()))

    def _fetch_page(page_url: str) -> tuple[list, list]:
        r = sess.get(page_url)
        s = BeautifulSoup(r.text, "lxml")
        found_students = []
        # Rows: header has "Name of a student attending the same course"
        # Student rows have lide/clovek.pl?id= link
        for tr in s.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            # Find name cell — has profile link
            person_id = None
            name_text = None
            study_info = None
            for a in tr.find_all("a", href=True):
                m = re.search(r"lide/clovek\.pl\?id=(\d+)", a["href"])
                if m:
                    person_id = m.group(1)
                    name_text = text_of(a).strip()
                    break
            if not name_text:
                continue
            # Study info is in the next td after the name link's td
            for i, td in enumerate(tds):
                if td.find("a", href=re.compile(r"lide/clovek")):
                    if i + 1 < len(tds):
                        study_info = text_of(tds[i + 1]).strip()
                    break
            found_students.append({"name": name_text, "person_id": person_id, "study_info": study_info})
        # Pagination: links with on=N
        next_pages = []
        for a in s.find_all("a", href=True):
            if "on=" in a["href"] and "predmet=" in a["href"]:
                full = (BASE_URL + a["href"]) if a["href"].startswith("/") else a["href"]
                next_pages.append(full)
        return found_students, list(dict.fromkeys(next_pages))

    students, extra_pages = _fetch_page(base_url)
    seen_urls = {base_url}
    for page_url in extra_pages:
        if page_url not in seen_urls:
            seen_urls.add(page_url)
            more, _ = _fetch_page(page_url)
            students.extend(more)

    # Deduplicate by person_id
    seen_ids: set[str] = set()
    unique: list[dict] = []
    for s in students:
        key = s["person_id"] or s["name"]
        if key not in seen_ids:
            seen_ids.add(key)
            unique.append(s)

    return {
        "studium": studium,
        "obdobi": obdobi,
        "course_code": target["code"],
        "course_name": target["name"],
        "group": group,
        "total": len(unique),
        "students": unique,
    }


def tool_course_syllabus(predmet_id: str) -> dict:
    """
    Return full course syllabus from the AIS course catalogue.
    predmet_id: numeric course ID (from ais_lectures_sheet, ais_course_progress, or plan progress links).
    Returns: university, faculty, code, title, credits, hours, prerequisites,
             learning outcomes, assessment methods, grade distribution, literature, supervisor.
    """
    sess = get_session()
    url = f"{BASE_URL}/auth/katalog/syllabus.pl?predmet={predmet_id}&lang=en"
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "lxml")

    info: dict = {}
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                key = text_of(cells[0]).rstrip(":").strip()
                val = text_of(cells[1]).strip()
                if key and val and len(key) < 80:
                    if key not in info:
                        info[key] = val

    return {
        "predmet_id": predmet_id,
        "syllabus": info,
        "raw_text": clean_page_text(soup)[:3000],
    }


def tool_excuse_notes(
    studium: str = None,
    obdobi: str = None,
    include_history: bool = False,
) -> dict:
    """
    Return absence/excuse notes submitted to the Study Department.
    Each note has: since, until, reason for absence, specifications.
    include_history: if True, show all past records (not just current period).
    """
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    sess = get_session()
    url = f"{BASE_URL}/auth/student/moje_omluvenky.pl"

    if include_history:
        resp = sess.post(url, data={
            "lang": "en",
            "studium": studium,
            "obdobi": obdobi,
            "filtr": "1",
            "omezeni": "Go",
        })
    else:
        resp = sess.get(f"{url}?studium={studium};obdobi={obdobi}&lang=en")

    soup = BeautifulSoup(resp.text, "lxml")

    notes = []
    for table in soup.find_all("table"):
        headers = [text_of(th) for th in table.find_all("th")]
        if "Since" in headers and "Until" in headers:
            for row in table.find_all("tr"):
                cells = [text_of(td) for td in row.find_all("td")]
                if cells and "No suitable" not in " ".join(cells):
                    notes.append(dict(zip(headers, cells)))
            break

    return {
        "studium": studium,
        "obdobi": obdobi,
        "include_history": include_history,
        "excuse_notes": notes,
    }
