"""Cheaper Inference rates: pay-per-use prices, filtered to configured models.

Pure: fake catalog payloads and fake readers, temp state dir.
Run: python3 -I -m unittest discover -s plugins/model-routing/tests
"""
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import core
import readers

NOW = datetime(2026, 11, 8, 18, 0, tzinfo=UTC)


def model(model_id, input_price, output_price, discount=None, *, provider="DeepSeek"):
    return {
        "id": model_id,
        "provider": provider,
        "owned_by": provider,
        "is_free": False,
        "pricing": {
            "input_per_million": input_price,
            "output_per_million": output_price,
            "list_input_per_million": "0.300000",
            "list_output_per_million": "1.200000",
            "discount_percent": discount,
        },
    }


class ParseTests(unittest.TestCase):
    def test_filters_to_configured_models_and_keeps_config_order(self):
        payload = {"data": [model("a", "0.25", "1.00"), model("b", "0.075", "0.24", "56.00"), model("c", "1", "2")]}
        rows = readers.parse_cheaper_models(payload, ["b", "a"])
        self.assertEqual([row["id"] for row in rows], ["b", "a"])
        self.assertAlmostEqual(rows[0]["input"], 0.075)
        self.assertAlmostEqual(rows[0]["output"], 0.24)
        self.assertEqual(rows[0]["discount"], 56.0)

    def test_skips_missing_and_unpriced_models(self):
        payload = {"data": [model("priced", "0.5", "1.5"), {"id": "no-pricing"}, model("bad", "free", "x")]}
        rows = readers.parse_cheaper_models(payload, ["priced", "missing", "no-pricing", "bad"])
        self.assertEqual([row["id"] for row in rows], ["priced"])

    def test_unknown_shapes_are_empty(self):
        for payload in (None, {}, {"data": "nope"}, []):
            self.assertEqual(readers.parse_cheaper_models(payload, ["a"]), [])

    def test_configured_models_reads_provider_list_and_default(self):
        cfg = {"model": {"default": "default-model", "provider": "custom:cheaperinference"},
               "providers": {"cheaperinference": {"models": ["one", "two"]}}}
        self.assertEqual(readers.cheaper_configured_models(cfg), ["one", "two", "default-model"])
        self.assertEqual(readers.cheaper_active_model(cfg), "default-model")

    def test_active_model_needs_the_cheaper_provider(self):
        cfg = {"model": {"default": "one", "provider": "openrouter"},
               "providers": {"cheaperinference": {"models": ["one"]}}}
        self.assertIsNone(readers.cheaper_active_model(cfg))


class CollectTests(unittest.TestCase):
    def cheaper(self):
        return {"id": "cheaperinference", "status": "ok", "observed_at": NOW.isoformat(),
                "spend": {"today": 0.42, "week": 1.9, "month": 4.47, "balance": None},
                "active_model": "b",
                "models": [{"id": "b", "provider": "DeepSeek", "input": 0.075, "output": 0.24,
                            "list_input": 0.3, "list_output": 1.2, "discount": 56.0, "free": False}]}

    def subscriptions(self):
        return {"supergrok": lambda: {"id": "supergrok", "status": "failed", "error": "offline"}}

    def openrouter(self):
        return {"id": "openrouter", "status": "failed", "error": "offline"}

    def test_state_carries_rates_and_renders_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = core.collect(now=NOW, read=self.subscriptions(), read_openrouter=self.openrouter,
                                 read_cheaper=self.cheaper, path=path)
            text = core.render_text(state, now=NOW)
        self.assertEqual(state["cheaperinference"]["models"][0]["id"], "b")
        self.assertIn("Cheaper Inference", text)
        self.assertIn("$0.075 in / $0.24 out", text)
        self.assertIn("56% off list", text)

    def test_last_good_rates_survive_a_failed_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            first = core.collect(now=NOW, read=self.subscriptions(), read_openrouter=self.openrouter,
                                 read_cheaper=self.cheaper, path=path)
            failing = lambda: {"id": "cheaperinference", "status": "failed", "error": "HTTP 503"}
            second = core.collect(now=NOW, read=self.subscriptions(), read_openrouter=self.openrouter,
                                  read_cheaper=failing, path=path)
        self.assertEqual(first["cheaperinference"]["status"], "ok")
        self.assertEqual(second["cheaperinference"]["status"], "failed")
        self.assertEqual(second["cheaperinference"]["models"][0]["id"], "b")

    def test_a_reader_that_escapes_never_stops_the_collector(self):
        def boom():
            raise RuntimeError("boom")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = core.collect(now=NOW, read=self.subscriptions(), read_openrouter=self.openrouter,
                                 read_cheaper=boom, path=path)
            self.assertTrue(path.exists())
        self.assertEqual(state["cheaperinference"]["status"], "failed")
        self.assertEqual(state["cheaperinference"]["error"], "RuntimeError")


class ReaderTests(unittest.TestCase):
    """read_cheaper_inference is total: every failure becomes a failed reading."""

    def read(self, payload=b"", *, usage=b'{"daily_spend":[]}', token="token", models=("m",), exc=None, now=None):
        def fake(req, timeout):
            if exc is not None:
                raise exc
            if req.full_url.endswith("/usage/daily"):
                return usage
            return payload

        with patch.object(readers, "_cheaper_urlopen", fake):
            return readers.read_cheaper_inference(token_fn=lambda: token,
                                                  models_fn=lambda: list(models), now=now)

    def catalog(self, *rows):
        return json.dumps({"data": list(rows)}).encode()

    def test_no_token_makes_no_request(self):
        with patch.object(readers, "_cheaper_urlopen", side_effect=AssertionError("must not run")):
            reading = readers.read_cheaper_inference(token_fn=lambda: None, models_fn=lambda: ["m"])
        self.assertEqual(reading["status"], "failed")
        self.assertEqual(reading["error"], "no Cheaper Inference key")

    def test_http_error_is_a_failed_reading(self):
        class HTTPError(Exception):
            code = 503

        reading = self.read(exc=HTTPError("down"))
        self.assertEqual(reading["status"], "failed")
        self.assertEqual(reading["error"], "usage unreadable (HTTPError)")

    def test_transport_error_is_a_failed_reading(self):
        reading = self.read(exc=TimeoutError())
        self.assertEqual(reading["status"], "failed")
        self.assertEqual(reading["error"], "usage unreadable (TimeoutError)")

    def test_hostile_prices_do_not_raise(self):
        huge = json.dumps({"data": [{"id": "m", "pricing": {"input_per_million": 1 << 2000,
                                                            "output_per_million": 1}}]}).encode()
        reading = self.read(huge)
        self.assertEqual(reading["status"], "failed")
        self.assertIn("usage", reading["error"])

    def test_non_string_provider_is_dropped(self):
        reading = self.read(self.catalog({"id": "m", "provider": {"x": 1},
                                          "pricing": {"input_per_million": "1", "output_per_million": "2"}}))
        self.assertEqual(reading["status"], "ok")
        self.assertEqual(reading["models"][0]["provider"], "")

    def test_malformed_json_is_a_failed_reading(self):
        reading = self.read(b"{not json")
        self.assertEqual(reading["status"], "failed")
        self.assertTrue(reading["error"])

    def test_recursion_error_from_the_parser_is_caught(self):
        with patch.object(readers.json, "loads", side_effect=RecursionError):
            reading = self.read(b"{}")
        self.assertEqual(reading["status"], "failed")
        self.assertIn("RecursionError", reading["error"])

    def test_balance_parses_common_shapes(self):
        for payload, want in (
            ({"balance_usd": "12.5"}, 12.5),
            ({"balance_usd": "12.5", "available_usd": "9.0", "reserved_usd": "3.5"}, 9.0),
            ({"wallet": {"available_usd": "3.25"}}, 3.25),
            ({"data": [{"balance": "0"}]}, 0.0),
        ):
            self.assertEqual(readers._find_balance(payload), want)
        for payload in ({"unrelated": 1}, None, {}, {"balance": "n/a"}):
            self.assertIsNone(readers._find_balance(payload))

    def test_balance_rides_along_with_spend(self):
        usage = json.dumps({"daily_spend": [{"date": "2026-11-26", "spend_usd": "0.10"}]}).encode()
        reading = self.read(b'{"data": [], "balance_usd": "7.5"}', usage=usage,
                            now=datetime(2026, 11, 26, 12, tzinfo=UTC))
        self.assertEqual(reading["status"], "ok")
        self.assertEqual(reading["spend"]["balance"], 7.5)

    def test_duplicate_configured_models_collapse(self):
        reading = self.read(self.catalog({"id": "m", "pricing": {"input_per_million": "1", "output_per_million": "2"}}),
                            models=("m", "m"))
        self.assertEqual([row["id"] for row in reading["models"]], ["m"])

    def test_spend_is_primary_and_rates_are_detail(self):
        usage = json.dumps({"daily_spend": [
            {"date": "2026-11-24", "spend_usd": "1.00"},
            {"date": "2026-11-26", "spend_usd": "0.25"}]}).encode()
        reading = self.read(self.catalog({"id": "m", "pricing": {"input_per_million": "1", "output_per_million": "2"}}),
                            usage=usage, now=datetime(2026, 11, 26, 12, tzinfo=UTC))
        self.assertEqual(reading["status"], "ok")
        self.assertEqual(reading["spend"]["today"], 0.25)
        self.assertEqual(reading["spend"]["week"], 1.25)
        self.assertEqual(reading["spend"]["month"], 1.25)
        self.assertEqual(reading["models"][0]["id"], "m")

    def test_spend_without_rates_is_still_ok(self):
        usage = json.dumps({"daily_spend": [{"date": "2026-11-26", "spend_usd": "0.10"}]}).encode()
        reading = self.read(b"{}", usage=usage, now=datetime(2026, 11, 26, 12, tzinfo=UTC))
        self.assertEqual(reading["status"], "ok")
        self.assertEqual(reading["spend"]["today"], 0.10)
        self.assertEqual(reading["models"], [])


class SpendTests(unittest.TestCase):
    def payload(self, *pairs):
        return {"daily_spend": [{"date": day, "spend_usd": amount} for day, amount in pairs]}

    def test_utc_week_month_and_today(self):
        now = datetime(2026, 11, 26, 12, tzinfo=UTC)  # Thursday
        out = readers.parse_cheaper_spend(self.payload(
            ("2026-10-31", "1.00"), ("2026-11-01", "2.00"),
            ("2026-11-22", "3.00"), ("2026-11-23", "0.40"), ("2026-11-26", "0.10")), now)
        self.assertEqual(out["today"], 0.10)
        self.assertAlmostEqual(out["week"], 0.50)   # Monday the 23rd onward
        self.assertAlmostEqual(out["month"], 5.50)  # the 1st onward
        self.assertIsNone(out["balance"])           # needs account:read, never zero

    def test_missing_today_reads_zero_and_unknown_shapes_are_none(self):
        now = datetime(2026, 11, 26, 12, tzinfo=UTC)
        self.assertEqual(readers.parse_cheaper_spend(self.payload(("2026-11-25", "1.00")), now)["today"], 0.0)
        for payload in (None, {}, {"daily_spend": "nope"}, {"daily_spend": [{"date": "bad"}]}):
            self.assertIsNone(readers.parse_cheaper_spend(payload, now))


if __name__ == "__main__":
    unittest.main()
