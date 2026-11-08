"""Unit tests for pace, latch, on-demand and the collector. Pure: fake readers, temp state dir.
Run: python3 -I -m unittest discover -s tests (from the repo root)."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import core  # noqa: E402
import pace  # noqa: E402
import readers  # noqa: E402

NOW = datetime(2026, 11, 8, 18, 0, tzinfo=timezone.utc)
CFG = dict(pace.DEFAULTS)


def reading(sub_id, used, reset_in_h, *, short=None, status="ok", age_s=60):
    windows = [{"kind": "week", "label": "Week", "used_percent": used,
                "reset_at": (NOW + timedelta(hours=reset_in_h)).isoformat()}]
    if short is not None:
        windows.append({"kind": "short", "label": "Current session", "used_percent": short,
                        "reset_at": (NOW + timedelta(hours=2)).isoformat()})
    return {"id": sub_id, "status": status, "observed_at": (NOW - timedelta(seconds=age_s)).isoformat(),
            "windows": windows}


class PaceTests(unittest.TestCase):
    def test_slack_halfway(self):
        # Halfway through the week, 30% used, reserve 0: line is 0.5 left, 0.7 left -> slack +0.20.
        p = pace.window_pace(30, NOW + timedelta(days=3.5), NOW, reserve=0.0)
        self.assertAlmostEqual(p["slack"], 0.20, places=3)
        self.assertAlmostEqual(p["pace_used_percent"], 50.0, places=1)

    def test_reserve_moves_line(self):
        p = pace.window_pace(50, NOW + timedelta(days=3.5), NOW, reserve=0.05)
        self.assertAlmostEqual(p["slack"], 0.5 - 0.525, places=3)

    def test_exhausted_never_eligible(self):
        s = pace.assess(reading("codex", 100, 30), NOW, CFG)
        self.assertFalse(s["eligible"])
        self.assertEqual(s["reason"], "weekly limit reached")

    def test_stale_not_eligible(self):
        s = pace.assess(reading("claude", 10, 30, age_s=3 * 3600), NOW, CFG)
        self.assertFalse(s["eligible"])
        self.assertFalse(s["fresh"])

    def test_short_window_bench_at_3_percent(self):
        self.assertFalse(pace.assess(reading("claude", 10, 30, short=98), NOW, CFG)["eligible"])
        self.assertTrue(pace.assess(reading("claude", 10, 30, short=96), NOW, CFG)["eligible"])

    def test_reset_passed_is_pending(self):
        s = pace.assess(reading("codex", 10, -1), NOW, CFG)
        self.assertFalse(s["eligible"])
        self.assertEqual(s["reason"], "new week not published yet")


class LatchTests(unittest.TestCase):
    def scores(self, a, b):
        return {"claude": {"eligible": True, "reserve_only": False, "slack": a},
                "codex": {"eligible": True, "reserve_only": False, "slack": b}}

    def test_needs_two_fresh_samples(self):
        latch = pace.update_latch({}, self.scores(0.3, 0.1), {"claude": "t1", "codex": "t1"}, CFG)
        self.assertEqual(latch["incumbent"], "claude")
        latch = pace.update_latch(latch, self.scores(0.1, 0.3), {"claude": "t2", "codex": "t2"}, CFG)
        self.assertEqual(latch["incumbent"], "claude")
        # Same observation again is not a new sample.
        latch = pace.update_latch(latch, self.scores(0.1, 0.3), {"claude": "t2", "codex": "t2"}, CFG)
        self.assertEqual(latch["incumbent"], "claude")
        latch = pace.update_latch(latch, self.scores(0.1, 0.3), {"claude": "t3", "codex": "t3"}, CFG)
        self.assertEqual(latch["incumbent"], "codex")

    def test_small_lead_holds(self):
        latch = {"incumbent": "claude"}
        for t in ("a", "b", "c"):
            latch = pace.update_latch(latch, self.scores(0.20, 0.25), {"claude": t, "codex": t}, CFG)
        self.assertEqual(latch["incumbent"], "claude")

    def test_ineligible_incumbent_drops_at_once(self):
        sc = self.scores(0.3, 0.1)
        sc["claude"]["eligible"] = False
        latch = pace.update_latch({"incumbent": "claude"}, sc, {"codex": "t"}, CFG)
        self.assertEqual(latch["incumbent"], "codex")


class OnDemandTests(unittest.TestCase):
    def s(self, slack, fresh=True, eligible=True):
        return {"fresh": fresh, "eligible": eligible, "slack": slack}

    def test_enter_only_when_all_10_over(self):
        self.assertTrue(pace.update_on_demand(False, {"a": self.s(-0.12), "b": self.s(-0.10)}, CFG)[0])
        self.assertFalse(pace.update_on_demand(False, {"a": self.s(-0.12), "b": self.s(-0.05)}, CFG)[0])

    def test_missing_reading_never_starts_paid_use(self):
        sc = {"a": self.s(-0.2), "b": {"fresh": False, "eligible": False, "slack": None}}
        self.assertFalse(pace.update_on_demand(False, sc, CFG)[0])

    def test_stay_until_green(self):
        self.assertTrue(pace.update_on_demand(True, {"a": self.s(-0.05), "b": self.s(-0.02)}, CFG)[0])
        self.assertFalse(pace.update_on_demand(True, {"a": self.s(0.0), "b": self.s(-0.2)}, CFG)[0])


class ReaderParseTests(unittest.TestCase):
    def test_supergrok_billing(self):
        body = {"config": {"currentPeriod": {"type": "USAGE_PERIOD_TYPE_WEEKLY", "start": "2026-11-02T23:51:44Z",
                                             "end": "2026-11-09T23:51:44Z"},
                           "creditUsagePercent": 19.0, "productUsage": [{"product": "GrokBuild", "usagePercent": 13.0}]}}
        p = readers.parse_supergrok_billing(body)
        self.assertEqual(p["windows"][0]["used_percent"], 19.0)
        self.assertEqual(p["products"][0]["product"], "GrokBuild")

    def test_openrouter_details(self):
        d = readers.parse_openrouter_details(["Credits balance: $92.83",
                                              "API key usage: $1.50 total • $0.25 today • $1.00 this week • $1.50 this month"])
        self.assertEqual(d, {"balance": 92.83, "today": 0.25, "week": 1.0, "month": 1.5})


class CardTests(unittest.TestCase):
    def test_sign_and_order_match_alex_format(self):
        # Over pace shows minus (red) and sorts first; headroom shows plus.
        scores = {"claude": pace.assess(reading("claude", 98, 84), NOW, CFG),
                  "codex": pace.assess(reading("codex", 10, 84), NOW, CFG)}
        cs = core.cards({"scores": scores, "subscriptions": {}})
        self.assertEqual(cs[0]["id"], "claude")
        self.assertLess(cs[0]["pace_delta"], 0)
        self.assertGreater(cs[1]["pace_delta"], 0)
        text = core.render_text({"scores": scores, "subscriptions": {}, "written_at": NOW.isoformat()})
        self.assertIn("98%  P: -", text)
        self.assertIn("over pace", text)


class CollectTests(unittest.TestCase):
    def test_collect_writes_state_and_keeps_last_good(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            ok = {"claude": lambda: reading("claude", 16, 127), "codex": lambda: reading("codex", 10, 100),
                  "supergrok": lambda: reading("supergrok", 19, 30)}
            orr = lambda: {"id": "openrouter", "status": "ok", "observed_at": NOW.isoformat(), "spend": {"today": 0.0}}
            st = core.collect(now=NOW, read=ok, read_openrouter=orr, path=path)
            self.assertIsNotNone(st["pick"])
            self.assertFalse(st["warning"]["active"])
            self.assertEqual(oct(path.stat().st_mode & 0o777), "0o600")
            failing = dict(ok, supergrok=lambda: {"id": "supergrok", "status": "failed", "error": "HTTP 401"})
            st2 = core.collect(now=NOW + timedelta(minutes=15), read=failing, read_openrouter=orr, path=path)
            self.assertEqual(st2["subscriptions"]["supergrok"]["status"], "failed")
            self.assertIn("observed_at", st2["subscriptions"]["supergrok"])  # last good kept
            self.assertTrue(st2["warning"]["active"])
            self.assertEqual(st2["last_transition"], "usage data unavailable")
            text = core.render_text(st2)
            self.assertIn("P: ", text)
            self.assertIn("Warning", text)
            rows = (Path(tmp) / "history.jsonl").read_text().splitlines()
            self.assertEqual(len(rows), 2)
            json.loads(rows[0])


if __name__ == "__main__":
    unittest.main()
