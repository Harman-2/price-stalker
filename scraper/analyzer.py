import argparse
from datetime import datetime, timedelta

from storage import get_price_history, get_latest_price

def get_price_stats(url):
    """Layer 1 — get min, max, average, and percentiles for this product."""
    records = get_price_history(url)
    if not records:
        return {"min": None, "max": None, "avg": None, "p20": None, "p50": None, "p80": None, "count": 0}

    prices = [record["price"] for record in records if record.get("price") is not None]
    if not prices:
        return {"min": None, "max": None, "avg": None, "p20": None, "p50": None, "p80": None, "count": 0}

    prices = sorted(prices)
    count = len(prices)

    def percentile(values, pct):
        if not values:
            return None
        index = max(0, min(count - 1, int(round((pct / 100) * (count - 1)))))
        return values[index]

    return {
        "min": prices[0],
        "max": prices[-1],
        "avg": sum(prices) / count,
        "p20": percentile(prices, 20),
        "p50": percentile(prices, 50),
        "p80": percentile(prices, 80),
        "count": count,
    }


def get_price_trend(url):
    """Layer 2 — is the price going up or down over the last 30 days?"""
    records = get_price_history(url)
    if not records:
        return "stable", []

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_records = []
    for record in records:
        timestamp = record.get("timestamp")
        if not timestamp:
            continue
        try:
            parsed = datetime.fromisoformat(timestamp)
        except ValueError:
            continue
        if parsed >= thirty_days_ago:
            recent_records.append(record)

    if len(recent_records) < 2:
        return "stable", [record.get("price") for record in recent_records if record.get("price") is not None]

    prices = [record["price"] for record in recent_records if record.get("price") is not None]
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
    return get_latest_price(url)


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


def main():
    parser = argparse.ArgumentParser(description="Analyze historical price data for a product")
    parser.add_argument("url", nargs="?", help="Amazon product URL")
    args = parser.parse_args()

    target_url = args.url or input("Paste the Amazon product URL to analyze: ").strip()
    if target_url:
        analyze(target_url)


if __name__ == "__main__":
    main()