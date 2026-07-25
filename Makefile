.PHONY: install dev test lint clean build publish publish-test

install:
	pip install -e .
	playwright install chromium

dev:
	pip install -e ".[dev]"
	playwright install chromium

test:
	pytest

clean:
	rm -rf dist/ build/ *.egg-info src/*.egg-info

build: clean
	pip install --upgrade build
	python -m build

publish: build
	pip install --upgrade twine
	twine upload dist/*

publish-test: build
	pip install --upgrade twine
	twine upload --repository testpypi dist/*
