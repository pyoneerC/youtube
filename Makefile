.PHONY: install test lint clean run docker-build docker-run

install:
	./install.sh

test:
	pytest

lint:
	flake8 .
	black --check .

format:
	black .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.pyc" -exec rm -rf {} +
	find . -type d -name "*.pyo" -exec rm -rf {} +
	find . -type d -name "*.pyd" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} +
	find . -type d -name "build" -exec rm -rf {} +

run:
	python app.py

docker-build:
	docker build -t insighthub .

docker-run:
	docker run -p 8000:8000 insighthub

setup-dev: install
	pre-commit install
	pip install -r requirements.txt
