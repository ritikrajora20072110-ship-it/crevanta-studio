import unittest
from backend.web_search import (
    clean_domain,
    extract_brand_name_from_title,
    extract_brands_from_listicle,
    search_brands_online,
    crawl_brand_website_for_contact
)
from backend.lead_verifier import get_verified_official_catalog
from backend.ollama_client import _synthesize_brand_pitch


class TestWebSearch(unittest.TestCase):

    def test_clean_domain(self):
        self.assertEqual(clean_domain("https://www.nitrro.in/contact"), "nitrro.in")
        self.assertEqual(clean_domain("http://wavesgym.com/"), "wavesgym.com")
        self.assertEqual(clean_domain("cult.fit"), "cult.fit")
        self.assertEqual(clean_domain("https://jeraifitness.com:443/about"), "jeraifitness.com")

    def test_extract_brand_name_from_title(self):
        self.assertEqual(
            extract_brand_name_from_title("Nitrro - Fitness Center in Mumbai & Pune, Best Bollywood Celebrity Gym ...", "nitrro.in"),
            "Nitrro"
        )
        self.assertEqual(
            extract_brand_name_from_title("Get the Best Fitness Workouts, Gyms and membership in India | WTF", "wtfgyms.com"),
            "WTF"
        )
        self.assertEqual(
            extract_brand_name_from_title("Waves Gym: Best Gym in Andheri West, Mumbai", "wavesgym.com"),
            "Waves Gym"
        )
        self.assertEqual(
            extract_brand_name_from_title("Jerai Fitness - India Leading Fitness Equipment Manufacturer", "jeraifitness.com"),
            "Jerai Fitness"
        )

    def test_extract_brands_from_listicle(self):
        snippet = "Explore the best gym equipment brands in India including Jerai, Viva, Life Fitness and Technogym."
        brands = extract_brands_from_listicle(snippet, "Best Gym Brands")
        self.assertTrue(any("Jerai" in b for b in brands))
        self.assertTrue(any("Viva" in b for b in brands))

    def test_search_brands_online_fitness_mumbai(self):
        results = search_brands_online("Identify 50 gym brands", location="Mumbai", count=5, indian_only=True)
        self.assertGreater(len(results), 0)
        first = results[0]
        self.assertIn("brand_name", first)
        self.assertIn("website", first)
        self.assertIn("recipient_email", first)
        self.assertIn("location", first)
        # Should contain Mumbai or India in location
        self.assertTrue(any("Mumbai" in b.get("location", "") or "India" in b.get("location", "") for b in results))

    def test_catalog_no_unrelated_spillover(self):
        # Searching for gym brands should prioritize verified fitness brands
        catalog = get_verified_official_catalog("gym fitness", count=6, indian_only=True)
        for c in catalog:
            cat = c.get("brand_niche", "").lower()
            bname = c.get("brand_name", "").lower()
            self.assertTrue(
                "gym" in cat or "fitness" in cat or "workout" in cat or "strength" in cat or "cult" in bname or "nitrro" in bname,
                f"Expected fitness brand but got: {c['brand_name']} ({c.get('brand_niche')})"
            )

    def test_synthesize_brand_pitch_niche_concepts(self):
        creator = {
            "name": "Athletic Creator",
            "handle": "@athlete",
            "niche": "Fitness & Training",
            "followers": "85K",
            "engagement_rate": "6.2%"
        }
        # Gym brand synthesis should generate gym/fitness concept, NOT fashion
        gym_pitch = _synthesize_brand_pitch("Nitrro Wellness", "Luxury Gym & Fitness Club", creator)
        self.assertIn("The 500-Rep Iron Durability Test", gym_pitch["part2_concept_title"])
        self.assertNotIn("One Wardrobe, Three Occasions", gym_pitch["part2_concept_title"])

        # Coffee brand synthesis should generate coffee concept
        coffee_pitch = _synthesize_brand_pitch("Blue Tokai Coffee", "Specialty Coffee Roaster", creator)
        self.assertIn("The Blind Pour-Over Showdown", coffee_pitch["part2_concept_title"])
        self.assertNotIn("One Wardrobe, Three Occasions", coffee_pitch["part2_concept_title"])


if __name__ == "__main__":
    unittest.main()
