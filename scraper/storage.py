import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from elasticsearch import Elasticsearch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DATA_FILE = DATA_DIR / "price_history.json"


def get_elasticsearch_client():
    endpoint = os.getenv("ELASTIC_ENDPOINT")
    username = os.getenv("ELASTIC_USERNAME")
    password = os.getenv("ELASTIC_PASSWORD")

    if endpoint and username and password:
        try:
            return Elasticsearch(
                endpoint,
                basic_auth=(username, password),
                request_timeout=10,
            )
        except Exception as exc:
            print(f"Elasticsearch client setup failed: {exc}")

    return None


def _load_local_history():
    if not DATA_FILE.exists():
        return {}

    try:
        with DATA_FILE.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_local_history(history):
    with DATA_FILE.open("w", encoding="utf-8") as handle:
        json.dump(history, handle, indent=2)


def save_price_record(record):
    client = get_elasticsearch_client()
    if client:
        try:
            client.index(index="price_history", document=record)
            return {"backend": "elasticsearch", "saved": True}
        except Exception as exc:
            print(f"Elasticsearch save failed: {exc}")

    history = _load_local_history()
    url = record.get("url")
    if url not in history:
        history[url] = []
    history[url].append(record)
    _save_local_history(history)
    return {"backend": "local-file", "saved": True}


def get_price_history(url):
    client = get_elasticsearch_client()
    if client:
        try:
            result = client.search(
                index="price_history",
                body={
                    "query": {"term": {"url": url}},
                    "sort": [{"timestamp": {"order": "asc"}}],
                    "size": 1000,
                },
            )
            hits = result.get("hits", {}).get("hits", [])
            return [hit.get("_source", {}) for hit in hits]
        except Exception as exc:
            print(f"Elasticsearch query failed: {exc}")

    history = _load_local_history()
    return history.get(url, [])


def get_latest_price(url):
    records = get_price_history(url)
    if not records:
        return None
    return records[-1].get("price")
