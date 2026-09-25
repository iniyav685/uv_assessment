from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role, User
from apps.accounts.serializers import UserSummarySerializer
from apps.organizations.models import Client, Department, IssueType

from .models import TicketStatus
from .serializers import creatable_offices


class LookupsView(APIView):
    """
    Reference data for forms and filters in one request, so the frontend can
    cache it once per session instead of making a call per dropdown.
    """

    def get(self, request):
        user: User = request.user

        if user.role == Role.CLIENT_POC:
            clients = Client.objects.filter(pk=user.client_office.client_id)
        else:
            clients = Client.objects.all()

        offices = [
            {
                "id": o.id,
                "label": o.label,
                "client": {"id": o.client_id, "name": o.client.name},
                "floors": [{"id": f.id, "label": f.label} for f in o.floors.all()],
            }
            for o in creatable_offices(user)
        ]

        technicians = []
        # Facility Managers see every department's technicians (not just one), since they
        # may need to reassign a blocked ticket in whichever department it currently sits in.
        if user.role in (Role.DEPARTMENT_POC, Role.FACILITY_MANAGER, Role.ADMIN):
            qs = User.objects.select_related("department").filter(
                role=Role.TECHNICIAN, is_active=True
            )
            if user.role == Role.DEPARTMENT_POC:
                qs = qs.filter(department_id=user.department_id)
            technicians = [
                {
                    **UserSummarySerializer(t).data,
                    "department_id": t.department_id,
                }
                for t in qs
            ]

        facility_managers = User.objects.select_related("department").filter(
            role=Role.FACILITY_MANAGER, is_active=True
        )

        department_pocs = []
        if user.role in (Role.FACILITY_MANAGER, Role.ADMIN):
            pocs = User.objects.select_related("department").filter(
                role=Role.DEPARTMENT_POC, is_active=True
            )
            department_pocs = [
                {**UserSummarySerializer(p).data, "department_id": p.department_id} for p in pocs
            ]

        return Response(
            {
                "statuses": [{"value": v, "label": label} for v, label in TicketStatus.choices],
                "departments": list(Department.objects.values("id", "name")),
                "clients": list(clients.values("id", "name")),
                "facility_managers": UserSummarySerializer(facility_managers, many=True).data,
                "issue_types": list(
                    IssueType.objects.values("id", "name", "department_id", "is_quick")
                ),
                "offices": offices,
                "technicians": technicians,
                "department_pocs": department_pocs,
            }
        )
