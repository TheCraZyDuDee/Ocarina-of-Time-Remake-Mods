"""Release tests: keep the exact user-tested True Dynamic IPS reproducible."""
from pathlib import Path
import hashlib
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"mods"/"fps"))
import build

class FPSReleaseTests(unittest.TestCase):
    def test_ips_sha_and_roundtrip(self):
        self.assertEqual(set(build.MODES),{"fixed-30","adaptive","true-dynamic"})
        for mode, supported in build.EXPECTED_PATCH_SHA256.items():
            for build_id, expected in supported.items():
                with self.subTest(mode=mode,build_id=build_id):
                    edits=build.patches_for(mode,build_id)
                    ips=build.ips32(edits)
                    self.assertEqual(build.parse_ips32(ips),
                                     {a:repl for a,_,repl in edits})
                    self.assertEqual(hashlib.sha256(ips).hexdigest(),expected)

    def test_dynamic_is_e0f3_only_and_preserves_native_controller(self):
        self.assertEqual(set(build.EXPECTED_PATCH_SHA256["true-dynamic"]),{build.E0F3})
        with self.assertRaisesRegex(ValueError,"Unsupported executable build"):
            build.patches_for("true-dynamic",build.BASE)
        edits=build.patches_for("true-dynamic",build.E0F3)
        records={a:r for a,_,r in edits}
        self.assertEqual(len(records),20)
        self.assertEqual(sum(len(words) for _,words in build.DYNAMIC_CAVES),16)
        self.assertEqual(records[build.DYNAMIC_HOOK],
                         build.branch(build.DYNAMIC_HOOK,build.DYNAMIC_CAVES[0][0]))
        for no_touch in (0x03B4EF90,0x03B4F080):
            self.assertNotIn(no_touch,records)
        for i,(start,words) in enumerate(build.DYNAMIC_CAVES):
            self.assertEqual(tuple(records[start+4*j] for j in range(len(words))),words)
            next_pc=(build.DYNAMIC_CAVES[i+1][0] if i+1<len(build.DYNAMIC_CAVES)
                     else build.DYNAMIC_HOOK+4)
            self.assertEqual(records[start+4*len(words)],
                             build.branch(start+4*len(words),next_pc))

    def test_user_tested_e0f3_209_byte_ips_is_frozen(self):
        payload=build.ips32(build.patches_for("true-dynamic",build.E0F3))
        self.assertEqual(len(payload),209)
        self.assertEqual(hashlib.sha256(payload).hexdigest(),
            "306e36cec3efc28a38df627ed38245fe29008855a85cfe4a249a7d8fb2fd1365")

    def test_all_releases_build_byte_identically(self):
        with tempfile.TemporaryDirectory() as folder:
            generated=build.build(folder)
            self.assertEqual(len(generated),3)
            for path in generated:
                with self.subTest(zip=path.name):
                    published=ROOT/"releases"/path.name
                    self.assertTrue(published.is_file(),published)
                    self.assertEqual(path.read_bytes(),published.read_bytes())
                    with zipfile.ZipFile(path) as z:
                        self.assertIsNone(z.testzip())
                        ips=[name for name in z.namelist() if name.endswith(".ips")]
                        self.assertEqual(len(ips),1 if "true-dynamic" in path.name else 2)
                        self.assertTrue(all(name.startswith(build.TITLE_ID+"/") for name in ips))
                        self.assertTrue(any(name.endswith("/README.txt") for name in z.namelist()))
                        self.assertFalse(any(".nso" in name.lower() for name in z.namelist()))

    def test_docs_and_retired_variable_mode(self):
        self.assertFalse((ROOT/"releases/oot-variable-both-builds.zip").exists())
        self.assertFalse((ROOT/"mods/fps/variable-average").exists())
        root=(ROOT/"README.md").read_text()
        category=(ROOT/"mods/fps/README.md").read_text()
        for mode,slug in (("fixed-30","fixed-30"),("adaptive","native-adaptive"),
                          ("true-dynamic","true-dynamic")):
            page=ROOT/"mods/fps"/slug/"README.md"
            self.assertTrue(page.is_file(),page)
            self.assertIn(f"mods/fps/{slug}/README.md",root)
            self.assertIn(f"{slug}/README.md",category)
            self.assertIn(build.OUTPUT_NAMES[mode],page.read_text())
        self.assertIn("E0F3 only",category)

    def test_bad_input_rejected(self):
        for blob in (b"",b"IPS32",b"IPS32EEOFgarbage"):
            with self.assertRaises(ValueError):
                build.parse_ips32(blob)
        with self.assertRaises(ValueError):
            build.branch(0x100,0x102)
        with self.assertRaises(ValueError):
            build.patches_for("true-dynamic","UNKNOWN")

if __name__=="__main__":
    unittest.main()
