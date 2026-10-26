from django.db import connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Liveness probe for load balancers and container health checks."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(
        responses={
            200: inline_serializer("Health", {"status": serializers.CharField()}),
            503: inline_serializer("HealthFailure", {"status": serializers.CharField()}),
        }
    )
    def get(self, request: Request) -> Response:
        try:
            connection.ensure_connection()
        except Exception:
            return Response(
                {"status": "db_unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        return Response({"status": "ok"})
