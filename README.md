# Price Stalker

Price Stalker is a lightweight price monitoring project that scrapes Amazon product pages, stores historical prices in Elasticsearch, analyzes price trends, and presents a simple buy/wait recommendation through a small web UI.

## What it does

- Scrapes Amazon product pages for current price and product name
- Stores price snapshots in Elasticsearch for trend analysis
- Analyzes historical pricing to determine whether a product is currently a good buy
- Exposes the analysis through a local API and a basic frontend

## Project structure

- [scraper/scraper.py](scraper/scraper.py) — scrapes a product URL and saves the data to Elasticsearch
- [scraper/analyzer.py](scraper/analyzer.py) — analyzes stored price history and returns a verdict such as BUY NOW, WAIT, or WATCH IT
- [agent/api.py](agent/api.py) — local HTTP API for analysis requests
- [ui/index.html](ui/index.html) — simple web interface for interacting with the app
- [scraper/requirements.txt](scraper/requirements.txt) and [agent/requirements.txt](agent/requirements.txt) — Python dependencies

## Prerequisites

- Python 3.9+
- Elasticsearch instance running and reachable
- Internet access for scraping Amazon pages

## Environment setup

Create a .env file in the project root with your Elasticsearch credentials:

```env
ELASTIC_ENDPOINT=https://your-elasticsearch-host:9200
ELASTIC_USERNAME=your-username
ELASTIC_PASSWORD=your-password
```

## Installation

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the required dependencies:

```bash
pip install -r scraper/requirements.txt
pip install -r agent/requirements.txt
```

## Running the scraper

Run the scraper manually and paste an Amazon product URL when prompted:

```bash
python scraper/scraper.py
```

This will scrape the product page, extract the price, and save it to Elasticsearch.

## Running the analyzer

Analyze a product by running:

```bash
python scraper/analyzer.py
```

You will be prompted to enter an Amazon product URL, and the script will print a summary of the current price, historical stats, and buying recommendation.

## Running the API

Start the API server:

```bash
python agent/api.py
```

The API will be available at:

- http://localhost:8000/analyze
- http://localhost:8000/chat

## Running the frontend

The frontend is a static HTML file. You can open [ui/index.html](ui/index.html) directly in your browser, or serve the folder with a simple static server:

```bash
cd ui
python3 -m http.server 8080
```

Then open http://localhost:8080 in your browser.

## Notes

- Amazon pages can change frequently, so the scraper selectors may need updates over time.
- The app assumes an Elasticsearch index named price_history exists or can be created automatically by indexing into it.
- This project is intended as a demo or personal tracker rather than a production-grade scraping system.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
