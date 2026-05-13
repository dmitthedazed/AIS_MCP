"""
Tools: ais_course_registration
"""
from bs4 import BeautifulSoup

from ais_mcp.context import resolve_studium_obdobi
from ais_mcp.parsers import clean_page_text, text_of
from ais_mcp.session import get_session, BASE_URL


def tool_course_registration(studium: str = None, obdobi: str = None) -> dict:
    """
    Return course registration / enrollment status for the current period.
    """
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    sess = get_session()
    url = (f"{BASE_URL}/auth/student/registrace.pl"
           f"?studium={studium};obdobi={obdobi}&lang=en")
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "lxml")

    courses = []
    for table in soup.find_all("table"):
        headers = [text_of(th) for th in table.find_all("th")]
        if not any(h in headers for h in ["Code", "Course", "Credits"]):
            continue
        col = {h: i for i, h in enumerate(headers)}
        for row in table.find_all("tr"):
            cells = [text_of(td) for td in row.find_all("td")]
            if len(cells) < 2:
                continue
            code_i = col.get("Code", 0)
            name_i = col.get("Course", 1)
            code = cells[code_i] if code_i < len(cells) else ""
            if not code:
                continue
            courses.append({h: cells[i] for i, h in enumerate(headers) if i < len(cells)})

    return {
        "studium": studium,
        "obdobi": obdobi,
        "courses": courses,
        "raw_text": clean_page_text(soup)[:2000],
    }
