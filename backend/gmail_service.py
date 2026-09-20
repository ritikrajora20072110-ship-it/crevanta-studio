import smtplib
import imaplib
import time
import uuid
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from typing import Dict, Any, Optional, List
from .config import Config
from .storage import record_outreach

# Thread-safe in-memory store for active bulk background jobs
BULK_JOBS: Dict[str, Dict[str, Any]] = {}
BULK_JOBS_LOCK = threading.Lock()


def verify_gmail_connection(user: Optional[str] = None, app_password: Optional[str] = None) -> Dict[str, Any]:
    """
    Tests live authentication against Gmail SMTP and IMAP servers.
    Accepts explicit credentials to verify on-the-fly from the UI, or defaults to Config.
    Automatically handles Google App Password formatting (strips spaces).
    Never fakes connection status.
    """
    target_user = (user or Config.GMAIL_USER or "").strip()
    target_pass = (app_password or Config.GMAIL_APP_PASSWORD or "").replace(" ", "").strip()

    if not target_user or not target_pass:
        return {
            "connected": False,
            "error": "CREDENTIALS_MISSING",
            "message": "Gmail address or 16-character Google App Password is missing."
        }

    try:
        # 1. Test SMTP SSL (Port 465) for live sending
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=12) as smtp_server:
            smtp_server.login(target_user, target_pass)

        # 2. Test IMAP SSL (Port 993) for live draft creation
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=12)
        imap.login(target_user, target_pass)
        imap.logout()

        return {
            "connected": True,
            "user": target_user,
            "message": f"Successfully authenticated as {target_user}! SMTP and IMAP are active."
        }
    except smtplib.SMTPAuthenticationError as e:
        return {
            "connected": False,
            "error": "BAD_CREDENTIALS",
            "message": (
                "Google rejected the credentials (535 Bad Credentials). "
                "Normal Gmail account passwords are not permitted by Google for SMTP/IMAP. "
                "Please generate a 16-character Google App Password at myaccount.google.com/apppasswords."
            )
        }
    except Exception as e:
        error_text = str(e)
        if "BadCredentials" in error_text or "Username and Password not accepted" in error_text:
            return {
                "connected": False,
                "error": "BAD_CREDENTIALS",
                "message": (
                    "Google rejected the credentials. "
                    "Make sure 2-Step Verification is active on your Google Account and use a 16-character App Password."
                )
            }
        return {
            "connected": False,
            "error": "AUTH_FAILED",
            "message": f"Gmail Connection Error: {error_text}. Check your internet connection and credentials."
        }


def _create_mime_message(
    to_email: str,
    subject: str,
    body_text: str,
    sender_name: Optional[str] = None,
    sender_email: Optional[str] = None
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    s_email = sender_email or Config.SENDER_EMAIL or Config.GMAIL_USER
    s_name = sender_name or Config.SENDER_NAME or Config.AGENCY_NAME

    msg["From"] = f"{s_name} <{s_email}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()

    part1 = MIMEText(body_text, "plain", "utf-8")
    msg.attach(part1)

    html_content = body_text.replace("\n", "<br>")
    html_body = f"""\
    <html>
      <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 15px; line-height: 1.6; color: #171717;">
        {html_content}
      </body>
    </html>
    """
    part2 = MIMEText(html_body, "html", "utf-8")
    msg.attach(part2)

    return msg


def send_email_via_smtp(
    to_email: str,
    subject: str,
    body_text: str,
    creator_name: str = "",
    brand_name: str = ""
) -> Dict[str, Any]:
    """
    Delivers an email in real time via Gmail SMTP.
    Requires valid credentials; never simulates or fakes delivery.
    """
    clean_user = (Config.GMAIL_USER or "").strip()
    clean_pass = (Config.GMAIL_APP_PASSWORD or "").replace(" ", "").strip()

    if not clean_user or not clean_pass:
        return {
            "success": False,
            "error": "GMAIL_NOT_CONFIGURED",
            "message": "Gmail is not configured. Enter your Gmail address and 16-character Google App Password in Settings."
        }

    try:
        msg = _create_mime_message(to_email, subject, body_text)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(clean_user, clean_pass)
            server.sendmail(clean_user, [to_email], msg.as_string())

        record = {
            "type": "sent_live",
            "to_email": to_email,
            "subject": subject,
            "body": body_text,
            "creator_name": creator_name,
            "brand_name": brand_name,
            "status": "Delivered via Gmail SMTP",
            "success": True
        }
        record_outreach(record)

        return {
            "success": True,
            "message": f"Email successfully delivered to {to_email} via Gmail."
        }

    except Exception as e:
        error_msg = str(e)
        record = {
            "type": "failed",
            "to_email": to_email,
            "subject": subject,
            "body": body_text,
            "creator_name": creator_name,
            "brand_name": brand_name,
            "status": f"Delivery Failed: {error_msg}",
            "success": False
        }
        record_outreach(record)
        return {
            "success": False,
            "error": error_msg,
            "message": f"Gmail SMTP Delivery Error: {error_msg}."
        }


def save_as_gmail_draft(
    to_email: str,
    subject: str,
    body_text: str,
    creator_name: str = "",
    brand_name: str = ""
) -> Dict[str, Any]:
    """
    Writes the pitch directly into the user's real [Gmail]/Drafts mailbox via IMAP.
    Never fakes draft creation.
    """
    clean_user = (Config.GMAIL_USER or "").strip()
    clean_pass = (Config.GMAIL_APP_PASSWORD or "").replace(" ", "").strip()

    if not clean_user or not clean_pass:
        return {
            "success": False,
            "error": "GMAIL_NOT_CONFIGURED",
            "message": "Gmail credentials missing. Configure Gmail in Settings to write drafts to your inbox."
        }

    try:
        msg = _create_mime_message(to_email, subject, body_text)
        raw_message = msg.as_bytes()

        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=15)
        imap.login(clean_user, clean_pass)
        drafts_folder = '"[Gmail]/Drafts"'
        imap.append(drafts_folder, '\\Draft', imaplib.Time2Internaldate(time.time()), raw_message)
        imap.logout()

        record = {
            "type": "draft_live",
            "to_email": to_email,
            "subject": subject,
            "body": body_text,
            "creator_name": creator_name,
            "brand_name": brand_name,
            "status": "Saved to Gmail Drafts",
            "success": True
        }
        record_outreach(record)

        return {
            "success": True,
            "message": f"Pitch saved directly into your Gmail Drafts for {to_email}."
        }

    except Exception as e:
        error_msg = str(e)
        return {
            "success": False,
            "error": error_msg,
            "message": f"Gmail IMAP Draft Error: {error_msg}."
        }


def _run_bulk_job(job_id: str, pitches: List[Dict[str, Any]], mode: str, delay_seconds: float):
    """Executes live delivery in background thread with rate limiting."""
    with BULK_JOBS_LOCK:
        if job_id not in BULK_JOBS:
            return
        job = BULK_JOBS[job_id]
        job["status"] = "running"

    total = len(pitches)
    success_count = 0
    failed_count = 0

    for idx, item in enumerate(pitches):
        with BULK_JOBS_LOCK:
            if BULK_JOBS[job_id]["status"] == "cancelled":
                break

        to_email = item.get("recipient_email", "").strip()
        subject = item.get("subject", "").strip()
        body = item.get("body", "").strip()
        brand_name = item.get("brand_name", f"Brand #{idx+1}")
        creator_name = item.get("creator_name", "")

        with BULK_JOBS_LOCK:
            BULK_JOBS[job_id]["current_brand"] = brand_name
            BULK_JOBS[job_id]["current_index"] = idx + 1

        if mode == "draft":
            res = save_as_gmail_draft(to_email, subject, body, creator_name, brand_name)
        else:
            res = send_email_via_smtp(to_email, subject, body, creator_name, brand_name)

        is_ok = res.get("success", False)
        if is_ok:
            success_count += 1
        else:
            failed_count += 1

        log_entry = {
            "index": idx + 1,
            "brand_name": brand_name,
            "to_email": to_email,
            "status": "delivered" if is_ok else "failed",
            "message": res.get("message", "")
        }

        with BULK_JOBS_LOCK:
            BULK_JOBS[job_id]["completed"] = idx + 1
            BULK_JOBS[job_id]["success_count"] = success_count
            BULK_JOBS[job_id]["failed_count"] = failed_count
            BULK_JOBS[job_id]["logs"].append(log_entry)

        if delay_seconds > 0 and idx < total - 1:
            time.sleep(delay_seconds)

    with BULK_JOBS_LOCK:
        if BULK_JOBS[job_id]["status"] != "cancelled":
            BULK_JOBS[job_id]["status"] = "completed"
        BULK_JOBS[job_id]["current_brand"] = "Done"


def send_batch_emails(
    pitches: List[Dict[str, Any]],
    mode: str = "send",
    delay_seconds: float = 1.0
) -> Dict[str, Any]:
    """Processes a batch of pitches synchronously."""
    results = []
    success_count = 0
    failed_count = 0
    for idx, item in enumerate(pitches):
        to_email = item.get("recipient_email", "").strip()
        subject = item.get("subject", "").strip()
        body = item.get("body", "").strip()
        brand_name = item.get("brand_name", f"Brand #{idx+1}")
        creator_name = item.get("creator_name", "")

        if mode == "draft":
            res = save_as_gmail_draft(to_email, subject, body, creator_name, brand_name)
        else:
            res = send_email_via_smtp(to_email, subject, body, creator_name, brand_name)

        if res.get("success"):
            success_count += 1
        else:
            failed_count += 1
        results.append(res)
        if delay_seconds > 0 and idx < len(pitches) - 1:
            time.sleep(delay_seconds)

    return {
        "total": len(pitches),
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results
    }


def create_bulk_job(pitches: List[Dict[str, Any]], mode: str = "send", delay_seconds: float = 0.75) -> str:
    """Initializes and runs real live batch dispatch."""
    job_id = f"job_{uuid.uuid4().hex[:10]}"
    job_info = {
        "job_id": job_id,
        "total": len(pitches),
        "completed": 0,
        "success_count": 0,
        "failed_count": 0,
        "mode": mode,
        "status": "pending",
        "current_brand": "Initializing...",
        "current_index": 0,
        "logs": []
    }
    with BULK_JOBS_LOCK:
        BULK_JOBS[job_id] = job_info

    worker = threading.Thread(
        target=_run_bulk_job,
        args=(job_id, pitches, mode, delay_seconds),
        daemon=True
    )
    worker.start()
    return job_id


def get_bulk_job(job_id: str) -> Optional[Dict[str, Any]]:
    with BULK_JOBS_LOCK:
        return BULK_JOBS.get(job_id)


def cancel_bulk_job(job_id: str) -> bool:
    with BULK_JOBS_LOCK:
        if job_id in BULK_JOBS:
            BULK_JOBS[job_id]["status"] = "cancelled"
            return True
        return False
