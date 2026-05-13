"""
Tools: ais_list_studies, ais_portal_menu
"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ais_mcp.context import resolve_studium_obdobi
from ais_mcp.parsers import text_of, clean_page_text
from ais_mcp.session import get_session, BASE_URL

PORTAL_URL = f"{BASE_URL}/auth/student/moje_studium.pl?_m=3110&lang=en"


def _parse_portal(url, html):
    soup = BeautifulSoup(html, "lxml")
    logged_in = text_of(soup.select_one("#log")).replace("Logged in:", "").strip()

    studies = []
    for table in soup.find_all("table"):
        headers = [text_of(th) for th in table.find_all("th")]
        if "Faculty" not in headers or "Study" not in headers:
            continue
        col = {h: i for i, h in enumerate(headers)}
        for row in table.find_all("tr"):
            cells = [text_of(td) for td in row.find_all("td")]
            if len(cells) < 3:
                continue
            links_in_row = row.find_all("a", href=True)
            href_sample = links_in_row[0]["href"] if links_in_row else ""
            studium_m = re.search(r"studium=(\d+)", href_sample)
            obdobi_m = re.search(r"obdobi=(\d+)", href_sample)
            studies.append({
                "faculty": cells[col.get("Faculty", 1)] if col.get("Faculty", 1) < len(cells) else "",
                "study": cells[col.get("Study", 2)] if col.get("Study", 2) < len(cells) else "",
                "progress": cells[col.get("Progress of study", 3)] if col.get("Progress of study", 3) < len(cells) else "",
                "studium": studium_m.group(1) if studium_m else None,
                "obdobi": obdobi_m.group(1) if obdobi_m else None,
            })

    items = []
    seen = set()

    def add_item(category, link):
        title = text_of(link) or link.get("title") or link.get("aria-label") or link["href"]
        full_url = urljoin(url, link["href"])
        key = (title, full_url)
        if key not in seen:
            seen.add(key)
            items.append({"category": category, "title": title, "url": full_url})

    for link in soup.select("table.portal_menu a[href]"):
        add_item("Portal", link)
    for block in soup.select(".rada-ikon"):
        cat = block.get("data-rada") or "Applications"
        cat = cat.replace("student_", "").replace("_", " ").title()
        for link in block.select("a[href]"):
            add_item(cat, link)
    for a in soup.find_all("a", href=True):
        label = text_of(a)
        if label in {"Register for examinations", "Registration, enrollment and post-enrollment changes", "Final thesis topic"}:
            add_item("Study", a)

    return {
        "logged_in": logged_in,
        "studies": studies,
        "items": items,
    }


def tool_list_studies() -> dict:
    """List all studies and study periods available in your AIS account."""
    sess = get_session()
    resp = sess.get(PORTAL_URL)
    data = _parse_portal(resp.url, resp.text)
    return {"logged_in": data["logged_in"], "studies": data["studies"]}


def tool_portal_menu(studium: str = None, obdobi: str = None) -> dict:
    """Return all links/applications from the Student's portal main page, grouped by category."""
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    sess = get_session()
    url = f"{BASE_URL}/auth/student/moje_studium.pl?_m=3110&lang=en&studium={studium}&obdobi={obdobi}"
    resp = sess.get(url)
    data = _parse_portal(resp.url, resp.text)
    return {
        "studium": studium,
        "obdobi": obdobi,
        "logged_in": data["logged_in"],
        "menu_items": data["items"],
    }


def tool_contact_departments(fakulta: str = "30") -> dict:
    """
    Return Study Department contact information for a faculty.
    Includes address, phone, email, office hours, contact persons (with field of activity),
    and faculty vice-deans.
    fakulta: faculty code — default 30 (FEI). Other codes: SvF=10, SjF=20, FCHPT=40, FAD=50, MTF=60, FIIT=70.
    """
    sess = get_session()
    url = f"{BASE_URL}/auth/pracoviste/stud_odd.pl?fakulta={fakulta}&lang=en"
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "lxml")

    department: dict = {}
    office_hours: list = []
    contact_persons: list = []
    vice_deans: list = []

    for table in soup.find_all("table"):
        headers = [text_of(th) for th in table.find_all("th")]
        if not headers:
            # Key-value info block (address, phone, email, note)
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) == 2:
                    key = text_of(cells[0]).rstrip(":")
                    val = text_of(cells[1])
                    if key:
                        department[key] = val
        elif "Day" in headers and "From" in headers:
            for row in table.find_all("tr"):
                cells = [text_of(td) for td in row.find_all("td")]
                if cells:
                    office_hours.append(dict(zip(headers, cells)))
        elif "Name" in headers and "Office" in headers:
            has_specs = "Specifications" in headers
            for row in table.find_all("tr"):
                cells = [text_of(td) for td in row.find_all("td")]
                if not cells:
                    continue
                entry = dict(zip(headers, cells))
                # Remove the "Send an e-mail" column (icon-only, no useful text)
                entry.pop("Send an e-mail", None)
                if has_specs:
                    vice_deans.append(entry)
                else:
                    contact_persons.append(entry)

    return {
        "faculty_code": fakulta,
        "department": department,
        "office_hours": office_hours,
        "contact_persons": contact_persons,
        "vice_deans": vice_deans,
    }
