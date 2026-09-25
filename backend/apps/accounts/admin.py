from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User

ORG_FIELDS = ("role", "title", "department", "location", "client_office")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "department",
        "is_active",
    )
    list_filter = ("role", "department", "location", "is_active")
    list_select_related = ("department",)
    fieldsets = BaseUserAdmin.fieldsets + (("Organisation", {"fields": ORG_FIELDS}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Organisation", {"fields": ("email", *ORG_FIELDS)}),
    )
