API Documentation
================

InsightHub provides a RESTful API for social media profile verification and analytics.

Accessing the Documentation
-------------------------

The API documentation is available through Swagger UI at:

- Local Development: http://localhost:8000/api/docs

Available Endpoints
-----------------

Health Check
~~~~~~~~~~

.. code-block:: http

    GET /health

Check the health status of the system.

Social Media Verification
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: http

    GET /check_social
    POST /check_social

Verify and analyze social media profiles.

Analytics
~~~~~~~~

.. code-block:: http

    GET /analytics

View analytics dashboard and metrics.

Monitoring
~~~~~~~~~

.. code-block:: http

    GET /metrics

Access Prometheus metrics for monitoring.

API Versioning
-------------

Currently, the API is in version 1.0.0. All endpoints are unversioned for simplicity.

Authentication
-------------

Currently, the API does not require authentication. Basic authentication is available in the schema for future use.

Error Handling
------------

The API uses standard HTTP status codes:

- 200: Success
- 400: Bad Request
- 404: Not Found
- 500: Internal Server Error

Error responses follow this format:

.. code-block:: json

    {
        "error": "Description of the error",
        "status": "error"
    }

Rate Limiting
-----------

There is currently no rate limiting implemented. Consider using Flask-Limiter for production deployment.
