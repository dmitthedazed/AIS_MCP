"""
Tools: ais_list_exams, ais_register_exam, ais_unregister_exam
"""
import re
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup

from ais_mcp.context import resolve_studium_obdobi
from ais_mcp.parsers import clean_page_text, text_of
from ais_mcp.session import get_session, BASE_URL

EXAMS_URL = f"{BASE_URL}/auth/student/terminy_seznam.pl"


def _parse_exam_tables(html, base_url):
    soup = BeautifulSoup(html, "lxml")
    sections = {}

    def _extract(section_keyword):
        """Find the section by heading keyword and extract its table."""
        for tag in soup.find_all(["h2", "h3", "h4", "b", "strong", "div"]):
            if section_keyword.lower() in tag.get_text(" ").lower():
                table = tag.find_next("table")
                if not table:
                    continue
                ths = [text_of(th) for th in table.find_all("th")]
                rows = []
                for tr in table.find_all("tr"):
                    cells = [text_of(td) for td in tr.find_all("td")]
                    if not cells:
                        continue
                    row = {ths[i]: cells[i] for i in range(min(len(ths), len(cells))) if ths[i]}
                    # Harvest action links (register/unregister URLs + exam IDs)
                    links = tr.find_all("a", href=True)
                    action_hrefs = [a["href"] for a in links]
                    forms = tr.find_all("form")
                    form_data = []
                    for f in forms:
                        inputs = {inp.get("name"): inp.get("value", "") for inp in f.find_all("input")}
                        form_data.append({"action": f.get("action", ""), "fields": inputs})
                    row["_action_hrefs"] = action_hrefs
                    row["_forms"] = form_data
                    # Try to extract exam term ID from href
                    exam_id = None
                    for href in action_hrefs:
                        m = re.search(r"termin=(\d+)", href)
                        if m:
                            exam_id = m.group(1)
                            break
                    for fd in form_data:
                        if "termin" in fd.get("fields", {}):
                            exam_id = fd["fields"]["termin"]
                            break
                    row["exam_id"] = exam_id
                    if any(v for v in cells):
                        rows.append(row)
                return rows
        return []

    sections["registered"] = _extract("Which exam sittings I have registered for")
    sections["available"] = _extract("Which exam sittings I can register for")
    sections["past"] = _extract("past exam")
    return sections


def tool_list_exams(
    studium: str = None,
    obdobi: str = None,
    mode: str = "available",
    course_code: str = None,
) -> dict:
    """
    List exam dates.
    mode: 'available' (default), 'registered', 'past', or 'all'
    course_code: optional filter, e.g. 'B-MAT2'
    Returns list with exam_id you can pass to ais_register_exam / ais_unregister_exam.
    """
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    sess = get_session()

    # Build filter by course code if requested
    # First get course list from the select dropdown
    resp = sess.post(EXAMS_URL, data={
        "studium": studium,
        "obdobi": obdobi,
        "filtr_predmet": "0",
        "zalozka": "1",
    })

    # If course_code specified, find its predmet ID from the select
    filtr_predmet = "0"
    if course_code:
        soup_init = BeautifulSoup(resp.text, "lxml")
        sel = soup_init.find("select", {"name": "filtr_predmet"})
        if sel:
            for opt in sel.find_all("option"):
                if course_code.upper() in opt.get_text():
                    filtr_predmet = opt.get("value", "0")
                    break
        if filtr_predmet != "0":
            resp = sess.post(EXAMS_URL, data={
                "studium": studium,
                "obdobi": obdobi,
                "filtr_predmet": filtr_predmet,
                "jen_predmet": "Restrict",
                "zalozka": "1",
            })

    sections = _parse_exam_tables(resp.text, resp.url)

    if mode == "all":
        result = sections
    elif mode in sections:
        result = {mode: sections[mode]}
    else:
        result = sections

    return {
        "studium": studium,
        "obdobi": obdobi,
        "mode": mode,
        "course_filter": course_code,
        **result,
    }


def tool_register_exam(exam_id: str, studium: str = None, obdobi: str = None) -> dict:
    """
    Register for an exam term. exam_id comes from ais_list_exams.
    """
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    sess = get_session()
    url = f"{BASE_URL}/auth/student/prihlasit_termin.pl"
    resp = sess.post(url, data={
        "termin": exam_id,
        "studium": studium,
        "obdobi": obdobi,
        "lang": "en",
    })
    soup = BeautifulSoup(resp.text, "lxml")
    return {
        "exam_id": exam_id,
        "status": "ok" if "credential_0" not in resp.text else "session_error",
        "message": clean_page_text(soup)[:1000],
    }


def tool_unregister_exam(exam_id: str, studium: str = None, obdobi: str = None) -> dict:
    """
    Unregister from an exam term. exam_id comes from ais_list_exams.
    """
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    sess = get_session()
    url = f"{BASE_URL}/auth/student/odhlasit_termin.pl"
    resp = sess.post(url, data={
        "termin": exam_id,
        "studium": studium,
        "obdobi": obdobi,
        "lang": "en",
    })
    soup = BeautifulSoup(resp.text, "lxml")
    return {
        "exam_id": exam_id,
        "status": "ok" if "credential_0" not in resp.text else "session_error",
        "message": clean_page_text(soup)[:1000],
    }
