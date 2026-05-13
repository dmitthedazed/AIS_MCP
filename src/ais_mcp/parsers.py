"""
Shared HTML parsing utilities — adapted from stuba-people-gui and stuba-student-gui.
"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

BASE_URL = "https://is.stuba.sk"


# ── Generic ──────────────────────────────────────────────────────────────────

def text_of(node):
    if node is None:
        return ""
    return " ".join(node.get_text(" ", strip=True).split())


def clean_page_text(soup):
    for node in soup.select("script,style,svg,#hlavicka,.searchinbreadcrumbs,.helpinbreadcrumbs"):
        node.decompose()
    lines, previous = [], None
    for raw in soup.get_text("\n", strip=True).splitlines():
        line = " ".join(raw.split())
        if not line or line == previous:
            continue
        lines.append(line)
        previous = line
    return "\n".join(lines)


def parse_breadcrumb_title(soup):
    title = soup.select_one("li.breadcrumb-item.active span")
    if title:
        return text_of(title)
    h1 = soup.find("h1")
    return text_of(h1) if h1 else ""


# ── People ────────────────────────────────────────────────────────────────────

def _find_regex(text, pattern):
    m = re.search(pattern, text)
    return m.group(1).strip() if m else ""


def _normalize_email(value):
    return value.replace(" [at] ", "@").strip()


def parse_person(url, html):
    soup = BeautifulSoup(html, "lxml")
    text_lines = [l.strip() for l in soup.get_text("\n", strip=True).splitlines() if l.strip()]
    text = "\n".join(text_lines)

    name = ""
    title = soup.select_one("li.breadcrumb-item.active span")
    if title:
        name = text_of(title)
    if not name:
        heading = soup.find("font", attrs={"size": "+1"})
        if heading:
            name = text_of(heading)

    ident = _find_regex(text, r"Identification number:\s*([0-9]+)")
    is_email = _find_regex(text, r"E-mail in the information system:\s*(.+)")
    uni_email = _find_regex(text, r"University e-mail:\s*(.+)")

    details = []
    capture = False
    for line in text_lines:
        if line.startswith("University e-mail:"):
            capture = True
            continue
        if not capture:
            continue
        if line in {"User information in vCard format", "Import person to postal contacts"}:
            break
        if line and not line.startswith("User forwards"):
            details.append(line)

    return {
        "name": name,
        "id": ident,
        "is_email": _normalize_email(is_email),
        "university_email": _normalize_email(uni_email),
        "details": details,
        "url": url,
    }


def parse_people_list(response_url, html):
    if "clovek.pl" in response_url:
        return {"type": "person", "person": parse_person(response_url, html)}

    soup = BeautifulSoup(html, "lxml")
    results = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "clovek.pl" not in href or "id=" not in href:
            continue
        name = link.get_text(" ", strip=True)
        if not name:
            continue
        description = ""
        node = link.next_sibling
        while node is not None and getattr(node, "name", None) != "br":
            if isinstance(node, str):
                description += node
            else:
                description += node.get_text(" ", strip=True)
            node = node.next_sibling
        results.append({
            "name": " ".join(name.split()),
            "description": " ".join(description.lstrip(" -").split()),
            "url": urljoin(response_url, href),
        })

    if results:
        return {"type": "list", "results": results}

    t = soup.get_text("\n", strip=True)
    if "No person was found" in t:
        return {"type": "list", "results": []}
    return {"type": "person", "person": parse_person(response_url, html)}


# ── Grades table ─────────────────────────────────────────────────────────────

def parse_grades_table(html):
    """Parse E-study record (pruchod_studiem.pl) — returns list of course dicts."""
    soup = BeautifulSoup(html, "lxml")
    courses = []
    for table in soup.find_all("table"):
        headers = [text_of(th) for th in table.find_all("th")]
        if "Code" not in headers or "Course" not in headers:
            continue
        col = {h: i for i, h in enumerate(headers)}
        for row in table.find_all("tr"):
            cells = [text_of(td) for td in row.find_all("td")]
            if not cells or len(cells) < 3:
                continue
            code_idx = col.get("Code", 0)
            name_idx = col.get("Course", 1)
            code = cells[code_idx] if code_idx < len(cells) else ""
            if not code:
                continue
            result_idx = col.get("Result", -1)
            credits_idx = col.get("Credits", -1)
            attempt_idx = col.get("Attempt", -1)
            comp_idx = col.get("Com.", -1)
            courses.append({
                "code": code,
                "name": cells[name_idx] if name_idx < len(cells) else "",
                "result": cells[result_idx] if 0 <= result_idx < len(cells) else "",
                "credits": cells[credits_idx] if 0 <= credits_idx < len(cells) else "",
                "attempt": cells[attempt_idx] if 0 <= attempt_idx < len(cells) else "",
                "completion": cells[comp_idx] if 0 <= comp_idx < len(cells) else "",
            })
    return courses


# ── Exam list ─────────────────────────────────────────────────────────────────

def parse_exam_list(html):
    """Parse terminy_seznam.pl — returns registered + available exam lists."""
    soup = BeautifulSoup(html, "lxml")

    def _parse_section(header_text):
        exams = []
        header = soup.find(lambda tag: tag.name in {"h3", "h4", "h2", "b", "strong"}
                           and header_text.lower() in tag.get_text(" ", strip=True).lower())
        if not header:
            return exams
        table = header.find_next("table")
        if not table:
            return exams
        headers = [text_of(th) for th in table.find_all("th")]
        col = {h: i for i, h in enumerate(headers)}
        for row in table.find_all("tr"):
            cells = [text_of(td) for td in row.find_all("td")]
            if len(cells) < 3:
                continue
            links = row.find_all("a", href=True)
            action_urls = [a["href"] for a in links]
            entry = {h: cells[i] for i, h in enumerate(headers) if i < len(cells) and h}
            entry["_action_urls"] = action_urls
            exams.append(entry)
        return exams

    registered = _parse_section("Which exam sittings I have registered for")
    available = _parse_section("Which exam sittings I can register for")
    return {"registered": registered, "available": available}
