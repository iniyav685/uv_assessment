from django.conf import settings
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User
from .serializers import MeSerializer

# Highlighted on the login page, one per role, in walkthrough order.
DEMO_USERNAMES = [
    "client.acme",
    "fm.chandan",
    "fm.neha",
    "poc.technical",
    "tech.prakash",
    "client.globex",
    "admin",
]


class LoginView(TokenObtainPairView):
    """POST {username, password} -> {access, refresh}. Rate limited."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class DemoAccountsView(APIView):
    """Seeded accounts for one-click login on the demo login page (DEMO_MODE only)."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        if not settings.DEMO_MODE:
            return Response({"enabled": False, "accounts": []})
        users = User.objects.select_related("department").filter(username__in=DEMO_USERNAMES)
        order = {u: i for i, u in enumerate(DEMO_USERNAMES)}
        accounts = sorted(
            (
                {
                    "username": u.username,
                    "display_name": u.display_name,
                    "role": u.role,
                    "role_label": u.get_role_display(),
                }
                for u in users
            ),
            key=lambda a: order[a["username"]],
        )
        return Response({"enabled": True, "password": settings.DEMO_PASSWORD, "accounts": accounts})


class MeView(RetrieveAPIView):
    serializer_class = MeSerializer

    def get_object(self):
        return self.request.user
