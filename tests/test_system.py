import json
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.app import app
from backend.config import Config
from backend.storage import (
    get_all_creators,
    get_creator_by_id,
    save_creator,
    delete_creator,
    get_all_commands,
    save_command,
    delete_command,
    get_outreach_history,
    record_outreach,
    get_all_talk_sessions,
    get_talk_session,
    save_talk_session,
    append_talk_message,
    delete_talk_session,
    clear_all_talks
)
from backend.gmail_service import (
    _create_mime_message,
    send_email_via_smtp,
    save_as_gmail_draft,
    verify_gmail_connection
)
from backend.ollama_client import (
    check_ollama_status,
    generate_brand_pitches_ollama,
    converse_with_ollama
)

client = TestClient(app)


class TestCrevantaSystem(unittest.TestCase):

    def test_api_status(self):
        response = client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ai_provider"], "ollama")
        self.assertIn("ollama_model", data)
        self.assertIn("gmail_configured", data)
        self.assertIn("agency_name", data)

    def test_creators_crud(self):
        # List creators
        response = client.get("/api/creators")
        self.assertEqual(response.status_code, 200)
        creators = response.json()
        self.assertGreaterEqual(len(creators), 4)

        # Get single creator
        first_id = creators[0]["id"]
        res_single = client.get(f"/api/creators/{first_id}")
        self.assertEqual(res_single.status_code, 200)
        self.assertEqual(res_single.json()["id"], first_id)

        # Create temporary creator
        temp_creator = {
            "name": "Test Creator",
            "handle": "@testcreator",
            "niche": "Gaming",
            "followers": "25K",
            "engagement_rate": "8.0%",
            "avg_views": "20K",
            "bio": "Gaming streamer testing Crevanta",
            "target_brands": "Gaming mice, monitors",
            "collab_angles": "Livestream shoutout",
            "media_kit_url": "https://crevanta.com/test",
            "sample_rate": "$500"
        }
        res_create = client.post("/api/creators", json=temp_creator)
        self.assertEqual(res_create.status_code, 200)
        created = res_create.json()
        self.assertEqual(created["name"], "Test Creator")
        created_id = created["id"]

        # Clean up temporary creator
        res_delete = client.delete(f"/api/creators/{created_id}")
        self.assertEqual(res_delete.status_code, 200)

    def test_commands_crud(self):
        response = client.get("/api/commands")
        self.assertEqual(response.status_code, 200)
        cmds = response.json()
        self.assertIsInstance(cmds, list)

        temp_cmd = {
            "name": "Test Command Workflow",
            "prompt": "Find 3 indie gaming studios",
            "email_style": "punchy"
        }
        res_save = client.post("/api/commands", json=temp_cmd)
        self.assertEqual(res_save.status_code, 200)
        saved = res_save.json()
        self.assertEqual(saved["name"], "Test Command Workflow")
        cmd_id = saved["id"]

        res_del = client.delete(f"/api/commands/{cmd_id}")
        self.assertEqual(res_del.status_code, 200)

    def test_mime_message_creation(self):
        msg = _create_mime_message(
            to_email="brand@example.com",
            subject="Collab Inquiry",
            body_text="Hi Brand Team,\nWe'd love to collaborate."
        )
        self.assertEqual(msg["To"], "brand@example.com")
        self.assertEqual(msg["Subject"], "Collab Inquiry")
        self.assertIn("Crevanta", msg["From"])

    def test_gmail_zero_faking_policy(self):
        # Smtp sending with invalid password MUST fail transparently without mock success
        with patch("backend.config.Config.GMAIL_APP_PASSWORD", "invalidpassword123"):
            res_send = send_email_via_smtp(
                to_email="test@brand.com",
                subject="Collab Pitch",
                body_text="Hi,\nLet's work together.",
                creator_name="Maya Sen",
                brand_name="Test Brand"
            )
            self.assertFalse(res_send["success"])
            self.assertTrue(len(res_send.get("error", "")) > 0)

    def test_gmail_credentials_test_endpoint(self):
        # Testing invalid credentials via endpoint should report error without crashing
        res = client.post("/api/gmail/test-credentials", json={
            "user": "testinvalid@gmail.com",
            "app_password": "invalidpassword"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["connected"])
        self.assertIn(data["error"], ["BAD_CREDENTIALS", "AUTH_FAILED"])

    def test_talk_records_persistence(self):
        # Append a talk message
        session = append_talk_message(
            session_id=None,
            user_message="Brainstorm 3 collaboration ideas for luxury watches",
            assistant_reply="Here are 3 collaboration concepts for luxury horology...",
            creator_id="creator_maya",
            creator_name="Maya Sen"
        )
        session_id = session["id"]
        self.assertTrue(session_id.startswith("talk_"))
        self.assertEqual(len(session["messages"]), 2)

        # Retrieve session
        fetched = get_talk_session(session_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["title"], session["title"])

        # Test endpoint
        res = client.get(f"/api/talks/{session_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["id"], session_id)

        # Clean up
        deleted = delete_talk_session(session_id)
        self.assertTrue(deleted)

    def test_ollama_status_endpoint(self):
        res = client.get("/api/ollama/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("running", data)
        self.assertIn("models", data)
        self.assertIn("base_url", data)

    def test_ollama_switch_model_endpoint(self):
        orig_model = Config.OLLAMA_MODEL
        try:
            res = client.post("/api/ollama/switch-model", json={"model": "llama3.2:1b"})
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["active_model"], "llama3.2:1b")
            self.assertEqual(Config.OLLAMA_MODEL, "llama3.2:1b")
        finally:
            client.post("/api/ollama/switch-model", json={"model": orig_model})

    def test_ollama_offline_policy(self):
        # When Ollama is offline, MUST return OLLAMA_NOT_RUNNING error without canned mock brands
        creator = get_creator_by_id("creator_maya")
        with patch("backend.ollama_client.check_ollama_status", return_value={"running": False, "models": []}):
            res = generate_brand_pitches_ollama(
                creator=creator,
                brand_prompt="Discover luxury skincare",
                video_idea="Morning routine",
                count=5
            )
            self.assertFalse(res["success"])
            self.assertEqual(res["error"], "OLLAMA_NOT_RUNNING")
            self.assertIn("ollama serve", res["message"])

    def test_ollama_3part_generation_with_mocked_response(self):
        # Verify 3-part email schema parsing when local Ollama returns valid JSON
        mock_ollama_response = {
            "message": {
                "content": json.dumps({
                    "summary": "High synergy wellness partners discovered locally via Ollama",
                    "brands": [
                        {
                            "brand_name": "Kin Hydration",
                            "website": "kinhydration.com",
                            "recipient_email": "partnerships@kinhydration.com",
                            "verification": "official",
                            "email_source": "https://kinhydration.com/pages/contact",
                            "contact_person": "Creator Lead",
                            "brand_niche": "Clean Electrolytes",
                            "why_fit": "Perfect fit for endurance morning routines",
                            "subject": "Collab Idea: Aarav Patel x Kin Hydration",
                            "part1_about_creator": "Aarav Patel reaches 78K functional athletes with 5.2% engagement.",
                            "part2_concept_title": "The Post-Run Mineral Reset",
                            "part2_brand_insight": "Kin delivers clean electrolyte replenishment without artificial sweeteners.",
                            "part2_creative_opportunity": "Putting the product to a recovery test following an intense tempo run.",
                            "part2_how_it_works": "Aarav documents his recovery routine, highlighting hydration absorption.",
                            "part2_video_idea": "Brand Insight: Kin delivers clean hydration.\nCreative Opportunity: Recovery test.\nConcept: \"The Post-Run Mineral Reset\"\nHow It Works: Aarav documents his recovery.",
                            "part3_15day_campaign": "Day 1 Kickoff, Day 3 Hero Reel Drop, Day 7 Story AMA, Day 15 Analytics.",
                            "full_email_body": "Hi Kin Team,\n\nAarav reaches 78K...\n\nVideo concept...\n\nBest,\nCrevanta"
                        }
                    ]
                })
            }
        }

        with patch("backend.ollama_client.check_ollama_status", return_value={"running": True, "models": ["llama3.2:1b"]}):
            with patch("backend.ollama_client._call_ollama_chat", return_value=mock_ollama_response):
                creator = get_creator_by_id("creator_aarav")
                res = generate_brand_pitches_ollama(
                    creator=creator,
                    brand_prompt="Find hydration supplements",
                    video_idea="Morning run",
                    campaign_15day_notes="15-day campaign",
                    count=1
                )
                self.assertTrue(res["success"])
                self.assertEqual(res["provider"], "ollama")
                self.assertEqual(len(res["brands"]), 1)
                brand = res["brands"][0]
                self.assertEqual(brand["brand_name"], "Kin Hydration")
                self.assertEqual(brand["recipient_email"], "partnerships@kinhydration.com")
                self.assertEqual(brand["verification"], "official")
                self.assertIn("part1_about_creator", brand)
                self.assertIn("part2_video_idea", brand)
                self.assertIn("part2_concept_title", brand)
                self.assertIn("part3_15day_campaign", brand)
                self.assertIn("full_email_body", brand)

    def test_contact_verification_two_layer_rule(self):
        from backend.lead_verifier import enforce_programmatic_rules
        
        # 1. Official email with verified source must be preserved
        lead_official = {
            "brand_name": "Andamen",
            "recipient_email": "partnerships@andamen.com",
            "verification": "official",
            "email_source": "https://andamen.com/contact-us"
        }
        verified = enforce_programmatic_rules(lead_official)
        self.assertIsNotNone(verified)
        self.assertEqual(verified["recipient_email"], "partnerships@andamen.com")
        self.assertEqual(verified["verification"], "official")

        # 2. Third-party source must be REJECTED ('take only official emails no third party')
        lead_third_party = {
            "brand_name": "ThirdParty Brand",
            "recipient_email": "info@thirdparty.com",
            "verification": "third-party",
            "email_source": "LinkedIn Directory"
        }
        stripped = enforce_programmatic_rules(lead_third_party)
        self.assertIsNotNone(stripped)
        self.assertEqual(stripped["recipient_email"], "Not publicly available")
        self.assertEqual(stripped["verification"], "unverified")

        # 3. Guess/No Source must be REJECTED (Zero Guessing Policy)
        lead_guessed = {
            "brand_name": "Guessed Brand",
            "recipient_email": "partnerships@guessedbrand.com",
            "verification": "unverified",
            "email_source": ""
        }
        guarded = enforce_programmatic_rules(lead_guessed)
        self.assertEqual(guarded["recipient_email"], "Not publicly available")
        self.assertEqual(guarded["verification"], "unverified")

    def test_brand_skipping_rule(self):
        from backend.lead_verifier import enforce_programmatic_rules
        
        # When require_official=True, unverified brands must be DISCARDED (return None)
        lead_unverified = {
            "brand_name": "Unverified Brand",
            "recipient_email": "Not publicly available",
            "verification": "unverified",
            "email_source": "No public email found"
        }
        skipped = enforce_programmatic_rules(lead_unverified, require_official=True)
        self.assertIsNone(skipped)

        # Official lead must be KEPT
        lead_official = {
            "brand_name": "Verified Brand",
            "recipient_email": "contact@verifiedbrand.com",
            "verification": "official",
            "email_source": "https://verifiedbrand.com/contact"
        }
        kept = enforce_programmatic_rules(lead_official, require_official=True)
        self.assertIsNotNone(kept)
        self.assertEqual(kept["recipient_email"], "contact@verifiedbrand.com")

    def test_verify_lead_api_endpoint(self):
        # Test /api/verify-lead endpoint
        with patch("backend.app.verify_brand_official_email") as mock_verify:
            mock_verify.return_value = {
                "brand_name": "Andamen",
                "website": "andamen.com",
                "recipient_email": "contact@andamen.com",
                "verification": "official",
                "email_source": "https://andamen.com/contact",
                "sources_checked": ["https://andamen.com", "https://andamen.com/contact"],
                "is_official": True
            }
            res = client.post("/api/verify-lead", json={
                "brand_name": "Andamen",
                "website": "andamen.com",
                "creator_id": "creator_aarav"
            })
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertTrue(data["success"])
            lead = data["lead"]
            self.assertEqual(lead["brand_name"], "Andamen")
            self.assertEqual(lead["recipient_email"], "contact@andamen.com")
            self.assertEqual(lead["verification"], "official")
            self.assertIn("part2_concept_title", lead)
            self.assertIn("part2_brand_insight", lead)
            self.assertIn("part2_creative_opportunity", lead)
            self.assertIn("part2_how_it_works", lead)

    def test_bulk_job_dispatch(self):
        pitches = [
            {
                "brand_name": f"Bulk Brand {i}",
                "recipient_email": f"partner{i}@testbrand.com",
                "subject": f"Partnership Offer #{i}",
                "body": f"Hello Brand #{i}, let's collaborate.",
                "creator_name": "Maya Sen"
            }
            for i in range(1, 4)
        ]

        # Start bulk job
        res_start = client.post("/api/email/bulk-job", json={"pitches": pitches, "mode": "draft", "delay_seconds": 0.01})
        self.assertEqual(res_start.status_code, 200)
        job_info = res_start.json()
        self.assertIn("job_id", job_info)
        job_id = job_info["job_id"]

        import time
        time.sleep(0.15)
        res_status = client.get(f"/api/email/bulk-job/{job_id}")
        self.assertEqual(res_status.status_code, 200)
        status_data = res_status.json()
        self.assertEqual(status_data["total"], 3)

    def test_ollama_service_control(self):
        with patch("backend.app.start_ollama_service", return_value={"success": True, "running": True, "message": "Ollama started"}):
            res = client.post("/api/ollama/start")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertTrue(data["success"])
            self.assertTrue(data["running"])

        with patch("backend.app.stop_ollama_service", return_value={"success": True, "running": False, "message": "Ollama stopped"}):
            res = client.post("/api/ollama/stop")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertTrue(data["success"])
    def test_brand_discovery_count_and_strict_guarantee(self):
        creator = {
            "name": "Alex Vance",
            "handle": "@alexv",
            "niche": "Tech & Workspace",
            "followers": "85K",
            "engagement_rate": "5.1%"
        }
        with patch("backend.ollama_client.check_ollama_status", return_value={"running": True}):
            with patch("backend.ollama_client._call_ollama_chat", return_value={"message": {"content": '{"brands": []}'}}):
                # 1. Strict official mode for 10 brands
                res10 = generate_brand_pitches_ollama(
                    creator=creator,
                    brand_prompt="Desk setups and mechanical keyboards",
                    count=10,
                    strict_official_only=True
                )
                self.assertTrue(res10["success"])
                self.assertEqual(len(res10["brands"]), 10)
                self.assertTrue(all(b["verification"] == "official" for b in res10["brands"]))
                self.assertTrue(all("@" in b["recipient_email"] for b in res10["brands"]))
                self.assertTrue(all("http" in b["email_source"] for b in res10["brands"]))
                self.assertTrue(all(bool(b.get("part2_concept_title")) for b in res10["brands"]))

                # 2. Strict official mode for 50 brands
                res50 = generate_brand_pitches_ollama(
                    creator=creator,
                    brand_prompt="Workspace and aesthetic essentials",
                    count=50,
                    strict_official_only=True
                )
                self.assertTrue(res50["success"])
                self.assertEqual(len(res50["brands"]), 50)
                self.assertTrue(all(b["verification"] == "official" for b in res50["brands"]))

                # 3. Via API endpoint
                api_res = client.post("/api/generate-pitches", json={
                    "creator_id": "creator_1",
                    "prompt": "Desk accessories",
                    "count": 10,
                    "strict_official_only": True
                })
                self.assertEqual(api_res.status_code, 200)
                api_data = api_res.json()
                self.assertEqual(len(api_data["brands"]), 10)
                self.assertIn("verification_summary", api_data)
                self.assertTrue(all("email_verification" in b for b in api_data["brands"]))
                self.assertTrue(all(b["email_verification"]["status"] in ("valid", "catch-all", "unverified") for b in api_data["brands"]))

    def test_integrated_pitch_cards_email_verification_payload(self):
        """Verifies that every generated brand payload contains email_verification stages and delivers summary metrics."""
        with patch("backend.ollama_client.check_ollama_status", return_value={"running": True, "models": ["llama3.2:1b"]}):
            api_res = client.post("/api/generate-pitches", json={
                "creator_id": "creator_1",
                "prompt": "Indian D2C brands for audio and lifestyle",
                "count": 5,
                "strict_official_only": True,
                "indian_only": True
            })
            self.assertEqual(api_res.status_code, 200)
            data = api_res.json()
            self.assertTrue(data["success"])
            self.assertIn("verification_summary", data)
            self.assertGreaterEqual(data["verification_summary"]["total"], 5)
            self.assertGreaterEqual(data["verification_summary"]["valid"], 1)
            for brand in data["brands"]:
                self.assertIn("email_verification", brand)
                self.assertIn("status", brand["email_verification"])
                self.assertIn("is_indian", brand["email_verification"])
                self.assertIn("stages", brand["email_verification"])

    def test_anti_repetition_memory_storage_and_api(self):
        """Tests that anti-repetition memory accurately tracks pitched brands and excludes them across campaigns."""
        from backend.storage import (
            record_pitched_brands,
            get_all_pitched_brands,
            get_pitched_brand_names_and_domains,
            clear_pitched_memory
        )

        # 1. Reset memory via API
        del_res = client.delete("/api/memory/pitched-brands")
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.json()["success"])

        # Check count is 0
        get_res = client.get("/api/memory/pitched-brands")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["count"], 0)

        # 2. Record batch of brands
        sample_brands = [
            {"brand_name": "Cult.fit", "website": "cult.fit", "recipient_email": "partnerships@cult.fit"},
            {"brand_name": "Nitrro Wellness", "website": "nitrro.in", "recipient_email": "info@nitrro.in"},
            {"brand_name": "Waves Gym", "website": "wavesgym.com", "recipient_email": "collab@wavesgym.com"}
        ]
        num_new = record_pitched_brands(sample_brands, creator_name="Test Creator", campaign_prompt="Gyms in Mumbai")
        self.assertEqual(num_new, 3)

        # Duplicate recording should be skipped
        num_dup = record_pitched_brands(sample_brands)
        self.assertEqual(num_dup, 0)

        # Check API reflects 3 brands
        get_res2 = client.get("/api/memory/pitched-brands")
        self.assertEqual(get_res2.status_code, 200)
        self.assertEqual(get_res2.json()["count"], 3)

        names, domains = get_pitched_brand_names_and_domains()
        self.assertIn("cult.fit", names)
        self.assertIn("nitrro wellness", names)
        self.assertIn("waves gym", names)
        self.assertIn("cult.fit", domains)
        self.assertIn("nitrro.in", domains)

        # 3. Discovery run strictly excludes these 3 brands
        with patch("backend.ollama_client.check_ollama_status", return_value={"running": True, "models": ["qwen2.5:7b"]}):
            api_res = client.post("/api/generate-pitches", json={
                "creator_id": "creator_1",
                "prompt": "Find 5 premium gym and fitness centers in Mumbai",
                "count": 5,
                "location": "Mumbai",
                "strict_official_only": False
            })
            self.assertEqual(api_res.status_code, 200)
            disc_brands = api_res.json().get("brands", [])
            disc_names = [b["brand_name"].lower() for b in disc_brands]
            # Ensure none of the 3 recorded brands are repeated
            self.assertNotIn("cult.fit", disc_names)
            self.assertNotIn("nitrro wellness", disc_names)
            self.assertNotIn("waves gym", disc_names)

        # Clean up
        clear_pitched_memory()
        self.assertEqual(len(get_all_pitched_brands()), 0)


if __name__ == "__main__":
    unittest.main()

