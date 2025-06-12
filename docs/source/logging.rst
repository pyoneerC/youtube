Sistema de Logging
================

InsightHub utiliza Loguru para proporcionar un sistema de logging avanzado y fácil de usar.

Configuración
------------

El sistema de logging está configurado con múltiples handlers:

1. **Console Handler**:
   * Salida formateada y coloreada
   * Nivel: INFO
   * Incluye timestamp, nivel, función y mensaje

2. **File Handler (app.log)**:
   * Todos los logs
   * Nivel: DEBUG
   * Rotación automática (100 MB)
   * Retención: 1 semana

3. **Error Handler (error.log)**:
   * Solo errores
   * Nivel: ERROR
   * Rotación automática
   * Backtrace incluido

4. **Critical Handler (critical.log)**:
   * Errores críticos
   * Nivel: CRITICAL
   * Diagnóstico completo
   * Backtrace detallado

Uso del Logger
-------------

Logging Básico
~~~~~~~~~~~~

.. code-block:: python

    from config.logger import logger

    # Diferentes niveles de logging
    logger.debug("Mensaje de debug")
    logger.info("Mensaje informativo")
    logger.warning("Advertencia")
    logger.error("Error")
    logger.critical("Error crítico")

Timing de Operaciones
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from config.logger import log_time

    with log_time("Mi Operación"):
        # Código a medir
        time.sleep(1)
        # Se registrará automáticamente el tiempo de ejecución

Manejo de Excepciones
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from config.logger import log_exceptions

    @log_exceptions
    def operacion_riesgosa():
        # Si ocurre una excepción, será registrada automáticamente
        raise ValueError("Algo salió mal")

Estructura de Logs
----------------

Los logs se guardan en el directorio ``logs/`` con la siguiente estructura::

    logs/
    ├── app.log      # Todos los logs
    ├── error.log    # Solo errores
    └── critical.log # Errores críticos

Formato de Log
------------

Cada entrada de log incluye::

    * Timestamp
    * Nivel de log
    * Nombre del módulo
    * Función
    * Número de línea
    * Mensaje

Ejemplo::

    2025-06-12 18:53:31 | INFO     | app:health_check:42 | Health check completed successfully

Rotación y Retención
------------------

* Los archivos de log rotan automáticamente al alcanzar 100 MB
* Se mantienen los logs de la última semana
* Los logs antiguos se comprimen automáticamente
