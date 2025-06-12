Guía de InsightHub
==================

InsightHub es una aplicación web que permite verificar y analizar perfiles de redes sociales, con capacidades avanzadas de monitoreo y logging.

.. toctree::
   :maxdepth: 2
   :caption: Contenido:

   instalacion
   monitoreo
   logging
   api
   desarrollo

Características Principales
-------------------------

* Sistema de logging avanzado con Loguru
* Métricas con Prometheus
* Monitoreo de salud del sistema
* Containerización con Docker
* CI/CD con GitHub Actions
* Backups automatizados
* Pre-commit hooks para calidad de código

Logging y Monitoreo
------------------

InsightHub incluye un sistema completo de logging y monitoreo:

* **Loguru**: Logging avanzado con rotación de archivos y formateo personalizado
* **Prometheus**: Métricas de rendimiento y uso
* **Grafana**: Visualización de métricas
* **Health Checks**: Endpoints de verificación de salud

Ejemplo de Uso de Logging
------------------------

.. code-block:: python

    from config.logger import log_time, log_exceptions

    @log_exceptions
    def mi_funcion():
        with log_time("Operación"):
            # Tu código aquí
            pass

Monitoreo del Sistema
-------------------

* **Health Check**: Disponible en ``/health``
* **Métricas Prometheus**: Puerto 8001
* **Dashboard Grafana**: Puerto 3000

API y Endpoints
-------------

Health Check
~~~~~~~~~~

.. code-block:: http

    GET /health

Respuesta::

    {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": "2025-06-12T18:53:31+00:00",
        "checks": {
            "database": true,
            "redis": true,
            "external_apis": true
        }
    }

Contribución
-----------

1. Fork del repositorio
2. Crear rama de feature
3. Realizar cambios
4. Ejecutar pruebas
5. Enviar pull request

Índices y tablas
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
