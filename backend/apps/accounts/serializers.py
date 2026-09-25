from rest_framework import serializers

from .models import User
from .permissions import TICKET_CREATOR_ROLES


class UserSummarySerializer(serializers.ModelSerializer):
    """Compact representation used inside tickets and activity entries."""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "full_name", "title", "role", "display_name", "initials")
        read_only_fields = fields

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class MeSerializer(UserSummarySerializer):
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    department_id = serializers.IntegerField(read_only=True)
    can_create_ticket = serializers.SerializerMethodField()

    class Meta(UserSummarySerializer.Meta):
        fields = (
            *UserSummarySerializer.Meta.fields,
            "username",
            "email",
            "role_label",
            "department_id",
            "can_create_ticket",
        )
        read_only_fields = fields

    def get_can_create_ticket(self, obj):
        return obj.role in TICKET_CREATOR_ROLES
