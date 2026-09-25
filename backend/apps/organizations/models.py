"""
Reference data the ticket flow depends on:

    Location (city / area)
      └── Property (a building, managed by a Facility Manager)
            └── ClientOffice (a Client's unit in the property) ── Floor(s)
    Department (one POC, many technicians) ── IssueType(s)
    Facility Managers are Users with a Location (one per location).
"""

import builtins

from django.conf import settings
from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.SlugField(max_length=30, unique=True)
    poc = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="poc_of_departments",
        help_text="Point of contact who receives new tickets for this department.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class IssueType(models.Model):
    name = models.CharField(max_length=120, unique=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="issue_types")
    is_quick = models.BooleanField(default=False, help_text="Shown as a 'Quick Issue' chip.")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Client(models.Model):
    name = models.CharField(max_length=150, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Location(models.Model):
    city = models.CharField(max_length=80)
    area = models.CharField(max_length=80, help_text="Locality within the city, e.g. 'HSR Layout'.")

    class Meta:
        ordering = ["city", "area"]
        constraints = [
            models.UniqueConstraint(fields=["city", "area"], name="unique_location_area_per_city"),
        ]

    def __str__(self):
        return f"{self.city} – {self.area}"


class Property(models.Model):
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="properties")
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=30, unique=True, help_text="Short code, e.g. 'Harness'.")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "properties"

    def __str__(self):
        return self.name


class ClientOffice(models.Model):
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="offices")
    property = models.ForeignKey(Property, on_delete=models.PROTECT, related_name="offices")
    unit = models.CharField(
        max_length=30, help_text="Unit number within the property, e.g. '1317'."
    )

    class Meta:
        ordering = ["client__name", "property__code", "unit"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "unit"], name="unique_office_unit_per_property"
            ),
        ]

    def __str__(self):
        return f"{self.client} — {self.label}"

    # `property` is a field on this model, so the builtin decorator is referenced explicitly.
    @builtins.property
    def label(self) -> str:
        return f"{self.property.code}-{self.unit}"


class Floor(models.Model):
    office = models.ForeignKey(ClientOffice, on_delete=models.CASCADE, related_name="floors")
    level = models.SmallIntegerField()
    label = models.CharField(max_length=20, help_text="Display label, e.g. '2F'.")

    class Meta:
        ordering = ["office", "level"]
        constraints = [
            models.UniqueConstraint(
                fields=["office", "level"], name="unique_floor_level_per_office"
            ),
        ]

    def __str__(self):
        return self.label
