.PHONY: install test clean run docker-build docker-run docker-compose-up docker-compose-down \
	coverage security-check build-docs serve-docs help backup monitor update-deps

install: ## Instalar dependencias del proyecto
	./scripts/install.sh

test: ## Ejecutar tests
	pytest

coverage: ## Ejecutar tests con reporte de cobertura
	pytest --cov=. --cov-report=html
	@echo "Reporte HTML generado en htmlcov/index.html"

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

docker-compose-up: ## Iniciar todos los servicios con docker-compose
	docker-compose up -d

docker-compose-down: ## Detener todos los servicios de docker-compose
	docker-compose down

backup: ## Ejecutar backup
	./scripts/backup.sh

monitor: ## Iniciar monitoreo
	docker-compose up -d prometheus grafana

update-deps: ## Actualizar dependencias
	pip install -r requirements.txt

build-docs: ## Construir documentación
	cd docs && sphinx-build -b html source build/html

serve-docs: build-docs ## Servir documentación localmente
	cd docs/build/html && python -m http.server 8080

help: ## Mostrar este mensaje de ayuda
	@echo "Comandos disponibles:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
