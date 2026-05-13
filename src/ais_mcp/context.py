"""
Auto-detect and cache current studium/obdobi/rozvrh_student for this session.
"""
import os
import re
import threading
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ais_mcp.session import get_session, BASE_URL

PORTAL_URL = f"{BASE_URL}/auth/student/moje_studium.pl?_m=3110&lang=en"

_lock = threading.Lock()
_cache = {}


def _detect_context():
    sess = get_session()
    resp = sess.get(PORTAL_URL)
    html = resp.text
    soup = BeautifulSoup(html, "lxml")

    # Extract studies table — find the active (enrolled/green) one
    studium = os.environ.get("AIS_DEFAULT_STUDIUM")
    obdobi = os.environ.get("AIS_DEFAULT_OBDOBI")

    # Try to get from URL parameters in links (they carry studium=X;obdobi=Y)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m_s = re.search(r"studium=(\d+)", href)
        m_o = re.search(r"obdobi=(\d+)", href)
        if m_s and m_o:
            if studium is None:
                studium = m_s.group(1)
            if obdobi is None:
                obdobi = m_o.group(1)
            break

    if not studium or not obdobi:
        raise RuntimeError(
            "Could not detect studium/obdobi from portal. "
            "Set AIS_DEFAULT_STUDIUM and AIS_DEFAULT_OBDOBI env vars."
        )

    # Extract rozvrh_student from Personal timetable link
    rozvrh_student = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "rozvrhy_view.pl" in href and "rozvrh_student=" in href:
            m = re.search(r"rozvrh_student=(\d+)", href)
            if m:
                rozvrh_student = m.group(1)
                break

    # Extract logged_in name from #log div
    log_div = soup.select_one("#log")
    logged_in = ""
    if log_div:
        logged_in = " ".join(log_div.get_text(" ", strip=True).replace("Logged in:", "").split())

    return {
        "studium": studium,
        "obdobi": obdobi,
        "rozvrh_student": rozvrh_student,
        "logged_in": logged_in,
        "portal_url": resp.url,
    }


def get_context():
    """Return cached {studium, obdobi, rozvrh_student, logged_in}. Thread-safe."""
    global _cache
    with _lock:
        if not _cache:
            _cache = _detect_context()
        return dict(_cache)


def reset_context():
    global _cache
    with _lock:
        _cache = {}


def resolve_studium_obdobi(studium=None, obdobi=None):
    ctx = get_context()
    return studium or ctx["studium"], obdobi or ctx["obdobi"]
