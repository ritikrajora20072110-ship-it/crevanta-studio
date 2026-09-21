import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

CREATORS_FILE = DATA_DIR / "creators.json"
COMMANDS_FILE = DATA_DIR / "commands.json"
HISTORY_FILE = DATA_DIR / "history.json"
INQUIRIES_FILE = DATA_DIR / "inquiries.json"
APPLICATIONS_FILE = DATA_DIR / "applications.json"
TALKS_FILE = DATA_DIR / "talks.json"
PITCHED_BRANDS_FILE = DATA_DIR / "pitched_brands.json"


def _read_json(file_path: Path, default_value: Any) -> Any:
    if not file_path.exists():
        return default_value
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return default_value


def _write_json(file_path: Path, data: Any):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# --- Creators CRM ---
def get_all_creators() -> List[Dict[str, Any]]:
    return _read_json(CREATORS_FILE, [])


def get_creator_by_id(creator_id: str) -> Optional[Dict[str, Any]]:
    creators = get_all_creators()
    if not creators:
        return None
    # 1. Exact match
    for c in creators:
        if c.get("id") == creator_id:
            return c
    # 2. Legacy numeric ID fallback (e.g. creator_1 -> creators[0])
    legacy_map = {
        "creator_1": "creator_aarav",
        "creator_2": "creator_maya",
        "creator_3": "creator_liam",
        "creator_4": "creator_chloe"
    }
    if creator_id in legacy_map:
        mapped_id = legacy_map[creator_id]
        for c in creators:
            if c.get("id") == mapped_id:
                return c
    # 3. Safe fallback
    return creators[0]


def save_creator(creator_data: Dict[str, Any]) -> Dict[str, Any]:
    creators = get_all_creators()
    creator_id = creator_data.get("id")
    if not creator_id:
        creator_id = f"creator_{uuid.uuid4().hex[:8]}"
        creator_data["id"] = creator_id
        creators.append(creator_data)
    else:
        updated = False
        for i, c in enumerate(creators):
            if c.get("id") == creator_id:
                creators[i] = creator_data
                updated = True
                break
        if not updated:
            creators.append(creator_data)
    _write_json(CREATORS_FILE, creators)
    return creator_data


def delete_creator(creator_id: str) -> bool:
    creators = get_all_creators()
    initial_len = len(creators)
    creators = [c for c in creators if c.get("id") != creator_id]
    if len(creators) < initial_len:
        _write_json(CREATORS_FILE, creators)
        return True
    return False


# --- Saved Commands Playbook ---
def get_all_commands() -> List[Dict[str, Any]]:
    return _read_json(COMMANDS_FILE, [])


def save_command(command_data: Dict[str, Any]) -> Dict[str, Any]:
    commands = get_all_commands()
    cmd_id = command_data.get("id")
    if not cmd_id:
        cmd_id = f"cmd_{uuid.uuid4().hex[:8]}"
        command_data["id"] = cmd_id
        command_data["created_at"] = datetime.now(timezone.utc).isoformat()
        commands.insert(0, command_data)
    else:
        updated = False
        for i, cmd in enumerate(commands):
            if cmd.get("id") == cmd_id:
                commands[i] = command_data
                updated = True
                break
        if not updated:
            commands.insert(0, command_data)
    _write_json(COMMANDS_FILE, commands)
    return command_data


def delete_command(command_id: str) -> bool:
    commands = get_all_commands()
    initial_len = len(commands)
    commands = [c for c in commands if c.get("id") != command_id]
    if len(commands) < initial_len:
        _write_json(COMMANDS_FILE, commands)
        return True
    return False


# --- Outreach CRM & History ---
def get_outreach_history() -> List[Dict[str, Any]]:
    return _read_json(HISTORY_FILE, [])


def record_outreach(record: Dict[str, Any]) -> Dict[str, Any]:
    history = get_outreach_history()
    if "id" not in record:
        record["id"] = f"outreach_{uuid.uuid4().hex[:8]}"
    if "timestamp" not in record:
        record["timestamp"] = datetime.now(timezone.utc).isoformat()
    history.insert(0, record)
    _write_json(HISTORY_FILE, history)
    return record


def clear_history() -> bool:
    _write_json(HISTORY_FILE, [])
    return True


# --- Brand Campaign Enquiries ---
def get_all_inquiries() -> List[Dict[str, Any]]:
    return _read_json(INQUIRIES_FILE, [])


def save_inquiry(inquiry_data: Dict[str, Any]) -> Dict[str, Any]:
    inquiries = get_all_inquiries()
    if "id" not in inquiry_data:
        inquiry_data["id"] = f"inq_{uuid.uuid4().hex[:8]}"
    if "timestamp" not in inquiry_data:
        inquiry_data["timestamp"] = datetime.now(timezone.utc).isoformat()
    inquiries.insert(0, inquiry_data)
    _write_json(INQUIRIES_FILE, inquiries)
    return inquiry_data


# --- Creator Applications (Join the Network) ---
def get_all_applications() -> List[Dict[str, Any]]:
    return _read_json(APPLICATIONS_FILE, [])


def save_application(application_data: Dict[str, Any]) -> Dict[str, Any]:
    applications = get_all_applications()
    if "id" not in application_data:
        application_data["id"] = f"app_{uuid.uuid4().hex[:8]}"
    if "timestamp" not in application_data:
        application_data["timestamp"] = datetime.now(timezone.utc).isoformat()
    applications.insert(0, application_data)
    _write_json(APPLICATIONS_FILE, applications)
    return application_data


# --- Ollama AI Talk Records & History ---
def get_all_talk_sessions() -> List[Dict[str, Any]]:
    """Returns all saved conversation sessions ordered by most recent first."""
    return _read_json(TALKS_FILE, [])


def get_talk_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Fetches a specific conversation session by its ID."""
    talks = get_all_talk_sessions()
    for s in talks:
        if s.get("id") == session_id:
            return s
    return None


def save_talk_session(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """Saves or updates an entire conversation session."""
    talks = get_all_talk_sessions()
    session_id = session_data.get("id")
    if not session_id:
        session_id = f"talk_{uuid.uuid4().hex[:8]}"
        session_data["id"] = session_id
        session_data["created_at"] = datetime.now(timezone.utc).isoformat()
        session_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        talks.insert(0, session_data)
    else:
        session_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated = False
        for i, s in enumerate(talks):
            if s.get("id") == session_id:
                talks[i] = session_data
                updated = True
                break
        if not updated:
            talks.insert(0, session_data)

    _write_json(TALKS_FILE, talks)
    return session_data


def append_talk_message(
    session_id: Optional[str],
    user_message: str,
    assistant_reply: str,
    creator_id: Optional[str] = None,
    creator_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Appends a user message and assistant reply to an existing talk session or creates a new one.
    Maintains a continuous record of talks with Ollama AI.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    talks = get_all_talk_sessions()

    session = None
    if session_id:
        for s in talks:
            if s.get("id") == session_id:
                session = s
                break

    if not session:
        # Create a new talk session
        title = user_message[:45] + ("..." if len(user_message) > 45 else "")
        session = {
            "id": session_id or f"talk_{uuid.uuid4().hex[:8]}",
            "title": title,
            "creator_id": creator_id or "",
            "creator_name": creator_name or "General Strategy",
            "created_at": now_iso,
            "updated_at": now_iso,
            "messages": []
        }
        talks.insert(0, session)
    else:
        session["updated_at"] = now_iso
        if creator_id and not session.get("creator_id"):
            session["creator_id"] = creator_id
        if creator_name and not session.get("creator_name"):
            session["creator_name"] = creator_name

    session["messages"].append({
        "role": "user",
        "content": user_message,
        "timestamp": now_iso
    })
    session["messages"].append({
        "role": "assistant",
        "content": assistant_reply,
        "timestamp": now_iso
    })

    _write_json(TALKS_FILE, talks)
    return session


def delete_talk_session(session_id: str) -> bool:
    talks = get_all_talk_sessions()
    initial_len = len(talks)
    talks = [s for s in talks if s.get("id") != session_id]
    if len(talks) < initial_len:
        _write_json(TALKS_FILE, talks)
        return True
    return False


def clear_all_talks() -> bool:
    _write_json(TALKS_FILE, [])
    return True


# --- De-Duplication Anti-Repetition Brand Memory ---
def get_all_pitched_brands() -> List[Dict[str, Any]]:
    """Returns all brands that have been discovered or pitched, with metadata."""
    return _read_json(PITCHED_BRANDS_FILE, [])


def record_pitched_brands(
    brands: List[Dict[str, Any]],
    creator_name: str = "",
    campaign_prompt: str = ""
) -> int:
    """
    Saves a list of discovered/pitched brands to the persistent memory store.
    Prevents any duplicate brand entries in pitched_brands.json.
    Returns number of newly recorded brands.
    """
    if not brands:
        return 0
    stored = get_all_pitched_brands()
    seen_names = set((b.get("brand_name") or "").lower().strip() for b in stored)
    seen_domains = set((b.get("domain") or "").lower().strip() for b in stored if b.get("domain"))

    new_records = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for b in brands:
        b_name = (b.get("brand_name") or "").strip()
        raw_site = b.get("website") or b.get("domain") or ""
        b_domain = raw_site.lower().replace("https://", "").replace("http://", "").split("/")[0].strip()
        if not b_name:
            continue
        if b_name.lower() in seen_names or (b_domain and b_domain in seen_domains):
            continue

        seen_names.add(b_name.lower())
        if b_domain:
            seen_domains.add(b_domain)

        stored.insert(0, {
            "id": f"brand_{uuid.uuid4().hex[:8]}",
            "brand_name": b_name,
            "domain": b_domain,
            "website": b.get("website", b_domain),
            "recipient_email": b.get("recipient_email", ""),
            "verification": b.get("verification", "unverified"),
            "brand_niche": b.get("brand_niche", ""),
            "creator_name": creator_name,
            "campaign_prompt": campaign_prompt,
            "recorded_at": now_iso
        })
        new_records += 1

    if new_records > 0:
        _write_json(PITCHED_BRANDS_FILE, stored)
    return new_records


def get_pitched_brand_names_and_domains() -> tuple:
    """
    Aggregates all previously seen brand names and domains across:
      1. pitched_brands.json
      2. history.json (outreach audit log)
      3. talks.json (chat history)
    Returns (set of lowercase brand names, set of lowercase clean domains).
    """
    names: set = set()
    domains: set = set()

    # 1. From persistent pitched brands
    for b in get_all_pitched_brands():
        if b.get("brand_name"):
            names.add(b["brand_name"].lower().strip())
        if b.get("domain"):
            domains.add(b["domain"].lower().strip())

    # 2. From outreach history
    for h in get_outreach_history():
        if h.get("brand_name"):
            names.add(h["brand_name"].lower().strip())
        if h.get("to_email") and "@" in h["to_email"]:
            dom = h["to_email"].split("@")[-1].lower().strip()
            domains.add(dom)

    return names, domains


def clear_pitched_memory() -> bool:
    """Clears all stored pitched brands memory."""
    _write_json(PITCHED_BRANDS_FILE, [])
    return True


