"""
Tools: ais_documents, ais_noticeboard
"""
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ais_mcp.parsers import clean_page_text, text_of
from ais_mcp.session import get_session, BASE_URL

DOCS_URL = f"{BASE_URL}/auth/dok_server/nove_dok.pl"
NOTICE_URL = f"{BASE_URL}/auth/vyveska/"


def tool_documents() -> dict:
    """Return list of newly published documents in AIS document server."""
    sess = get_session()
    resp = sess.get(f"{DOCS_URL}?lang=en")
    soup = BeautifulSoup(resp.text, "lxml")

    docs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "dok_server" in href or "soubor" in href or "file" in href.lower():
            docs.append({
                "title": text_of(a),
                "url": urljoin(resp.url, href),
            })

    return {
        "documents": docs,
        "raw_text": clean_page_text(soup)[:3000],
    }


def tool_noticeboard(folder_id: str = None) -> dict:
    """Return noticeboard messages. Optionally specify a folder_id."""
    sess = get_session()
    if folder_id:
        url = f"{NOTICE_URL}slozka.pl?sloz={folder_id}&lang=en"
    else:
        url = f"{NOTICE_URL}?lang=en"
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "lxml")

    folders = []
    messages = []

    # Find folder links
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "slozka.pl" in href or "vyveska" in href:
            folders.append({"title": text_of(a), "url": urljoin(resp.url, href)})

    # Find actual notice entries
    for table in soup.find_all("table"):
        headers = [text_of(th) for th in table.find_all("th")]
        if not headers:
            continue
        col = {h: i for i, h in enumerate(headers)}
        for row in table.find_all("tr"):
            cells = [text_of(td) for td in row.find_all("td")]
            if not cells:
                continue
            entry = {h: cells[i] for i, h in enumerate(headers) if i < len(cells) and h}
            links = [{"text": text_of(a), "url": urljoin(resp.url, a["href"])} for a in row.find_all("a", href=True)]
            entry["_links"] = links
            if any(v for v in cells):
                messages.append(entry)

    return {
        "folder_id": folder_id,
        "folders": folders[:20],
        "messages": messages[:50],
        "raw_text": clean_page_text(soup)[:2000],
    }
