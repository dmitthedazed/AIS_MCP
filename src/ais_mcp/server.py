"""
AIS MCP server — STU is.stuba.sk for Claude Code / Claude Desktop.
"""
from mcp.server.fastmcp import FastMCP

from ais_mcp.tools.auth import tool_whoami, tool_eduroam_credentials
from ais_mcp.tools.people import tool_search_people, tool_get_person
from ais_mcp.tools.portal import tool_list_studies, tool_portal_menu, tool_contact_departments
from ais_mcp.tools.academics import (
    tool_grades, tool_grades_all, tool_plan_progress, tool_course_eplans,
    tool_study_details, tool_schoolmates, tool_excuse_notes, tool_course_syllabus,
    tool_course_grade_stats,
)
from ais_mcp.tools.schedule import tool_schedule, tool_academic_calendar, tool_year_schedule
from ais_mcp.tools.exams import tool_list_exams, tool_register_exam, tool_unregister_exam
from ais_mcp.tools.courses import tool_course_registration
from ais_mcp.tools.thesis import tool_thesis_topics, tool_submissions
from ais_mcp.tools.finance import tool_financing, tool_scholarships, tool_orders
from ais_mcp.tools.mail import (
    tool_mail_inbox, tool_mail_read, tool_mail_reply, tool_mail_forward,
    tool_mail_download_attachment, tool_mail_delete, tool_mail_move,
    tool_mail_spam, tool_mail_mark_read, tool_mail_delete_bulk,
    tool_mail_move_bulk, tool_mail_folders,
)
from ais_mcp.tools.documents import tool_documents, tool_noticeboard
from ais_mcp.tools.generic import tool_fetch_page
from ais_mcp.tools.mail_send import tool_mail_send
from ais_mcp.tools.submit_file import tool_list_open_submissions, tool_submit_file
from ais_mcp.tools.print_docs import tool_list_print_documents, tool_print_document
from ais_mcp.tools.lectures import tool_lectures_sheet, tool_course_progress, tool_test_detail

app = FastMCP(
    "ais",
    instructions=(
        "MCP server for STU AIS (is.stuba.sk). "
        "Requires AIS_USERNAME and AIS_PASSWORD environment variables. "
        "All student tools auto-detect the active studium/obdobi on first call. "
        "Credentials are cached in ~/.cache/ais-mcp/cookies.json (mode 600)."
    ),
)

# ── System / auth ────────────────────────────────────────────────────────────
@app.tool(name="ais_whoami")
def ais_whoami() -> dict:
    """Return current logged-in user and active study context (studium, obdobi)."""
    return tool_whoami()


@app.tool(name="ais_eduroam_credentials")
def ais_eduroam_credentials() -> dict:
    """Return eduroam/wifi credentials (login, password, validity) from AIS."""
    return tool_eduroam_credentials()


# ── People ───────────────────────────────────────────────────────────────────
@app.tool(name="ais_search_people")
def ais_search_people(
    query: str,
    students: bool = True,
    staff: bool = True,
    graduates: bool = False,
    external: bool = False,
    suggest: bool = True,
) -> dict:
    """
    Search the STU people directory.
    query: at least 3 characters (name or login).
    suggest=True is faster (autocomplete, max 50 results).
    suggest=False does a full paginated search.
    """
    return tool_search_people(query, students, staff, graduates, external, suggest)


@app.tool(name="ais_get_person")
def ais_get_person(id_or_url: str) -> dict:
    """
    Fetch full profile of a person.
    Pass a numeric person ID or a full is.stuba.sk URL.
    """
    return tool_get_person(id_or_url)


# ── Portal / studies ─────────────────────────────────────────────────────────
@app.tool(name="ais_list_studies")
def ais_list_studies() -> dict:
    """List all studies and study periods in your AIS account."""
    return tool_list_studies()


@app.tool(name="ais_portal_menu")
def ais_portal_menu(studium: str = None, obdobi: str = None) -> dict:
    """
    Return all links/applications from the Student's portal main page,
    grouped by category. Useful for discovering available AIS features.
    """
    return tool_portal_menu(studium, obdobi)


@app.tool(name="ais_contact_departments")
def ais_contact_departments(fakulta: str = "30") -> dict:
    """
    Return Study Department contact info for a faculty.
    Includes: address, phone, email, office hours, contact persons with fields of activity,
    faculty vice-deans.
    fakulta: 30=FEI (default), 10=SvF, 20=SjF, 40=FCHPT, 50=FAD, 60=MTF, 70=FIIT.
    """
    return tool_contact_departments(fakulta)


# ── Academics ────────────────────────────────────────────────────────────────
@app.tool(name="ais_grades")
def ais_grades(studium: str = None, obdobi: str = None) -> dict:
    """
    Return courses and exam results for the current study period.
    Each course: code, name, completion type, attempts, result, credits.
    """
    return tool_grades(studium, obdobi)


@app.tool(name="ais_grades_all")
def ais_grades_all(studium: str = None) -> dict:
    """Return full study record across all periods."""
    return tool_grades_all(studium)


@app.tool(name="ais_plan_progress")
def ais_plan_progress(studium: str = None, obdobi: str = None) -> dict:
    """Return study plan progress: obligatory/optional/elective credit completion."""
    return tool_plan_progress(studium, obdobi)


@app.tool(name="ais_course_eplans")
def ais_course_eplans(studium: str = None, obdobi: str = None) -> dict:
    """Return list of course e-plans (syllabi) for the current period."""
    return tool_course_eplans(studium, obdobi)


@app.tool(name="ais_study_details")
def ais_study_details(studium: str = None, obdobi: str = None) -> dict:
    """
    Return detailed study info: programme, study field, form, credits enrolled/obtained,
    degree, start date, admission resolution, financing, thesis topic/supervisor,
    ISIC card number. Also shows study interruptions and trips abroad.
    """
    return tool_study_details(studium, obdobi)


@app.tool(name="ais_schoolmates")
def ais_schoolmates(
    studium: str = None,
    obdobi: str = None,
    course_code: str = None,
    group: str = "all",
) -> dict:
    """
    List classmates by course.
    Without course_code: return courses you share with others this period.
    With course_code (e.g. 'B-MAT2'): fetch the full student list (all pages).
    group: 'all' (default) | 'seminar' (your seminar group) | 'teacher' (same teacher group).
    Each student: name, person_id (pass to ais_get_person), study_info.
    """
    return tool_schoolmates(studium, obdobi, course_code, group)


@app.tool(name="ais_course_syllabus")
def ais_course_syllabus(predmet_id: str) -> dict:
    """
    Return the full course syllabus from the AIS catalogue.
    predmet_id: numeric course ID — from ais_lectures_sheet, ais_course_progress, or plan progress links.
    Returns: code, title, credits, hours, prerequisites, learning outcomes,
             assessment criteria, grade distribution, literature, supervisor.
    """
    return tool_course_syllabus(predmet_id)


@app.tool(name="ais_course_grade_stats")
def ais_course_grade_stats(
    predmet_id: str,
    obdobi: str,
    fakulta: str = "30",
) -> dict:
    """
    Return grade distribution for a course in a completed period.
    predmet_id: numeric course ID — from ais_lectures_sheet courses[].predmet_id.
    obdobi: period ID — must be a completed period (current period is not available).
            Known periods: 705=WS 2025/2026, 693=SS 2024/2025, 692=WS 2024/2025.
    fakulta: faculty code — default 30 (FEI). Other codes: SvF=10, SjF=20, FCHPT=40, FAD=50, MTF=60, FIIT=70.
    Returns: terms list with A/B/C/D/E/FX counts per exam sitting, plus attendance totals.
    """
    return tool_course_grade_stats(predmet_id, obdobi, fakulta)


@app.tool(name="ais_excuse_notes")
def ais_excuse_notes(
    studium: str = None,
    obdobi: str = None,
    include_history: bool = False,
) -> dict:
    """
    Return absence/excuse notes submitted to the Study Department.
    Each note: since, until, reason for absence, specifications.
    include_history: True = show all past records across all periods.
    """
    return tool_excuse_notes(studium, obdobi, include_history)


# ── Schedule ─────────────────────────────────────────────────────────────────
@app.tool(name="ais_schedule")
def ais_schedule(rozvrh_student: str = None) -> dict:
    """
    Return personal weekly timetable as {Monday: [...], Tuesday: [...], ...}.
    Each event: room, course, teacher.
    rozvrh_student: numeric ID (auto-detected if omitted).
    """
    return tool_schedule(rozvrh_student)


@app.tool(name="ais_academic_calendar")
def ais_academic_calendar(studium: str = None, obdobi: str = None) -> dict:
    """Return academic calendar weeks overview (week numbers, dates, types)."""
    return tool_academic_calendar(studium, obdobi)


@app.tool(name="ais_year_schedule")
def ais_year_schedule(obdobi: str = None, fakulta: str = "30") -> dict:
    """
    Return academic year schedule: exam periods, holidays, registration windows.
    fakulta: faculty code, default 30 (FEI).
    """
    return tool_year_schedule(obdobi, fakulta)


# ── Exams ────────────────────────────────────────────────────────────────────
@app.tool(name="ais_list_exams")
def ais_list_exams(
    studium: str = None,
    obdobi: str = None,
    mode: str = "available",
    course_code: str = None,
) -> dict:
    """
    List exam dates.
    mode: 'available' (default) | 'registered' | 'past' | 'all'
    course_code: optional filter, e.g. 'B-MAT2'
    Returns exam_id needed for ais_register_exam / ais_unregister_exam.
    """
    return tool_list_exams(studium, obdobi, mode, course_code)


@app.tool(name="ais_register_exam")
def ais_register_exam(exam_id: str, studium: str = None, obdobi: str = None) -> dict:
    """
    Register for an exam date. exam_id from ais_list_exams.
    CAUTION: This performs a real write action in AIS.
    """
    return tool_register_exam(exam_id, studium, obdobi)


@app.tool(name="ais_unregister_exam")
def ais_unregister_exam(exam_id: str, studium: str = None, obdobi: str = None) -> dict:
    """
    Unregister from an exam date. exam_id from ais_list_exams.
    CAUTION: This performs a real write action in AIS.
    """
    return tool_unregister_exam(exam_id, studium, obdobi)


# ── Courses & thesis ─────────────────────────────────────────────────────────
@app.tool(name="ais_course_registration")
def ais_course_registration(studium: str = None, obdobi: str = None) -> dict:
    """Return course enrollment/registration status for the current period."""
    return tool_course_registration(studium, obdobi)


@app.tool(name="ais_thesis_topics")
def ais_thesis_topics(studium: str = None, obdobi: str = None) -> dict:
    """Return thesis/diploma topics list for selection."""
    return tool_thesis_topics(studium, obdobi)


@app.tool(name="ais_submissions")
def ais_submissions(studium: str = None, obdobi: str = None) -> dict:
    """Return coursework and project submission boxes with deadlines."""
    return tool_submissions(studium, obdobi)


# ── Finance ──────────────────────────────────────────────────────────────────
@app.tool(name="ais_financing")
def ais_financing(studium: str = None, obdobi: str = None) -> dict:
    """Return study financing history and current financing status (ME SK, etc.)."""
    return tool_financing(studium, obdobi)


@app.tool(name="ais_scholarships")
def ais_scholarships(studium: str = None, obdobi: str = None) -> dict:
    """Return paid-out scholarships list."""
    return tool_scholarships(studium, obdobi)


@app.tool(name="ais_orders")
def ais_orders(studium: str = None, obdobi: str = None) -> dict:
    """Return financial orders (ISIC, transport card, etc.)."""
    return tool_orders(studium, obdobi)


# ── Communication ─────────────────────────────────────────────────────────────
@app.tool(name="ais_mail_inbox")
def ais_mail_inbox(folder: str = "inbox", limit: int = 25) -> dict:
    """
    List AIS internal messages.
    folder: 'inbox' (default), 'sent', 'trash', 'spam', 'unfinished'
    limit: max messages to return (default 25)
    """
    return tool_mail_inbox(folder, limit)


@app.tool(name="ais_mail_read")
def ais_mail_read(message_id: str, folder_id: str = "789370") -> dict:
    """
    Read a specific AIS message.
    message_id: eid from ais_mail_inbox.
    folder_id: fid from ais_mail_inbox (default: inbox).
    """
    return tool_mail_read(message_id, folder_id)


@app.tool(name="ais_mail_download_attachment")
def ais_mail_download_attachment(
    message_id: str,
    pid: str,
    folder_id: str = "789370",
    save_to: str | None = None,
) -> dict:
    """
    Download a mail attachment to a local file.
    message_id: eid from ais_mail_read.
    pid: attachment pid from ais_mail_read attachments[].pid.
    folder_id: fid from ais_mail_read (default: inbox).
    save_to: absolute path or directory to save the file (default: ~/Downloads/<filename>).
    Returns saved_path, filename, size_bytes, content_type.
    """
    return tool_mail_download_attachment(message_id, pid, folder_id, save_to)


@app.tool(name="ais_mail_reply")
def ais_mail_reply(
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
    folder_id: fid from ais_mail_inbox.
    body: reply text (emoji supported).
    quote_original: include original quoted message below your text (default True).
    attachments: list of absolute file paths to attach (optional).
    save_sent: save copy to Sent folder (default True).
    CAUTION: This sends a real message.
    """
    return tool_mail_reply(message_id, body, folder_id, quote_original, attachments, save_sent)


@app.tool(name="ais_mail_forward")
def ais_mail_forward(
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
    to: recipient login or email. Separate multiple with semicolons.
    folder_id: fid from ais_mail_inbox.
    body: optional text to prepend before the forwarded content.
    include_original: include the original quoted message (default True).
    attachments: additional files to attach (optional).
    CAUTION: This sends a real message.
    """
    return tool_mail_forward(message_id, to, folder_id, body, include_original, attachments, save_sent)


@app.tool(name="ais_mail_folders")
def ais_mail_folders() -> dict:
    """
    List all mail folders with folder_id (fid), name, unread count, total count.
    Use folder_id values in ais_mail_inbox, ais_mail_move, ais_mail_move_bulk.
    """
    return tool_mail_folders()


@app.tool(name="ais_mail_delete")
def ais_mail_delete(message_id: str, folder_id: str = "789370") -> dict:
    """
    Move a single message to Trash.
    message_id: eid from ais_mail_inbox. folder_id: fid from ais_mail_inbox.
    CAUTION: Deletes the message (moves to Trash).
    """
    return tool_mail_delete(message_id, folder_id)


@app.tool(name="ais_mail_delete_bulk")
def ais_mail_delete_bulk(message_ids: list[str], folder_id: str = "789370") -> dict:
    """
    Move multiple messages to Trash in one request.
    message_ids: list of eid values. folder_id: fid from ais_mail_inbox.
    CAUTION: Deletes all listed messages.
    """
    return tool_mail_delete_bulk(message_ids, folder_id)


@app.tool(name="ais_mail_move")
def ais_mail_move(message_id: str, folder_id: str, target_folder_id: str) -> dict:
    """
    Move a message to another folder.
    message_id: eid. folder_id: current fid. target_folder_id: destination fid from ais_mail_folders.
    CAUTION: Moves the message.
    """
    return tool_mail_move(message_id, folder_id, target_folder_id)


@app.tool(name="ais_mail_move_bulk")
def ais_mail_move_bulk(
    message_ids: list[str], folder_id: str, target_folder_id: str
) -> dict:
    """
    Move multiple messages to another folder.
    message_ids: list of eid values. folder_id: current fid. target_folder_id: destination fid.
    CAUTION: Moves all listed messages.
    """
    return tool_mail_move_bulk(message_ids, folder_id, target_folder_id)


@app.tool(name="ais_mail_mark_read")
def ais_mail_mark_read(
    message_ids: list[str],
    folder_id: str = "789370",
    unread: bool = False,
) -> dict:
    """
    Mark messages as read or unread.
    message_ids: list of eid values from ais_mail_inbox.
    folder_id: fid. unread: True = mark unread, False = mark read (default).
    """
    return tool_mail_mark_read(message_ids, folder_id, unread)


@app.tool(name="ais_mail_spam")
def ais_mail_spam(message_id: str, folder_id: str = "789370") -> dict:
    """
    Mark a message as spam and remove it from the folder.
    message_id: eid. folder_id: fid.
    CAUTION: Marks as spam and removes the message.
    """
    return tool_mail_spam(message_id, folder_id)


@app.tool(name="ais_documents")
def ais_documents() -> dict:
    """Return newly published documents from AIS document server."""
    return tool_documents()


@app.tool(name="ais_noticeboard")
def ais_noticeboard(folder_id: str = None) -> dict:
    """Return noticeboard messages. folder_id optionally narrows to a specific board."""
    return tool_noticeboard(folder_id)


# ── Write actions ────────────────────────────────────────────────────────────
@app.tool(name="ais_mail_send")
def ais_mail_send(
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
    to: recipient AIS login (e.g. 'xlogin') or email. Separate multiple with semicolons.
    message_type: 'internal' (AIS-to-AIS, default) or 'external' (regular email).
    attachments: list of absolute file paths to attach (optional). Emoji in subject/body supported.
    confirm_receipt: request read receipt.
    keep_message: keep draft in Unfinished box.
    keep_addresses: remember To/Cc/Bcc for next compose.
    save_sent: save copy to Sent folder (default True).
    CAUTION: This sends a real message.
    """
    return tool_mail_send(to, subject, body, cc, bcc, message_type, attachments,
                          confirm_receipt, keep_message, keep_addresses, save_sent)


@app.tool(name="ais_list_print_documents")
def ais_list_print_documents(studium: str = None, obdobi: str = None) -> dict:
    """List study documents available for download or electronic sealing."""
    return tool_list_print_documents(studium, obdobi)


@app.tool(name="ais_print_document")
def ais_print_document(
    doc_type: str = "confirmation",
    language: str = "en",
    sealed: bool = False,
    save_to: str | None = None,
    studium: str = None,
    obdobi: str = None,
) -> dict:
    """
    Download a study document as PDF or trigger electronic sealing.
    doc_type: 'confirmation' | 'registration' | 'enrollment'
    language: 'en' (default) or 'sk'. Only confirmation supports English.
    sealed: False = download PDF immediately (default).
            True = e-seal; document appears in Document Storage within ~1 hour.
    save_to: path or directory to save (default: ~/Downloads).
    CAUTION: sealed=True triggers a real action in AIS.
    """
    return tool_print_document(doc_type, language, sealed, save_to, studium, obdobi)


@app.tool(name="ais_list_open_submissions")
def ais_list_open_submissions(studium: str = None, obdobi: str = None) -> dict:
    """
    List coursework submission boxes currently open for file upload.
    Returns odevzdavarna_id values to pass to ais_submit_file.
    """
    return tool_list_open_submissions(studium, obdobi)


@app.tool(name="ais_submit_file")
def ais_submit_file(
    odevzdavarna_id: str,
    file_path: str,
    description: str = "",
    studium: str = None,
    obdobi: str = None,
) -> dict:
    """
    Upload a file to a coursework submission box.
    odevzdavarna_id: from ais_list_open_submissions.
    file_path: absolute path to the file on this machine.
    description: optional note for the teacher.
    CAUTION: This performs a real file upload in AIS.
    """
    return tool_submit_file(odevzdavarna_id, file_path, description, studium, obdobi)


# ── Lectures & attendance ────────────────────────────────────────────────────
@app.tool(name="ais_lectures_sheet")
def ais_lectures_sheet(studium: str = None, obdobi: str = None) -> dict:
    """
    Return attendance overview for all courses this period.
    Each course: code, name, predmet_id, attendance_summary {present/absent/excused/late/...},
    and full per-session attendance list with session_info and status.
    Use ais_course_progress(predmet_id) to get grades and test scores.
    """
    return tool_lectures_sheet(studium, obdobi)


@app.tool(name="ais_course_progress")
def ais_course_progress(
    predmet_id: str,
    studium: str = None,
    obdobi: str = None,
) -> dict:
    """
    Return progress grades and test results for a specific course.
    predmet_id: numeric course ID — get it from ais_lectures_sheet courses[].predmet_id.
    Returns:
      progress: running score groupings (activities A 1-5, tests T 1, ...) with totals.
      tests: list of individual tests with score, max, percentage, date, and detail_id.
    """
    return tool_course_progress(predmet_id, studium, obdobi)


@app.tool(name="ais_test_detail")
def ais_test_detail(
    detail_id: str,
    predmet_id: str,
    studium: str = None,
    obdobi: str = None,
) -> dict:
    """
    Return per-question breakdown for a specific test attempt.
    detail_id: from ais_course_progress tests[].detail_id.
    predmet_id: numeric course ID.
    Returns list of questions with question text, your answer, and points earned.
    """
    return tool_test_detail(detail_id, predmet_id, studium, obdobi)


# ── Generic ──────────────────────────────────────────────────────────────────
@app.tool(name="ais_fetch_page")
def ais_fetch_page(url: str, format: str = "text") -> dict:
    """
    Fetch any is.stuba.sk/auth/ page and return cleaned text.
    format: 'text' (default, human-readable) or 'raw' (full HTML, up to 50KB).
    Use this for pages not covered by other tools.
    """
    return tool_fetch_page(url, format)
