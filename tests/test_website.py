import unittest
from fastapi.testclient import TestClient
from backend.app import app
from backend.storage import get_all_inquiries, get_all_applications, get_all_creators

client = TestClient(app)

class TestCrevantaWebsite(unittest.TestCase):

    def test_homepage_serves_agency_editorial(self):
        res = client.get("/")
        self.assertEqual(res.status_code, 200)
        content = res.text
        self.assertIn("CREVANTA", content)
        self.assertIn("WHERE BRANDS", content)
        self.assertIn("MEET INFLUENCE", content)
        self.assertIn("editorial.css", content)
        self.assertIn("Mayank Tanwar", content)
        print("✓ test_homepage_serves_agency_editorial passed")

    def test_studio_route_serves_automation_portal(self):
        res = client.get("/studio")
        self.assertEqual(res.status_code, 200)
        content = res.text
        self.assertIn("Campaign Studio", content)
        self.assertIn("1-Click", content)
        print("✓ test_studio_route_serves_automation_portal passed")

    def test_public_creators_endpoint(self):
        res = client.get("/api/public-creators")
        self.assertEqual(res.status_code, 200)
        creators = res.json()
        self.assertGreaterEqual(len(creators), 5)
        names = [c["name"] for c in creators]
        self.assertIn("Mayank Tanwar", names)
        self.assertIn("Maya Sen", names)
        print("✓ test_public_creators_endpoint passed")

    def test_brand_inquiry_submission(self):
        payload = {
            "brand_name": "Test Luxe Brand",
            "website": "luxebrand.com",
            "contact_name": "Eleanor Vance",
            "email": "eleanor@luxebrand.com",
            "campaign_objective": "Autumn Product Launch",
            "budget_range": "$15,000 - $35,000",
            "message": "We would like to book Mayank and Maya."
        }
        res = client.post("/api/inquiries", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("id", data)
        self.assertEqual(data["brand_name"], "Test Luxe Brand")

        # Verify persisted
        inquiries = get_all_inquiries()
        self.assertTrue(any(i["brand_name"] == "Test Luxe Brand" for i in inquiries))
        print("✓ test_brand_inquiry_submission passed")

    def test_creator_application_submission(self):
        payload = {
            "name": "Arjun Kapoor",
            "handle": "@arjun.visuals",
            "youtube": "youtube.com/@arjunvisuals",
            "niche": "Architecture & Slow Living",
            "followers": "35K",
            "email": "arjun@visuals.com",
            "location": "Chandigarh / New Delhi",
            "past_collabs": "Uniqlo, MUJI"
        }
        res = client.post("/api/creator-applications", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("id", data)
        self.assertEqual(data["name"], "Arjun Kapoor")

        # Verify persisted
        apps = get_all_applications()
        self.assertTrue(any(a["name"] == "Arjun Kapoor" for a in apps))
        print("✓ test_creator_application_submission passed")


if __name__ == "__main__":
    unittest.main()
