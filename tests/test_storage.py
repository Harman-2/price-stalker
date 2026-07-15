import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper"))

from storage import _save_local_history, _load_local_history


def test_local_history_round_trip(tmp_path, monkeypatch):
    import storage

    monkeypatch.setattr(storage, "DATA_FILE", tmp_path / "price_history.json")

    record = {"url": "https://example.com/product", "price": 19.99, "timestamp": "2026-01-01T00:00:00"}
    storage.save_price_record(record)

    history = _load_local_history()
    assert history[record["url"]][0]["price"] == 19.99
