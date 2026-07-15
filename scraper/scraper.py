import argparse
import os
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup

from storage import save_price_record

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

def scrape_amazon_price(url):
    """Fetch current price and product name from an Amazon URL."""
    if not url or not url.startswith("http"):
        raise ValueError("A valid product URL is required")

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Product name
        name_tag = soup.find(id="productTitle")
        product_name = name_tag.get_text(strip=True) if name_tag else "Unknown Product"

        # Price — Amazon uses several possible elements
        price = None
        selectors = [
            {"id": "priceblock_ourprice"},
            {"id": "priceblock_dealprice"},
            {"class": "a-price-whole"},
            {"id": "price_inside_buybox"},
        ]
        for sel in selectors:
            tag = soup.find(attrs=sel)
            if tag:
                raw = tag.get_text(strip=True).replace(",", "").replace("$", "")
                match = re.search(r"[\d]+\.?[\d]*", raw)
                if match:
                    price = float(match.group())
                    break

        if price is None:
            print("Could not find price. Amazon may be blocking the request.")
            return None

        result = {
            "product_name": product_name,
            "url": url,
            "price": price,
            "currency": "USD",
            "source": "amazon",
            "timestamp": datetime.utcnow().isoformat()
        }

        print(f"\n Product: {product_name[:60]}")
        print(f" Price:   ${price}")
        return result

    except Exception as e:
        print(f" Scraping failed: {e}")
        return None


def save_to_storage(data):
    """Store the price data point in Elasticsearch or fall back to a local JSON file."""
    result = save_price_record(data)
    if result["backend"] == "elasticsearch":
        print(f"Saved to Elastic: ${data['price']} at {data['timestamp']}")
    else:
        print(f"Saved locally: ${data['price']} at {data['timestamp']}")


def scrape_and_save(url):
    """Main function — scrape price and save it to storage."""
    print(f"\n Scraping: {url}\n")
    data = scrape_amazon_price(url)
    if data:
        save_to_storage(data)
        return data
    return None


def main():
    parser = argparse.ArgumentParser(description="Scrape an Amazon product price and store it")
    parser.add_argument("url", nargs="?", help="Amazon product URL")
    args = parser.parse_args()

    target_url = args.url or input("Paste an Amazon product URL: ").strip()
    if target_url:
        scrape_and_save(target_url)


if __name__ == "__main__":
    main()