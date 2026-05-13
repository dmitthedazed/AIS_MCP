"""
Tool: ais_mail_send — compose and send an internal AIS message.
"""
from pathlib import Path

from bs4 import BeautifulSoup

from ais_mcp.parsers import clean_page_text
from ais_mcp.session import get_session, BASE_URL

COMPOSE_URL = f"{BASE_URL}/auth/posta/nova_zprava.pl"

_MIME = {
    ".pdf": "application/pdf",
    ".zip": "application/zip",
    ".py": "text/x-python",
    ".txt": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".mp4": "video/mp4",
    ".tar": "application/x-tar",
    ".gz": "application/gzip",
    ".7z": "application/x-7z-compressed",
}


def _guess_mime(path: Path) -> str:
    return _MIME.get(path.suffix.lower(), "application/octet-stream")


def _get_compose_tokens() -> dict:
    """Fetch compose page and return all hidden field values."""
    sess = get_session()
    resp = sess.get(f"{COMPOSE_URL}?lang=en")
    soup = BeautifulSoup(resp.text, "lxml")

    fields = {}
    for inp in soup.find_all("input", type="hidden"):
        name = inp.get("name", "")
        if name:
            fields[name] = inp.get("value", "")

    # mfu_id is hidden in the form
    if "mfu_id" not in fields:
        mfu = soup.find("input", {"name": "mfu_id"})
        fields["mfu_id"] = mfu.get("value", "multiuploader") if mfu else "multiuploader"

    if "hash" not in fields:
        raise RuntimeError("Could not extract CSRF hash from compose page")
    return fields


def _ajax_upload(path: Path, hidden: dict) -> None:
    """
    Upload a single file via AJAX (jQuery File Upload protocol).
    AIS links it to the session by hash+serializace; no ID needed in the final POST.
    """
    sess = get_session()
    headers = {"X-Requested-With": "XMLHttpRequest"}
    upload_data = {
        "lang": "en",
        "mfu_id": hidden.get("mfu_id", "multiuploader"),
        "hash": hidden["hash"],
        "serializace": hidden.get("serializace", ""),
    }
    with open(path, "rb") as fh:
        resp = sess.post(
            COMPOSE_URL,
            data=upload_data,
            files={"mfu_upload": (path.name, fh, _guess_mime(path))},
            headers=headers,
            allow_redirects=False,
        )
    if not resp.ok:
        raise RuntimeError(f"File upload failed for {path.name}: HTTP {resp.status_code}")
    try:
        result = resp.json()
        files = result.get("files", [])
        if files and "error" in files[0]:
            raise RuntimeError(f"File upload rejected: {files[0]['error']}")
    except ValueError:
        pass  # non-JSON response is fine if HTTP was 200


def tool_mail_send(
    to: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
    message_type: str = "internal",
    attachments: list[str] | None = None,
    confirm_receipt: bool = False,
    keep_message: bool = False,
    keep_addresses: bool = False,
    save_sent: bool = True,
) -> dict:
    """
    Send an AIS internal message, optionally with file attachments.

    to: recipient login (e.g. 'xsavin') or email address. Separate multiple with semicolons.
    subject: message subject (emoji supported)
    body: plain-text message body (emoji supported)
    cc: CC recipients (optional)
    bcc: BCC recipients (optional)
    message_type: 'internal' (default, AIS-to-AIS) or 'external' (regular email)
    attachments: list of absolute file paths to attach (optional)
    confirm_receipt: request read receipt (default False)
    keep_message: keep message in Unfinished box (default False)
    keep_addresses: remember To/Cc/Bcc for next message (default False)
    save_sent: save copy to Sent folder (default True)

    Returns status and any confirmation/error text from AIS.
    """
    hidden = _get_compose_tokens()

    # Validate and upload attachments before sending
    paths = []
    if attachments:
        for fp in attachments:
            p = Path(fp)
            if not p.exists():
                raise FileNotFoundError(f"Attachment not found: {fp}")
            if not p.is_file():
                raise ValueError(f"Attachment path is not a file: {fp}")
            paths.append(p)
        for p in paths:
            _ajax_upload(p, hidden)

    sess = get_session()
    data = {
        "lang": "en",
        "zprava": "1" if message_type == "internal" else "0",
        "mlist": "",
        "To": to,
        "Cc": cc,
        "Bcc": bcc,
        "Subject": subject,
        "Data": body,
        "mfu_id": hidden.get("mfu_id", "multiuploader"),
        "hash": hidden["hash"],
        "serializace": hidden.get("serializace", ""),
        "akce": "schranka",
        "send": "SEND MESSAGE",
    }
    if "ulozit_do_sl" in hidden:
        data["ulozit_do_sl"] = hidden["ulozit_do_sl"]

    # Checkboxes: only include when checked (unchecked = absent from POST)
    if confirm_receipt:
        data["potvrdit_prijeti_zpravy"] = "1"
    if keep_message:
        data["zachovat_zpravu"] = "1"
    if keep_addresses:
        data["zachovat_adresy"] = "1"
    if save_sent:
        data["ulozit_odesl_zpravu"] = "1"

    resp = sess.post(COMPOSE_URL, data=data, allow_redirects=True)
    soup = BeautifulSoup(resp.text, "lxml")
    text = clean_page_text(soup)

    success = (
        "was sent" in text.lower()
        or "message sent" in text.lower()
        or "Mail folder" in text
        or "slozka" in resp.url
        or (resp.url != f"{COMPOSE_URL}?lang=en" and "nova_zprava" not in resp.url)
    )

    result = {
        "status": "sent" if success else "error",
        "to": to,
        "subject": subject,
        "message": text[:500],
        "final_url": resp.url,
    }
    if paths:
        result["attachments"] = [p.name for p in paths]
    return result
