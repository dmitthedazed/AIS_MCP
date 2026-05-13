"""
Tools: ais_whoami, ais_eduroam_credentials
"""
import re
from html.parser import HTMLParser

from ais_mcp.context import get_context
from ais_mcp.session import get_session, BASE_URL

EDUROAM_URL = f"{BASE_URL}/auth/wifi/heslo_vpn_sit.pl?_m=3532&lang=en"


class _TextTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self._row = None
        self._cell = None
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
            self._in_cell = True

    def handle_data(self, data):
        if self._in_cell and self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self._in_cell:
            self._row.append(" ".join("".join(self._cell or []).split()))
            self._cell = None
            self._in_cell = False
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


def tool_whoami() -> dict:
    """Return current logged-in user info and active study context."""
    ctx = get_context()
    return {
        "logged_in": ctx["logged_in"],
        "studium": ctx["studium"],
        "obdobi": ctx["obdobi"],
        "rozvrh_student": ctx.get("rozvrh_student"),
        "portal_url": ctx.get("portal_url"),
    }


def tool_eduroam_credentials() -> dict:
    """Return eduroam/wifi login and password from AIS."""
    sess = get_session()
    resp = sess.get(EDUROAM_URL)
    parser = _TextTableParser()
    parser.feed(resp.text)

    data = {}
    for row in parser.rows:
        if len(row) < 2:
            continue
        label = row[0].strip().rstrip(":").lower()
        value = row[1].strip()
        if label == "login":
            data["login"] = value
        elif label == "password":
            data["password"] = value
        elif label == "password validity period":
            data["validity"] = value

    if "login" not in data or "password" not in data:
        raise RuntimeError("eduroam credentials not found — check session")
    return data
