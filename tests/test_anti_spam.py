import unittest
from fastapi.testclient import TestClient

from backend.app import app
from backend.anti_spam import (
    sanitize_for_inbox,
    optimize_subject_line,
    append_opt_out_footer,
    generate_spintax_pitch,
    analyze_deliverability
)
from backend.gmail_service import _create_mime_message

client = TestClient(app)


class TestAntiSpamDeliverability(unittest.TestCase):

    def test_sanitize_replaces_spam_triggers(self):
        spammy_text = (
            "Hey! This is 100% FREE and GUARANTEED to make money fast!!! "
            "Act now and don't miss out! Click here to claim your exclusive offer now!!!"
        )
        cleaned, triggers = sanitize_for_inbox(spammy_text)
        
        self.assertNotIn("100% free", cleaned.lower())
        self.assertNotIn("guaranteed", cleaned.lower())
        self.assertNotIn("make money", cleaned.lower())
        self.assertNotIn("act now", cleaned.lower())
        self.assertNotIn("click here", cleaned.lower())
        self.assertNotIn("!!!", cleaned)
        self.assertGreaterEqual(len(triggers), 4)

    def test_subject_line_optimization(self):
        # Exclamation marks and promotional wording
        raw_subj = "EXCLUSIVE PARTNERSHIP OPPORTUNITY 100% FREE NOW!!!"
        clean_subj = optimize_subject_line(raw_subj, "Gymshark", "Mayank")
        
        self.assertNotIn("!", clean_subj)
        self.assertNotIn("100% free", clean_subj.lower())
        self.assertLessEqual(len(clean_subj.split()), 8)

    def test_opt_out_footer_appended(self):
        body = "Hi Team,\n\nWe love your products and want to pitch a concept."
        protected_body = append_opt_out_footer(body)
        
        self.assertIn("opt-out", protected_body.lower())
        self.assertTrue(protected_body.startswith(body))

        # Does not duplicate if already present
        double_protected = append_opt_out_footer(protected_body)
        self.assertEqual(protected_body.count("opt-out"), 1)

    def test_spintax_variation_defeats_fingerprinting(self):
        creator = {
            "name": "Mayank Tanwar",
            "handle": "@mayank",
            "followers": "185K",
            "engagement_rate": "5.8%"
        }
        pitch1 = generate_spintax_pitch(
            brand_name="Gymshark",
            brand_niche="Activewear",
            creator=creator,
            concept_title="The Flow Test",
            brand_insight="Gymshark combines seamless knit with technical stretch.",
            creative_opportunity="Documenting authentic gym workouts.",
            how_it_works="Mayank wears the Onyx range during a high-intensity session."
        )
        self.assertIn("opt-out", pitch1["full_email_body"].lower())
        self.assertNotIn("!", pitch1["subject"])
        self.assertGreater(len(pitch1["full_email_body"]), 100)

    def test_deliverability_scoring(self):
        # Clean pitch should score 90+
        clean_body = (
            "Hi Gymshark Team,\n\n"
            "I lead creator partnerships at Crevanta Agency. We manage Mayank Tanwar (@mayank) "
            "who commands an engaged community of 185K activewear enthusiasts.\n\n"
            "We have formulated a bespoke 4-part video concept for Gymshark.\n\n"
            "Would your team be open to a 10-minute briefing call this week to review our moodboard?\n\n"
            "Best regards,\nCrevanta Partnerships Team\ncrevanta.com\n\n"
            "PS: If you'd prefer not to receive collaboration concepts, reply 'opt-out' and I'll remove you."
        )
        analysis_clean = analyze_deliverability(
            subject="Partnership Concept: Mayank × Gymshark",
            body=clean_body,
            to_email="press@gymshark.com"
        )
        self.assertGreaterEqual(analysis_clean["score"], 90)
        self.assertEqual(analysis_clean["risk_level"], "low")
        self.assertEqual(analysis_clean["badge_color"], "emerald")

        # Spammy pitch should be flagged
        spam_body = "100% FREE GUARANTEED CASH ACT NOW CLICK HERE TO BUY NOW WINNER!!!"
        analysis_spam = analyze_deliverability(
            subject="FREE MONEY $$$ NOW!!!",
            body=spam_body,
            to_email="test@test.com"
        )
        self.assertLess(analysis_spam["score"], 70)
        self.assertGreaterEqual(len(analysis_spam["findings"]), 2)

    def test_mime_headers_anti_spam_hygiene(self):
        msg = _create_mime_message(
            to_email="collabs@brand.com",
            subject="Partnership Concept: Creator x Brand",
            body_text="Hi team,\n\nLet's collaborate on an authentic story.\n\nBest,\nCrevanta",
            sender_name="Crevanta Partnerships",
            sender_email="partnerships@crevanta.com"
        )
        self.assertEqual(msg["Reply-To"], "Crevanta Partnerships <partnerships@crevanta.com>")
        self.assertIn("Crevanta Mail Engine", msg["X-Mailer"])
        self.assertEqual(msg["X-Priority"], "3")
        self.assertIn("crevanta.com", msg["Message-ID"])

    def test_api_deliverability_endpoints(self):
        # 1. Analyze endpoint
        res_analyze = client.post("/api/anti-spam/analyze", json={
            "subject": "Partnership Concept: Mayank x Gymshark",
            "body": "Hi team, we would love to collaborate. Reply opt-out if not interested.",
            "to_email": "press@gymshark.com"
        })
        self.assertEqual(res_analyze.status_code, 200)
        data_analyze = res_analyze.json()
        self.assertIn("score", data_analyze)
        self.assertGreaterEqual(data_analyze["score"], 80)

        # 2. Sanitize endpoint
        res_sanitize = client.post("/api/anti-spam/sanitize", json={
            "subject": "100% FREE SPONSORSHIP OFFER!!!",
            "body": "Act now for a guaranteed winner deal!!!"
        })
        self.assertEqual(res_sanitize.status_code, 200)
        data_sanitize = res_sanitize.json()
        self.assertNotIn("100% free", data_sanitize["clean_subject"].lower())
        self.assertNotIn("act now", data_sanitize["clean_body"].lower())
        self.assertIn("opt-out", data_sanitize["clean_body"].lower())

        # 3. Status endpoint
        res_status = client.get("/api/deliverability/status")
        self.assertEqual(res_status.status_code, 200)
        data_status = res_status.json()
        self.assertTrue(data_status["anti_spam_shield_active"])
        self.assertTrue(data_status["human_pacing_active"])
        self.assertEqual(data_status["safe_daily_limit"], 50)


if __name__ == "__main__":
    unittest.main()
