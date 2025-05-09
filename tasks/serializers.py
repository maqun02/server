from rest_framework import serializers
from .models import CrawlerTask
from users.serializers import UserSimpleSerializer

class CrawlerTaskSerializer(serializers.ModelSerializer):
    user = UserSimpleSerializer(read_only=True)
    status_display = serializers.SerializerMethodField()
    mode_display = serializers.SerializerMethodField()
    
    class Meta:
        model = CrawlerTask
        fields = ['id', 'url', 'mode', 'mode_display', 'status', 'status_display', 'user', 
                 'started_at', 'ended_at', 'depth', 'created_at']
        read_only_fields = ['id', 'status', 'user', 'started_at', 'ended_at', 'created_at']
    
    def get_status_display(self, obj):
        return obj.get_status_display()
    
    def get_mode_display(self, obj):
        return obj.get_mode_display()

class CrawlerTaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CrawlerTask
        fields = ['url', 'mode', 'depth']
        
    def validate_depth(self, value):
        if value < 1:
            raise serializers.ValidationError("爬取深度必须大于等于1")
        elif value > 5:
            raise serializers.ValidationError("为保护服务器资源，爬取深度不能超过5")
        return value
    
    def create(self, validated_data):
        # 不在这里设置user，而是在视图的perform_create方法中设置
        task = CrawlerTask.objects.create(**validated_data)
        return task 