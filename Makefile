.PHONY: install test lint clean run docker-build docker-run docker-compose-up docker-compose-down \
	coverage type-check security-check build-docs serve-docs help

install: ## Instalar dependencias del proyecto
	./install.sh

test: ## Ejecutar tests
	pytest

coverage: ## Ejecutar tests con reporte de cobertura
	pytest --cov=. --cov-report=html
	@echo "Reporte HTML generado en htmlcov/index.html"

lint: ## Verificar estilo de código
	flake8 .
	black --check .
	isort --check-only .

format: ## Formatear código automáticamente
	black .
	isort .

type-check: ## Verificar tipos con mypy
	mypy .

security-check: ## Ejecutar análisis de seguridad
	bandit -r .
	safety check

clean: ## Limpiar archivos temporales y compilados
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
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete

run: ## Ejecutar aplicación en modo desarrollo
	python app.py

docker-build: ## Construir imagen Docker
	docker build -t insighthub .

docker-run: ## Ejecutar contenedor Docker
	docker run -p 8000:8000 insighthub

docker-compose-up: ## Iniciar todos los servicios con Docker Compose
	docker-compose up --build -d

docker-compose-down: ## Detener todos los servicios de Docker Compose
	docker-compose down

build-docs: ## Generar documentación
	sphinx-build -b html docs/source docs/build

serve-docs: ## Servir documentación localmente
	python -m http.server 8080 --directory docs/build

setup-dev: install ## Configurar entorno de desarrollo
	pre-commit install
	pip install -r requirements.txt

migrate: ## Ejecutar migraciones de base de datos (si se implementan en el futuro)
	flask db upgrade

requirements: ## Actualizar requirements.txt
	pip freeze > requirements.txt

backup: ## Ejecutar backup
	./scripts/backup.sh

deploy: ## Desplegar a producción
	git push heroku main

monitor: ## Iniciar monitoreo
	docker-compose up prometheus grafana

update-deps: ## Actualizar dependencias
	pip-compile requirements.in
	pip-sync requirements.txt

help: ## Mostrar esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
