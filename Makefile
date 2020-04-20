.PHONY: lint types black clean

lint:
	@python -m flake8 --exclude=.git,venv* scrapy_pyppeteer/*.py tests/*.py

types:
	@mypy --ignore-missing-imports --follow-imports=skip scrapy_pyppeteer/*.py tests/*.py

black:
	@black --check scrapy_pyppeteer tests

clean:
	@rm -rf .mypy_cache/ .tox/ build/ dist/ htmlcov/ .coverage coverage.xml
