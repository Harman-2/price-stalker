import os
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from datetime import datetime, timedelta

load_dotenv(dotenv_path="../.env")

es = Elasticsearch(
    os.getenv("ELASTIC_ENDPOINT"),
    basic_auth=(
        os.getenv("ELASTIC_USERNAME"),
        os.getenv("ELASTIC_PASSWORD")
    )
)

def get_price_stats(url):
    """Layer 1 — get min, max, average, and percentiles for this product."""
    result = es.search(index="price_history", body={
        "query": {
            "term": { "url": url }
        },
        "aggs": {
            "min_price":     { "min": { "field": "price" } },
            "max_price":     { "max": { "field": "price" } },
            "avg_price":     { "avg": { "field": "price" } },
            "price_percentiles": {
                "percentiles": {
                    "field": "price",
                    "percents": [20, 50, 80]
                }
            }
        },
        "size": 0
    })

    aggs = result["aggregations"]
    return {
        "min":   aggs["min_price"]["value"],
        "max":   aggs["max_price"]["value"],
        "avg":   aggs["avg_price"]["value"],
        "p20":   aggs["price_percentiles"]["values"]["20.0"],
        "p50":   aggs["price_percentiles"]["values"]["50.0"],
        "p80":   aggs["price_percentiles"]["values"]["80.0"],
        "count": result["hits"]["total"]["value"]
    }


def get_price_trend(url):
    """Layer 2 — is the price going up or down over the last 30 days?"""
    thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()

    result = es.search(index="price_history", body={
        "query": {
            "bool": {
                "must": [
                    { "term": { "url": url } },
                    { "range": { "timestamp": { "gte": thirty_days_ago } } }
                ]
            }
        },
        "aggs": {
            "prices_over_time": {
                "date_histogram": {
                    "field": "timestamp",
                    "calendar_interval": "week"
                },
                "aggs": {
                    "avg_price": { "avg": { "field": "price" } }
                }
            }
        },
        "size": 0
    })

    buckets = result["aggregations"]["prices_over_time"]["buckets"]

    if len(buckets) < 2:
        return "stable", []

    prices = [b["avg_price"]["value"] for b in buckets if b["avg_price"]["value"]]

    if len(prices) < 2:
        return "stable", prices

    first_half = sum(prices[:len(prices)//2]) / (len(prices)//2)
    second_half = sum(prices[len(prices)//2:]) / (len(prices) - len(prices)//2)

    diff_pct = ((second_half - first_half) / first_half) * 100

    if diff_pct <= -5:
        trend = "falling"
    elif diff_pct >= 5:
        trend = "rising"
    else:
        trend = "stable"

    return trend, prices


def get_current_price(url):
    """Get the most recently scraped price for this product."""
    result = es.search(index="price_history", body={
        "query": { "term": { "url": url } },
        "sort": [{ "timestamp": { "order": "desc" } }],
        "size": 1
    })

    hits = result["hits"]["hits"]
    if not hits:
        return None
    return hits[0]["_source"]["price"]


def analyze(url):
    """Main function — run all three layers and return a verdict."""

    print(f"\n Analyzing price history for:\n{url}\n")

    # Check we have enough data
    stats = get_price_stats(url)

    if stats["count"] == 0:
        print(" No price history found for this product. Scrape it a few times first.")
        return

    current_price = get_current_price(url)
    trend, price_history = get_price_trend(url)

    print(f"   Price Stats:")
    print(f"   Current:  ${current_price}")
    print(f"   Min ever: ${stats['min']}")
    print(f"   Max ever: ${stats['max']}")
    print(f"   Average:  ${round(stats['avg'], 2)}")
    print(f"   Trend:    {trend}")
    print(f"   Data points: {stats['count']}")

    # Layer 1 — where does current price sit?
    if current_price <= stats["p20"]:
        price_signal = "low"
    elif current_price >= stats["p80"]:
        price_signal = "high"
    else:
        price_signal = "medium"

    # Layer 4 — combine signals into verdict
    print(f"\n Analysis:")

    if price_signal == "low" and trend in ["falling", "stable"]:
        verdict = "BUY NOW"
        reason = (
            f"This price (${current_price}) is in the bottom 20% of "
            f"historical prices and the trend is {trend}. "
            f"This is a genuinely good deal."
        )

    elif price_signal == "high" or trend == "rising":
        verdict = "WAIT"
        reason = (
            f"This price (${current_price}) is {'near its highest' if price_signal == 'high' else 'average'} "
            f"and the trend is {trend}. "
            f"Historical low is ${stats['min']} — worth waiting for a better price."
        )

    else:
        verdict = "WATCH IT"
        reason = (
            f"This price (${current_price}) is in the middle of its historical range "
            f"(${stats['min']} – ${stats['max']}). "
            f"Set an alert for below ${round(stats['p20'], 2)} to get a great deal."
        )

    print(f"\n{'='*50}")
    print(f"  VERDICT: {verdict}")
    print(f"  {reason}")
    print(f"{'='*50}\n")

    return {
        "verdict": verdict,
        "reason": reason,
        "current_price": current_price,
        "stats": stats,
        "trend": trend
    }


if __name__ == "__main__":
    url = input("Paste the Amazon product URL to analyze: ").strip()
    analyze(url)