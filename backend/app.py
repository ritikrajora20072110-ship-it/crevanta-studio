import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import Config
from .storage import (
    get_all_creators,
    get_creator_by_id,
    save_creator,
    delete_creator,
    get_all_commands,
    save_command,
    delete_command,
    get_outreach_history,
    clear_history,
    save_inquiry,
    get_all_inquiries,
    save_application,
    get_all_applications,
    get_all_talk_sessions,
    get_talk_session,
    save_talk_session,
    append_talk_message,
    delete_talk_session,
    clear_all_talks
)
from .ollama_client import (
    check_ollama_status,
    generate_brand_pitches_ollama,
    converse_with_ollama,
    pull_ollama_model,
    start_ollama_service,
    stop_ollama_service,
    _synthesize_brand_pitch
)
from .lead_verifier import (
    verify_brand_official_email,
    format_crevanta_video_idea
)
from .gmail_service import (
    verify_gmail_connection,
    send_email_via_smtp,
    save_as_gmail_draft,
    send_batch_emails,
    create_bulk_job,
    get_bulk_job,
    cancel_bulk_job
)
from .anti_spam import (
    analyze_deliverability,
    sanitize_for_inbox,
    optimize_subject_line,
    append_opt_out_footer
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = BASE_DIR / "static" if (BASE_DIR / "static").exists() else FRONTEND_DIR

app = FastAPI(title="Crevanta Agency API", version="2.0.0")

# Mount frontend folders (supporting both /frontend and legacy /static routes)
app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/studio")
def serve_studio():
    return FileResponse(FRONTEND_DIR / "studio.html")


@app.get("/api/public-creators")
def get_public_creators():
    return get_all_creators()


@app.post("/api/inquiries")
def submit_inquiry(inquiry: Dict[str, Any]):
    return save_inquiry(inquiry)


@app.get("/api/inquiries")
def list_inquiries():
    return get_all_inquiries()


@app.post("/api/creator-applications")
def submit_creator_application(application: Dict[str, Any]):
    return save_application(application)


@app.get("/api/creator-applications")
def list_creator_applications():
    return get_all_applications()


# --- Models ---
class SettingsUpdate(BaseModel):
    OLLAMA_BASE_URL: Optional[str] = None
    OLLAMA_MODEL: Optional[str] = None
    GMAIL_USER: Optional[str] = None
    GMAIL_APP_PASSWORD: Optional[str] = None
    AGENCY_NAME: Optional[str] = None
    SENDER_NAME: Optional[str] = None
    SENDER_EMAIL: Optional[str] = None


class GmailTestCredentialsRequest(BaseModel):
    user: str
    app_password: str


class OllamaPullRequest(BaseModel):
    model: str = "llama3.2:1b"


class OllamaSwitchRequest(BaseModel):
    model: str


class GenerateRequest(BaseModel):
    creator_id: Optional[str] = None
    custom_creator: Optional[Dict[str, Any]] = None
    prompt: str
    video_idea: Optional[str] = ""
    campaign_15day_notes: Optional[str] = ""
    email_style: str = "punchy"
    custom_instructions: Optional[str] = ""
    count: Optional[int] = 10
    ollama_model: Optional[str] = None
    strict_official_only: Optional[bool] = False


class VerifyLeadRequest(BaseModel):
    brand_name: str
    website: str
    creator_id: Optional[str] = None


class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    session_id: Optional[str] = None
    creator_id: Optional[str] = None
    ollama_model: Optional[str] = None


class EmailSendRequest(BaseModel):
    to_email: str
    subject: str
    body: str
    creator_name: Optional[str] = ""
    brand_name: Optional[str] = ""


class BatchEmailRequest(BaseModel):
    pitches: List[Dict[str, Any]]
    mode: str = "send"  # 'send' or 'draft'
    delay_seconds: Optional[float] = 1.0
    pacing_mode: Optional[str] = "human_safe"  # 'human_safe', 'balanced', or 'drafts'


class AnalyzeDeliverabilityRequest(BaseModel):
    subject: str
    body: str
    to_email: Optional[str] = ""


class SanitizeEmailRequest(BaseModel):
    subject: Optional[str] = ""
    body: str


class TestEmailRequest(BaseModel):
    recipient: str
    creator_name: Optional[str] = "Demo Creator"


# --- API Routes ---
@app.get("/api/status")
def get_system_status():
    return Config.get_status()


@app.post("/api/settings")
def update_system_settings(settings: SettingsUpdate):
    updates = settings.model_dump(exclude_none=True)
    return Config.update_settings(updates)


# --- Creators Endpoints ---
@app.get("/api/creators")
def list_creators():
    return get_all_creators()


@app.get("/api/creators/{creator_id}")
def get_creator(creator_id: str):
    creator = get_creator_by_id(creator_id)
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")
    return creator


@app.post("/api/creators")
def create_or_update_creator(creator_data: Dict[str, Any]):
    return save_creator(creator_data)


@app.delete("/api/creators/{creator_id}")
def remove_creator(creator_id: str):
    success = delete_creator(creator_id)
    if not success:
        raise HTTPException(status_code=404, detail="Creator not found")
    return {"success": True}


# --- Saved Commands Endpoints ---
@app.get("/api/commands")
def list_saved_commands():
    return get_all_commands()


@app.post("/api/commands")
def store_command(cmd: Dict[str, Any]):
    return save_command(cmd)


@app.delete("/api/commands/{command_id}")
def remove_command(command_id: str):
    success = delete_command(command_id)
    if not success:
        raise HTTPException(status_code=404, detail="Command not found")
    return {"success": True}


# --- Ollama Local AI Endpoints ---
@app.get("/api/ollama/status")
def get_ollama_status(base_url: Optional[str] = None):
    return check_ollama_status(base_url)


@app.post("/api/ollama/start")
def start_ollama():
    return start_ollama_service()


@app.post("/api/ollama/stop")
def stop_ollama():
    return stop_ollama_service()


@app.post("/api/ollama/pull")
def pull_model_endpoint(req: OllamaPullRequest):
    return pull_ollama_model(req.model)


@app.post("/api/ollama/switch-model")
def switch_model_endpoint(req: OllamaSwitchRequest):
    Config.update_settings({"OLLAMA_MODEL": req.model})
    return {"success": True, "active_model": req.model}


# --- Persistent AI Talk Records Endpoints ---
@app.get("/api/talks")
def list_talks():
    return get_all_talk_sessions()


@app.get("/api/talks/{session_id}")
def get_single_talk(session_id: str):
    session = get_talk_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Talk session not found")
    return session


@app.delete("/api/talks/{session_id}")
def remove_talk(session_id: str):
    success = delete_talk_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Talk session not found")
    return {"success": True}


@app.delete("/api/talks")
def clear_talks():
    clear_all_talks()
    return {"success": True}


# --- AI Brand & Pitch Generation (100% Native Ollama Local AI) ---
@app.post("/api/generate-pitches")
def generate_pitches(req: GenerateRequest):
    creator = None
    if req.creator_id:
        creator = get_creator_by_id(req.creator_id)
    if not creator and req.custom_creator:
        creator = req.custom_creator
    if not creator:
        raise HTTPException(status_code=400, detail="Creator not found or not specified")

    prompt_combined = req.prompt
    if req.custom_instructions:
        prompt_combined += f"\nAdditional Instructions: {req.custom_instructions}"

    return generate_brand_pitches_ollama(
        creator=creator,
        brand_prompt=prompt_combined,
        video_idea=req.video_idea or "",
        campaign_15day_notes=req.campaign_15day_notes or "",
        email_style=req.email_style or "punchy",
        count=req.count or 10,
        model=req.ollama_model or Config.OLLAMA_MODEL,
        strict_official_only=req.strict_official_only or False
    )


# --- Standalone Brand Research & Official Lead Verification Endpoint ---
@app.post("/api/verify-lead")
def verify_lead_endpoint(req: VerifyLeadRequest):
    """
    Executes Crevanta's strict Brand Research & Contact Verification Protocol:
    1. Verifies official website and checks for explicitly published official contact.
    2. Zero pattern-guessing, zero third party emails.
    3. Formulates bespoke 4-part video concept matching Crevanta's Creative Formula.
    """
    creator = get_creator_by_id(req.creator_id) if req.creator_id else None
    if not creator:
        creators = get_all_creators()
        creator = creators[0] if creators else {
            "name": "Featured Creator",
            "handle": "@creator",
            "niche": "Lifestyle & Aesthetics",
            "followers": "75K",
            "engagement_rate": "5.4%"
        }

    # 1. Live contact verification on official website
    verification_result = verify_brand_official_email(
        brand_name=req.brand_name,
        website=req.website
    )

    # 2. Formulate 4-part video concept adhering to 10 Archetypes
    niche = creator.get("niche", "Lifestyle")
    synth = _synthesize_brand_pitch(
        brand_name=req.brand_name,
        brand_niche=niche,
        creator=creator
    )

    # Merge verified official contact information
    synth["recipient_email"] = verification_result["recipient_email"]
    synth["verification"] = verification_result["verification"]
    synth["email_source"] = verification_result["email_source"]
    synth["sources_checked"] = verification_result.get("sources_checked", [])
    synth["website"] = verification_result.get("website", req.website)

    return {
        "success": True,
        "lead": synth,
        "verification": verification_result
    }


# --- Real-Time AI Conversation with Persistent Record Keeping ---
@app.post("/api/chat")
def chat_with_ai(req: ChatRequest):
    creator = None
    creator_name = "General Agency Strategy"
    if req.creator_id:
        creator = get_creator_by_id(req.creator_id)
        if creator:
            creator_name = creator.get("name", "Creator")

    target_model = req.ollama_model or Config.OLLAMA_MODEL
    res = converse_with_ollama(req.messages, creator, model=target_model)

    if res.get("success"):
        # Auto-persist conversation history to disk
        user_msg = req.messages[-1].get("content", "") if req.messages else ""
        assistant_reply = res.get("reply", "")
        session = append_talk_message(
            session_id=req.session_id,
            user_message=user_msg,
            assistant_reply=assistant_reply,
            creator_id=req.creator_id,
            creator_name=creator_name
        )
        res["session_id"] = session["id"]
        res["session"] = session

    return res


# --- Gmail Live Verification & Testing Endpoints ---
@app.get("/api/gmail/verify")
def verify_gmail():
    return verify_gmail_connection()


@app.post("/api/gmail/test-credentials")
def test_gmail_credentials(req: GmailTestCredentialsRequest):
    """Verifies arbitrary Gmail credentials in real-time from the UI before saving."""
    return verify_gmail_connection(user=req.user, app_password=req.app_password)

@app.post("/api/email/send")
def send_single_email(req: EmailSendRequest):
    return send_email_via_smtp(
        to_email=req.to_email,
        subject=req.subject,
        body_text=req.body,
        creator_name=req.creator_name or "",
        brand_name=req.brand_name or ""
    )


@app.post("/api/email/draft")
def draft_single_email(req: EmailSendRequest):
    return save_as_gmail_draft(
        to_email=req.to_email,
        subject=req.subject,
        body_text=req.body,
        creator_name=req.creator_name or "",
        brand_name=req.brand_name or ""
    )


@app.post("/api/email/batch")
def batch_email_action(req: BatchEmailRequest):
    return send_batch_emails(
        pitches=req.pitches,
        mode=req.mode,
        delay_seconds=req.delay_seconds or 1.0
    )


# --- 1-Click Background Bulk Dispatch Job with Anti-Spam Human Jitter ---
@app.post("/api/email/bulk-job")
def start_bulk_dispatch_job(req: BatchEmailRequest):
    job_id = create_bulk_job(
        pitches=req.pitches,
        mode=req.mode,
        delay_seconds=req.delay_seconds or 0.75,
        pacing_mode=req.pacing_mode or "human_safe"
    )
    return {"job_id": job_id, "total": len(req.pitches), "pacing_mode": req.pacing_mode or "human_safe"}


# --- Deliverability & Anti-Spam Health Endpoints ---
@app.post("/api/anti-spam/analyze")
def analyze_deliverability_endpoint(req: AnalyzeDeliverabilityRequest):
    """Analyzes a pitch for Primary Inbox placement readiness and detects spam triggers."""
    return analyze_deliverability(
        subject=req.subject,
        body=req.body,
        to_email=req.to_email or ""
    )


@app.post("/api/anti-spam/sanitize")
def sanitize_email_endpoint(req: SanitizeEmailRequest):
    """Auto-sanitizes pitch content, optimizes subject line, and appends opt-out footer."""
    clean_subj = optimize_subject_line(req.subject or "")
    clean_body, triggers = sanitize_for_inbox(req.body)
    clean_body = append_opt_out_footer(clean_body)
    analysis = analyze_deliverability(clean_subj, clean_body)

    return {
        "success": True,
        "clean_subject": clean_subj,
        "clean_body": clean_body,
        "triggers_replaced": triggers,
        "deliverability": analysis
    }


@app.get("/api/deliverability/status")
def deliverability_status_endpoint():
    """Returns real-time account deliverability health and today's volume quota."""
    history = get_outreach_history()
    import datetime
    today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    today_sent = 0
    for h in history:
        ts = h.get("timestamp", "")
        if ts.startswith(today_str) and h.get("type") == "sent_live":
            today_sent += 1

    sender_email = Config.SENDER_EMAIL or Config.GMAIL_USER or ""
    is_custom_domain = "@" in sender_email and not sender_email.endswith("@gmail.com")

    # Recommended daily ceiling for cold outreach is 45-50 to guarantee high domain reputation
    safe_daily_limit = 50
    quota_pct = round((today_sent / safe_daily_limit) * 100, 1)

    return {
        "sender_email": sender_email,
        "is_custom_domain": is_custom_domain,
        "domain_type": "Google Workspace / Custom Domain" if is_custom_domain else "Personal @gmail.com",
        "today_sent_count": today_sent,
        "safe_daily_limit": safe_daily_limit,
        "quota_used_percent": quota_pct,
        "reputation_status": "Healthy (Safe Zone)" if today_sent < 40 else "Approaching Daily Limit",
        "human_pacing_active": True,
        "anti_spam_shield_active": True,
        "opt_out_shield_active": True
    }


@app.get("/api/email/bulk-job/{job_id}")
def check_bulk_job_status(job_id: str):
    job = get_bulk_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Bulk job not found")
    return job


@app.post("/api/email/bulk-job/{job_id}/cancel")
def cancel_bulk_job_endpoint(job_id: str):
    cancelled = cancel_bulk_job(job_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True, "status": "cancelled"}


@app.post("/api/email/test")
def send_test_email(req: TestEmailRequest):
    subject = f"[Test Pitch] Crevanta Collab Preview: {req.creator_name} x Sample Brand"
    body = (
        f"Hi there,\n\n"
        f"This is a live test email sent from Crevanta Studio via your connected Gmail.\n\n"
        f"Your system is successfully hooked up to Gmail SMTP! When you run commands for {req.creator_name}, "
        f"pitches will be delivered in this exact formatting.\n\n"
        f"Best regards,\nCrevanta Partnerships Team"
    )
    return send_email_via_smtp(
        to_email=req.recipient,
        subject=subject,
        body_text=body,
        creator_name=req.creator_name,
        brand_name="Crevanta Test"
    )


# --- History / Audit Log ---
@app.get("/api/history")
def list_history():
    return get_outreach_history()


@app.delete("/api/history")
def reset_history():
    clear_history()
    return {"success": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host=Config.HOST, port=Config.PORT, reload=True)
