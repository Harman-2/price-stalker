import os
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
import vertexai
from vertexai.generative_models import GenerativeModel, Part, Content

load_dotenv(dotenv_path="../.env")

# Connect to Elastic
es = Elasticsearch(
    cloud_id=os.getenv("ELASTIC_CLOUD_ID"),
    basic_auth=(
        os.getenv("ELASTIC_USERNAME"),
        os.getenv("ELASTIC_PASSWORD")
    )
)

# Connect to Vertex AI Gemini
vertexai.init(
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location="us-central1"
)
model = GenerativeModel(
    "gemini-1.5-flash-002",
    system_instruction="""You are Price Stalker, an intelligent shopping agent.
When given an Amazon URL, analyze the price and tell the user whether to BUY NOW, WAIT, or WATCH IT.
Always be specific with dollar amounts and percentages. Be friendly and helpful."""
)

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

def scrape_current_price(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        name_tag = soup.find(id="productTitle")
        product_name = name_tag.get_text(strip=True) if name_tag else "Unknown Product"
        price = None
        for sel in [{"id": "priceblock_ourprice"}, {"id": "priceblock_dealprice"},
                    {"class": "a-price-whole"}, {"id": "price_inside_buybox"}]:
            tag = soup.find(attrs=sel)
            if tag:
                raw = tag.get_text(strip=True).replace(",", "").replace("$", "")
                match = re.search(r"[\d]+\.?[\d]*", raw)
                if match:
                    price = float(match.group())
                    break
        if price:
            es.index(index="price_history", document={
                "product_name": product_name, "url": url,
                "price": price, "currency": "USD",
                "source": "amazon", "timestamp": datetime.now().isoformat()
            })
        return product_name, price
    except Exception as e:
        return "Unknown", None

def analyze_price_history(url):
    try:
        stats = es.search(index="price_history", body={
            "query": {"term": {"url": url}},
            "aggs": {
                "min_price": {"min": {"field": "price"}},
                "max_price": {"max": {"field": "price"}},
                "avg_price": {"avg": {"field": "price"}},
                "pcts": {"percentiles": {"field": "price", "percents": [20, 80]}}
            },
            "size": 1,
            "sort": [{"timestamp": {"order": "desc"}}]
        })
        aggs = stats["aggregations"]
        current = stats["hits"]["hits"][0]["_source"]["price"]
        min_p = aggs["min_price"]["value"]
        max_p = aggs["max_price"]["value"]
        avg_p = round(aggs["avg_price"]["value"], 2)
        p20 = aggs["pcts"]["values"]["20.0"]
        p80 = aggs["pcts"]["values"]["80.0"]

        thirty_ago = (datetime.now() - timedelta(days=30)).isoformat()
        trend_res = es.search(index="price_history", body={
            "query": {"bool": {"must": [
                {"term": {"url": url}},
                {"range": {"timestamp": {"gte": thirty_ago}}}
            ]}},
            "aggs": {"over_time": {"date_histogram": {
                "field": "timestamp", "calendar_interval": "week"
            }, "aggs": {"avg_price": {"avg": {"field": "price"}}}}},
            "size": 0
        })
        buckets = trend_res["aggregations"]["over_time"]["buckets"]
        prices = [b["avg_price"]["value"] for b in buckets if b["avg_price"]["value"]]
        trend = "stable"
        if len(prices) >= 2:
            first = sum(prices[:len(prices)//2]) / (len(prices)//2)
            second = sum(prices[len(prices)//2:]) / (len(prices) - len(prices)//2)
            diff = ((second - first) / first) * 100
            if diff <= -5: trend = "falling"
            elif diff >= 5: trend = "rising"

        if current <= p20 and trend in ["falling", "stable"]:
            verdict = "BUY NOW"
        elif current >= p80 or trend == "rising":
            verdict = "WAIT"
        else:
            verdict = "WATCH IT"

        return {
            "current_price": current,
            "min_price": min_p,
            "max_price": max_p,
            "avg_price": avg_p,
            "trend": trend,
            "verdict": verdict
        }
    except Exception as e:
        return {"error": str(e)}

def run_agent():
    print("\n🕵️  Price Stalker Agent started!")
    print("Paste an Amazon URL and I'll tell you if it's a good deal.\n")

    chat = model.start_chat()

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ["exit", "quit", "bye"]:
            print("Price Stalker: Happy shopping! 👋")
            break

        # Scrape and analyze first
        print("\n⚙️  Scraping price...")
        product_name, price = scrape_current_price(user_input)

        if price:
            print(f"⚙️  Analyzing history...")
            analysis = analyze_price_history(user_input)

            context = f"""
The user wants to know about this Amazon product: {user_input}

Here is the live data I collected:
- Product: {product_name}
- Current price: ${price}
- Min ever: ${analysis.get('min_price')}
- Max ever: ${analysis.get('max_price')}
- Average: ${analysis.get('avg_price')}
- Trend: {analysis.get('trend')}
- Verdict: {analysis.get('verdict')}

Based on this data, give the user a clear friendly verdict with specific numbers.
"""
            response = chat.send_message(context)
        else:
            response = chat.send_message(f"I could not scrape the price for: {user_input}. Tell the user politely and suggest they try a different URL.")

        print(f"\n🕵️  Price Stalker: {response.text}\n")

if __name__ == "__main__":
    run_agent()