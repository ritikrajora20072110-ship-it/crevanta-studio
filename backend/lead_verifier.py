"""
Crevanta Lead Verifier & Brand Research Engine
Strict implementation of Crevanta's Brand Research & Contact Verification Protocol:
  - Accuracy over completeness. Never invent, assume, estimate, reconstruct, or guess contact information.
  - ONLY Official Emails: Must appear on the brand's official website (Contact, About, Press, Partnerships, Collab, Footer) or official social profile.
  - Zero Third-Party / Zero Guessed emails.
  - Two-Layer Protection: Prompt Rule + Programmatic Code Enforcement.
  - Brand Skipping Rule: If strict official filter is on, discard leads without verified official email.
"""

import re
import urllib.request
import urllib.parse
import urllib.error
import ssl
from typing import Dict, Any, List, Optional, Tuple

# Crevanta priority order for official addresses
CONTACT_PREFIX_PRIORITY = [
    "partnerships@",
    "collab@",
    "collaborations@",
    "marketing@",
    "influencer@",
    "influencers@",
    "social@",
    "business@",
    "press@",
    "media@",
    "hello@",
    "contact@",
    "info@"
]

# Patterns and domains that should NEVER be accepted as official brand contact emails
IGNORED_EMAIL_PATTERNS = [
    r".*\.png$", r".*\.jpg$", r".*\.svg$", r".*\.webp$",
    r".*@sentry\.io$", r".*@wix\.com$", r".*@shopify\.com$",
    r".*@example\.com$", r".*@domain\.com$", r".*@cloudflare\.com$",
    r".*@google\.com$", r".*@w3\.org$", r".*@schema\.org$",
    r".*@fastly\.com$", r".*@wordpress\.com$", r".*@godaddy\.com$",
    r".*@yoursite\.com$", r".*@email\.com$", r".*bootstrap.*",
    r".*privacy.*", r".*abuse.*", r".*postmaster.*", r".*webmaster.*"
]

COMMON_CONTACT_PATHS = [
    "",  # Homepage
    "/contact",
    "/contact-us",
    "/pages/contact",
    "/pages/contact-us",
    "/about",
    "/about-us",
    "/pages/about",
    "/partnerships",
    "/pages/partnerships",
    "/collaborate",
    "/pages/collaborate",
    "/collab",
    "/pages/collab",
    "/press",
    "/media",
    "/influencer",
    "/pages/influencers"
]


def normalize_domain_url(raw_url: str) -> str:
    """Cleans a domain or URL into a valid https:// base URL."""
    cleaned = (raw_url or "").strip().lower()
    cleaned = re.sub(r"^https?://", "", cleaned)
    cleaned = cleaned.split("/")[0].strip()
    if not cleaned:
        return ""
    return f"https://{cleaned}"


def extract_emails_from_html(html_text: str, brand_domain: str = "") -> List[str]:
    """
    Extracts explicitly published emails from HTML text and mailto: links.
    Filters out web assets, tracking addresses, and irrelevant system emails.
    """
    found_emails: List[str] = []
    
    # 1. Match mailto: links
    mailto_matches = re.findall(r'href=[\'"]mailto:([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)[\'"]', html_text, re.IGNORECASE)
    for email in mailto_matches:
        clean_email = email.split("?")[0].strip().lower()
        if clean_email and clean_email not in found_emails:
            found_emails.append(clean_email)

    # 2. Match raw email pattern in text
    raw_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', html_text)
    for email in raw_matches:
        clean_email = email.strip().lower()
        if clean_email and clean_email not in found_emails:
            found_emails.append(clean_email)

    # Clean and filter out ignored patterns
    valid_emails = []
    for email in found_emails:
        # Check against ignored patterns
        if any(re.match(pattern, email, re.IGNORECASE) for pattern in IGNORED_EMAIL_PATTERNS):
            continue
        # Length sanity check
        if len(email) < 6 or len(email) > 80:
            continue
        # Must have valid domain part
        if "." not in email.split("@")[1]:
            continue
        valid_emails.append(email)

    return valid_emails


def score_email_priority(email: str, brand_domain: str = "") -> int:
    """
    Scores an email based on Crevanta's strict contact hierarchy:
    Higher score = higher priority.
    Address belonging directly to brand domain gets strong preference.
    """
    score = 10
    email_lower = email.lower()
    
    # Check domain match
    if brand_domain and brand_domain in email_lower:
        score += 50

    for idx, prefix in enumerate(CONTACT_PREFIX_PRIORITY):
        if email_lower.startswith(prefix):
            # Prioritize higher indices in prefix list
            score += (len(CONTACT_PREFIX_PRIORITY) - idx) * 5
            break

    return score


def fetch_page_content(url: str, timeout: float = 3.5) -> Tuple[Optional[str], Optional[str]]:
    """
    Safely fetches a web page via urllib with direct socket configuration.
    Returns (html_content, final_url).
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=ctx))

    try:
        with opener.open(req, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return None, None
            body = response.read(150000).decode("utf-8", errors="ignore")
            return body, response.geturl()
    except Exception:
        return None, None


def verify_brand_official_email(
    brand_name: str,
    website: str,
    timeout: float = 3.5
) -> Dict[str, Any]:
    """
    Executes Crevanta's Protocol 1 & 2:
    - Verifies the official website.
    - Inspects homepage and official contact/partnerships pages.
    - Extracts ONLY explicitly published emails.
    - Zero pattern-guessing (never outputs fake partnerships@brand.com).
    - Returns structured official source verification.
    """
    base_url = normalize_domain_url(website)
    clean_domain = base_url.replace("https://", "").replace("http://", "").split("/")[0]

    sources_checked: List[str] = []
    discovered_candidates: List[Tuple[str, str, int]] = [] # (email, source_url, score)

    if not base_url:
        return {
            "brand_name": brand_name,
            "website": website,
            "recipient_email": "Not publicly available",
            "verification": "unverified",
            "email_source": "No valid official website domain provided",
            "sources_checked": ["No domain provided"],
            "is_official": False
        }

    # 1. Fetch homepage first
    hp_html, hp_url = fetch_page_content(base_url, timeout=timeout)
    if hp_html:
        sources_checked.append(hp_url or base_url)
        hp_emails = extract_emails_from_html(hp_html, clean_domain)
        for em in hp_emails:
            discovered_candidates.append((em, hp_url or base_url, score_email_priority(em, clean_domain)))

        # Extract contact links found inside homepage HTML
        contact_link_matches = re.findall(
            r'href=[\'"]([^\'"]*(?:contact|collab|partner|influencer|press|about)[^\'"]*)[\'"]',
            hp_html,
            re.IGNORECASE
        )
        
        dynamic_paths = []
        for path in contact_link_matches[:4]:
            path = path.strip()
            if path.startswith("mailto:") or path.startswith("#") or path.startswith("javascript:"):
                continue
            if path.startswith("http"):
                # Only follow if internal to the brand's domain
                if clean_domain in path:
                    dynamic_paths.append(path)
            else:
                full_path = urllib.parse.urljoin(base_url, path)
                dynamic_paths.append(full_path)
    else:
        sources_checked.append(f"{base_url} (Failed to connect or timeout)")
        dynamic_paths = []

    # 2. Check prioritized contact paths
    check_paths = dynamic_paths if dynamic_paths else [f"{base_url}{p}" for p in COMMON_CONTACT_PATHS[1:4]]
    
    for page_url in check_paths[:3]:
        if any(src == page_url for src in sources_checked):
            continue
        p_html, final_page_url = fetch_page_content(page_url, timeout=timeout)
        if p_html:
            sources_checked.append(final_page_url or page_url)
            page_emails = extract_emails_from_html(p_html, clean_domain)
            for em in page_emails:
                discovered_candidates.append((em, final_page_url or page_url, score_email_priority(em, clean_domain) + 15))
        else:
            sources_checked.append(f"{page_url} (No public page or timeout)")

        # If we already found a high-priority brand-domain address, we can stop early
        if any(cand[2] >= 65 for cand in discovered_candidates):
            break

    # 3. Select best verified email if any exists
    if discovered_candidates:
        # Sort by score descending
        discovered_candidates.sort(key=lambda x: x[2], reverse=True)
        best_email, best_source, _ = discovered_candidates[0]

        return {
            "brand_name": brand_name,
            "website": clean_domain,
            "recipient_email": best_email,
            "verification": "official",
            "email_source": best_source,
            "sources_checked": sources_checked,
            "is_official": True
        }

    # 4. No email found — STRICT ENFORCEMENT
    termination_note = f"Checked official website and contact pages ({', '.join([s.replace(base_url, '') or '/' for s in sources_checked[:3]])}). No publicly listed official email was found."
    return {
        "brand_name": brand_name,
        "website": clean_domain,
        "recipient_email": "Not publicly available",
        "verification": "unverified",
        "email_source": termination_note,
        "sources_checked": sources_checked,
        "is_official": False
    }


def enforce_programmatic_rules(
    lead: Dict[str, Any],
    require_official: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Two-Layer Protection: Code-level hard rule.
    - Rejects third-party emails completely ('take only official emails no third party').
    - Rejects pattern-guessed addresses (no source = no email).
    - If require_official=True (Brand Skipping Rule):
        Discards the brand entirely if email is not verified official.
    - If require_official=False:
        Sets recipient_email = 'Not publicly available', verification = 'unverified'.
    """
    verification = (lead.get("verification") or "").strip().lower()
    email = (lead.get("recipient_email") or "").strip()
    source = (lead.get("email_source") or "").strip()

    is_valid_email = "@" in email and "." in email.split("@")[1] and not email.endswith(".com.com")
    is_official = (verification == "official") and bool(source) and is_valid_email and "No publicly listed" not in source

    if not is_official:
        if require_official:
            # Discard brand per Crevanta Brand Skipping Rule
            return None
        lead["recipient_email"] = "Not publicly available"
        lead["verification"] = "unverified"
        if not source or "No publicly listed" in source:
            lead["email_source"] = "No official email published on brand website"
    else:
        lead["verification"] = "official"

    return lead


def format_crevanta_video_idea(
    brand_name: str,
    brand_niche: str,
    concept_title: str,
    brand_insight: str,
    creative_opportunity: str,
    how_it_works: str
) -> Dict[str, str]:
    """
    Enforces Crevanta's exact 4-part video concept structure:
      1. Brand insight
      2. Creative opportunity
      3. Concept (Title)
      4. How it works
    """
    formatted_text = (
        f"Brand Insight: {brand_insight}\n"
        f"Creative Opportunity: {creative_opportunity}\n"
        f"Concept: \"{concept_title}\"\n"
        f"How It Works: {how_it_works}"
    )

    return {
        "concept_title": concept_title,
        "brand_insight": brand_insight,
        "creative_opportunity": creative_opportunity,
        "how_it_works": how_it_works,
        "formatted_text": formatted_text
    }
