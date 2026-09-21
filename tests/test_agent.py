import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.app import app
from backend.agent_orchestrator import AutonomousCampaignAgent
from backend.storage import get_all_creators, DATA_DIR, ROOT_DIR

client = TestClient(app)


class TestAutonomousAgent(unittest.TestCase):

    def setUp(self):
        self.creators = get_all_creators()
        self.assertGreater(len(self.creators), 0)
        self.creator = self.creators[0]

    def test_autonomous_creator_analysis(self):
        """Verifies that the agent autonomously derives optimal brand targets and hooks from creator bio."""
        tech_creator = {
            "name": "Alex Tech",
            "niche": "Smartphones & Workspace Gadgets",
            "bio": "Reviewing flagship mobile hardware, silicon thermals, and mechanical desk setups."
        }
        analysis = AutonomousCampaignAgent.analyze_creator_positioning(tech_creator)
        self.assertIn("smartphones", analysis["target_query"].lower())
        self.assertIn("stress test", analysis["video_hook"].lower())
        self.assertGreaterEqual(len(analysis["brand_categories"]), 2)

        fitness_creator = {
            "name": "Maya Lift",
            "niche": "Strength & Crossfit",
            "bio": "Competitive powerlifter and athletic performance coach."
        }
        fit_analysis = AutonomousCampaignAgent.analyze_creator_positioning(fitness_creator)
        self.assertIn("gym", fit_analysis["target_query"].lower())
        self.assertIn("500-rep", fit_analysis["video_hook"].lower())

    def test_internet_notification_events(self):
        """Verifies that event notifications are emitted with internet_active=True when web tools are used."""
        events_captured = []

        def mock_event(ev):
            events_captured.append(ev)

        mock_brand_pitch = {
            "success": True,
            "provider": "ollama",
            "model": "qwen2.5:7b",
            "brands": [
                {
                    "brand_name": "Test Brand",
                    "website": "testbrand.in",
                    "domain": "testbrand.in",
                    "recipient_email": "partnerships@testbrand.in",
                    "verification": "official",
                    "email_source": "Official website",
                    "deliverability": {"score": 95}
                }
            ]
        }

        with patch("backend.agent_orchestrator.check_ollama_status", return_value={"running": True, "models": ["qwen2.5:7b"]}):
            with patch("backend.agent_orchestrator.search_brands_online", return_value=[
                {"brand_name": "Test Brand", "website": "testbrand.in", "domain": "testbrand.in", "recipient_email": "partnerships@testbrand.in", "verification": "official", "email_source": "Official website"}
            ]):
                with patch("backend.agent_orchestrator.generate_brand_pitches_ollama", return_value=mock_brand_pitch):
                    res = AutonomousCampaignAgent.execute_autonomous_pipeline(
                        creator=self.creator,
                        count=2,
                        indian_only=True,
                        strict_official_only=False,
                        on_event=mock_event
                    )

        self.assertTrue(res["success"])
        self.assertGreater(len(events_captured), 3)

        # Check for internet_active notifications
        internet_events = [e for e in events_captured if e.get("internet_active")]
        self.assertGreater(len(internet_events), 0)
        for ie in internet_events:
            self.assertIn("stage", ie)
            self.assertIn("detail", ie)
            self.assertIn("timestamp", ie)

    def test_auto_pilot_endpoint(self):
        """Tests the POST /api/agent/auto-pilot endpoint executes end-to-end with zero user prompt."""
        mock_brand_pitch = {
            "success": True,
            "provider": "ollama",
            "model": "qwen2.5:7b",
            "brands": [
                {
                    "brand_name": "Auto Brand",
                    "website": "autobrand.in",
                    "domain": "autobrand.in",
                    "recipient_email": "collab@autobrand.in",
                    "verification": "official",
                    "email_source": "Official website",
                    "deliverability": {"score": 98}
                }
            ]
        }
        with patch("backend.agent_orchestrator.check_ollama_status", return_value={"running": True, "models": ["qwen2.5:7b"]}):
            with patch("backend.agent_orchestrator.generate_brand_pitches_ollama", return_value=mock_brand_pitch):
                res = client.post("/api/agent/auto-pilot", json={
                    "creator_id": self.creator["id"],
                    "count": 3,
                    "indian_only": True
                })
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertTrue(data.get("success"))
                self.assertIn("brands", data)
                self.assertIn("autonomous_metadata", data)
                self.assertEqual(data["autonomous_metadata"]["mode"], "auto_pilot")
                self.assertTrue(len(data["brands"]) > 0)

    def test_stream_discovery_sse_endpoint(self):
        """Tests that POST /api/agent/stream-discovery streams SSE data frames with event and complete types."""
        mock_brand_pitch = {
            "success": True,
            "provider": "ollama",
            "model": "qwen2.5:7b",
            "brands": [
                {
                    "brand_name": "Stream Brand",
                    "website": "streambrand.in",
                    "domain": "streambrand.in",
                    "recipient_email": "collab@streambrand.in",
                    "verification": "official",
                    "email_source": "Official website"
                }
            ]
        }
        with patch("backend.agent_orchestrator.check_ollama_status", return_value={"running": True, "models": ["qwen2.5:7b"]}):
            with patch("backend.agent_orchestrator.generate_brand_pitches_ollama", return_value=mock_brand_pitch):
                res = client.post("/api/agent/stream-discovery", json={
                    "creator_id": self.creator["id"],
                    "count": 2,
                    "indian_only": True
                })
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.headers.get("content-type"), "text/event-stream; charset=utf-8")
            
            body_text = res.text
            self.assertIn("data: ", body_text)
            self.assertIn('"type": "event"', body_text)
            self.assertIn('"type": "complete"', body_text)

    def test_workspace_file_isolation(self):
        """Guarantees that all storage paths and operations are strictly isolated inside the project workspace."""
        workspace_root = ROOT_DIR.resolve()
        data_dir = DATA_DIR.resolve()

        # Assert data directory is inside project workspace
        self.assertTrue(str(data_dir).startswith(str(workspace_root)))

        # Assert no paths resolve outside
        from backend.storage import (
            CREATORS_FILE,
            COMMANDS_FILE,
            HISTORY_FILE,
            INQUIRIES_FILE,
            APPLICATIONS_FILE,
            TALKS_FILE,
            PITCHED_BRANDS_FILE
        )
        for f in [CREATORS_FILE, COMMANDS_FILE, HISTORY_FILE, INQUIRIES_FILE, APPLICATIONS_FILE, TALKS_FILE, PITCHED_BRANDS_FILE]:
            self.assertTrue(str(f.resolve()).startswith(str(workspace_root)), f"Path {f} leaks outside workspace!")


if __name__ == "__main__":
    unittest.main()
