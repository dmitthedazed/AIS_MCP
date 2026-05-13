"""
Tools: ais_mail_inbox, ais_mail_read, ais_mail_send, ais_mail_reply,
       ais_mail_forward, ais_mail_delete, ais_mail_move, ais_mail_mark_read,
       ais_mail_folders, ais_mail_download_attachment
"""
import re

from bs4 import BeautifulSoup, Tag

from ais_mcp.parsers import text_of
from ais_mcp.session import get_session, BASE_URL

MAIL_FOLDER_URL = f"{BASE_URL}/auth/posta/slozka.pl"
MAIL_READ_URL   = f"{BASE_URL}/auth/posta/email.pl"
COMPOSE_URL     = f"{BASE_URL}/auth/posta/nova_zprava.pl"

FOLDERS = {
    "inbox":      "dosla",
    "sent":       "odeslana",
    "trash":      "kos",
    "spam":       "spam",
    "unfinished": "rozpracovana",
}

_EID_RE = re.compile(r"eid=(\d+)")
_FID_RE = re.compile(r"fid=(\d+)")
_PID_RE = re.compile(r"pid=(\d+)")


def _parse_eid_fid(href: str) -> tuple[str | None, str | None]:
    em = _EID_RE.search(href)
    fm = _FID_RE.search(href)
    return (em.group(1) if em else None), (fm.group(1) if fm else None)


def tool_mail_inbox(folder: str = "inbox", limit: int = 25) -> dict:
    """
    List messages in a mail folder.
    folder: 'inbox' (default), 'sent', 'trash', 'spam', 'unfinished'
    limit: max number of messages to return (default 25)

    Each message includes message_id (eid) and folder_id (fid) for
    ais_mail_read and ais_mail_reply.
    """
    folder_param = FOLDERS.get(folder.lower(), "dosla")
    sess = get_session()
    resp = sess.get(f"{MAIL_FOLDER_URL}?slozka={folder_param}&lang=en")
    soup = BeautifulSoup(resp.text, "lxml")

    messages = []

    # Find only <tr> rows that directly contain an email.pl link — these are message rows
    msg_rows = soup.find_all("a", href=re.compile(r"email\.pl[^\"']*eid="))
    seen_eids: set[str] = set()

    for a_tag in msg_rows:
        row = a_tag.find_parent("tr")
        if row is None:
            continue

        eid, fid = _parse_eid_fid(a_tag["href"])
        if not eid or eid in seen_eids:
            continue
        seen_eids.add(eid)

        # Scan row for attachment indicator and unread status
        has_attachment = any(
            "pid=" in a.get("href", "") for a in row.find_all("a", href=True)
        )
        is_unread = bool(row.find("b")) or "neprecteno" in (row.get("class") or [])

        # Get column headers from the nearest ancestor table's <th> row
        parent_table = row.find_parent("table")
        headers_th: list[str] = []
        if parent_table:
            th_row = parent_table.find("tr", lambda r: r.find("th"))
            if th_row:
                headers_th = [text_of(th).strip() for th in th_row.find_all("th")]

        # Map cells positionally to headers
        cells = row.find_all("td")
        cell_texts = [text_of(td).strip() for td in cells]
        entry: dict = {}
        for i, h in enumerate(headers_th):
            if h and i < len(cell_texts):
                val = cell_texts[i]
                if val:
                    entry[h.lower()] = val

        entry["message_id"]    = eid
        entry["folder_id"]     = fid
        entry["unread"]        = is_unread
        entry["has_attachment"] = has_attachment
        messages.append(entry)

        if len(messages) >= limit:
            break

    return {
        "folder": folder,
        "count": len(messages),
        "messages": messages[:limit],
    }


def _parse_mail_page(soup: BeautifulSoup) -> dict:
    """
    Parse an email.pl page into structured fields:
    headers (from/subject/to/received/size), body text, attachments list.
    """
    # ── Headers ────────────────────────────────────────────────────────────────
    # Find the inner "Headers" table (has a <th> with text "Headers")
    headers: dict[str, str] = {}
    _HEADER_LABELS = {"from", "subject", "to", "cc", "received", "sent", "size", "tags"}
    headers_table = None
    for th in soup.find_all("th"):
        if "header" in text_of(th).lower():
            headers_table = th.find_parent("table")
            break
    if headers_table is None:
        # fallback: find a table whose direct-child <tr> rows look like label/value pairs
        for table in soup.find_all("table"):
            direct_rows = table.find_all("tr", recursive=False) or table.find("tbody", recursive=False) and table.find("tbody").find_all("tr", recursive=False) or []
            for row in (direct_rows or table.find_all("tr"))[:3]:
                cols = row.find_all("td", recursive=False)
                if len(cols) == 2 and text_of(cols[0]).strip().lower() in _HEADER_LABELS:
                    headers_table = table
                    break
            if headers_table:
                break

    if headers_table:
        for row in headers_table.find_all("tr"):
            cols = row.find_all("td", class_="odsazena")
            if len(cols) >= 2:
                key = text_of(cols[0]).strip().lower()
                val = text_of(cols[1]).strip()
                if key in _HEADER_LABELS and val:
                    headers[key] = val

    # ── Body ───────────────────────────────────────────────────────────────────
    body = ""
    # Body is in <td class="odsazena" colspan="2" align="left"> with no child table
    for td in soup.find_all("td", class_="odsazena"):
        if td.get("colspan") == "2" and td.get("align") == "left" and not td.find("table"):
            body = td.get_text(separator="\n").strip()
            if body:
                break
    # Fallback: look for <pre> or <div> with message body
    if not body:
        for tag in soup.find_all(["pre", "div"], class_=re.compile(r"body|text|zprava", re.I)):
            body = tag.get_text(separator="\n").strip()
            if body:
                break

    # ── Attachments ────────────────────────────────────────────────────────────
    attachments = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "email.pl" in href and "pid=" in href:
            pm = _PID_RE.search(href)
            raw = text_of(a).strip()
            # Parse "filename.ext [mime/type, X KiB ]"
            m = re.match(r"^(.+?)\s*\[([^,\]]+),\s*([^\]]+)\]", raw)
            if m:
                attachments.append({
                    "name":     m.group(1).strip(),
                    "mime":     m.group(2).strip(),
                    "size":     m.group(3).strip(),
                    "pid":      pm.group(1) if pm else None,
                    "url": href if href.startswith("http") else BASE_URL + "/auth/posta/" + href.lstrip("./"),
                })
            elif raw:
                attachments.append({
                    "name": raw, "pid": pm.group(1) if pm else None,
                    "url": href if href.startswith("http") else BASE_URL + "/auth/posta/" + href.lstrip("./"),
                })

    return {"headers": headers, "body": body, "attachments": attachments}


def tool_mail_read(message_id: str, folder_id: str = "789370") -> dict:
    """
    Read a specific message with structured output.
    message_id: eid from ais_mail_inbox.
    folder_id: fid from ais_mail_inbox (default: inbox fid).

    Returns: from, subject, to, received, size, body, attachments[].
    """
    sess = get_session()
    resp = sess.get(f"{MAIL_READ_URL}?eid={message_id};fid={folder_id};lang=en")
    soup = BeautifulSoup(resp.text, "lxml")
    parsed = _parse_mail_page(soup)

    return {
        "message_id": message_id,
        "folder_id":  folder_id,
        **parsed["headers"],
        "body":        parsed["body"],
        "attachments": parsed["attachments"],
    }


def tool_mail_download_attachment(
    message_id: str,
    pid: str,
    folder_id: str = "789370",
    save_to: str | None = None,
) -> dict:
    """
    Download a mail attachment to a local file.

    message_id: eid from ais_mail_read.
    pid: attachment pid from ais_mail_read attachments list.
    folder_id: fid from ais_mail_read (default: inbox).
    save_to: absolute path to save the file. Defaults to ~/Downloads/<filename>.

    Returns: saved_path, filename, size_bytes, content_type.
    """
    import os
    from pathlib import Path

    sess = get_session()
    url = f"{MAIL_READ_URL}?fid={folder_id};eid={message_id};pid={pid};lang=en"
    resp = sess.get(url, allow_redirects=True)

    if not resp.ok:
        raise RuntimeError(f"Download failed: HTTP {resp.status_code}")

    # Extract filename from Content-Disposition or URL
    content_disp = resp.headers.get("Content-Disposition", "")
    fname_match = re.search(r'filename="?([^";\r\n]+)"?', content_disp)
    filename = fname_match.group(1).strip() if fname_match else f"attachment_{pid}"

    if save_to:
        dest = Path(save_to)
        if dest.is_dir():
            dest = dest / filename
    else:
        downloads = Path.home() / "Downloads"
        downloads.mkdir(exist_ok=True)
        dest = downloads / filename

    dest.write_bytes(resp.content)

    return {
        "saved_path":    str(dest),
        "filename":      filename,
        "size_bytes":    len(resp.content),
        "content_type":  resp.headers.get("Content-Type", ""),
    }


def _get_reply_tokens(eid: str, fid: str, action: str = "odpovedet") -> dict:
    """
    Fetch reply/forward compose page and extract all form tokens + pre-filled fields.
    action: 'odpovedet' (reply) or 'preposlat' (forward).
    """
    sess = get_session()
    resp = sess.get(f"{COMPOSE_URL}?fid={fid};eid={eid};menu_akce={action};lang=en")
    soup = BeautifulSoup(resp.text, "lxml")

    fields: dict = {}
    for inp in soup.find_all("input", type="hidden"):
        name = inp.get("name", "")
        if name:
            fields[name] = inp.get("value", "")

    if "mfu_id" not in fields:
        mfu = soup.find("input", {"name": "mfu_id"})
        fields["mfu_id"] = mfu.get("value", "multiuploader") if mfu else "multiuploader"

    for name in ("To", "Cc", "Subject"):
        inp = soup.find("input", {"name": name})
        if inp:
            fields[f"_pre_{name}"] = inp.get("value", "")

    ta = soup.find("textarea", {"name": "Data"})
    if ta:
        fields["_pre_Data"] = ta.get_text()

    if "hash" not in fields:
        raise RuntimeError(f"Could not extract CSRF hash from reply page (eid={eid})")
    return fields


def tool_mail_reply(
    message_id: str,
    body: str,
    folder_id: str = "789370",
    quote_original: bool = True,
    attachments: list[str] | None = None,
    save_sent: bool = True,
) -> dict:
    """
    Reply to an AIS message.

    message_id: eid from ais_mail_inbox.
    folder_id:  fid from ais_mail_inbox.
    body: your reply text (emoji supported).
    quote_original: prepend original quoted message below your text (default True).
    attachments: list of absolute file paths to attach (optional).
    save_sent: save copy to Sent folder (default True).

    CAUTION: This sends a real message.
    """
    from ais_mcp.tools.mail_send import _ajax_upload
    from pathlib import Path

    hidden = _get_reply_tokens(message_id, folder_id, "odpovedet")

    paths = []
    if attachments:
        for fp in attachments:
            p = Path(fp)
            if not p.exists():
                raise FileNotFoundError(f"Attachment not found: {fp}")
            if not p.is_file():
                raise ValueError(f"Not a file: {fp}")
            paths.append(p)
        for p in paths:
            _ajax_upload(p, hidden)

    quoted = hidden.get("_pre_Data", "")
    data_body = f"{body}\n{quoted}" if quote_original and quoted else body

    sess = get_session()
    post_data = {
        "lang":        "en",
        "zprava":      "1",
        "mlist":       "",
        "To":          hidden.get("_pre_To", ""),
        "Cc":          hidden.get("_pre_Cc", ""),
        "Bcc":         "",
        "Subject":     hidden.get("_pre_Subject", ""),
        "Data":        data_body,
        "mfu_id":      hidden.get("mfu_id", "multiuploader"),
        "hash":        hidden["hash"],
        "serializace": hidden.get("serializace", ""),
        "old_fid":     hidden.get("old_fid", folder_id),
        "old_eid":     hidden.get("old_eid", message_id),
        "fid":         hidden.get("fid", folder_id),
        "eid":         hidden.get("eid", message_id),
        "menu_akce":   "odpovedet",
        "akce":        "schranka",
        "send":        "SEND MESSAGE",
    }
    if "ulozit_do_sl" in hidden:
        post_data["ulozit_do_sl"] = hidden["ulozit_do_sl"]
    if save_sent:
        post_data["ulozit_odesl_zpravu"] = "1"
    if "pridane_prilohy" in hidden:
        post_data["pridane_prilohy"] = hidden["pridane_prilohy"]

    resp = sess.post(COMPOSE_URL, data=post_data, allow_redirects=True)
    soup = BeautifulSoup(resp.text, "lxml")

    # Check success by URL redirect
    success = "slozka" in resp.url or "nova_zprava" not in resp.url

    result = {
        "status":      "sent" if success else "error",
        "replied_to":  message_id,
        "to":          post_data["To"],
        "subject":     post_data["Subject"],
        "final_url":   resp.url,
    }
    if not success:
        parsed = _parse_mail_page(soup)
        result["error_detail"] = parsed["body"][:300]
    if paths:
        result["attachments"] = [p.name for p in paths]
    return result


# ── Single-message write actions ──────────────────────────────────────────────

def _msg_action(message_id: str, folder_id: str, **extra_fields) -> dict:
    """POST action form on email.pl for a single message."""
    sess = get_session()
    data = {"lang": "en", "fid": folder_id, "eid": message_id, **extra_fields}
    resp = sess.post(MAIL_READ_URL, data=data, allow_redirects=True)
    success = resp.ok and "nova_zprava" not in resp.url
    return {"status": "ok" if success else "error", "final_url": resp.url}


def tool_mail_delete(message_id: str, folder_id: str = "789370") -> dict:
    """
    Delete (move to Trash) a single message.
    message_id: eid from ais_mail_inbox.
    folder_id: fid from ais_mail_inbox.
    CAUTION: Moves message to Trash.
    """
    return _msg_action(message_id, folder_id, smazat="Delete")


def tool_mail_move(
    message_id: str,
    folder_id: str,
    target_folder_id: str,
) -> dict:
    """
    Move a message to another folder.
    message_id: eid from ais_mail_inbox.
    folder_id: current fid from ais_mail_inbox.
    target_folder_id: destination fid from ais_mail_folders.
    CAUTION: Moves the message.
    """
    return _msg_action(
        message_id, folder_id,
        menu_akce="presunout",
        menu_slozka=target_folder_id,
        provest_akci="Go",
    )


def tool_mail_spam(message_id: str, folder_id: str = "789370") -> dict:
    """
    Mark a message as spam and delete it.
    message_id: eid from ais_mail_inbox.
    folder_id: fid from ais_mail_inbox.
    CAUTION: Marks as spam and removes from inbox.
    """
    return _msg_action(message_id, folder_id, spam="Tick as spam*")


# ── Bulk actions (one or many messages) ───────────────────────────────────────

def _bulk_action(
    message_ids: list[str],
    folder_id: str,
    action: str,
    target_folder_id: str = "0",
) -> dict:
    """
    POST a bulk action on slozka.pl for the given eids.
    action: 'precteno' | 'neprecteno' | 'vymazat' | 'presunout' | 'spam'
    """
    sess = get_session()
    data = [
        ("lang", "en"),
        ("fid", folder_id),
        ("on", "0"),
        ("menu_data", "oznacene"),
        ("menu_akce", action),
        ("menu_slozka", target_folder_id),
        ("cela_stranka", ",".join(message_ids)),
        ("provest_akci", "Go"),
    ]
    for eid in message_ids:
        data.append(("email", eid))
    resp = sess.post(MAIL_FOLDER_URL, data=data, allow_redirects=True)
    return {
        "status": "ok" if resp.ok else "error",
        "affected": len(message_ids),
        "final_url": resp.url,
    }


def tool_mail_mark_read(
    message_ids: list[str],
    folder_id: str = "789370",
    unread: bool = False,
) -> dict:
    """
    Mark one or more messages as read or unread.
    message_ids: list of eid values from ais_mail_inbox.
    folder_id: fid from ais_mail_inbox.
    unread: True = mark as unread, False = mark as read (default).
    """
    action = "neprecteno" if unread else "precteno"
    return _bulk_action(message_ids, folder_id, action)


def tool_mail_delete_bulk(
    message_ids: list[str],
    folder_id: str = "789370",
) -> dict:
    """
    Delete multiple messages at once (move to Trash).
    message_ids: list of eid values from ais_mail_inbox.
    folder_id: fid from ais_mail_inbox.
    CAUTION: Moves all listed messages to Trash.
    """
    return _bulk_action(message_ids, folder_id, "vymazat")


def tool_mail_move_bulk(
    message_ids: list[str],
    folder_id: str,
    target_folder_id: str,
) -> dict:
    """
    Move multiple messages to another folder.
    message_ids: list of eid values from ais_mail_inbox.
    folder_id: current fid.
    target_folder_id: destination fid from ais_mail_folders.
    CAUTION: Moves all listed messages.
    """
    return _bulk_action(message_ids, folder_id, "presunout", target_folder_id)


# ── Folders ────────────────────────────────────────────────────────────────────

def tool_mail_folders() -> dict:
    """
    List all mail folders with their folder_id (fid), name, and message counts.
    Use folder_id values for ais_mail_inbox, ais_mail_move, etc.
    """
    sess = get_session()
    resp = sess.get(f"{MAIL_FOLDER_URL}?lang=en")
    soup = BeautifulSoup(resp.text, "lxml")

    folders = []
    seen: set[str] = set()

    # Folders are in div.node-container[id=fid] inside a .tree div
    for node in soup.find_all("div", class_="node-container"):
        fid = node.get("id", "")
        if not fid.isdigit() or fid in seen:
            continue
        seen.add(fid)
        label = node.find(class_="node-label")
        raw = label.get_text(" ", strip=True) if label else ""
        m = re.search(r"(.+?)\s*\(\s*(\d+)\s*(?:/\s*(\d+))?\s*\)", raw)
        if m:
            folders.append({
                "folder_id": fid,
                "name":      m.group(1).strip(),
                "unread":    int(m.group(2)),
                "total":     int(m.group(3)) if m.group(3) else int(m.group(2)),
            })
        elif raw:
            folders.append({"folder_id": fid, "name": raw, "unread": 0, "total": 0})

    return {"folders": folders}


# ── Forward ────────────────────────────────────────────────────────────────────

def tool_mail_forward(
    message_id: str,
    to: str,
    folder_id: str = "789370",
    body: str = "",
    include_original: bool = True,
    attachments: list[str] | None = None,
    save_sent: bool = True,
) -> dict:
    """
    Forward a message to a new recipient.
    message_id: eid from ais_mail_inbox.
    to: new recipient login or email. Separate multiple with semicolons.
    folder_id: fid from ais_mail_inbox.
    body: optional text to prepend before the forwarded message.
    include_original: include the original quoted message (default True).
    attachments: additional files to attach (optional).
    save_sent: save copy to Sent folder (default True).
    CAUTION: This sends a real message.
    """
    from ais_mcp.tools.mail_send import _ajax_upload
    from pathlib import Path

    hidden = _get_reply_tokens(message_id, folder_id, "preposlat")

    paths = []
    if attachments:
        for fp in attachments:
            p = Path(fp)
            if not p.exists():
                raise FileNotFoundError(f"Attachment not found: {fp}")
            paths.append(p)
        for p in paths:
            _ajax_upload(p, hidden)

    quoted = hidden.get("_pre_Data", "")
    data_body = (f"{body}\n{quoted}" if body else quoted) if include_original else body

    sess = get_session()
    post_data = {
        "lang":        "en",
        "zprava":      "1",
        "mlist":       "",
        "To":          to,
        "Cc":          "",
        "Bcc":         "",
        "Subject":     hidden.get("_pre_Subject", ""),
        "Data":        data_body,
        "mfu_id":      hidden.get("mfu_id", "multiuploader"),
        "hash":        hidden["hash"],
        "serializace": hidden.get("serializace", ""),
        "old_fid":     hidden.get("old_fid", folder_id),
        "old_eid":     hidden.get("old_eid", message_id),
        "fid":         hidden.get("fid", folder_id),
        "eid":         hidden.get("eid", message_id),
        "menu_akce":   "preposlat",
        "akce":        "schranka",
        "send":        "SEND MESSAGE",
    }
    if "ulozit_do_sl" in hidden:
        post_data["ulozit_do_sl"] = hidden["ulozit_do_sl"]
    if save_sent:
        post_data["ulozit_odesl_zpravu"] = "1"
    if "pridane_prilohy" in hidden:
        post_data["pridane_prilohy"] = hidden["pridane_prilohy"]

    resp = sess.post(COMPOSE_URL, data=post_data, allow_redirects=True)
    success = "slozka" in resp.url or "nova_zprava" not in resp.url

    result = {
        "status":      "sent" if success else "error",
        "forwarded":   message_id,
        "to":          to,
        "subject":     post_data["Subject"],
        "final_url":   resp.url,
    }
    if paths:
        result["attachments"] = [p.name for p in paths]
    return result
