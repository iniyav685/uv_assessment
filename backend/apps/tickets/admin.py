from django.contrib import admin

from .models import Attachment, Ticket, TicketActivity, TicketComment


class ActivityInline(admin.TabularInline):
    model = TicketActivity
    extra = 0
    can_delete = False
    readonly_fields = ("kind", "actor", "from_value", "to_value", "comment", "created_at")

    def has_add_permission(self, request, obj=None):
        return False  # the audit trail is append-only, written by the service layer


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "status", "department", "client_office", "created_at")
    list_filter = ("status", "department", "issue_types")
    list_select_related = ("department", "client_office__client", "client_office__property")
    search_fields = ("title", "description")
    readonly_fields = ("status", "created_at", "updated_at", "closed_at", "closed_by")
    inlines = [ActivityInline]


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    can_delete = False
    fields = ("original_name", "content_type", "size", "status", "created_at")
    readonly_fields = fields


@admin.register(TicketComment)
class TicketCommentAdmin(admin.ModelAdmin):
    list_display = ("ticket", "author", "body_text", "created_at")
    list_select_related = ("ticket", "author")
    readonly_fields = ("ticket", "author", "body_html", "body_text", "created_at")
    inlines = [AttachmentInline]


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "ticket", "content_type", "size", "status", "created_at")
    list_filter = ("status", "content_type")
    readonly_fields = ("storage_key", "uploaded_by", "ticket", "comment", "created_at")
