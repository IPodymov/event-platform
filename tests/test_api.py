from unittest import mock

import pytest
from django.db import OperationalError
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_reports_ok(api_client: APIClient) -> None:
    response = api_client.get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_reports_unavailable_database(api_client: APIClient) -> None:
    with mock.patch("config.views.connection.ensure_connection", side_effect=OperationalError):
        response = api_client.get(reverse("health"))

    assert response.status_code == 503


def test_openapi_schema_is_generated(api_client: APIClient) -> None:
    response = api_client.get(reverse("schema"), {"format": "json"})

    assert response.status_code == 200
    assert "/api/health/" in response.json()["paths"]


def test_swagger_ui_is_served(api_client: APIClient) -> None:
    response = api_client.get(reverse("swagger-ui"))

    assert response.status_code == 200
