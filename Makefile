.PHONY: install test clean run docker-build docker-run docker-compose-up docker-compose-down \
	coverage security-check build-docs serve-docs help backup monitor update-deps api-docs validate-api \
	check-ports kill-port ensure-deps clean-ports

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

clean-ports: ## Limpiar puertos usados por la aplicación
	@echo "Limpiando puertos..."
	@for port in 8000 8001 8002 8003; do \
		pid=$$(lsof -ti :$$port 2>/dev/null); \
		if [ ! -z "$$pid" ]; then \
			echo "Liberando puerto $$port (PID: $$pid)..."; \
			kill -9 $$pid 2>/dev/null || true; \
			sleep 1; \
		fi; \
	done
	@echo "Puertos limpiados"

ensure-deps: ## Asegurar que todas las dependencias están instaladas
	@command -v gunicorn >/dev/null 2>&1 || { \
		echo "Instalando gunicorn y otras dependencias..."; \
		pip install -r requirements.txt; \
	}

run: clean-ports ensure-deps ## Ejecutar aplicación en modo desarrollo
	@echo "Iniciando aplicación..."
	@if ! gunicorn app:app \
		--bind 0.0.0.0:8000 \
		--worker-class gthread \
		--threads 4 \
		--workers 4 \
		--log-level info \
		--access-logfile - \
		--error-logfile - \
		--capture-output; then \
		echo "Error al iniciar la aplicación. Intentando limpiar puertos nuevamente..."; \
		make clean-ports; \
		gunicorn app:app \
			--bind 0.0.0.0:8000 \
			--worker-class gthread \
			--threads 4 \
			--workers 4 \
			--log-level info \
			--access-logfile - \
			--error-logfile - \
			--capture-output; \
	fi

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
	./scripts/serve_docs.sh

api-docs: ## Ver documentación de la API
	@echo "API documentation available at http://localhost:8000/api/docs"
	@echo "Make sure the application is running with 'make run'"

validate-api: ## Validar especificación OpenAPI
	yamllint static/swagger/openapi.yaml

check-ports: ## Verificar puertos en uso
	@echo "Verificando puerto 8000..."
	@lsof -i :8000 || echo "Puerto 8000 disponible"
	@echo "Verificando puerto 8001 (Prometheus)..."
	@lsof -i :8001 || echo "Puerto 8001 disponible"

kill-port: ## Matar proceso en puerto específico (usar como: make kill-port PORT=8001)
	@if [ "$(PORT)" = "" ]; then \
		echo "Especifica un puerto: make kill-port PORT=8001"; \
		exit 1; \
	fi
	@echo "Intentando liberar puerto $(PORT)..."
	@lsof -ti :$(PORT) | xargs kill -9 2>/dev/null || echo "Puerto $(PORT) ya está libre"

help: ## Mostrar este mensaje de ayuda
	@echo "Comandos disponibles:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
