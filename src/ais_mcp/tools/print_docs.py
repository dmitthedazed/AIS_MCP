"""
Tools: ais_print_document — generate and download study documents from AIS.
"""
from pathlib import Path

from bs4 import BeautifulSoup

from ais_mcp.context import resolve_studium_obdobi
from ais_mcp.parsers import clean_page_text, text_of
from ais_mcp.session import get_session, BASE_URL

PRINT_URL = f"{BASE_URL}/auth/student/tisk_dokumentu.pl"

# doc_type → (param_key, supports_language, supports_seal)
_DOC_TYPES = {
    "confirmation":  ("potvrzeni_tisk",    True,  True),
    "registration":  ("reg_arch_tisk",     False, False),
    "enrollment":    ("zapis_arch_tisk",   False, False),
}

_AVAILABLE_DOCS = [
    {"type": "confirmation",  "name": "Confirmation of study", "sealed": True,  "languages": ["sk", "en"]},
    {"type": "registration",  "name": "Registration sheet",    "sealed": False, "languages": ["sk"]},
    {"type": "enrollment",    "name": "Enrollment sheet",       "sealed": False, "languages": ["sk"]},
]


def tool_list_print_documents(studium: str = None, obdobi: str = None) -> dict:
    """
    List study documents available for download or electronic sealing.
    Returns document types you can pass to ais_print_document.
    """
    studium, _ = resolve_studium_obdobi(studium, obdobi)
    return {
        "studium": studium,
        "documents": _AVAILABLE_DOCS,
        "note": (
            "Use ais_print_document to download a PDF immediately. "
            "Electronic sealing (sealed=True) queues the document to Document Storage "
            "with an e-signature; it appears there within ~1 hour."
        ),
    }


def tool_print_document(
    doc_type: str = "confirmation",
    language: str = "en",
    sealed: bool = False,
    save_to: str | None = None,
    studium: str = None,
    obdobi: str = None,
) -> dict:
    """
    Download a study document as PDF, or trigger electronic sealing.

    doc_type: 'confirmation' | 'registration' | 'enrollment'
    language: 'en' or 'sk' (only confirmation supports English)
    sealed: False (default) = download PDF immediately.
            True = trigger e-seal; document appears in Document Storage within ~1 hour.
    save_to: path or directory to save (default: ~/Downloads/<filename>).

    Returns saved_path, filename, size_bytes for immediate downloads.
    """
    studium, _ = resolve_studium_obdobi(studium, obdobi)

    if doc_type not in _DOC_TYPES:
        return {
            "error": f"Unknown doc_type '{doc_type}'",
            "available": list(_DOC_TYPES.keys()),
        }

    param_key, supports_lang, supports_seal = _DOC_TYPES[doc_type]

    if sealed and not supports_seal:
        return {"error": f"doc_type '{doc_type}' does not support electronic sealing"}

    # Build URL
    param = f"{param_key}_el=1" if sealed else f"{param_key}=1"
    url = f"{PRINT_URL}?{param};studium={studium};lang=en"
    if supports_lang and language == "en":
        url += ";jazyk=eng"

    sess = get_session()
    resp = sess.get(url)

    content_type = resp.headers.get("Content-Type", "")

    if sealed or "text/html" in content_type:
        # Electronic seal: parse response for success/error
        soup = BeautifulSoup(resp.text, "lxml")
        # Look for error or ok messages
        for el in soup.find_all(class_=True):
            cls = " ".join(el.get("class", []))
            txt = el.get_text(strip=True)
            if ("uis_msg" in cls or "ok" in cls or "ko" in cls) and txt:
                status = "error" if "ko" in cls else "queued"
                return {
                    "status": status,
                    "doc_type": doc_type,
                    "language": language,
                    "message": txt,
                    "note": "Check Document Storage (ais_fetch_page) in ~1 hour." if status == "queued" else "",
                }
        return {
            "status": "unknown",
            "doc_type": doc_type,
            "message": clean_page_text(soup)[:400],
        }

    # Direct PDF download
    if "pdf" not in content_type.lower():
        soup = BeautifulSoup(resp.text, "lxml")
        return {
            "status": "error",
            "message": clean_page_text(soup)[:400],
        }

    # Determine filename — AIS always returns "file.pdf", so build a better name
    lang_suffix = f"_{language}" if supports_lang else ""
    filename_hint = f"ais_{doc_type}{lang_suffix}.pdf"

    # Save path
    if save_to:
        dest = Path(save_to)
        if dest.is_dir():
            dest = dest / filename_hint
    else:
        dest = Path.home() / "Downloads" / filename_hint

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)

    return {
        "status": "downloaded",
        "doc_type": doc_type,
        "language": language,
        "saved_path": str(dest),
        "filename": dest.name,
        "size_bytes": len(resp.content),
    }
