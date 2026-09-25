from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models import Q


class Role(models.TextChoices):
    CLIENT_POC = "client_poc", "Client POC"
    FACILITY_MANAGER = "facility_manager", "Facility Manager"
    DEPARTMENT_POC = "department_poc", "Department POC"
    TECHNICIAN = "technician", "Technician"
    ADMIN = "admin", "Admin"


class AppUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom user so roles and org mappings live on the user row.

    - Client POC        -> belongs to one ClientOffice (its location comes from the property)
    - Facility Manager  -> belongs to one Location. A new ticket is auto-linked to the
                           FM of the office's location (the "concerned" FM).
    - Department POC /
      Technician        -> belong to one Department. A new ticket is auto-assigned to
                           the POC of the issue's department (Department.poc).
    """

    Role = Role

    email = models.EmailField(unique=True)
    # No default: every user must be given a role explicitly (enforced by the check constraint).
    role = models.CharField(max_length=20, choices=Role.choices)
    title = models.CharField(
        max_length=80,
        blank=True,
        help_text="Designation shown next to the name, e.g. 'IT Manager'.",
    )
    department = models.ForeignKey(
        "organizations.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="members",
    )
    location = models.ForeignKey(
        "organizations.Location",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="staff",
    )
    client_office = models.ForeignKey(
        "organizations.ClientOffice",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="client_users",
    )

    objects = AppUserManager()

    class Meta:
        ordering = ["first_name", "last_name", "username"]
        constraints = [
            models.CheckConstraint(
                condition=Q(role__in=Role.values), name="accounts_user_role_valid"
            ),
            models.CheckConstraint(
                condition=~Q(role=Role.CLIENT_POC) | Q(client_office__isnull=False),
                name="accounts_client_poc_has_office",
            ),
            models.CheckConstraint(
                condition=~Q(role__in=[Role.DEPARTMENT_POC, Role.TECHNICIAN])
                | Q(department__isnull=False),
                name="accounts_dept_staff_has_department",
            ),
            models.CheckConstraint(
                condition=~Q(role=Role.FACILITY_MANAGER) | Q(location__isnull=False),
                name="accounts_fm_has_location",
            ),
            # Auto-linking needs an unambiguous Facility Manager per location.
            models.UniqueConstraint(
                fields=["location"],
                condition=Q(role=Role.FACILITY_MANAGER, is_active=True),
                name="accounts_one_active_fm_per_location",
            ),
        ]

    @property
    def display_name(self) -> str:
        name = self.get_full_name() or self.username
        role_label = self.get_role_display()
        if self.department_id:
            return f"{name} ({role_label}, {self.department.name})"
        return f"{name} ({self.title or role_label})"

    @property
    def initials(self) -> str:
        parts = [p for p in (self.first_name, self.last_name) if p]
        return "".join(p[0] for p in parts).upper() or self.username[:2].upper()

    @property
    def is_internal(self) -> bool:
        return self.role != Role.CLIENT_POC

    def __str__(self):
        return self.get_full_name() or self.username
