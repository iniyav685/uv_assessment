from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    ticket_number = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ("id", "ticket", "ticket_number", "message", "is_read", "created_at")
        read_only_fields = fields

    def get_ticket_number(self, obj):
        return obj.ticket.number
