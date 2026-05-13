"""
Tools: ais_financing, ais_scholarships, ais_orders
"""
from bs4 import BeautifulSoup

from ais_mcp.context import resolve_studium_obdobi
from ais_mcp.parsers import clean_page_text
from ais_mcp.session import get_session, BASE_URL


def _fetch_text(url):
    sess = get_session()
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "lxml")
    return clean_page_text(soup)


def tool_financing(studium: str = None, obdobi: str = None) -> dict:
    """Return study financing history and current financing status."""
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    text = _fetch_text(
        f"{BASE_URL}/auth/student/financovani.pl?obdobi={obdobi};studium={studium}&lang=en"
    )
    return {"studium": studium, "obdobi": obdobi, "text": text}


def tool_scholarships(studium: str = None, obdobi: str = None) -> dict:
    """Return paid-out scholarships list."""
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    text = _fetch_text(
        f"{BASE_URL}/auth/student/vypl_stip_student.pl?obdobi={obdobi};studium={studium}&lang=en"
    )
    return {"studium": studium, "obdobi": obdobi, "text": text}


def tool_orders(studium: str = None, obdobi: str = None) -> dict:
    """Return financial orders (ISIC, transport card, etc.)."""
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    text = _fetch_text(
        f"{BASE_URL}/auth/financovani/objednavky.pl?obdobi={obdobi};studium={studium}&lang=en"
    )
    return {"studium": studium, "obdobi": obdobi, "text": text}
