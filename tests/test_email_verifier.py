import unittest
import tempfile
import csv
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.app import app
from backend.email_verifier import (
    validate_syntax,
    is_disposable_domain,
    is_indian_entity,
    check_domain_exists,
    lookup_mx_records,
    check_smtp_mailbox,
    apply_mx_rate_limit,
    verify_email,
    verify_email_list,
    verify_csv,
    get_cached_verification,
    save_verification_to_db,
    get_verification_records,
    get_verification_stats
)
from backend.lead_verifier import (
    verify_brand_official_email,
    enforce_programmatic_rules,
    get_verified_official_catalog
)

client = TestClient(app)


class TestEmailVerifier(unittest.TestCase):

    def test_syntax_validation(self):
        # 1. Valid RFC 5322 emails
        valid, clean, local, domain = validate_syntax("collab@boat-lifestyle.com")
        self.assertTrue(valid)
        self.assertEqual(local, "collab")
        self.assertEqual(domain, "boat-lifestyle.com")

        valid, clean, local, domain = validate_syntax("press.team+partner@mamaearth.in")
        self.assertTrue(valid)
        self.assertEqual(domain, "mamaearth.in")

        # 2. Invalid emails
        valid, clean, local, err = validate_syntax("plainaddress")
        # plainaddress has no dot, so invalid domain too
        self.assertFalse(valid)

        valid, clean, local, err = validate_syntax("user@@domain.com")
        self.assertFalse(valid)

        valid, clean, local, err = validate_syntax("user@domain..com")
        self.assertFalse(valid)

        # 3. Domain only input
        valid, clean, local, domain = validate_syntax("mamaearth.in")
        self.assertTrue(valid)
        self.assertEqual(domain, "mamaearth.in")

    def test_disposable_domain_detection(self):
        # Known disposable domains must be flagged
        self.assertTrue(is_disposable_domain("mailinator.com"))
        self.assertTrue(is_disposable_domain("tempmail.com"))
        self.assertTrue(is_disposable_domain("guerrillamail.com"))
        self.assertTrue(is_disposable_domain("sub.10minutemail.com"))

        # Legitimate brand domains must NOT be flagged
        self.assertFalse(is_disposable_domain("boat-lifestyle.com"))
        self.assertFalse(is_disposable_domain("gmail.com"))
        self.assertFalse(is_disposable_domain("mamaearth.in"))

    def test_indian_brand_filter(self):
        # 1. Indian ccTLDs
        is_ind, reason = is_indian_entity("care@mamaearth.in")
        self.assertTrue(is_ind)
        self.assertIn(".in", reason)

        is_ind, reason = is_indian_entity("support@snitch.co.in")
        self.assertTrue(is_ind)

        # 2. Known Indian Brand domains (.com)
        is_ind, reason = is_indian_entity("collab@boat-lifestyle.com")
        self.assertTrue(is_ind)

        is_ind, reason = is_indian_entity("care@sugarcosmetics.com")
        self.assertTrue(is_ind)

        # 3. Known Indian Brand name
        is_ind, reason = is_indian_entity("info@custombrand.com", brand_name="boAt Lifestyle")
        self.assertTrue(is_ind)

        # 4. Indian website content markers (GSTIN, +91, INR, Indian metros)
        gstin_text = "Registered office in Mumbai, Maharashtra. GSTIN: 27AAAAA0000A1Z5. Phone: +91 22 12345678. Price: INR 1,499."
        is_ind, reason = is_indian_entity("info@novelbrand.com", website_text=gstin_text)
        self.assertTrue(is_ind)

        # 5. Non-Indian company rejected
        is_ind, reason = is_indian_entity("press@gymshark.com")
        self.assertFalse(is_ind)

        is_ind, reason = is_indian_entity("collab@target.com")
        self.assertFalse(is_ind)

    @patch("backend.email_verifier.dns.resolver.Resolver")
    def test_domain_existence_check(self, mock_resolver_cls):
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = ["104.21.32.1"]
        mock_resolver_cls.return_value = mock_resolver

        exists, ip = check_domain_exists("boat-lifestyle.com")
        self.assertTrue(exists)

    def test_smtp_catch_all_detection(self):
        # Mock smtplib.SMTP so fake address is accepted (code 250)
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp_cls.return_value = mock_smtp
            mock_smtp.connect.return_value = (220, b"mx.catchall.com")
            mock_smtp.has_extn.return_value = False
            mock_smtp.mail.return_value = (250, b"Sender OK")
            # Fake random mailbox returns 250 -> CATCH-ALL!
            mock_smtp.rcpt.return_value = (250, b"Recipient OK")

            res = check_smtp_mailbox("mx.catchall.com", "target@catchall.com")
            self.assertEqual(res["status"], "catch-all")
            self.assertTrue(res["is_catch_all"])
            self.assertIn("catch-all", res["reason"].lower())

    def test_smtp_valid_and_invalid_mailbox(self):
        # 1. Valid mailbox: Fake address rejected (550), Target address accepted (250)
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp_cls.return_value = mock_smtp
            mock_smtp.connect.return_value = (220, b"mx.target.com")
            mock_smtp.has_extn.return_value = False
            mock_smtp.mail.return_value = (250, b"Sender OK")

            # First rcpt (fake address) fails 550, Second rcpt (real address) passes 250
            mock_smtp.rcpt.side_effect = [(550, b"User unknown"), (250, b"User exists")]

            res = check_smtp_mailbox("mx.target.com", "real@target.com")
            self.assertEqual(res["status"], "valid")
            self.assertFalse(res["is_catch_all"])
            self.assertEqual(res["smtp_code"], 250)

        # 2. Invalid mailbox: Both fail or real mailbox fails 550
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp_cls.return_value = mock_smtp
            mock_smtp.connect.return_value = (220, b"mx.target.com")
            mock_smtp.has_extn.return_value = False
            mock_smtp.mail.return_value = (250, b"Sender OK")

            mock_smtp.rcpt.side_effect = [(550, b"User unknown"), (550, b"No such mailbox")]

            res = check_smtp_mailbox("mx.target.com", "fake@target.com")
            self.assertEqual(res["status"], "invalid")
            self.assertEqual(res["smtp_code"], 550)

    def test_mx_rate_limiter(self):
        import time
        # Applying rate limit back-to-back to same MX host must pace queries
        t0 = time.time()
        apply_mx_rate_limit("mx1.testdomain.com", delay_seconds=0.1)
        apply_mx_rate_limit("mx1.testdomain.com", delay_seconds=0.1)
        elapsed = time.time() - t0
        self.assertGreaterEqual(elapsed, 0.08)

    def test_sqlite_persistence_and_caching(self):
        test_email = "test_cache_check@boat-lifestyle.com"
        record = {
            "email": test_email,
            "domain": "boat-lifestyle.com",
            "status": "valid",
            "reason": "Verified via test",
            "is_indian": True,
            "is_catch_all": False,
            "mx_host": "mail.boat-lifestyle.com",
            "smtp_code": 250,
            "details": {"test": True}
        }
        save_verification_to_db(record)

        cached = get_cached_verification(test_email)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["status"], "valid")
        self.assertEqual(cached["mx_host"], "mail.boat-lifestyle.com")
        self.assertTrue(cached["cached"])

    def test_csv_file_verification(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as in_f:
            in_f.write("email,brand_name\n")
            in_f.write("collab@boat-lifestyle.com,boAt\n")
            in_f.write("invalid-syntax,BadBrand\n")
            in_f.write("test@mailinator.com,DisposableBrand\n")
            in_path = in_f.name

        out_path = in_path.replace(".csv", "_out.csv")

        try:
            results = verify_csv(in_path, out_path, check_indian_only=False)
            self.assertEqual(len(results), 3)

            # Check that output CSV was generated and has headers
            self.assertTrue(Path(out_path).exists())
            with open(out_path, mode="r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                self.assertEqual(len(rows), 3)
                statuses = [r["status"] for r in rows]
                self.assertIn("disposable", statuses)
        finally:
            Path(in_path).unlink(missing_ok=True)
            Path(out_path).unlink(missing_ok=True)

    def test_fastapi_endpoints(self):
        # 1. Stats endpoint
        res = client.get("/api/email-verifier/stats")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total", data)
        self.assertIn("valid", data)
        self.assertIn("indian_entities", data)

        # 2. Single verification endpoint
        res = client.post("/api/email-verifier/verify", json={
            "email_or_domain": "contact@mamaearth.in",
            "skip_smtp": True
        })
        self.assertEqual(res.status_code, 200)
        v_data = res.json()
        self.assertTrue(v_data["is_indian"])

        # 3. Records history endpoint
        res = client.get("/api/email-verifier/records?limit=10")
        self.assertEqual(res.status_code, 200)
        records = res.json()
        self.assertIsInstance(records, list)

    def test_pipeline_gate_indian_only(self):
        # 1. Indian brand with verified email passes
        lead_ind = {
            "brand_name": "boAt Lifestyle",
            "website": "boat-lifestyle.com",
            "recipient_email": "collab@boat-lifestyle.com",
            "verification": "official",
            "email_source": "https://www.boat-lifestyle.com/pages/contact-us"
        }
        approved = enforce_programmatic_rules(lead_ind, require_official=True, require_indian=True)
        self.assertIsNotNone(approved)
        self.assertTrue(approved["is_indian"])

        # 2. Non-Indian brand is rejected under Indian Brands Only rule
        lead_foreign = {
            "brand_name": "Gymshark",
            "website": "gymshark.com",
            "recipient_email": "press@gymshark.com",
            "verification": "official",
            "email_source": "https://support.gymshark.com"
        }
        rejected = enforce_programmatic_rules(lead_foreign, require_official=True, require_indian=True)
        self.assertIsNone(rejected)

        # 3. Verified official catalog returns Indian brands only when indian_only=True
        indian_catalog = get_verified_official_catalog(count=15, indian_only=True)
        self.assertGreaterEqual(len(indian_catalog), 5)
        for b in indian_catalog:
            is_ind, _ = is_indian_entity(b["website"], brand_name=b["brand_name"])
            self.assertTrue(is_ind, f"Brand {b['brand_name']} ({b['website']}) should be Indian")


if __name__ == "__main__":
    unittest.main()
