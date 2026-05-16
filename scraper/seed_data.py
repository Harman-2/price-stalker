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

PRODUCT_URL = "https://www.amazon.com/Barbie-Dreamhouse-3-Story-Playset-Elevator/dp/B0BLJTJ38M?ref_=ast_sto_dp&th=1"
PRODUCT_NAME = "Barbie Dreamhouse, Pool Party Doll House with 75+ Pieces"

price_history = [
    (60, 129.99),
    (57, 129.99),
    (54, 119.99),
    (51, 119.99),
    (48, 109.99),
    (45, 89.99),   # sale dip
    (42, 89.99),
    (39, 99.99),
    (36, 109.99),
    (33, 119.99),
    (30, 129.99),
    (27, 124.99),
    (24, 114.99),
    (21, 94.99),   # another dip
    (18, 94.99),
    (15, 104.99),
    (12, 114.99),
    (9,  119.99),
    (6,  109.99),
    (3,  99.99),
    (0,  89.00),   # today's real scraped price
]

print(f"\nSeeding {len(price_history)} historical data points...\n")

for days_ago, price in price_history:
    timestamp = datetime.now() - timedelta(days=days_ago)
    doc = {
        "product_name": PRODUCT_NAME,
        "url": PRODUCT_URL,
        "price": price,
        "currency": "USD",
        "source": "amazon",
        "timestamp": timestamp.isoformat()
    }
    es.index(index="price_history", document=doc)
    print(f" {timestamp.strftime('%Y-%m-%d')} — ${price}")

print(f"\n Done! 60 days of price history seeded.")