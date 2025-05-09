from rest_framework import serializers
from .models import SystemLog
from users.serializers import UserSimpleSerializer

class SystemLogSerializer(serializers.ModelSerializer):
    user = UserSimpleSerializer(read_only=True)
    action_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = SystemLog
        fields = ['id', 'user', 'action', 'action_display', 'target_id', 'status', 
                  'status_display', 'message', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_action_display(self, obj):
        return obj.get_action_display()
    
    def get_status_display(self, obj):
        return obj.get_status_display() 