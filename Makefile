.PHONY: lint types

lint:
	@python -m flake8 --exclude=.git,venv* *.py

types:
	@mypy --ignore-missing-imports --follow-imports=skip *.py
