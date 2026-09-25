"""
Who a new ticket goes to:
  * Department POC    — the POC of the issue's department (Department.poc).
  * Facility Manager  — the FM of the location the client office is in. A partial
                        unique constraint on User guarantees at most one active FM
                        per location.
"""

from apps.accounts.models import Role, User
from apps.organizations.models import Department


def poc_for(department: Department) -> User | None:
    poc = department.poc
    return poc if poc and poc.is_active else None


def facility_manager_for(location_id: int) -> User | None:
    return User.objects.filter(
        role=Role.FACILITY_MANAGER, location_id=location_id, is_active=True
    ).first()
