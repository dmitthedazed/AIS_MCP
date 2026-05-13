"""
Tools: ais_thesis_topics, ais_submissions
"""
from bs4 import BeautifulSoup

from ais_mcp.context import resolve_studium_obdobi
from ais_mcp.parsers import clean_page_text, text_of
from ais_mcp.session import get_session, BASE_URL


def tool_thesis_topics(studium: str = None, obdobi: str = None) -> dict:
    """Return list of thesis/project topics available for selection."""
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    sess = get_session()
    url = (f"{BASE_URL}/auth/student/temata_prihlasovani.pl"
           f"?studium={studium};obdobi={obdobi}&lang=en")
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "lxml")
    return {
        "studium": studium,
        "obdobi": obdobi,
        "text": clean_page_text(soup),
    }


def tool_submissions(studium: str = None, obdobi: str = None) -> dict:
    """Return coursework submission boxes for current period."""
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    sess = get_session()
    url = (f"{BASE_URL}/auth/student/odevzdavarny.pl"
           f"?studium={studium};obdobi={obdobi}&lang=en")
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "lxml")

    boxes = []
    for table in soup.find_all("table"):
        headers = [text_of(th) for th in table.find_all("th")]
        if not headers:
            continue
        for row in table.find_all("tr"):
            cells = [text_of(td) for td in row.find_all("td")]
            if not cells:
                continue
            entry = {headers[i]: cells[i] for i in range(min(len(headers), len(cells))) if headers[i]}
            if any(entry.values()):
                # Collect submission links
                links = [{"text": text_of(a), "href": a["href"]} for a in row.find_all("a", href=True)]
                entry["_links"] = links
                boxes.append(entry)

    return {
        "studium": studium,
        "obdobi": obdobi,
        "submissions": boxes,
        "raw_text": clean_page_text(soup)[:2000],
    }
