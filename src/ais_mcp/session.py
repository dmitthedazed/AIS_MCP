"""
AIS session manager: login, cookie cache, auto-relogin on session expiry.
"""
import json
import os
import stat
import threading
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import requests

BASE_URL = "https://is.stuba.sk"
LOGIN_URL = f"{BASE_URL}/auth/"
COOKIE_NAME = "UISAuth"
CACHE_PATH = Path.home() / ".cache" / "ais-mcp" / "cookies.json"

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class _LoginFormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self._current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self._current = {"action": attrs.get("action", ""), "fields": {}}
        elif self._current is not None and tag in {"input", "button"}:
            name = attrs.get("name")
            if not name:
                return
            ft = attrs.get("type", "").lower()
            if ft in {"checkbox", "radio"} and "checked" not in attrs:
                return
            self._current["fields"][name] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form" and self._current is not None:
            self.forms.append(self._current)
            self._current = None


def _parse_login_form(html):
    p = _LoginFormParser()
    p.feed(html)
    for form in p.forms:
        if "credential_0" in form["fields"] and "credential_1" in form["fields"]:
            return form
    raise RuntimeError("login form not found — page structure may have changed")


class SessionManager:
    """Thread-safe singleton AIS HTTP session."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._rlock = threading.RLock()
        self._session = self._make_session()
        self._try_load_cached_cookie()

    # ------------------------------------------------------------------
    def _make_session(self):
        s = requests.Session()
        s.headers.update({
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        return s

    def _try_load_cached_cookie(self):
        try:
            if CACHE_PATH.exists():
                data = json.loads(CACHE_PATH.read_text())
                token = data.get("UISAuth")
                if token:
                    self._session.cookies.set(COOKIE_NAME, token, domain="is.stuba.sk", path="/")
        except Exception:
            pass

    def _save_cookie(self, token):
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps({"UISAuth": token}))
        CACHE_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)

    def _login(self):
        username = os.environ.get("AIS_USERNAME")
        password = os.environ.get("AIS_PASSWORD")
        if not username or not password:
            raise RuntimeError(
                "AIS_USERNAME and AIS_PASSWORD environment variables are required"
            )
        resp = self._session.get(LOGIN_URL, timeout=30)
        form = _parse_login_form(resp.text)
        data = dict(form["fields"])
        data["credential_0"] = username
        data["credential_1"] = password
        action = urljoin(LOGIN_URL, form["action"] or "/system/login.pl")
        result = self._session.post(action, data=data, allow_redirects=True, timeout=30)
        token = self._session.cookies.get(COOKIE_NAME, domain="is.stuba.sk") or \
                self._session.cookies.get(COOKIE_NAME)
        if not token:
            if "credential_0" in result.text or "Log in to system" in result.text:
                raise RuntimeError("AIS login failed — check credentials")
            raise RuntimeError("UISAuth cookie not found after login")
        self._save_cookie(token)

    def _is_logged_out(self, text):
        return (
            "credential_0" in text
            or "Log in to system" in text
            or "Log in to System" in text
        )

    # ------------------------------------------------------------------
    def get(self, url, **kwargs):
        with self._rlock:
            resp = self._session.get(url, timeout=30, **kwargs)
            if self._is_logged_out(resp.text):
                self._login()
                resp = self._session.get(url, timeout=30, **kwargs)
            return resp

    def post(self, url, **kwargs):
        with self._rlock:
            resp = self._session.post(url, timeout=30, **kwargs)
            if self._is_logged_out(resp.text):
                self._login()
                resp = self._session.post(url, timeout=30, **kwargs)
            return resp

    def ensure_logged_in(self):
        with self._rlock:
            resp = self._session.get(LOGIN_URL, timeout=30)
            if self._is_logged_out(resp.text):
                self._login()
            elif "Log out" not in resp.text and COOKIE_NAME not in self._session.cookies:
                self._login()


_manager = SessionManager()


def get_session() -> SessionManager:
    return _manager
