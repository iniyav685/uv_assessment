from django.urls import path
from rest_framework.routers import DefaultRouter

from .lookups import LookupsView
from .views import TicketViewSet

router = DefaultRouter()
router.register("tickets", TicketViewSet, basename="ticket")

urlpatterns = [
    path("lookups/", LookupsView.as_view(), name="lookups"),
    *router.urls,
]
