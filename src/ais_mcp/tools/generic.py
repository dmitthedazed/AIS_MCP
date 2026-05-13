"""
Tool: ais_fetch_page — generic escape hatch for any AIS page
"""
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ais_mcp.parsers import clean_page_text, parse_breadcrumb_title
from ais_mcp.session import get_session, BASE_URL


def tool_fetch_page(url: str, format: str = "text") -> dict:
    """
    Fetch any AIS page and return its cleaned text content.
    Useful for pages not covered by other tools.
    url: absolute URL (must start with https://is.stuba.sk/auth/)
    format: 'text' (default, cleaned) or 'raw' (full HTML)
    """
    if not url.startswith("http"):
        url = urljoin(BASE_URL + "/auth/", url)

    sess = get_session()
    resp = sess.get(url)

    if format == "raw":
        return {"url": resp.url, "html": resp.text[:50000]}

    soup = BeautifulSoup(resp.text, "lxml")
    title = parse_breadcrumb_title(soup)
    text = clean_page_text(soup)
    return {
        "url": resp.url,
        "title": title or resp.url,
        "text": text,
    }
