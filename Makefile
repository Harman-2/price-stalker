install:
	python3 -m pip install -r requirements.txt

run-scraper:
	python3 scraper/scraper.py

run-analyzer:
	python3 scraper/analyzer.py

run-api:
	python3 agent/api.py

test:
	pytest -q
