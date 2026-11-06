"""Synthetic-only tests of the E0F3 frame-step control-flow verifier."""
import hashlib
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1] / "mods" / "fps" / "research" / "true-dynamic"
sys.path.insert(0, str(ROOT))
import frame_step_cfg_audit as cfg


def B(pc, dst):
    return 0x14000000 | (((dst - pc) // 4) & 0x3FFFFFF)


def synthetic_words():
    # No original game window is used; NOP-only synthetic memory with
    # the small known fingerprinted opcodes inserted for graph testing.
    words = {cfg.START + i * 4: 0xD503201F for i in range(
        (cfg.FIRST_BYTES + cfg.SECOND_BYTES) // 4)}
    words.update(cfg.KEY_WORDS)
    final = cfg.CONT + cfg.SECOND_BYTES - 4
    words[final] = 0xD65F03C0  # RET
    # Synthetic first path exits after its call, while second remains
    # reachable from the TBNZ true branch.
    words[cfg.FIRST_CALL + 4] = B(cfg.FIRST_CALL + 4, final)
    # On the taken branch, bypass the synthetic first-call region.
    # The REAL original game uses a longer conditional path instead.
    words[cfg.GATE + 0x50] = B(cfg.GATE + 0x50, cfg.SECOND_CALL)
    return words


class CFGTests(unittest.TestCase):
    def test_gate_and_two_call_targets(self):
        self.assertEqual(cfg.branch_target(cfg.GATE, cfg.KEY_WORDS[cfg.GATE]),
                         0x006E6D18)
        for site in (cfg.FIRST_CALL, cfg.SECOND_CALL):
            self.assertEqual(cfg.branch_target(site, cfg.KEY_WORDS[site]), cfg.CALLEE)

    def test_bit_one_branch_selects_distinct_paths(self):
        r = cfg.analyze_words(synthetic_words())
        self.assertTrue(r["bit1_clear_can_reach_first"])
        self.assertTrue(r["bit1_set_can_reach_second"])
        self.assertFalse(r["first_continuation_can_reach_second"])
        self.assertFalse(r["second_continuation_can_reach_first"])

    def test_fallthrough_double_path_is_detected_if_present(self):
        words = synthetic_words()
        words[cfg.FIRST_CALL + 4] = 0xD503201F  # no branch over second
        self.assertTrue(cfg.analyze_words(words)["first_continuation_can_reach_second"])

    def test_bad_original_fingerprint_rejected(self):
        words = synthetic_words()
        words[cfg.GATE] = 0
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            cfg.analyze_words(words)

    def test_private_window_digest_is_required(self):
        raw = struct.pack("<256I", *([0xD503201F] * 256))
        data = {
            "build_id": cfg.BUILD, "window_first_main_offset": f"main+0x{cfg.START:08x}",
            "instruction_words_u32_le": ["0xd503201f"] * 256,
            "sha256_window": hashlib.sha256(raw).hexdigest()
        }
        self.assertEqual(len(cfg.checked_window(data, cfg.START, 0x400)), 256)
        data["sha256_window"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            cfg.checked_window(data, cfg.START, 0x400)

    def test_indirect_branch_and_ret_stop_graph(self):
        pc = cfg.START
        self.assertEqual(cfg.successors(pc, 0xD65F03C0), [])
        self.assertEqual(cfg.successors(pc, 0xD61F0000), [])
        self.assertEqual(cfg.successors(pc, 0xD503201F), [pc + 4])


if __name__ == "__main__":
    unittest.main()
