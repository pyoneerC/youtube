Sistema de Monitoreo
===================

InsightHub incluye un sistema completo de monitoreo basado en Prometheus y Grafana.

Componentes
----------

1. **Health Check**
2. **Prometheus Metrics**
3. **Grafana Dashboard**

Health Check
-----------

Endpoint: ``/health``

Verifica:
* Conexión a la base de datos
* Conexión a Redis
* APIs externas
* Estado general del sistema

Ejemplo de respuesta::

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

Prometheus Metrics
----------------

Métricas Disponibles
~~~~~~~~~~~~~~~~~~

1. **Request Count**::

    app_requests_total{method="GET", endpoint="/health", http_status="200"}

2. **Request Latency**::

    app_request_latency_seconds{endpoint="/health"}

Acceso a Prometheus
~~~~~~~~~~~~~~~~~

* URL: http://localhost:9090
* Endpoints importantes:
  * ``/metrics``: Métricas raw
  * ``/targets``: Estado de los targets
  * ``/graph``: Interface de consultas

Grafana
-------

Acceso
~~~~~~

* URL: http://localhost:3000
* Credenciales por defecto:
  * Usuario: admin
  * Contraseña: admin

Dashboards Incluidos
~~~~~~~~~~~~~~~~~

1. **Application Overview**:
   * Request rate
   * Error rate
   * Latencia promedio
   * Códigos de estado

2. **System Metrics**:
   * Uso de CPU
   * Uso de memoria
   * Disco
   * Red

Configuración de Alertas
----------------------

Alertas Predefinidas:

1. **High Error Rate**:
   * Condición: >5% de errores en 5 minutos
   * Severidad: High

2. **High Latency**:
   * Condición: P95 >500ms en 5 minutos
   * Severidad: Warning

3. **Service Down**:
   * Condición: No respuesta en 1 minuto
   * Severidad: Critical

Mantenimiento
------------

Backup de Dashboards
~~~~~~~~~~~~~~~~~

.. code-block:: bash

    make backup-dashboards

Actualización de Configuración
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    make update-monitoring
