.PHONY: lint types

lint:
	@python -m flake8 --exclude=.git,venv* scrapy_pyppeteer/*.py tests/*.py

types:
	@mypy --ignore-missing-imports --follow-imports=skip scrapy_pyppeteer/*.py tests/*.py

black:
	@black --check scrapy_pyppeteer tests
