import smtplib
import imaplib
import time
import uuid
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
import random
from typing import Dict, Any, Optional, List
from .config import Config
from .storage import record_outreach
from .anti_spam import (
    sanitize_for_inbox,
    optimize_subject_line,
    append_opt_out_footer,
    analyze_deliverability
)

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
    """
    Constructs an RFC 5322 compliant MIME message optimized for PRIMARY INBOX deliverability:
    - Auto-sanitizes spam trigger words and shouting casing.
    - Appends polite 1-line opt-out reputation shield.
    - Message-ID generated under sender's domain (never leaks localhost).
    - Reply-To and X-Mailer headers configured for trusted client behavior.
    - Clean 1:1 personal styling matching manual Gmail compose.
    """
    clean_subject = optimize_subject_line(subject)
    clean_body, _ = sanitize_for_inbox(body_text)
    clean_body = append_opt_out_footer(clean_body)

    msg = MIMEMultipart("alternative")
    s_email = sender_email or Config.SENDER_EMAIL or Config.GMAIL_USER
    s_name = sender_name or Config.SENDER_NAME or Config.AGENCY_NAME
    sender_domain = s_email.split("@")[1] if "@" in s_email else "gmail.com"

    msg["From"] = f"{s_name} <{s_email}>"
    msg["To"] = to_email
    msg["Reply-To"] = f"{s_name} <{s_email}>"
    msg["Subject"] = clean_subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=sender_domain)
    msg["X-Mailer"] = "Crevanta Mail Engine (Macintosh; Apple Silicon)"
    msg["X-Priority"] = "3"

    part1 = MIMEText(clean_body, "plain", "utf-8")
    msg.attach(part1)

    html_content = clean_body.replace("\n", "<br>")
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


def _run_bulk_job(
    job_id: str,
    pitches: List[Dict[str, Any]],
    mode: str,
    delay_seconds: float,
    pacing_mode: str = "human_safe"
):
    """Executes live delivery in background thread with smart human jitter pacing to defeat spam algorithms."""
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
            BULK_JOBS[job_id]["pacing_note"] = f"Dispatching to {brand_name}..."

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

        # Smart Anti-Spam Human Jitter Pacing:
        if idx < total - 1:
            if mode == "draft":
                sleep_time = max(0.5, delay_seconds if delay_seconds > 0 else 1.0)
            elif pacing_mode == "human_safe":
                # High-deliverability human cadence (20 - 35 seconds with random jitter)
                sleep_time = round(random.uniform(20.0, 35.0), 1)
            elif pacing_mode == "balanced":
                # Balanced safe cadence (8 - 15 seconds)
                sleep_time = round(random.uniform(8.0, 15.0), 1)
            elif delay_seconds >= 3.0:
                # Custom specified delay with micro-jitter
                sleep_time = round(delay_seconds + random.uniform(-1.0, 2.0), 1)
            else:
                sleep_time = max(0.5, delay_seconds)

            with BULK_JOBS_LOCK:
                BULK_JOBS[job_id]["pacing_note"] = (
                    f"Anti-Spam Human Jitter: Pausing {sleep_time}s to emulate manual typing and protect Gmail sender reputation..."
                )

            time.sleep(sleep_time)

    with BULK_JOBS_LOCK:
        if BULK_JOBS[job_id]["status"] != "cancelled":
            BULK_JOBS[job_id]["status"] = "completed"
        BULK_JOBS[job_id]["current_brand"] = "Done"
        BULK_JOBS[job_id]["pacing_note"] = "All pitches processed with deliverability protection."


def send_batch_emails(
    pitches: List[Dict[str, Any]],
    mode: str = "send",
    delay_seconds: float = 1.0,
    pacing_mode: str = "human_safe"
) -> Dict[str, Any]:
    """Processes a batch of pitches synchronously with deliverability protection."""
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

        if idx < len(pitches) - 1:
            if mode == "draft":
                sleep_time = max(0.5, delay_seconds)
            elif pacing_mode == "human_safe":
                sleep_time = random.uniform(20.0, 35.0)
            elif pacing_mode == "balanced":
                sleep_time = random.uniform(8.0, 15.0)
            else:
                sleep_time = max(0.5, delay_seconds)
            time.sleep(sleep_time)

    return {
        "total": len(pitches),
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results
    }


def create_bulk_job(
    pitches: List[Dict[str, Any]],
    mode: str = "send",
    delay_seconds: float = 0.75,
    pacing_mode: str = "human_safe"
) -> str:
    """Initializes and runs real live batch dispatch with anti-spam human jitter."""
    job_id = f"job_{uuid.uuid4().hex[:10]}"
    job_info = {
        "job_id": job_id,
        "total": len(pitches),
        "completed": 0,
        "success_count": 0,
        "failed_count": 0,
        "mode": mode,
        "pacing_mode": pacing_mode,
        "status": "pending",
        "current_brand": "Initializing...",
        "current_index": 0,
        "pacing_note": "Starting deliverability-safe dispatch...",
        "logs": []
    }
    with BULK_JOBS_LOCK:
        BULK_JOBS[job_id] = job_info

    worker = threading.Thread(
        target=_run_bulk_job,
        args=(job_id, pitches, mode, delay_seconds, pacing_mode),
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
