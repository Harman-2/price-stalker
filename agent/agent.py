import os
import sys
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from google import genai
from google.genai import types

load_dotenv(dotenv_path="../.env")

# Connect to Elastic
es = Elasticsearch(
    os.getenv("ELASTIC_ENDPOINT"),
    basic_auth=(
        os.getenv("ELASTIC_USERNAME"),
        os.getenv("ELASTIC_PASSWORD")
    )
)

# Connect to Gemini
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# TOOLS — functions Gemini can call

def scrape_current_price(url: str) -> dict:
    """Scrape the current price of an Amazon product."""
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

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        name_tag = soup.find(id="productTitle")
        product_name = name_tag.get_text(strip=True) if name_tag else "Unknown Product"

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

        if price:
            doc = {
                "product_name": product_name,
                "url": url,
                "price": price,
                "currency": "USD",
                "source": "amazon",
                "timestamp": datetime.now().isoformat()
            }
            es.index(index="price_history", document=doc)
            return {"product_name": product_name, "price": price, "status": "success"}
        else:
            return {"status": "error", "message": "Could not find price"}

    except Exception as e:
        return {"status": "error", "message": str(e)}


def analyze_price_history(url: str) -> dict:
    """Analyze the price history for a product and return stats and verdict."""
    try:
        # Get stats
        stats_result = es.search(index="price_history", body={
            "query": { "term": { "url": url } },
            "aggs": {
                "min_price": { "min": { "field": "price" } },
                "max_price": { "max": { "field": "price" } },
                "avg_price": { "avg": { "field": "price" } },
                "percentiles": {
                    "percentiles": {
                        "field": "price",
                        "percents": [20, 80]
                    }
                }
            },
            "size": 1,
            "sort": [{ "timestamp": { "order": "desc" } }]
        })

        aggs = stats_result["aggregations"]
        count = stats_result["hits"]["total"]["value"]

        if count == 0:
            return {"status": "error", "message": "No price history found"}

        current_price = stats_result["hits"]["hits"][0]["_source"]["price"]
        min_price = aggs["min_price"]["value"]
        max_price = aggs["max_price"]["value"]
        avg_price = round(aggs["avg_price"]["value"], 2)
        p20 = aggs["percentiles"]["values"]["20.0"]
        p80 = aggs["percentiles"]["values"]["80.0"]

        # Trend
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
        trend_result = es.search(index="price_history", body={
            "query": {
                "bool": {
                    "must": [
                        { "term": { "url": url } },
                        { "range": { "timestamp": { "gte": thirty_days_ago } } }
                    ]
                }
            },
            "aggs": {
                "over_time": {
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

        buckets = trend_result["aggregations"]["over_time"]["buckets"]
        prices = [b["avg_price"]["value"] for b in buckets if b["avg_price"]["value"]]

        trend = "stable"
        if len(prices) >= 2:
            first = sum(prices[:len(prices)//2]) / (len(prices)//2)
            second = sum(prices[len(prices)//2:]) / (len(prices) - len(prices)//2)
            diff = ((second - first) / first) * 100
            if diff <= -5:
                trend = "falling"
            elif diff >= 5:
                trend = "rising"

        # Verdict
        if current_price <= p20 and trend in ["falling", "stable"]:
            verdict = "BUY NOW"
        elif current_price >= p80 or trend == "rising":
            verdict = "WAIT"
        else:
            verdict = "WATCH IT"

        return {
            "status": "success",
            "current_price": current_price,
            "min_price": min_price,
            "max_price": max_price,
            "avg_price": avg_price,
            "trend": trend,
            "verdict": verdict,
            "data_points": count
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

# GEMINI AGENT SETUP

tools = [scrape_current_price, analyze_price_history]

SYSTEM_PROMPT = """
You are Price Stalker, an intelligent shopping agent that helps users 
decide whether to buy a product now or wait for a better price.

When a user gives you an Amazon URL:
1. Call scrape_current_price to get the live price
2. Call analyze_price_history to get the historical analysis
3. Give a clear, friendly verdict: BUY NOW, WAIT, or WATCH IT
4. Always explain WHY with specific numbers
5. If the verdict is WAIT, tell them what price to watch for

Be conversational, helpful, and specific. Use $ amounts and percentages.
Never give a verdict without calling both tools first.
"""

def run_agent():
    print("\n Price Stalker Agent started!")
    print("Paste an Amazon URL and I'll tell you if it's a good deal.\n")

    conversation_history = []

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ["exit", "quit", "bye"]:
            print("Price Stalker: Happy shopping! 👋")
            break

        conversation_history.append(
            types.Content(role="user", parts=[types.Part(text=user_input)])
        )

        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=conversation_history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=tools,
            )
        )

        # Handle tool calls
        while response.candidates[0].content.parts[0].function_call if response.candidates[0].content.parts else False:
            tool_call = response.candidates[0].content.parts[0].function_call
            tool_name = tool_call.name
            tool_args = dict(tool_call.args)

            print(f"\n Agent calling: {tool_name}({tool_args})")

            if tool_name == "scrape_current_price":
                tool_result = scrape_current_price(**tool_args)
            elif tool_name == "analyze_price_history":
                tool_result = analyze_price_history(**tool_args)
            else:
                tool_result = {"error": "Unknown tool"}

            # Add tool result back to conversation
            conversation_history.append(response.candidates[0].content)
            conversation_history.append(
                types.Content(
                    role="user",
                    parts=[types.Part(
                        function_response=types.FunctionResponse(
                            name=tool_name,
                            response=tool_result
                        )
                    )]
                )
            )

            response = client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=conversation_history,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    tools=tools,
                )
            )

        # Final text response
        final_text = response.text
        conversation_history.append(
            types.Content(role="model", parts=[types.Part(text=final_text)])
        )
        print(f"\n Price Stalker: {final_text}\n")


if __name__ == "__main__":
    run_agent()