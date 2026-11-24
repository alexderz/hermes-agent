"""Cheaper Inference rates: pay-per-use prices, filtered to configured models.

Pure: fake catalog payloads and fake readers, temp state dir.
Run: python3 -I -m unittest discover -s plugins/model-routing/tests
"""
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


if __name__ == "__main__":
    unittest.main()
