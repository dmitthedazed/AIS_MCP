"""
Tool: ais_submit_file — upload a file to a coursework submission box.
"""
import os
from pathlib import Path

from bs4 import BeautifulSoup

from ais_mcp.context import resolve_studium_obdobi
from ais_mcp.parsers import clean_page_text, text_of
from ais_mcp.session import get_session, BASE_URL

SUBMIT_URL = f"{BASE_URL}/auth/student/odevzdavarny_odevzdani.pl"
LIST_URL = f"{BASE_URL}/auth/student/odevzdavarny.pl"


def _get_submission_tokens(odevzdavarna: str, studium: str, obdobi: str):
    """Fetch the submission page and extract CSRF hash + hidden fields."""
    sess = get_session()
    url = (f"{SUBMIT_URL}?studium={studium};obdobi={obdobi}"
           f";odevzdavarna={odevzdavarna}&lang=en")
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "lxml")

    hidden = {}
    # Find the upload form (has mfu_upload file field)
    for form in soup.find_all("form"):
        inputs = form.find_all("input")
        field_names = [i.get("name", "") for i in inputs]
        if "mfu_upload" in field_names or "hash" in field_names:
            for inp in inputs:
                name = inp.get("name")
                if name and inp.get("type") != "file":
                    hidden[name] = inp.get("value", "")
            break

    if "hash" not in hidden:
        raise RuntimeError(
            f"Could not find upload form for odevzdavarna={odevzdavarna}. "
            "Check that the submission box is open and the ID is correct."
        )
    return hidden, resp.url


def tool_list_open_submissions(studium: str = None, obdobi: str = None) -> dict:
    """
    List submission boxes that are currently open for file upload.
    Returns odevzdavarna IDs you can pass to ais_submit_file.
    """
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    sess = get_session()
    resp = sess.get(f"{LIST_URL}?studium={studium};obdobi={obdobi}&lang=en")
    soup = BeautifulSoup(resp.text, "lxml")

    boxes = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "odevzdavarny_odevzdani.pl" in href and "odevzdavarna=" in href:
            import re
            m = re.search(r"odevzdavarna=(\d+)", href)
            if m:
                oid = m.group(1)
                # Find surrounding context (course name, box name)
                row = a.find_parent("tr")
                cells = [text_of(td) for td in row.find_all("td")] if row else []
                boxes.append({
                    "odevzdavarna_id": oid,
                    "details": " | ".join(c for c in cells if c),
                    "url": BASE_URL + href if href.startswith("/") else href,
                })

    # Deduplicate by odevzdavarna_id
    seen = set()
    unique = []
    for b in boxes:
        if b["odevzdavarna_id"] not in seen:
            seen.add(b["odevzdavarna_id"])
            unique.append(b)

    return {
        "studium": studium,
        "obdobi": obdobi,
        "open_submissions": unique,
    }


def tool_submit_file(
    odevzdavarna_id: str,
    file_path: str,
    description: str = "",
    studium: str = None,
    obdobi: str = None,
) -> dict:
    """
    Upload a file to a coursework submission box.

    odevzdavarna_id: submission box ID — get it from ais_list_open_submissions.
    file_path: absolute path to the file to upload.
    description: optional description for the file.

    Returns upload status and confirmation text.
    """
    studium, obdobi = resolve_studium_obdobi(studium, obdobi)
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    hidden, page_url = _get_submission_tokens(odevzdavarna_id, studium, obdobi)
    sess = get_session()

    # Build multipart POST
    with open(path, "rb") as fh:
        files = {"mfu_upload": (path.name, fh, _guess_mime(path))}
        data = {k: v for k, v in hidden.items() if k != "mfu_upload"}
        if description:
            data["popis"] = description
        data["lang"] = "en"

        resp = sess.post(SUBMIT_URL, data=data, files=files, allow_redirects=True)

    soup = BeautifulSoup(resp.text, "lxml")
    text = clean_page_text(soup)

    success = (
        path.name in resp.text
        or "inserted" in text.lower()
        or "entered" in text.lower()
        or "uploaded" in text.lower()
        or "was inserted" in text.lower()
    )

    return {
        "status": "uploaded" if success else "error",
        "file": path.name,
        "odevzdavarna_id": odevzdavarna_id,
        "message": text[:600],
        "final_url": resp.url,
    }


def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".zip": "application/zip",
        ".py": "text/x-python",
        ".txt": "text/plain",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(ext, "application/octet-stream")
