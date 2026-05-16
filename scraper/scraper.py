import os
import re
import json
from datetime import datetime
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from elasticsearch import Elasticsearch

load_dotenv(dotenv_path="../.env")

# Connect to Elastic
es = Elasticsearch(
    os.getenv("ELASTIC_ENDPOINT"),
    basic_auth=(
        os.getenv("ELASTIC_USERNAME"),
        os.getenv("ELASTIC_PASSWORD")
    )
)

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
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
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


def save_to_elastic(data):
    """Index the price data point into Elasticsearch."""
    try:
        es.index(index="price_history", document=data)
        print(f"Saved to Elastic: ${data['price']} at {data['timestamp']}")
    except Exception as e:
        print(f" Elastic save failed: {e}")


def scrape_and_save(url):
    """Main function — scrape price and save to Elastic."""
    print(f"\n Scraping: {url}\n")
    data = scrape_amazon_price(url)
    if data:
        save_to_elastic(data)
        return data
    return None


# Test it directly
if __name__ == "__main__":
    test_url = input("Paste an Amazon product URL: ").strip()
    scrape_and_save(test_url)