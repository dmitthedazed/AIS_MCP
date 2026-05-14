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

    def _parse_students(soup: BeautifulSoup) -> list[dict]:
        # The name td is the one containing a lide/clovek link WITH text;
        # the study_info td immediately follows it.
        # Column count differs between page 1 and subsequent pages, so use link-based detection.
        found = []
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            person_id = None
            name_text = None
            name_td_idx = None
            for i, td in enumerate(tds):
                for a in td.find_all("a", href=True):
                    m = re.search(r"lide/clovek\.pl\?id=(\d+)", a["href"])
                    if m:
                        person_id = m.group(1)
                        t = text_of(a).strip()
                        if t:
                            name_text = t
                            name_td_idx = i
                        break
                if name_text:
                    break
            if not person_id:
                continue
            # Fallback: name may be plain text in td after photo td
            if not name_text and name_td_idx is not None and name_td_idx + 1 < len(tds):
                name_text = text_of(tds[name_td_idx + 1]).strip()
            if not name_text:
                continue
            study_info = None
            if name_td_idx is not None and name_td_idx + 1 < len(tds):
                study_info = text_of(tds[name_td_idx + 1]).strip()
            found.append({"name": name_text, "person_id": person_id, "study_info": study_info})
        return found

    def _extract_page_urls(soup: BeautifulSoup) -> list[str]:
        # Only spoluzaci.pl pagination links in lang=en, not email/language-switch links
        seen: set[str] = set()
        urls: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "spoluzaci.pl" not in href or "on=" not in href:
                continue
            if "lang=en" not in href and "lang=e" not in href:
                continue
            full = (BASE_URL + href) if href.startswith("/") else href
            if full not in seen:
                seen.add(full)
                urls.append(full)
        return urls

    first_resp = sess.get(base_url)
    first_soup = BeautifulSoup(first_resp.text, "lxml")
    students = _parse_students(first_soup)

    for page_url in _extract_page_urls(first_soup):
        s = BeautifulSoup(sess.get(page_url).text, "lxml")
        students.extend(_parse_students(s))

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


def tool_course_grade_stats(
    predmet_id: str,
    obdobi: str,
    fakulta: str = "30",
) -> dict:
    """
    Return grade distribution statistics for a course in a completed period.
    predmet_id: numeric course ID (from ais_lectures_sheet or hodnoceni list).
    obdobi: period ID — must be a completed period (current period returns an error).
    fakulta: faculty code — default 30 (FEI). Other codes: SvF=10, SjF=20, FCHPT=40, FAD=50, MTF=60, FIIT=70.
    Returns: list of term rows (regular exam, resit, ...) with counts per grade (A/B/C/D/E/FX)
             and attendance totals.
    """
    sess = get_session()
    url = (f"{BASE_URL}/auth/student/hodnoceni.pl"
           f"?fakulta={fakulta};obdobi={obdobi};predmet={predmet_id};lang=en")
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "lxml")

    # Error page check
    error_el = soup.find(class_=lambda c: c and "uis_msg" in c)
    if error_el:
        return {"error": text_of(error_el).strip(), "predmet_id": predmet_id, "obdobi": obdobi}

    terms = []
    for table in soup.find_all("table"):
        headers = [text_of(th).strip() for th in table.find_all("th")]
        if "Term" not in headers or "FX" not in headers:
            continue
        for row in table.find_all("tr"):
            cells = [text_of(td).strip() for td in row.find_all("td")]
            if not cells or not cells[1]:  # skip empty Term cell
                continue
            entry = dict(zip(headers, cells))
            entry.pop("Ord.", None)
            # Parse attendance from the "All exam sittings" text block in table 2
            terms.append(entry)
        break  # only the first matching table has clean numeric data

    # Extract attendance totals from the text description blocks (second table)
    attendance = {}
    for td in soup.find_all("td"):
        t = text_of(td)
        m = re.search(r"(Regular exam sitting|first resit|second resit)\s*\(attendance:\s*(\d+)\)", t)
        if m:
            attendance[m.group(1)] = int(m.group(2))
        m2 = re.search(r"All exam sittings\s*\(attendance:\s*(\d+)\)", t)
        if m2:
            attendance["all"] = int(m2.group(1))

    return {
        "predmet_id": predmet_id,
        "obdobi": obdobi,
        "fakulta": fakulta,
        "terms": terms,
        "attendance": attendance,
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
