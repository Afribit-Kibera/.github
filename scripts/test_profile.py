"""Privacy, attribution and chart-data checks; no network access during unit tests."""

import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
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
            return [{"login":login,"html_url":f"https://github.com/{login}","avatar_url":"https://avatars.githubusercontent.com/u/1?v=4","type":"Bot" if login.endswith("[bot]") else "User"} for login in ["novyrix", "codex", "github-actions[bot]"]]
        if parts[3].startswith("commits?"):
            self.assertNotEqual(repo, "afribit-wallet")
            if missing and repo == "nfc":
                return {}
            params = parse_qs(urlsplit(endpoint).query)
            self.assertEqual(params["sha"],["main"])
            start = datetime.fromisoformat(params["since"][0])
            return [{"sha":f"{repo}-{index}-{number}","parents":[{"sha":"parent"}],"commit":{"committer":{"date":(start+timedelta(weeks=index)).isoformat()}}} for index in range(12) for number in range(index)]
        self.fail(f"Unexpected endpoint: {endpoint}")

    def sample(self, missing=False):
        with patch.object(profile,"api",side_effect=lambda endpoint:self.fake_api(endpoint,missing)), contextlib.redirect_stdout(io.StringIO()):
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

    def test_automation_is_not_published_as_a_contributor(self):
        data = self.sample()
        self.assertEqual([item["login"] for item in data["contributors"]],["novyrix"])
        self.assertNotIn("codex",json.dumps(data["contributors"]).lower())

    def test_readme_does_not_restore_ai_collaborator_credit(self):
        data = self.sample()
        # Previously published snapshots must not restore the removed attribution.
        data["contributors"].append({"login":"codex","automation":True})
        template = (profile.PROFILE / "README.template.md").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "README.template.md").write_text(template,encoding="utf-8")
            with patch.object(profile,"PROFILE",path):
                profile.generate_readme(data)
            readme = (path / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("github.com/codex",readme)
        self.assertNotIn("AI and automation assistance",readme)
        self.assertIn("Btrust Pathways",readme)
        self.assertIn("Gemini",readme)

    def test_activity_matrix_reconciles_to_weekly_totals(self):
        data = self.sample()
        matrix = data["activity"]["repositories"]
        self.assertEqual(len(matrix),6)
        for index, week in enumerate(data["activity"]["weeks"]):
            self.assertEqual(sum(row["commits"][index] for row in matrix),week["commits"])
        self.assertNotIn("afribit-wallet",[row["repository"] for row in matrix])

    def test_missing_activity_is_not_zero(self):
        data = self.sample(missing=True)
        self.assertFalse(data["activity"]["complete"])
        self.assertEqual(data["activity"]["weeks"],[])
        self.assertEqual(data["activity"]["repositories"],[])
        self.assertEqual(data["activity"]["unavailable_repositories"],["nfc"])

    def test_valid_empty_commit_list_means_zero(self):
        repo = {"full_name":"Afribit-Kibera/nfc","default_branch":"main"}
        with patch.object(profile,"paged",return_value=[]):
            result = profile.activity_from_commits(repo,["2026-10-18"],datetime(2026,10,21,tzinfo=timezone.utc))
        self.assertEqual(result,{"2026-10-18":0})

    def test_commit_window_deduplicates_and_excludes_merges(self):
        repo = {"full_name":"Afribit-Kibera/Website","default_branch":"main"}
        def commit(sha,date,parents=1):
            return {"sha":sha,"parents":[{}]*parents,"commit":{"committer":{"date":date}}}
        rows = [commit("a","2026-10-18T00:00:00Z",0),commit("a","2026-10-18T00:00:00Z",0),commit("b","2026-10-20T12:00:00Z"),commit("merge","2026-10-19T12:00:00Z",2),commit("old","2026-10-17T23:59:59Z"),commit("future","2026-10-22T00:00:00Z")]
        with patch.object(profile,"paged",return_value=rows):
            result = profile.activity_from_commits(repo,["2026-10-18"],datetime(2026,10,21,tzinfo=timezone.utc))
        self.assertEqual(result,{"2026-10-18":2})

    def test_pagination_preserves_existing_query(self):
        with patch.object(profile,"api",side_effect=[[{}]*100,[{"last":True}]]) as request:
            result = profile.paged("repos/Afribit-Kibera/Website/commits?sha=main")
        self.assertEqual(len(result),101)
        self.assertEqual(request.call_args_list[1].args[0],"repos/Afribit-Kibera/Website/commits?sha=main&per_page=100&page=2")

    def test_failed_commit_read_does_not_publish_partial_activity(self):
        original = self.fake_api
        def fail(endpoint):
            if "nfc/commits?" in endpoint:
                raise RuntimeError("Public read failed")
            return original(endpoint)
        with patch.object(profile,"api",side_effect=fail),contextlib.redirect_stdout(io.StringIO()):
            data = profile.collect()
        self.assertFalse(data["activity"]["complete"])
        self.assertEqual(data["activity"]["weeks"],[])
        self.assertEqual(data["activity"]["repositories"],[])

    def test_week_boundary_is_sunday_utc(self):
        stamp = datetime.fromisoformat("2026-10-18T02:00:00+03:00").timestamp()
        self.assertEqual(profile.normalise_week(stamp),"2026-10-11")

    def test_marked_regions_preserve_manual_copy(self):
        original = "before\n<!-- chart:start -->old<!-- chart:end -->\nafter"
        result = profile.update_region(original,"chart","new")
        self.assertEqual(result,"before\n<!-- chart:start -->\nnew\n<!-- chart:end -->\nafter")
        with self.assertRaises(ValueError):
            profile.update_region(original,"absent","new")

    def test_asset_hash_is_stable_across_windows_line_endings(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            with patch.object(profile,"ASSETS",path):
                (path / "sample.svg").write_bytes(b"<svg>\n</svg>\n")
                lf = profile.asset_url("sample.svg")
                (path / "sample.svg").write_bytes(b"<svg>\r\n</svg>\r\n")
                self.assertEqual(lf,profile.asset_url("sample.svg"))

    def test_all_chart_elements_stay_in_canvas(self):
        data = self.sample()
        for theme in profile.PALETTES:
            for mobile in [False,True]:
                for canvas in [profile.header(theme,mobile),profile.community_header(theme,mobile),profile.overview(data,theme,mobile)]:
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
        self.assertTrue(all(not item["automation"] for item in data["contributors"]))
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
