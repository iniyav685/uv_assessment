from rest_framework.permissions import BasePermission

from .models import Role

# Roles that may raise tickets (technicians only act on tickets assigned to them).
TICKET_CREATOR_ROLES = {Role.CLIENT_POC, Role.FACILITY_MANAGER, Role.DEPARTMENT_POC, Role.ADMIN}


class CanCreateTicket(BasePermission):
    message = "Your role is not allowed to create tickets."

    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.role in TICKET_CREATOR_ROLES)
