"""Privacy, attribution and chart-data checks; no network access during unit tests."""

import contextlib
from datetime import datetime, timezone
import io
import json
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import refresh_profile as profile


class PublicProfileTests(unittest.TestCase):
    def setUp(self):
        self.allowed = {item["repo"] for item in profile.CONFIG["projects"] if "repo" in item}
        self.calls = []

    def fake_api(self, endpoint, missing=False):
        self.calls.append(endpoint)
        parts = endpoint.split("/")
        self.assertEqual(parts[:2], ["repos", "Afribit-Kibera"])
        self.assertIn(parts[2], self.allowed)
        repo = parts[2]
        if len(parts) == 3:
            return {"name":repo,"full_name":f"Afribit-Kibera/{repo}","html_url":f"https://github.com/Afribit-Kibera/{repo}","fork":repo=="afribit-wallet","default_branch":"main","pushed_at":"2026-10-20T00:00:00Z","private":False,"visibility":"public","owner":{"login":"Afribit-Kibera"}}
        if parts[3] == "languages":
            self.assertNotEqual(repo, "afribit-wallet")
            return {"TypeScript":900,"CSS":100}
        if parts[3].startswith("contributors"):
            self.assertNotEqual(repo, "afribit-wallet")
            return [{"login":login,"html_url":f"https://github.com/{login}","avatar_url":"https://avatars.githubusercontent.com/u/1?v=4","type":"User"} for login in ["novyrix", "codex"]]
        if parts[3:] == ["stats", "commit_activity"]:
            self.assertNotEqual(repo, "afribit-wallet")
            if missing and repo == "nfc":
                return {}
            start = int(datetime(2026, 7, 26, tzinfo=timezone.utc).timestamp())
            return [{"week":start+index*604800,"total":index,"days":[index,0,0,0,0,0,0]} for index in range(12)]
        self.fail(f"Unexpected endpoint: {endpoint}")

    def sample(self, missing=False):
        with patch.object(profile,"api",side_effect=lambda endpoint:self.fake_api(endpoint,missing)), patch.object(profile.time,"sleep"), contextlib.redirect_stdout(io.StringIO()):
            return profile.collect()

    def test_private_metadata_is_rejected(self):
        for record in [{"private":True,"visibility":"private"},{"private":False,"visibility":"internal"}]:
            with self.assertRaises(ValueError):
                profile.public_metadata(record)

    def test_private_projects_are_summary_only(self):
        private = [item for item in profile.CONFIG["projects"] if item.get("source")=="private"]
        self.assertEqual(len(private),3)
        self.assertTrue(all("repo" not in item for item in private))
        self.assertTrue(all("github.com" not in item.get("url","") for item in private))
        data = self.sample()
        self.assertEqual(data["public_repositories"],7)
        self.assertEqual(data["showcased_projects"],10)
        for item in private:
            self.assertNotIn(item["name"].lower(),json.dumps(data).lower())

    def test_fork_history_is_excluded(self):
        data = self.sample()
        self.assertEqual(data["original_repositories"],6)
        self.assertEqual(data["languages"],{"TypeScript":5400,"CSS":600})
        wallet = next(item for item in data["repositories"] if item["name"]=="afribit-wallet")
        self.assertNotIn("languages",wallet)
        self.assertEqual(data["activity"]["weeks"][-1]["commits"],66)

    def test_ai_attribution_is_not_a_person(self):
        data = self.sample()
        people = [item["login"] for item in data["contributors"] if not item["automation"]]
        automation = [item["login"] for item in data["contributors"] if item["automation"]]
        self.assertEqual(people,["novyrix"])
        self.assertEqual(automation,["codex"])

    def test_missing_activity_is_not_zero(self):
        data = self.sample(missing=True)
        self.assertFalse(data["activity"]["complete"])
        self.assertEqual(data["activity"]["weeks"],[])
        self.assertEqual(data["activity"]["unavailable_repositories"],["nfc"])

    def test_other_language_color_matches_legend(self):
        values = {"TypeScript":800,"CSS":100,"HTML":80,"Shell":20}
        buckets = profile.language_buckets(values,["TypeScript","CSS"])
        self.assertEqual(buckets,{"TypeScript":800,"CSS":100,"Other":100})
        self.assertEqual(sum(buckets.values()),sum(values.values()))

    def test_marked_regions_preserve_manual_copy(self):
        original = "before\n<!-- chart:start -->old<!-- chart:end -->\nafter"
        result = profile.update_region(original,"chart","new")
        self.assertEqual(result,"before\n<!-- chart:start -->\nnew\n<!-- chart:end -->\nafter")
        with self.assertRaises(ValueError):
            profile.update_region(original,"absent","new")

    def test_all_chart_elements_stay_in_canvas(self):
        data = self.sample()
        for theme in profile.PALETTES:
            for mobile in [False,True]:
                for canvas in [profile.header(theme,mobile),profile.community_header(theme,mobile),profile.overview(data,theme,mobile),profile.source_mix(data,theme,mobile),profile.activity_chart(data,theme,mobile)]:
                    for element in canvas.root.iter("rect"):
                        x,y,w,h = (float(element.get(key,"0")) for key in ["x","y","width","height"])
                        self.assertGreaterEqual(min(x,y,w,h),0)
                        self.assertLessEqual(x+w,canvas.width+0.01)
                        self.assertLessEqual(y+h,canvas.height+0.01)
                    ET.fromstring(ET.tostring(canvas.root))

    @unittest.skipUnless(profile.DATA.exists(),"Run the collector to check the generated dataset")
    def test_generated_assets_are_self_contained(self):
        data = json.loads(profile.DATA.read_text(encoding="utf-8"))
        self.assertEqual(data["public_repositories"],len(data["repositories"]))
        self.assertEqual(data["original_repositories"],sum(not item["fork"] for item in data["repositories"]))
        for asset in profile.ASSETS.glob("*.svg"):
            root = ET.parse(asset).getroot()
            self.assertIsNotNone(root.find(f"{{{profile.NS}}}title"))
            self.assertIsNotNone(root.find(f"{{{profile.NS}}}desc"))
            for node in root.iter():
                self.assertFalse(node.tag.endswith("script"))
                href = node.get("href","")
                self.assertTrue(not href or href.startswith("data:image/png;base64,"))


if __name__ == "__main__":
    unittest.main()
