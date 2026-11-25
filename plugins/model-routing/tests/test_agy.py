"""Antigravity quota is display-only. The official CLI /usage command is not a model call.

Run from the repo root: python3 -I -m unittest discover -s plugins/model-routing/tests
"""

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import core
import pace
import readers
from hermes_platform.resolver.core import Candidate, Resolution
from test_routing import CFG, NOW, reading

SECRET_PROSE = "SECRET-PROSE"
SECRET_STDERR = "SECRET-STDERR"
USAGE_ARGV = ["--print", "/usage", "--output-format", "json"]


def offline_cheaper():
    return {"id": "cheaperinference", "status": "failed", "error": "offline"}


def envelope(groups, **overrides):
    payload = {
        "status": "SUCCESS",
        "conversation_id": "",
        "num_turns": 0,
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "thinking_tokens": 0,
            "cache_read_tokens": 0,
            "total_tokens": 0,
        },
        "command": {"name": "usage", "data": {"groups": groups}},
    }
    payload.update(overrides)
    return payload


def groups():
    return [
        {
            "name": "Gemini Models",
            "description": SECRET_PROSE,
            "buckets": [
                {
                    "id": "gemini-weekly",
                    "name": "Week",
                    "description": SECRET_PROSE,
                    "window": "weekly",
                    "remaining_fraction": 0.42,
                    "reset_time": "2026-11-27T18:00:00Z",
                },
                {
                    "id": "gemini-5h",
                    "name": "Five hours",
                    "window": "5h",
                    "remaining_fraction": 0.90,
                    "reset_time": "2026-11-22T22:00:00Z",
                },
            ],
        },
        {
            "name": "Claude and GPT models",
            "buckets": [
                {
                    "id": "3p-weekly",
                    "name": "Week",
                    "window": "weekly",
                    "remaining_fraction": 0.15,
                    "reset_time": "2026-11-26T12:00:00Z",
                },
                {
                    "id": "3p-5h",
                    "name": "Five hours",
                    "window": "5h",
                    "remaining_fraction": 0.0,
                    "reset_time": "2026-11-22T20:00:00Z",
                },
            ],
        },
        {
            "name": "Gemini 4 Argon",
            "buckets": [
                {
                    "id": "gemini-argon-wtu-weekly",
                    "name": "Week",
                    "window": "weekly",
                    "remaining_fraction": 0.004,
                    "reset_time": "2026-11-28T00:00:00Z",
                },
            ],
        },
    ]


def stored_groups():
    """Reader output: reset_time is stored as reset_at and prose is already gone."""
    cleaned = []
    for group in groups():
        buckets = []
        for bucket in group["buckets"]:
            item = {key: value for key, value in bucket.items() if key != "description"}
            item["reset_at"] = item.pop("reset_time")
            buckets.append(item)
        cleaned.append({"name": group["name"], "buckets": buckets})
    return cleaned


def found(path="/usr/bin/agy"):
    return Resolution("path_executable", (Candidate(path, "PATH", True),))


def missing():
    return Resolution("missing", (Candidate("agy", "PATH", False),))


def completed(payload, code=0, stderr=SECRET_STDERR):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    err = stderr if isinstance(stderr, bytes) else stderr.encode()
    return subprocess.CompletedProcess(["agy"], code, stdout=raw, stderr=err)


class AgyCommandTests(unittest.TestCase):
    def test_usage_command_is_closed_stdin_with_a_deadline(self):
        seen = {}

        def fake_run(argv, **kwargs):
            seen["argv"] = list(argv)
            seen["kwargs"] = kwargs
            return completed(envelope(groups()))

        with (
            patch(
                "hermes_platform.resolver.core.locate_command", return_value=found()
            ) as locate,
            patch("readers.subprocess.run", side_effect=fake_run),
        ):
            result = readers.read_agy()
        locate.assert_called_once_with("agy")
        self.assertEqual(seen["argv"], ["/usr/bin/agy", *USAGE_ARGV])
        self.assertIs(seen["kwargs"]["stdin"], subprocess.DEVNULL)
        self.assertEqual(seen["kwargs"]["timeout"], readers.AGY_TIMEOUT_S)
        self.assertIs(seen["kwargs"]["stdout"], subprocess.PIPE)
        self.assertIs(seen["kwargs"]["stderr"], subprocess.PIPE)
        self.assertFalse(seen["kwargs"].get("shell", False))
        self.assertEqual(result["status"], "ok")
        blob = json.dumps(result)
        self.assertNotIn(SECRET_STDERR, blob)
        self.assertNotIn(SECRET_PROSE, blob)
        self.assertNotIn("input_tokens", blob)

    def test_zero_inference_counters_are_kept_out_of_state(self):
        with (
            patch("hermes_platform.resolver.core.locate_command", return_value=found()),
            patch("readers.subprocess.run", return_value=completed(envelope(groups()))),
        ):
            result = readers.read_agy()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            [bucket["id"] for group in result["groups"] for bucket in group["buckets"]],
            [
                "gemini-weekly",
                "gemini-5h",
                "3p-weekly",
                "3p-5h",
                "gemini-argon-wtu-weekly",
            ],
        )
        argon = result["groups"][2]["buckets"][0]
        self.assertEqual(argon["remaining_fraction"], 0.004)
        self.assertEqual(argon["reset_at"], "2026-11-28T00:00:00Z")
        self.assertEqual(
            set(argon), {"id", "name", "window", "remaining_fraction", "reset_at"}
        )
        self.assertNotIn("plan", result)
        self.assertNotIn("windows", result)

    def test_missing_executable_deadline_and_failed_process_are_safe(self):
        def unused_run(*_args, **_kwargs):
            raise AssertionError("agy must not be spawned when it is not found")

        with (
            patch(
                "hermes_platform.resolver.core.locate_command", return_value=missing()
            ),
            patch("readers.subprocess.run", side_effect=unused_run),
        ):
            missing_result = readers.read_agy()
        self.assertEqual(missing_result["status"], "failed")
        self.assertEqual(missing_result["error"], "agy not found")

        def timed_out(*_args, **kwargs):
            raise subprocess.TimeoutExpired(
                cmd="agy",
                timeout=kwargs.get("timeout", 0),
                output=b"SECRET-BODY",
                stderr=b"SECRET-STDERR",
            )

        with (
            patch("hermes_platform.resolver.core.locate_command", return_value=found()),
            patch("readers.subprocess.run", side_effect=timed_out),
        ):
            timed = readers.read_agy()
        self.assertEqual(timed["error"], "agy usage timed out")
        self.assertNotIn("SECRET", json.dumps(timed))

        with (
            patch("hermes_platform.resolver.core.locate_command", return_value=found()),
            patch(
                "readers.subprocess.run",
                return_value=completed(envelope(groups()), code=2),
            ),
        ):
            failed = readers.read_agy()
        self.assertEqual(failed["error"], "agy usage failed")
        self.assertNotIn("groups", failed)
        self.assertNotIn(SECRET_STDERR, json.dumps(failed))
        self.assertNotIn("0.42", json.dumps(failed))

    def test_malformed_empty_and_nonzero_inference_stay_failed(self):
        cases = {
            "malformed": (completed(b"{not json"), "agy usage returned malformed data"),
            "empty stdout": (completed(b""), "agy usage returned malformed data"),
            "empty groups": (
                completed(envelope([])),
                "agy usage returned no quota data",
            ),
            "turns": (
                completed(envelope(groups(), num_turns=1)),
                "agy usage did not return a quota result",
            ),
            "tokens": (
                completed(envelope(groups())),
                "agy usage did not return a quota result",
            ),
            "status": (
                completed(envelope(groups(), status="ERROR")),
                "agy usage did not return a quota result",
            ),
            "command": (
                completed(envelope(groups())),
                "agy usage did not return a quota result",
            ),
        }
        token_payload = envelope(groups())
        token_payload["usage"]["total_tokens"] = 4
        command_payload = envelope(groups())
        command_payload["command"]["name"] = "chat"
        raw = {
            "tokens": completed(token_payload),
            "command": completed(command_payload),
        }

        for name, (proc, error) in cases.items():
            with self.subTest(name=name):
                proc = raw.get(name, proc)
                with (
                    patch(
                        "hermes_platform.resolver.core.locate_command",
                        return_value=found(),
                    ),
                    patch("readers.subprocess.run", return_value=proc),
                ):
                    result = readers.read_agy()
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["error"], error)
                self.assertNotIn(SECRET_PROSE, json.dumps(result))
                self.assertNotIn("gemini-weekly", json.dumps(result))

    def test_oversized_integer_fraction_stays_unknown(self):
        sample = groups()
        sample[0]["buckets"][0]["remaining_fraction"] = 10**400
        with (
            patch(
                "hermes_platform.resolver.core.locate_command", return_value=found()
            ),
            patch("readers.subprocess.run", return_value=completed(envelope(sample))),
        ):
            result = readers.read_agy()
        self.assertEqual(result["status"], "ok")
        weekly = result["groups"][0]["buckets"][0]
        self.assertIsNone(weekly["remaining_fraction"])
        self.assertNotEqual(weekly["remaining_fraction"], 0)
        self.assertEqual(result["groups"][0]["buckets"][1]["remaining_fraction"], 0.90)
        self.assertEqual(result["groups"][1]["buckets"][0]["remaining_fraction"], 0.15)
        self.assertEqual(result["groups"][2]["buckets"][0]["remaining_fraction"], 0.004)
        blob = json.dumps(result)
        self.assertNotIn(SECRET_STDERR, blob)
        self.assertNotIn(SECRET_PROSE, blob)
        self.assertNotIn(str(10**400), blob)


class AgyParseTests(unittest.TestCase):
    def test_invalid_fractions_stay_unknown_without_coercion(self):
        sample = groups()
        sample[0]["buckets"][0]["remaining_fraction"] = True
        sample[0]["buckets"][1]["remaining_fraction"] = False
        sample[1]["buckets"][0]["remaining_fraction"] = float("nan")
        sample[1]["buckets"][1]["remaining_fraction"] = float("inf")
        sample[2]["buckets"][0]["remaining_fraction"] = 1.01
        extra = {
            "id": "low",
            "name": "Low",
            "window": "weekly",
            "remaining_fraction": -0.01,
            "reset_time": "2026-11-28T00:00:00Z",
        }
        sample[2]["buckets"].append(extra)
        sample[2]["buckets"].append(
            {
                "id": "text",
                "name": "Text",
                "window": "weekly",
                "remaining_fraction": "0",
                "reset_time": "2026-11-28T00:00:00Z",
            }
        )
        parsed = readers.parse_agy_usage(envelope(sample))
        self.assertTrue(parsed["ok"])
        fractions = [
            bucket["remaining_fraction"]
            for group in parsed["groups"]
            for bucket in group["buckets"]
        ]
        self.assertEqual(fractions, [None, None, None, None, None, None, None])
        self.assertIn(
            "low",
            [bucket["id"] for group in parsed["groups"] for bucket in group["buckets"]],
        )

    def test_genuine_zero_and_full_remain_distinct(self):
        sample = groups()
        sample[0]["buckets"][0]["remaining_fraction"] = 0
        sample[0]["buckets"][1]["remaining_fraction"] = 1
        sample[1]["buckets"][0]["remaining_fraction"] = 0.0
        sample[1]["buckets"][1]["remaining_fraction"] = 1.0
        parsed = readers.parse_agy_usage(envelope(sample))
        weekly = parsed["groups"][0]["buckets"][0]["remaining_fraction"]
        short = parsed["groups"][0]["buckets"][1]["remaining_fraction"]
        self.assertEqual(weekly, 0.0)
        self.assertEqual(short, 1.0)
        self.assertIsNot(weekly, True)
        self.assertEqual(parsed["groups"][2]["buckets"][0]["window"], "weekly")
        self.assertEqual(len(parsed["groups"][2]["buckets"]), 1)

    def test_unparseable_reset_does_not_drop_the_fraction(self):
        sample = groups()
        sample[0]["buckets"][0]["reset_time"] = "next friday"
        parsed = readers.parse_agy_usage(envelope(sample))
        bucket = parsed["groups"][0]["buckets"][0]
        self.assertIsNone(bucket["reset_at"])
        self.assertEqual(bucket["remaining_fraction"], 0.42)


def routed_readers():
    return {
        "claude": lambda: reading("claude", 40, 84),
        "codex": lambda: reading("codex", 55, 84),
        "supergrok": lambda: reading("supergrok", 25, 84),
    }


def over_pace_readers():
    return {
        "claude": lambda: reading("claude", 80, 84),
        "codex": lambda: reading("codex", 80, 84),
        "supergrok": lambda: reading("supergrok", 80, 84),
    }


def tempting_agy():
    """A reading that would win the latch if it were scored like the other subscriptions."""
    return {
        "id": "agy",
        "status": "ok",
        "observed_at": NOW.isoformat(),
        "groups": stored_groups(),
        "windows": [
            {
                "kind": "week",
                "label": "Week",
                "used_percent": 0,
                "reset_at": (NOW + timedelta(hours=84)).isoformat(),
            }
        ],
    }


class AgyCollectTests(unittest.TestCase):
    def test_display_data_does_not_change_routing(self):
        orr = lambda: {
            "id": "openrouter",
            "status": "ok",
            "observed_at": NOW.isoformat(),
            "spend": {"today": 1.0},
        }
        with tempfile.TemporaryDirectory() as tmp:
            plain = core.collect(
                now=NOW,
                read=routed_readers(),
                read_openrouter=orr,
                read_cheaper=offline_cheaper,
                path=Path(tmp) / "plain.json",
            )
            shown = core.collect(
                now=NOW,
                read={**routed_readers(), "agy": tempting_agy},
                read_openrouter=orr,
                read_cheaper=offline_cheaper,
                path=Path(tmp) / "shown.json",
            )
        for key in ("scores", "latch", "pick", "on_demand", "warning"):
            self.assertEqual(plain[key], shown[key], key)
        self.assertNotIn("agy", shown["scores"])
        self.assertNotEqual(shown["pick"]["subscription"], "agy")
        self.assertIn("agy", shown["subscriptions"])

    def test_on_demand_still_starts_when_agy_is_present(self):
        orr = lambda: {
            "id": "openrouter",
            "status": "ok",
            "observed_at": NOW.isoformat(),
            "spend": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            plain = core.collect(
                now=NOW,
                read=over_pace_readers(),
                read_openrouter=orr,
                read_cheaper=offline_cheaper,
                path=Path(tmp) / "plain.json",
            )
            shown = core.collect(
                now=NOW,
                read={**over_pace_readers(), "agy": tempting_agy},
                read_openrouter=orr,
                read_cheaper=offline_cheaper,
                path=Path(tmp) / "shown.json",
            )
        self.assertTrue(plain["on_demand"]["active"])
        self.assertEqual(plain["on_demand"], shown["on_demand"])
        self.assertEqual(plain["pick"], shown["pick"])
        self.assertEqual(plain["warning"], shown["warning"])

    def test_failed_read_keeps_last_good_but_the_card_is_unknown(self):
        orr = lambda: {
            "id": "openrouter",
            "status": "ok",
            "observed_at": NOW.isoformat(),
            "spend": {},
        }
        ok = {
            "id": "agy",
            "status": "ok",
            "observed_at": NOW.isoformat(),
            "groups": stored_groups(),
        }
        failed = {
            "id": "agy",
            "status": "failed",
            "error": "agy usage failed",
            "attempted_at": (NOW + timedelta(minutes=15)).isoformat(),
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            first = core.collect(
                now=NOW,
                read={**routed_readers(), "agy": lambda: ok},
                read_openrouter=orr,
                read_cheaper=offline_cheaper,
                path=path,
            )
            second = core.collect(
                now=NOW + timedelta(minutes=15),
                read={**routed_readers(), "agy": lambda: failed},
                read_openrouter=orr,
                read_cheaper=offline_cheaper,
                path=path,
            )
            history = (Path(tmp) / "history.jsonl").read_text().splitlines()
        card = next(item for item in core.cards(first, now=NOW) if item["id"] == "agy")
        self.assertTrue(card["fresh"])
        self.assertEqual(card["summary"]["group_name"], "Gemini Models")
        self.assertEqual(card["summary"]["tag"], "G")
        self.assertAlmostEqual(card["summary"]["remaining_percent"], 42.0)
        hidden = next(
            item
            for item in core.cards(second, now=NOW + timedelta(minutes=15))
            if item["id"] == "agy"
        )
        self.assertFalse(hidden["fresh"])
        self.assertIsNone(hidden["summary"])
        self.assertEqual(hidden["groups"], [])
        self.assertIsNone(hidden["pace_delta"])
        kept = second["subscriptions"]["agy"]
        self.assertEqual(kept["status"], "failed")
        self.assertEqual(kept["groups"][2]["buckets"][0]["remaining_fraction"], 0.004)
        self.assertFalse(second["warning"]["active"])
        self.assertNotIn("agy", json.loads(history[-1])["slack"])

    def test_stale_ok_reading_does_not_display_a_number(self):
        observed = (NOW - timedelta(hours=3)).isoformat()
        state = {
            "written_at": NOW.isoformat(),
            "scores": {"claude": pace.assess(reading("claude", 10, 84), NOW, CFG)},
            "subscriptions": {
                "agy": {
                    "id": "agy",
                    "status": "ok",
                    "observed_at": observed,
                    "groups": stored_groups(),
                },
            },
        }
        card = next(item for item in core.cards(state, now=NOW) if item["id"] == "agy")
        self.assertFalse(card["fresh"])
        self.assertEqual(card["reason"], "reading stale")
        self.assertIsNone(card["summary"])
        self.assertEqual(card["groups"], [])
        self.assertEqual(
            state["subscriptions"]["agy"]["groups"][0]["name"], "Gemini Models"
        )

    def test_oversized_fraction_still_persists_every_subscription(self):
        sample = groups()
        sample[1]["buckets"][0]["remaining_fraction"] = 10**400
        orr = lambda: {
            "id": "openrouter",
            "status": "ok",
            "observed_at": NOW.isoformat(),
            "spend": {"today": 1.25},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            with (
                patch(
                    "hermes_platform.resolver.core.locate_command",
                    return_value=found(),
                ),
                patch(
                    "readers.subprocess.run",
                    return_value=completed(envelope(sample)),
                ),
            ):
                state = core.collect(
                    now=NOW,
                    read={**routed_readers(), "agy": readers.read_agy},
                    read_openrouter=orr,
                    read_cheaper=offline_cheaper,
                    path=path,
                )
            raw = path.read_text()
        self.assertEqual(
            set(state["subscriptions"]), {"claude", "codex", "supergrok", "agy"}
        )
        for sub_id in ("claude", "codex", "supergrok"):
            self.assertEqual(state["subscriptions"][sub_id]["status"], "ok")
            self.assertIn("windows", state["subscriptions"][sub_id])
            self.assertTrue(state["scores"][sub_id]["fresh"])
        agy = state["subscriptions"]["agy"]
        self.assertEqual(agy["status"], "ok")
        self.assertIsNone(agy["groups"][1]["buckets"][0]["remaining_fraction"])
        self.assertNotEqual(agy["groups"][1]["buckets"][0]["remaining_fraction"], 0)
        self.assertEqual(agy["groups"][0]["buckets"][0]["remaining_fraction"], 0.42)
        self.assertEqual(agy["groups"][2]["buckets"][0]["remaining_fraction"], 0.004)
        saved = json.loads(raw)
        self.assertEqual(set(saved["subscriptions"]), set(state["subscriptions"]))
        self.assertEqual(set(saved["scores"]), set(state["scores"]))
        self.assertNotIn("agy", saved["scores"])
        self.assertNotIn(str(10**400), raw)
        self.assertNotIn(SECRET_STDERR, raw)
        self.assertNotIn(SECRET_PROSE, raw)
        moment = pace.parse_ts(agy["observed_at"])
        card = next(
            item for item in core.cards(state, now=moment) if item["id"] == "agy"
        )
        self.assertTrue(card["fresh"])
        unknown = card["groups"][1]["buckets"][0]["remaining_percent"]
        self.assertIsNone(unknown)
        self.assertNotEqual(unknown, 0)
        self.assertEqual(card["groups"][0]["buckets"][0]["remaining_percent"], 42.0)
        self.assertAlmostEqual(card["groups"][2]["buckets"][0]["remaining_percent"], 0.4)
        self.assertEqual(card["summary"]["group_name"], "Gemini Models")
        text = core.render_text(state, now=moment)
        self.assertIn("Gemini Models", text)
        unknown_line = next(
            line
            for line in text.splitlines()
            if "Claude and GPT" in line and "weekly" in line
        )
        self.assertIn("–", unknown_line)
        self.assertNotIn("0%", unknown_line)


class AgyCardTests(unittest.TestCase):
    def card(self, sample):
        state = {
            "written_at": NOW.isoformat(),
            "scores": {
                "claude": pace.assess(reading("claude", 98, 84), NOW, CFG),
                "codex": pace.assess(reading("codex", 10, 84), NOW, CFG),
            },
            "subscriptions": {
                "agy": {
                    "id": "agy",
                    "status": "ok",
                    "observed_at": NOW.isoformat(),
                    "groups": sample,
                },
            },
        }
        cards = core.cards(state, now=NOW)
        self.assertEqual([item["id"] for item in cards], ["claude", "codex", "agy"])
        self.assertLess(cards[0]["pace_delta"], 0)
        self.assertGreater(cards[1]["pace_delta"], 0)
        return cards[2]

    def test_summary_speaks_for_the_gemini_pool_not_an_aggregate(self):
        card = self.card(stored_groups())
        self.assertEqual(card["name"], "Antigravity")
        self.assertIsNone(card["plan"])
        self.assertTrue(card["display_only"])
        self.assertFalse(card["eligible"])
        self.assertIsNone(card["pace_delta"])
        self.assertIsNone(card["pace_used_percent"])
        self.assertIsNone(card["used_percent"])
        self.assertEqual(card["summary"]["window"], "weekly")
        self.assertEqual(card["summary"]["bucket_id"], "gemini-weekly")
        self.assertNotEqual(card["summary"]["remaining_percent"], 0)
        names = [group["name"] for group in card["groups"]]
        self.assertEqual(
            names, ["Gemini Models", "Claude and GPT models", "Gemini 4 Argon"]
        )
        self.assertEqual([group["tag"] for group in card["groups"]], ["G", "CG", "Ar"])
        argon = card["groups"][2]
        self.assertEqual([bucket["window"] for bucket in argon["buckets"]], ["weekly"])
        five_hour = card["groups"][1]["buckets"][1]
        self.assertEqual(five_hour["remaining_percent"], 0.0)
        self.assertNotEqual(
            five_hour["reset_label"], card["groups"][1]["buckets"][0]["reset_label"]
        )
        self.assertNotEqual(five_hour["reset_label"], "?")
        text = core.render_text(
            {
                "written_at": NOW.isoformat(),
                "scores": {"codex": pace.assess(reading("codex", 10, 84), NOW, CFG)},
                "subscriptions": {
                    "agy": {
                        "id": "agy",
                        "status": "ok",
                        "observed_at": NOW.isoformat(),
                        "groups": stored_groups(),
                    }
                },
            },
            now=NOW,
        )
        agy_lines = "\n".join(
            line
            for line in text.splitlines()
            if "Antigravity" in line or line.startswith("    ")
        )
        self.assertIn("Gemini 4 Argon", text)
        self.assertIn("separate", text)
        self.assertNotIn("over pace", agy_lines)
        self.assertNotIn("P:", agy_lines)

    def test_tiny_positive_fraction_is_not_shown_as_zero(self):
        payload = envelope([
            {"name": "Gemini Models", "buckets": [
                {"id": "gemini-weekly", "name": "Week", "window": "weekly",
                 "remaining_fraction": 1e-12, "reset_time": "2026-11-27T18:00:00Z"},
                {"id": "gemini-5h", "name": "Five hours", "window": "5h",
                 "remaining_fraction": 0, "reset_time": "2026-11-22T22:00:00Z"}]},
            {"name": "Gemini 4 Argon", "buckets": [
                {"id": "gemini-argon-wtu-weekly", "name": "Week", "window": "weekly",
                 "remaining_fraction": 1.0, "reset_time": "2026-11-28T00:00:00Z"}]},
        ])
        parsed = readers.parse_agy_usage(payload)
        fraction = parsed["groups"][0]["buckets"][0]["remaining_fraction"]
        self.assertEqual(fraction, 1e-12)
        card = self.card(parsed["groups"])
        percent = card["summary"]["remaining_percent"]
        self.assertEqual(card["summary"]["group_name"], "Gemini Models")
        self.assertEqual(percent, fraction * 100)
        self.assertGreater(percent, 0)
        self.assertLess(percent, 1)
        self.assertEqual(core.format_remaining(percent), "<1%")
        self.assertEqual(card["groups"][0]["buckets"][1]["remaining_percent"], 0.0)
        self.assertEqual(core.format_remaining(0), "0%")
        self.assertEqual(core.format_remaining(None), "–")
        text = core.render_text({
            "written_at": NOW.isoformat(),
            "scores": {"codex": pace.assess(reading("codex", 10, 84), NOW, CFG)},
            "subscriptions": {"agy": {"id": "agy", "status": "ok", "observed_at": NOW.isoformat(),
                                      "groups": parsed["groups"]}},
        }, now=NOW)
        gemini = next(line for line in text.splitlines() if line.startswith("    Gemini Models"))
        short = next(line for line in text.splitlines() if "5-hour" in line)
        self.assertIn("<1%", gemini)
        self.assertIn("0%", short)

    def test_summary_pace_uses_the_gemini_week(self):
        moment = datetime(2026, 11, 26, 12, tzinfo=UTC)
        sample = [{"name": "Gemini Models", "buckets": [
            {"id": "gemini-weekly", "name": "Week", "window": "weekly",
             "remaining_fraction": 0.35, "reset_at": "2026-11-29T20:27:00Z"}]}]
        card = core.agy_view({"id": "agy", "status": "ok", "observed_at": moment.isoformat(),
                              "groups": sample}, moment, CFG)
        expected = pace.window_pace(65.0, pace.parse_ts("2026-11-29T20:27:00Z"), moment)
        self.assertAlmostEqual(card["summary"]["pace_delta"], expected["p_points"])
        self.assertAlmostEqual(card["summary"]["pace_used_percent"], expected["pace_used_percent"])
        self.assertLess(card["summary"]["pace_delta"], 0)
        self.assertIsNone(card["pace_delta"])

    def test_zero_weekly_keeps_the_other_groups(self):
        sample = stored_groups()
        sample[0]["buckets"][0]["remaining_fraction"] = 0
        sample[2]["buckets"][0]["remaining_fraction"] = 0.5
        card = self.card(sample)
        self.assertEqual(card["summary"]["group_name"], "Gemini Models")
        self.assertEqual(card["summary"]["tag"], "G")
        self.assertEqual(card["summary"]["remaining_percent"], 0.0)
        self.assertEqual(card["groups"][2]["buckets"][0]["remaining_percent"], 50.0)

    def test_missing_agy_card_is_unknown_rather_than_omitted(self):
        cards = core.cards(
            {"written_at": NOW.isoformat(), "scores": {}, "subscriptions": {}}
        )
        card = next(item for item in cards if item["id"] == "agy")
        self.assertFalse(card["fresh"])
        self.assertEqual(card["reason"], "no reading")
        self.assertIsNone(card["summary"])
        self.assertIsNone(card["plan"])

    def test_invalid_weekly_does_not_invent_a_summary(self):
        sample = stored_groups()
        for group in sample:
            for bucket in group["buckets"]:
                if bucket["window"] == "weekly":
                    bucket["remaining_fraction"] = True
        card = self.card(sample)
        self.assertIsNone(card["summary"])
        self.assertEqual(card["groups"][0]["buckets"][1]["remaining_percent"], 90.0)
        self.assertIsNone(card["groups"][0]["buckets"][0]["remaining_percent"])

    def test_stopped_collection_expires_a_reading_saved_while_fresh(self):
        limit = pace.DEFAULTS["stale_after_s"]
        observed = datetime.now(UTC) - timedelta(seconds=limit + 90)
        written = observed + timedelta(seconds=30)
        self.assertLess((written - observed).total_seconds(), limit)
        self.assertGreater(
            (datetime.now(UTC) - written).total_seconds(), limit
        )
        state = {
            "written_at": written.isoformat(),
            "scores": {"claude": pace.assess(reading("claude", 10, 84), NOW, CFG)},
            "subscriptions": {
                "agy": {
                    "id": "agy",
                    "status": "ok",
                    "observed_at": observed.isoformat(),
                    "groups": stored_groups(),
                }
            },
        }
        cards = core.cards(state)
        card = next(item for item in cards if item["id"] == "agy")
        self.assertFalse(card["fresh"])
        self.assertEqual(card["reason"], "reading stale")
        self.assertIsNone(card["summary"])
        self.assertEqual(card["groups"], [])
        text = core.render_text(state)
        self.assertIn("Antigravity: reading stale", text)
        self.assertNotIn("Gemini", text)
        paced = next(item for item in cards if item["id"] == "claude")
        scored = pace.assess(reading("claude", 10, 84), NOW, CFG)
        self.assertTrue(paced["fresh"])
        self.assertEqual(paced["used_percent"], scored["used_percent"])
        self.assertEqual(paced["pace_delta"], scored["p_points"])

    def test_explicit_clock_is_fresh_when_the_saved_write_is_old(self):
        state = {
            "written_at": (NOW - timedelta(hours=3)).isoformat(),
            "scores": {"claude": pace.assess(reading("claude", 98, 84), NOW, CFG)},
            "subscriptions": {
                "agy": {
                    "id": "agy",
                    "status": "ok",
                    "observed_at": NOW.isoformat(),
                    "groups": stored_groups(),
                }
            },
        }
        card = next(item for item in core.cards(state, now=NOW) if item["id"] == "agy")
        self.assertTrue(card["fresh"])
        self.assertEqual(card["summary"]["group_name"], "Gemini Models")
        self.assertEqual(card["reason"], "")
        text = core.render_text(state, now=NOW)
        self.assertIn("Gemini 4 Argon", text)
        self.assertNotIn("reading stale", text)
        paced = next(item for item in core.cards(state, now=NOW) if item["id"] == "claude")
        self.assertLess(paced["pace_delta"], 0)

    def test_explicit_clock_is_stale_when_the_saved_write_is_recent(self):
        state = {
            "written_at": NOW.isoformat(),
            "scores": {"codex": pace.assess(reading("codex", 10, 84), NOW, CFG)},
            "subscriptions": {
                "agy": {
                    "id": "agy",
                    "status": "ok",
                    "observed_at": (
                        NOW - timedelta(seconds=pace.DEFAULTS["stale_after_s"] + 1)
                    ).isoformat(),
                    "groups": stored_groups(),
                }
            },
        }
        card = next(item for item in core.cards(state, now=NOW) if item["id"] == "agy")
        self.assertFalse(card["fresh"])
        self.assertEqual(card["reason"], "reading stale")
        self.assertIsNone(card["summary"])
        self.assertEqual(card["groups"], [])
        text = core.render_text(state, now=NOW)
        self.assertIn("Antigravity: reading stale", text)
        self.assertNotIn("Gemini", text)
        self.assertIn("P: ", text)

    def test_corrupted_fraction_does_not_throw_at_card_projection(self):
        self.assertIsNone(core._remaining_percent(10**400))
        self.assertIsNone(core._remaining_percent(-(10**400)))
        self.assertEqual(core._remaining_percent(0), 0.0)
        self.assertEqual(core._remaining_percent(1e-12), 1e-10)
        self.assertIsNone(core._remaining_percent(True))
        self.assertIsNone(core._remaining_percent(float("nan")))
        sample = stored_groups()
        sample[2]["buckets"][0]["remaining_fraction"] = 10**400
        card = self.card(sample)
        argon = card["groups"][2]["buckets"][0]
        self.assertIsNone(argon["remaining_percent"])
        self.assertNotEqual(argon["remaining_percent"], 0)
        self.assertEqual(card["groups"][0]["buckets"][0]["remaining_percent"], 42.0)
        self.assertEqual(card["groups"][1]["buckets"][0]["remaining_percent"], 15.0)
        self.assertEqual(card["summary"]["group_name"], "Gemini Models")
        text = core.render_text(
            {
                "written_at": (NOW - timedelta(hours=5)).isoformat(),
                "scores": {"codex": pace.assess(reading("codex", 10, 84), NOW, CFG)},
                "subscriptions": {
                    "agy": {
                        "id": "agy",
                        "status": "ok",
                        "observed_at": NOW.isoformat(),
                        "groups": sample,
                    }
                },
            },
            now=NOW,
        )
        argon_line = next(
            line for line in text.splitlines() if line.startswith("    Gemini 4 Argon")
        )
        self.assertIn("–", argon_line)
        self.assertNotIn("0%", argon_line)
        self.assertNotIn(str(10**400), text)


if __name__ == "__main__":
    unittest.main()
