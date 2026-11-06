"""Tests for standalone FPS mod patches; no game files required."""
import hashlib
import sys
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mods" / "fps"))
import build  # noqa: E402


class TestFpsMods(unittest.TestCase):
    def test_ips32_round_trip_and_regression_hashes(self):
        for mode in build.MODES:
            for index, build_id in enumerate(build.BUILDS):
                with self.subTest(mode=mode, build_id=build_id):
                    edits = build.patches_for(mode, build_id)
                    blob = build.ips32(edits)
                    self.assertEqual(
                        build.parse_ips32(blob),
                        {off: replacement for off, _, replacement in edits},
                    )
                    self.assertEqual(
                        hashlib.sha256(blob).hexdigest(),
                        build.EXPECTED_PATCH_SHA256[mode][index],
                    )

    def test_paths_and_archive_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            for path in build.build(Path(directory)):
                with zipfile.ZipFile(path) as archive:
                    self.assertIsNone(archive.testzip())
                    patches = [p for p in archive.namelist() if p.endswith(".ips")]
                    self.assertEqual(len(patches), 2)
                    for p in patches:
                        self.assertTrue(p.startswith(build.TITLE_ID + "/"))
                        self.assertTrue(any(p.endswith(k + ".ips") for k in build.BUILDS))
                        self.assertTrue(archive.read(p).startswith(b"IPS32"))
                    self.assertTrue(any(p.endswith("/README.txt") for p in archive.namelist()))

    def test_mutually_distinct_mods(self):
        for build_id in build.BUILDS:
            self.assertNotEqual(
                build.ips32(build.patches_for("fixed-30", build_id)),
                build.ips32(build.patches_for("adaptive", build_id)),
            )

    def test_each_mod_has_a_page_and_zip(self):
        slugs = {
            "fixed-30": "fixed-30",
            "adaptive": "native-adaptive",
            "variable": "variable-average",
        }
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        category_readme = (ROOT / "mods" / "fps" / "README.md").read_text(encoding="utf-8")
        for mode, slug in slugs.items():
            page = ROOT / "mods" / "fps" / slug / "README.md"
            archive = ROOT / "releases" / f"oot-{mode}-both-builds.zip"
            self.assertTrue(page.is_file(), page)
            self.assertTrue(archive.is_file(), archive)
            self.assertIn(f"mods/fps/{slug}/README.md", root_readme)
            self.assertIn(f"{slug}/README.md", category_readme)
            self.assertIn(archive.name, page.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
