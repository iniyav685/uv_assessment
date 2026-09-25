from django.contrib import admin

from .models import Client, ClientOffice, Department, Floor, IssueType, Location, Property


class FloorInline(admin.TabularInline):
    model = Floor
    extra = 0


@admin.register(ClientOffice)
class ClientOfficeAdmin(admin.ModelAdmin):
    list_display = ("client", "property", "unit")
    list_select_related = ("client", "property")
    inlines = [FloorInline]


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "poc")
    list_select_related = ("poc",)


@admin.register(IssueType)
class IssueTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "is_quick")
    list_filter = ("department", "is_quick")


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("city", "area")


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "location")
    list_filter = ("location",)
    list_select_related = ("location",)


admin.site.register(Client)
