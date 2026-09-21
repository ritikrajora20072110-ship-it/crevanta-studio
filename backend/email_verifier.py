"""
Crevanta Self-Hosted Email Verification Checker & Strict Indian Brand Filter.

Requirements Implemented:
1. Input: List of email addresses or domains from CSV file, CLI, or callable Python functions.
2. Sequential Verification (Cheapest checks first, stop early upon failure):
   - Strict Indian Brand / Company Filter: Only emails/domains belonging to Indian companies or working in India.
   - Syntax Check: RFC 5322 regex validation.
   - Disposable Email Check: Fast memory set check against known blocklist (mailinator, guerrillamail, 10minutemail, etc.).
   - Domain Existence Check: DNS A/AAAA record lookup.
   - MX Record Lookup: Confirm domain accepts mail using dnspython.
   - SMTP Handshake Check: Issue MAIL FROM / RCPT TO without sending DATA.
   - Catch-All Detection: Flags catch-all domains as 'unverifiable — catch-all' rather than marking as valid.
3. Statuses Output: valid / invalid / catch-all / disposable / timeout.
4. Retry Logic: Short 5-10s timeout per SMTP check with automatic retries.
5. Local SQLite Database Logging & Cache: Prevents re-checking same email twice (30-day TTL).
6. Rate Limiting: Minimum 2-3s delay between queries to the same MX mail server domain.
7. Pipeline Integration Gate: Brands are ONLY approved if email verification approves ('valid').
"""

import os
import sys
import re
import csv
import time
import json
import uuid
import socket
import smtplib
import sqlite3
import argparse
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set

# Try importing dnspython
try:
    import dns.resolver
    HAS_DNSPYTHON = True
except ImportError:
    HAS_DNSPYTHON = False

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "email_verifications.db"

# --- RATE LIMITING & THREAD SAFETY ---
_mx_lock = threading.Lock()
_mx_last_hit: Dict[str, float] = {}
RATE_LIMIT_DELAY_SECONDS = 2.5  # 2.5s pacing per mail server domain

# --- INDIAN DOMAINS & BRANDS STRICT FILTER ---
INDIAN_TLDS = {
    ".in", ".co.in", ".net.in", ".org.in", ".ind.in",
    ".firm.in", ".gen.in", ".ac.in", ".edu.in", ".gov.in", ".res.in"
}

# Catalog of prominent Indian consumer brands, D2C, ecommerce, tech, fashion, food
KNOWN_INDIAN_DOMAINS = {
    # Consumer Tech & Audio
    "boat-lifestyle.com", "gonoise.com", "noise.in", "fireboltt.com", "zebronics.com",
    "portronics.com", "hammeronline.in", "boult.com", "boultaudio.com", "crossbeats.com",
    "pebblecart.com", "ambraneindia.com", "mivi.in", "ptron.in", "wingslifestyle.com",
    "headphonezone.in", "noisefit.com",

    # Beauty, Skincare & Personal Care
    "mamaearth.in", "sugarcosmetics.com", "nykaa.com", "bombayshavingcompany.com",
    "mcaffeine.com", "plumgoodness.com", "dotandkey.com", "foxtale.in", "aqualogica.in",
    "drseths.in", "thedermaco.com", "beminimalist.co", "minimalist.co", "beardo.in",
    "ustraa.com", "forestessentialsindia.com", "kamaayurveda.com", "purplle.com",
    "myglamm.com", "re-equil.com", "earthrhythm.com", "juicychemistry.com", "pilgrim.in",
    "discoverpilgrim.com", "lotusherbals.com", "biotique.com", "himalayawellness.in",

    # Fashion, Apparel, Jewelry & Eyewear
    "andamen.com", "snitch.co.in", "thesouledstore.com", "bewakoof.com", "rare-rabbit.com",
    "thehouseofrare.com", "nicobar.com", "bluestone.com", "caratlane.com", "giva.co",
    "chumbak.com", "fabindia.com", "lenskart.com", "mokobara.com", "uppercase.co.in",
    "dailyobjects.com", "wforwoman.com", "aurelia.com", "manyavar.com", "raymond.in",
    "bata.in", "metroshoes.net", "mochishoes.com", "woodlandworldwide.com", "da-milano.com",
    "titan.co.in", "fastrack.in", "skinn.in", "tanishq.co.in", "voylla.com",

    # Food, Beverage & Wellness
    "licious.in", "fresh2home.com", "countrydelight.in", "epigamia.com", "trueelements.com",
    "kapiva.in", "bira91.com", "paperboatdrinks.com", "sleepyowl.co", "chaayos.com",
    "chaipoint.com", "thirdwavecoffeeroasters.com", "bluetokaicoffee.com", "subko.coffee",
    "slurrpfarm.com", "yogabar.in", "wholetruthfoods.com", "rawpressery.com",
    "idfreshfood.com", "vowfoods.com", "curefoods.in", "rebel-foods.com", "faasos.com",
    "behrouzbiryani.com", "ovenstory.in",

    # Home, Furniture & Mattresses
    "wakefit.co", "sleepycat.in", "thesleepcompany.in", "sundayrest.com", "pepperfry.com",
    "urbanladder.com", "woodenstreet.com", "at-home.co.in", "ddecor.com",

    # Mobility & EV
    "atherenergy.com", "olaelectric.com", "ultraviolette.com", "simpleenergy.in",
    "torkmotors.com", "revolt-motors.com", "bajajauto.com", "tvsmotor.com",
    "heromotocorp.com", "royalenfield.com", "tatamotors.com", "mahindra.com",

    # Platforms, Marketplaces & Tech
    "zomato.com", "swiggy.in", "swiggy.com", "flipkart.com", "myntra.com", "ajio.com",
    "tatacliq.com", "reliancedigital.in", "jiomart.com", "urbancompany.com", "cult.fit",
    "cred.club", "zerodha.com", "groww.in", "paytm.com", "phonepe.com", "razorpay.com",
    "cashfree.com", "inmobi.com", "zoho.com", "freshworks.com", "postman.com",

    # Fitness, Gyms & Athletic Training
    "cult.fit", "nitrro.in", "jeraifitness.com", "wavesgym.com", "atmanawellness.com",
    "vivafitness.net", "chisel.co.in", "wtfgyms.com", "fitpass.co.in", "gymlocator.in",

    # Global brands with dedicated Indian operations / subsidiaries
    "amazon.in", "samsung.com/in", "nike.in", "adidas.co.in", "puma.com/in",
    "decathlon.in", "ikea.com/in", "muji.in", "uniqlo.com/in", "starbucks.in",
    "hul.co.in", "nestle.in", "itcportal.com", "britannia.co.in", "marico.com"
}

KNOWN_INDIAN_BRAND_NAMES = {
    "boat", "boat lifestyle", "noise", "fire-boltt", "fireboltt", "zebronics",
    "portronics", "hammer", "boult", "boult audio", "crossbeats", "pebble",
    "ambrane", "mivi", "ptron", "wings", "headphone zone", "mamaearth",
    "sugar cosmetics", "nykaa", "bombay shaving company", "mcaffeine",
    "plum", "plum goodness", "dot & key", "dot and key", "foxtale", "aqualogica",
    "dr. sheth's", "dr sheths", "the derma co", "minimalist", "beardo", "ustraa",
    "forest essentials", "kama ayurveda", "purplle", "myglamm", "pilgrim",
    "andamen", "snitch", "the souled store", "bewakoof", "rare rabbit",
    "nicobar", "bluestone", "caratlane", "giva", "chumbak", "fabindia",
    "lenskart", "mokobara", "uppercase", "dailyobjects", "titan", "fastrack",
    "tanishq", "licious", "fresh2home", "country delight", "epigamia",
    "true elements", "kapiva", "bira 91", "paper boat", "sleepy owl",
    "chaayos", "chai point", "third wave coffee", "blue tokai", "subko",
    "slurrp farm", "yoga bar", "the whole truth", "raw pressery", "id fresh food",
    "wakefit", "sleepycat", "the sleep company", "pepperfry", "urban ladder",
    "ather", "ather energy", "ola electric", "ultraviolette", "tata motors",
    "mahindra", "royal enfield", "tvs", "bajaj", "zomato", "swiggy", "flipkart",
    "myntra", "ajio", "tata cliq", "jio", "urban company", "cult.fit", "cultfit",
    "nitrro", "nitrro wellness", "jerai", "jerai fitness", "waves gym", "atmana wellness", "viva fitness",
    "cred", "zerodha", "groww", "paytm", "phonepe", "razorpay", "zoho"
}

# --- DISPOSABLE / TEMP-EMAIL DOMAINS BLOCKLIST ---
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "guerrillamail.net", "guerrillamail.biz",
    "guerrillamail.org", "guerrillamailblock.com", "grr.la", "sharklasers.com",
    "10minutemail.com", "10minutemail.net", "tempmail.com", "temp-mail.org",
    "throwawaymail.com", "yopmail.com", "yopmail.fr", "yopmail.net", "cool.fr.nf",
    "trashmail.com", "trashmail.net", "trashmail.me", "dispostable.com",
    "mytemp.email", "fakemailgenerator.com", "fakeinbox.com", "getairmail.com",
    "mohmal.com", "crazymailing.com", "generator.email", "emailondeck.com",
    "jetable.org", "mailcatch.com", "maildrop.cc", "tempail.com", "mytempemail.com",
    "burnermail.io", "inboxbear.com", "dropmail.me", "tempinbox.com", "spamgourmet.com",
    "incognitomail.com", "fakemail.net", "nada.ltd", "getnada.com", "abv.bg",
    "trashymail.com", "binkmail.com", "safetymail.info", "spam4.me", "bccto.me",
    "disposablemail.com", "mailnull.com", "spambox.us", "hidemail.de", "mytrashmail.com"
}


import contextlib

@contextlib.contextmanager
def get_db_connection():
    """Yields sqlite3 connection and ensures it is safely closed."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


# --- SQLITE DATABASE INITIALIZATION ---
def init_db():
    """Initializes local SQLite database and indexes for caching email verifications."""
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_verifications (
                email TEXT PRIMARY KEY,
                domain TEXT,
                status TEXT,
                reason TEXT,
                is_indian INTEGER,
                is_catch_all INTEGER,
                mx_host TEXT,
                smtp_code INTEGER,
                details TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_domain ON email_verifications(domain)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON email_verifications(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_is_indian ON email_verifications(is_indian)")
        conn.commit()


# Run init on module load
init_db()


def get_cached_verification(email: str, max_age_days: int = 30) -> Optional[Dict[str, Any]]:
    """Retrieves cached verification result from SQLite if verified within max_age_days."""
    clean_email = email.strip().lower()
    cutoff_time = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()

    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM email_verifications 
            WHERE email = ? AND updated_at >= ?
        """, (clean_email, cutoff_time))
        row = cur.fetchone()
        if row:
            data = dict(row)
            if data.get("details"):
                try:
                    data["details"] = json.loads(data["details"])
                except Exception:
                    pass
            data["cached"] = True
            return data
    return None


def save_verification_to_db(record: Dict[str, Any]):
    """Persists verification verdict to SQLite."""
    now_iso = datetime.now(timezone.utc).isoformat()
    clean_email = record.get("email", "").strip().lower()
    details_str = json.dumps(record.get("details", {})) if isinstance(record.get("details"), (dict, list)) else str(record.get("details", ""))

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO email_verifications (
                email, domain, status, reason, is_indian, is_catch_all, mx_host, smtp_code, details, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                domain=excluded.domain,
                status=excluded.status,
                reason=excluded.reason,
                is_indian=excluded.is_indian,
                is_catch_all=excluded.is_catch_all,
                mx_host=excluded.mx_host,
                smtp_code=excluded.smtp_code,
                details=excluded.details,
                updated_at=excluded.updated_at
        """, (
            clean_email,
            record.get("domain", ""),
            record.get("status", "invalid"),
            record.get("reason", ""),
            1 if record.get("is_indian") else 0,
            1 if record.get("is_catch_all") else 0,
            record.get("mx_host", ""),
            record.get("smtp_code", 0),
            details_str,
            now_iso,
            now_iso
        ))
        conn.commit()


# --- CHECK 1: STRICT INDIAN BRAND FILTER ---
def is_indian_entity(
    email_or_domain: str,
    brand_name: Optional[str] = None,
    website_text: Optional[str] = None
) -> Tuple[bool, str]:
    """
    STRICT FILTER: Checks if email/domain belongs to an Indian company or operates in India.
    Returns: (is_indian: bool, reason: str)
    """
    clean_input = email_or_domain.strip().lower()
    domain = clean_input.split("@")[-1] if "@" in clean_input else clean_input
    domain = domain.replace("http://", "").replace("https://", "").split("/")[0].strip()

    # 1. Check Indian ccTLD (.in, .co.in, etc.)
    for tld in INDIAN_TLDS:
        if domain.endswith(tld):
            return True, f"Official Indian ccTLD ({tld})"

    # 2. Check Known Indian Enterprise / D2C Domain Catalog
    if domain in KNOWN_INDIAN_DOMAINS:
        return True, "Verified Indian Brand / D2C company domain"

    # Base domain check (e.g. sub.boat-lifestyle.com -> boat-lifestyle.com)
    parts = domain.split(".")
    if len(parts) >= 2:
        base_domain = ".".join(parts[-2:])
        if base_domain in KNOWN_INDIAN_DOMAINS:
            return True, "Verified Indian Brand domain"
        if len(parts) >= 3:
            three_part = ".".join(parts[-3:])
            if three_part in KNOWN_INDIAN_DOMAINS:
                return True, "Verified Indian Brand domain"

    # 3. Check Brand Name against known Indian brands
    if brand_name:
        b_clean = brand_name.strip().lower()
        if b_clean in KNOWN_INDIAN_BRAND_NAMES:
            return True, f"Verified Indian enterprise brand name ({brand_name})"
        for k_name in KNOWN_INDIAN_BRAND_NAMES:
            if k_name in b_clean or b_clean in k_name:
                return True, f"Matches Indian brand portfolio ({k_name})"

    # 4. Check Website Content / Indicators (GSTIN, +91, INR, Indian metros, Pvt Ltd)
    if website_text:
        text_lower = website_text.lower()
        # GSTIN pattern (2 digits state code + 10 chars PAN + 1 + Z + 1)
        if re.search(r"\b\d{2}[a-z]{5}\d{4}[a-z]{1}[a-z\d]{1}[z]{1}[a-z\d]{1}\b", text_lower):
            return True, "Verified Indian GSTIN registration detected"
        # Indian phone indicators
        if "+91" in website_text or "091-" in website_text:
            return True, "Indian contact dial code (+91) detected"
        # Currency indicators
        if "₹" in website_text or "inr" in text_lower or "rupees" in text_lower or "rs." in text_lower:
            return True, "Indian Rupee (INR / ₹) commercial currency"
        # Indian corporate entities
        if "private limited" in text_lower or "pvt ltd" in text_lower or "pvt. ltd" in text_lower or "cin:" in text_lower:
            return True, "Indian corporate registration (Pvt Ltd / CIN)"
        # Indian manufacturing / logistics
        if "pan india" in text_lower or "all india delivery" in text_lower or "made in india" in text_lower:
            return True, "Indian distribution / manufacturing presence"
        # Indian headquarters / hubs
        indian_cities = ["bengaluru", "bangalore", "mumbai", "new delhi", "delhi ncr", "gurugram", "gurgaon", "noida", "hyderabad", "pune", "chennai", "kolkata", "ahmedabad", "jaipur"]
        if any(city in text_lower for city in indian_cities):
            return True, "Headquartered / operating in Indian business hub"

    return False, "Non-Indian entity: does not match Indian ccTLD, brand directory, or Indian operations criteria"


# --- CHECK 2: SYNTAX VALIDATION ---
def validate_syntax(email_or_domain: str) -> Tuple[bool, str, str, str]:
    """
    Regex validation of email format adhering to RFC 5322.
    Also handles domain-only input.
    Returns: (is_valid, clean_email_or_domain, local_part, domain)
    """
    cleaned = email_or_domain.strip().lower()
    if not cleaned:
        return False, "", "", "Empty input"

    if "@" in cleaned:
        # Full email address check
        email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$"
        if not re.match(email_regex, cleaned):
            return False, cleaned, "", "Invalid email regex syntax"

        parts = cleaned.split("@")
        if len(parts) != 2:
            return False, cleaned, "", "Multiple @ symbols"

        local_part, domain = parts
        if len(local_part) > 64:
            return False, cleaned, local_part, "Local part exceeds 64 characters"
        if len(cleaned) > 254:
            return False, cleaned, local_part, "Email exceeds 254 characters"
        if ".." in cleaned:
            return False, cleaned, local_part, "Consecutive dots not permitted"

        # Domain part sanity
        domain_parts = domain.split(".")
        if any(len(p) == 0 for p in domain_parts) or len(domain_parts[-1]) < 2:
            return False, cleaned, local_part, "Invalid domain extension"

        return True, cleaned, local_part, domain
    else:
        # Domain-only input
        domain = cleaned.replace("http://", "").replace("https://", "").split("/")[0].strip()
        domain_regex = r"^[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$"
        if not re.match(domain_regex, domain):
            return False, domain, "", "Invalid domain syntax"
        if len(domain.split(".")[-1]) < 2:
            return False, domain, "", "Domain TLD too short"
        return True, domain, "", domain


# --- CHECK 3: DISPOSABLE EMAIL DOMAIN CHECK ---
def is_disposable_domain(domain: str) -> bool:
    """Checks domain against in-memory hash set of known disposable / temp email providers."""
    clean_domain = domain.strip().lower()
    if clean_domain in DISPOSABLE_DOMAINS:
        return True
    parts = clean_domain.split(".")
    if len(parts) >= 2:
        base_domain = ".".join(parts[-2:])
        if base_domain in DISPOSABLE_DOMAINS:
            return True
    return False


def get_dns_resolver(timeout: float = 7.0):
    """Creates a dnspython Resolver, falling back to public DNS if /etc/resolv.conf is restricted."""
    if not HAS_DNSPYTHON:
        return None
    try:
        resolver = dns.resolver.Resolver()
    except (dns.resolver.NoResolverConfiguration, PermissionError, Exception):
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = ["8.8.8.8", "1.1.1.1", "8.8.4.4"]
    resolver.timeout = timeout
    resolver.lifetime = timeout
    return resolver


# --- CHECK 4: DOMAIN DNS EXISTENCE (A / AAAA) ---
def check_domain_exists(domain: str, timeout: float = 7.0) -> Tuple[bool, str]:
    """
    Checks if domain has valid A or AAAA records.
    Uses dnspython if installed, with standard library socket fallback.
    """
    clean_domain = domain.strip().lower()

    resolver = get_dns_resolver(timeout=timeout)
    if resolver:
        try:
            # Try A record
            try:
                answers = resolver.resolve(clean_domain, "A")
                if answers:
                    return True, str(answers[0])
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                pass

            # Try AAAA record
            try:
                answers_aaaa = resolver.resolve(clean_domain, "AAAA")
                if answers_aaaa:
                    return True, str(answers_aaaa[0])
            except Exception:
                pass

            return False, f"Domain {clean_domain} has no A or AAAA records"
        except dns.resolver.NXDOMAIN:
            return False, f"Domain {clean_domain} does not exist (NXDOMAIN)"
        except Exception:
            # Fallback to socket if dnspython encounters network resolution issues
            pass

    # Socket fallback
    try:
        addrinfo = socket.getaddrinfo(clean_domain, None)
        if addrinfo:
            ip = addrinfo[0][4][0]
            return True, str(ip)
        return False, f"Socket resolution returned empty for {clean_domain}"
    except socket.gaierror:
        return False, f"Domain {clean_domain} failed DNS resolution (NXDOMAIN/No IP)"
    except Exception as e:
        return False, f"DNS existence check error: {str(e)}"


# --- CHECK 5: MX RECORD LOOKUP (dnspython) ---
def lookup_mx_records(domain: str, timeout: float = 7.0) -> Tuple[List[str], str]:
    """
    Confirm domain accepts mail by querying MX records using dnspython.
    Returns: (sorted_mx_hosts_list, status_message)
    """
    clean_domain = domain.strip().lower()
    mx_records: List[Tuple[int, str]] = []

    resolver = get_dns_resolver(timeout=timeout)
    if resolver:
        try:
            answers = resolver.resolve(clean_domain, "MX")
            for r in answers:
                priority = int(r.preference)
                exchange = str(r.exchange).rstrip(".").strip().lower()
                if exchange and exchange != ".":
                    mx_records.append((priority, exchange))
            
            if mx_records:
                mx_records.sort(key=lambda x: x[0])
                sorted_hosts = [x[1] for x in mx_records]
                return sorted_hosts, f"Found {len(sorted_hosts)} MX record(s)"
            else:
                return [], f"Domain {clean_domain} has empty or null MX record"
        except dns.resolver.NXDOMAIN:
            return [], f"Domain {clean_domain} does not exist (NXDOMAIN)"
        except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            return [], f"Domain {clean_domain} has no MX records"
        except Exception:
            # Continue to fallback
            pass

    # Fallback: check if domain itself answers on mail via socket or system
    has_a, ip = check_domain_exists(clean_domain, timeout=timeout)
    if has_a:
        # Per RFC 5321 implicit MX fallback, but modern SMTP usually strictly configures MX
        return [clean_domain], "Using implicit domain A-record fallback for MX"
    return [], f"No MX records found for {clean_domain}"


# --- RATE LIMITER HELPER ---
def apply_mx_rate_limit(mx_host: str, delay_seconds: float = RATE_LIMIT_DELAY_SECONDS):
    """
    Enforces minimum delay between queries to the same MX mail server domain.
    Prevents blacklisting for spam-like probing behavior.
    """
    # Extract base domain of mail server (e.g. google.com for aspmx.l.google.com)
    parts = mx_host.lower().split(".")
    base_mx = ".".join(parts[-2:]) if len(parts) >= 2 else mx_host.lower()

    with _mx_lock:
        now = time.time()
        last_hit = _mx_last_hit.get(base_mx, 0.0)
        elapsed = now - last_hit
        if elapsed < delay_seconds:
            sleep_time = delay_seconds - elapsed
            time.sleep(sleep_time)
        _mx_last_hit[base_mx] = time.time()


# --- CHECK 6: SMTP HANDSHAKE & CATCH-ALL DETECTION ---
def check_smtp_mailbox(
    mx_host: str,
    target_email: str,
    sender_email: str = "probe@crevanta.com",
    timeout: float = 7.0,
    max_retries: int = 2
) -> Dict[str, Any]:
    """
    Connects to MX mail server, issues EHLO, MAIL FROM, and RCPT TO without sending DATA.
    Detects Catch-All domains by probing a random non-existent address first.
    Flags catch-all as 'unverifiable — catch-all'.
    """
    clean_target = target_email.strip().lower()
    domain = clean_target.split("@")[-1]

    # Enforce rate limit before probing mail server
    apply_mx_rate_limit(mx_host)

    last_error = ""
    for attempt in range(max_retries + 1):
        smtp = None
        try:
            # Connect on standard SMTP port 25 with short timeout
            smtp = smtplib.SMTP(timeout=timeout)
            smtp.set_debuglevel(0)
            
            connect_code, connect_msg = smtp.connect(mx_host, 25)
            if connect_code >= 400:
                # Connection rejected or temporarily unavailable
                if attempt < max_retries:
                    time.sleep(1.0)
                    continue
                return {
                    "status": "timeout",
                    "smtp_code": connect_code,
                    "reason": f"SMTP connect refused ({connect_code}): {connect_msg.decode('utf-8', 'ignore')}",
                    "is_catch_all": False
                }

            # Issue EHLO / HELO
            try:
                smtp.ehlo()
            except Exception:
                smtp.helo()

            # If server supports STARTTLS, upgrade connection safely
            if smtp.has_extn("starttls"):
                try:
                    smtp.starttls()
                    smtp.ehlo()
                except Exception:
                    pass

            # Issue MAIL FROM
            mf_code, _ = smtp.mail(sender_email)
            if mf_code >= 400:
                if attempt < max_retries:
                    time.sleep(1.0)
                    continue
                return {
                    "status": "timeout",
                    "smtp_code": mf_code,
                    "reason": f"MAIL FROM rejected by {mx_host} (code {mf_code})",
                    "is_catch_all": False
                }

            # 1. CATCH-ALL PROBE: Test random non-existent address
            fake_mailbox = f"crevanta_probe_{uuid.uuid4().hex[:12]}@{domain}"
            fake_code, _ = smtp.rcpt(fake_mailbox)
            
            if fake_code == 250:
                # Server accepted a random non-existent address -> Catch-All!
                try:
                    smtp.quit()
                except Exception:
                    pass
                return {
                    "status": "catch-all",
                    "smtp_code": 250,
                    "reason": "unverifiable — catch-all (server accepts all recipient addresses)",
                    "is_catch_all": True
                }

            # 2. TARGET MAILBOX PROBE: Test real target address
            rcpt_code, rcpt_msg = smtp.rcpt(clean_target)
            rcpt_str = rcpt_msg.decode("utf-8", "ignore") if isinstance(rcpt_msg, bytes) else str(rcpt_msg)

            try:
                smtp.quit()
            except Exception:
                pass

            if rcpt_code == 250:
                return {
                    "status": "valid",
                    "smtp_code": 250,
                    "reason": "Mailbox exists and verified via SMTP handshake",
                    "is_catch_all": False
                }
            elif rcpt_code in (550, 551, 552, 553, 554):
                return {
                    "status": "invalid",
                    "smtp_code": rcpt_code,
                    "reason": f"Mailbox does not exist (SMTP {rcpt_code}: {rcpt_str.strip()})",
                    "is_catch_all": False
                }
            elif rcpt_code in (421, 450, 451, 452):
                # Temporary failure / greylisting
                if attempt < max_retries:
                    time.sleep(2.0)
                    continue
                return {
                    "status": "timeout",
                    "smtp_code": rcpt_code,
                    "reason": f"Server greylisting / temporary deferral (SMTP {rcpt_code}: {rcpt_str.strip()})",
                    "is_catch_all": False
                }
            else:
                return {
                    "status": "invalid",
                    "smtp_code": rcpt_code,
                    "reason": f"SMTP check rejected (code {rcpt_code}: {rcpt_str.strip()})",
                    "is_catch_all": False
                }

        except (socket.timeout, TimeoutError):
            last_error = f"Connection to {mx_host} timed out ({timeout}s)"
            if attempt < max_retries:
                time.sleep(1.0)
                continue
        except (socket.error, ConnectionRefusedError, smtplib.SMTPServerDisconnected) as e:
            last_error = f"SMTP connection failed on {mx_host}: {str(e)}"
            if attempt < max_retries:
                time.sleep(1.0)
                continue
        except Exception as e:
            last_error = f"SMTP handshake error: {str(e)}"
            if attempt < max_retries:
                time.sleep(1.0)
                continue
        finally:
            if smtp:
                try:
                    smtp.close()
                except Exception:
                    pass

    return {
        "status": "timeout",
        "smtp_code": 0,
        "reason": last_error or f"Connection to {mx_host} failed after {max_retries} retries",
        "is_catch_all": False
    }


# --- CORE PIPELINE FUNCTION: verify_email ---
def verify_email(
    email_or_domain: str,
    brand_name: Optional[str] = None,
    website_text: Optional[str] = None,
    check_indian_only: bool = True,
    force_recheck: bool = False,
    timeout: float = 7.0,
    skip_smtp: bool = False
) -> Dict[str, Any]:
    """
    Verifies an email or domain following strict requirements:
    1. Checks local SQLite cache (<30 days) to prevent duplicate verification.
    2. Indian Brands Only Strict Filter (stops early if non-Indian).
    3. Syntax Check (RFC 5322 regex, stops early if invalid).
    4. Disposable Domain Check (stops early if disposable).
    5. Domain Existence DNS Check (A/AAAA, stops early if domain not found).
    6. MX Record Lookup (stops early if no MX).
    7. SMTP Handshake & Catch-All Check (rate-limited, stops early).
    8. Persists results to SQLite.
    
    Returns:
      {
        "email": str,
        "domain": str,
        "status": "valid" | "invalid" | "catch-all" | "disposable" | "timeout",
        "reason": str,
        "is_indian": bool,
        "is_catch_all": bool,
        "mx_host": str,
        "smtp_code": int,
        "stages": dict,
        "approved": bool
      }
    """
    clean_input = email_or_domain.strip().lower()
    stages = {}

    # Check 0: Local SQLite Cache
    if not force_recheck and "@" in clean_input:
        cached = get_cached_verification(clean_input)
        if cached:
            # If Indian only filter is active, verify cached record complies
            if check_indian_only and not cached.get("is_indian"):
                return {
                    "email": clean_input,
                    "domain": cached.get("domain", ""),
                    "status": "invalid",
                    "reason": "Non-Indian company or domain (cached)",
                    "is_indian": False,
                    "is_catch_all": bool(cached.get("is_catch_all")),
                    "mx_host": cached.get("mx_host", ""),
                    "smtp_code": cached.get("smtp_code", 0),
                    "stages": {"cache": "hit", "indian_filter": "failed"},
                    "approved": False,
                    "cached": True
                }
            return {
                "email": cached["email"],
                "domain": cached["domain"],
                "status": cached["status"],
                "reason": cached["reason"],
                "is_indian": bool(cached["is_indian"]),
                "is_catch_all": bool(cached["is_catch_all"]),
                "mx_host": cached.get("mx_host", ""),
                "smtp_code": cached.get("smtp_code", 0),
                "stages": {"cache": "hit"},
                "approved": cached["status"] == "valid" and (not check_indian_only or bool(cached["is_indian"])),
                "cached": True
            }

    # Step 1: INDIAN BRANDS ONLY — STRICT FILTER
    is_indian, indian_reason = is_indian_entity(clean_input, brand_name=brand_name, website_text=website_text)
    stages["indian_filter"] = {"passed": is_indian, "reason": indian_reason}

    if check_indian_only and not is_indian:
        domain_part = clean_input.split("@")[-1] if "@" in clean_input else clean_input
        result = {
            "email": clean_input,
            "domain": domain_part,
            "status": "invalid",
            "reason": f"Rejected by Indian Brands Only Filter: {indian_reason}",
            "is_indian": False,
            "is_catch_all": False,
            "mx_host": "",
            "smtp_code": 0,
            "stages": stages,
            "approved": False
        }
        if "@" in clean_input:
            save_verification_to_db(result)
        return result

    # Step 2: SYNTAX CHECK (RFC 5322 regex)
    is_valid_syntax, clean_item, local_part, domain_or_err = validate_syntax(clean_input)
    if not is_valid_syntax:
        stages["syntax"] = {"passed": False, "error": domain_or_err}
        result = {
            "email": clean_input,
            "domain": "",
            "status": "invalid",
            "reason": f"Syntax Error: {domain_or_err}",
            "is_indian": is_indian,
            "is_catch_all": False,
            "mx_host": "",
            "smtp_code": 0,
            "stages": stages,
            "approved": False
        }
        if "@" in clean_input:
            save_verification_to_db(result)
        return result

    domain = domain_or_err
    target_email = clean_item if "@" in clean_item else f"info@{domain}"
    stages["syntax"] = {"passed": True, "local_part": local_part, "domain": domain}

    # Step 3: DISPOSABLE / TEMP-EMAIL DOMAIN CHECK
    if is_disposable_domain(domain):
        stages["disposable"] = {"passed": False, "reason": "Known disposable/temporary email service"}
        result = {
            "email": target_email,
            "domain": domain,
            "status": "disposable",
            "reason": "Disposable / temporary email domain rejected",
            "is_indian": is_indian,
            "is_catch_all": False,
            "mx_host": "",
            "smtp_code": 0,
            "stages": stages,
            "approved": False
        }
        save_verification_to_db(result)
        return result
    stages["disposable"] = {"passed": True}

    # Step 4: DOMAIN EXISTENCE CHECK (DNS A / AAAA)
    domain_exists, dns_ip_or_err = check_domain_exists(domain, timeout=timeout)
    if not domain_exists:
        stages["dns_existence"] = {"passed": False, "reason": dns_ip_or_err}
        result = {
            "email": target_email,
            "domain": domain,
            "status": "invalid",
            "reason": f"Domain does not exist: {dns_ip_or_err}",
            "is_indian": is_indian,
            "is_catch_all": False,
            "mx_host": "",
            "smtp_code": 0,
            "stages": stages,
            "approved": False
        }
        save_verification_to_db(result)
        return result
    stages["dns_existence"] = {"passed": True, "ip": dns_ip_or_err}

    # Step 5: MX RECORD LOOKUP (dnspython)
    mx_hosts, mx_msg = lookup_mx_records(domain, timeout=timeout)
    if not mx_hosts:
        stages["mx_lookup"] = {"passed": False, "reason": mx_msg}
        result = {
            "email": target_email,
            "domain": domain,
            "status": "invalid",
            "reason": f"No valid MX records: {mx_msg}",
            "is_indian": is_indian,
            "is_catch_all": False,
            "mx_host": "",
            "smtp_code": 0,
            "stages": stages,
            "approved": False
        }
        save_verification_to_db(result)
        return result
    primary_mx = mx_hosts[0]
    stages["mx_lookup"] = {"passed": True, "primary_mx": primary_mx, "all_mx": mx_hosts[:3]}

    # If verifying a domain only, or if skip_smtp is requested, we can complete here
    if "@" not in clean_input or skip_smtp:
        result = {
            "email": target_email,
            "domain": domain,
            "status": "valid",
            "reason": f"Domain has active mail exchange ({primary_mx})",
            "is_indian": is_indian,
            "is_catch_all": False,
            "mx_host": primary_mx,
            "smtp_code": 250,
            "stages": stages,
            "approved": True
        }
        save_verification_to_db(result)
        return result

    # Step 6: SMTP HANDSHAKE CHECK & CATCH-ALL DETECTION
    smtp_res = check_smtp_mailbox(
        mx_host=primary_mx,
        target_email=target_email,
        timeout=timeout
    )
    stages["smtp_handshake"] = smtp_res

    status = smtp_res.get("status", "invalid")
    is_catch_all = smtp_res.get("is_catch_all", False)
    smtp_code = smtp_res.get("smtp_code", 0)
    reason = smtp_res.get("reason", "")

    # Approved ONLY if status == 'valid' and meets Indian filter
    approved = (status == "valid") and (not check_indian_only or is_indian)

    result = {
        "email": target_email,
        "domain": domain,
        "status": status,
        "reason": reason,
        "is_indian": is_indian,
        "is_catch_all": is_catch_all,
        "mx_host": primary_mx,
        "smtp_code": smtp_code,
        "stages": stages,
        "approved": approved
    }

    # Persist to SQLite
    save_verification_to_db(result)
    return result


# --- FUNCTION 2: BATCH LIST VERIFICATION ---
def verify_email_list(
    items: List[str],
    check_indian_only: bool = True,
    force_recheck: bool = False,
    timeout: float = 7.0,
    skip_smtp: bool = False
) -> List[Dict[str, Any]]:
    """Verifies a list of email addresses or domains sequentially with rate limiting."""
    results = []
    for item in items:
        clean = item.strip()
        if not clean:
            continue
        res = verify_email(
            email_or_domain=clean,
            check_indian_only=check_indian_only,
            force_recheck=force_recheck,
            timeout=timeout,
            skip_smtp=skip_smtp
        )
        results.append(res)
    return results


# --- FUNCTION 3: CSV INPUT & EXPORT ---
def verify_csv(
    input_csv_path: str,
    output_csv_path: Optional[str] = None,
    email_column: str = "email",
    check_indian_only: bool = True,
    force_recheck: bool = False
) -> List[Dict[str, Any]]:
    """
    Reads email addresses or domains from a CSV file, runs verification pipeline,
    and optionally writes output CSV with verification columns.
    """
    in_path = Path(input_csv_path)
    if not in_path.exists():
        raise FileNotFoundError(f"CSV file not found: {input_csv_path}")

    rows = []
    items_to_check = []
    with open(in_path, mode="r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            # Simple list without headers
            f.seek(0)
            simple_reader = csv.reader(f)
            for row in simple_reader:
                if row and row[0].strip():
                    items_to_check.append({"email": row[0].strip(), "_raw": {}})
        else:
            col_target = None
            for col in reader.fieldnames:
                if col.lower() in ("email", "emails", "domain", "domains", "website", "recipient_email", "contact_email"):
                    col_target = col
                    break
            if not col_target:
                col_target = reader.fieldnames[0]

            for row in reader:
                val = row.get(col_target, "").strip()
                if val:
                    items_to_check.append({"email": val, "_raw": row})

    results = []
    for entry in items_to_check:
        em = entry["email"]
        brand = entry["_raw"].get("brand_name") or entry["_raw"].get("brand") or None
        verdict = verify_email(
            email_or_domain=em,
            brand_name=brand,
            check_indian_only=check_indian_only,
            force_recheck=force_recheck
        )
        combined = {**entry["_raw"], **verdict}
        results.append(combined)

    if output_csv_path:
        out_path = Path(output_csv_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if results:
            fieldnames = list(results[0].keys())
            # Clean stages dictionary for CSV representation
            with open(out_path, mode="w", newline="", encoding="utf-8") as out_f:
                writer = csv.DictWriter(out_f, fieldnames=fieldnames)
                writer.writeheader()
                for r in results:
                    csv_row = {**r}
                    if isinstance(csv_row.get("stages"), dict):
                        csv_row["stages"] = json.dumps(csv_row["stages"])
                    writer.writerow(csv_row)

    return results


# --- DATABASE QUERY & AUDIT HELPERS ---
def get_verification_records(
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
    indian_only: Optional[bool] = None
) -> List[Dict[str, Any]]:
    """Queries verified email history from SQLite database with pagination."""
    query = "SELECT * FROM email_verifications WHERE 1=1"
    params = []

    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    if indian_only is not None:
        query += " AND is_indian = ?"
        params.append(1 if indian_only else 0)

    query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            if r.get("details"):
                try:
                    r["details"] = json.loads(r["details"])
                except Exception:
                    pass
        return rows


def get_verification_stats() -> Dict[str, Any]:
    """Returns total verification counts categorized by status and Indian origin."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM email_verifications")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM email_verifications WHERE status = 'valid'")
        valid_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM email_verifications WHERE status = 'catch-all'")
        catch_all_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM email_verifications WHERE status = 'disposable'")
        disposable_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM email_verifications WHERE status = 'invalid'")
        invalid_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM email_verifications WHERE status = 'timeout'")
        timeout_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM email_verifications WHERE is_indian = 1")
        indian_count = cur.fetchone()[0]

    return {
        "total": total,
        "valid": valid_count,
        "catch_all": catch_all_count,
        "disposable": disposable_count,
        "invalid": invalid_count,
        "timeout": timeout_count,
        "indian_entities": indian_count
    }


# --- CLI INTERFACE ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crevanta Self-Hosted Email Verifier & Indian Brand Filter")
    parser.add_argument("--csv", type=str, help="Path to input CSV file containing email addresses or domains")
    parser.add_argument("--output", type=str, help="Path to write verified results CSV")
    parser.add_argument("--email", type=str, help="Single email address or domain to verify")
    parser.add_argument("--no-indian-filter", action="store_true", help="Disable Indian brands strict filter")
    parser.add_argument("--force", action="store_true", help="Bypass SQLite cache and force re-verification")
    parser.add_argument("--skip-smtp", action="store_true", help="Skip SMTP handshake (DNS/MX only)")

    args = parser.parse_args()

    check_indian = not args.no_indian_filter

    if args.email:
        print(f"\n🔍 Verifying: {args.email}")
        res = verify_email(
            email_or_domain=args.email,
            check_indian_only=check_indian,
            force_recheck=args.force,
            skip_smtp=args.skip_smtp
        )
        print(json.dumps(res, indent=2))
        sys.exit(0 if res.get("approved") else 1)

    elif args.csv:
        print(f"\n📂 Processing CSV: {args.csv} (Indian Only: {check_indian})")
        res_list = verify_csv(
            input_csv_path=args.csv,
            output_csv_path=args.output,
            check_indian_only=check_indian,
            force_recheck=args.force
        )
        print(f"✓ Processed {len(res_list)} records.")
        if args.output:
            print(f"✓ Results saved to {args.output}")
        sys.exit(0)

    else:
        parser.print_help()
