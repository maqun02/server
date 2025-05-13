from rest_framework import serializers
from .models import CrawlerResult, IdentifiedComponent, StaticResource
from tasks.serializers import CrawlerTaskSerializer

class IdentifiedComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = IdentifiedComponent
        fields = ['id', 'component', 'keyword', 'created_at']

class StaticResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaticResource
        fields = ['id', 'url', 'resource_type', 'md5_hash', 'is_matched', 'created_at']

class CrawlerResultSerializer(serializers.ModelSerializer):
    components = IdentifiedComponentSerializer(many=True, read_only=True)
    resources = StaticResourceSerializer(source='resource_items', many=True, read_only=True)
    
    class Meta:
        model = CrawlerResult
        fields = ['id', 'url', 'title', 'headers', 'resources', 'components', 'created_at']
        read_only_fields = ['id', 'created_at']

class FullResultSerializer(serializers.ModelSerializer):
    task = CrawlerTaskSerializer(read_only=True)
    components = IdentifiedComponentSerializer(many=True, read_only=True)
    resources = StaticResourceSerializer(source='resource_items', many=True, read_only=True)
    
    class Meta:
        model = CrawlerResult
        fields = ['id', 'task', 'url', 'title', 'headers', 'resources', 'components', 'created_at']
        read_only_fields = ['id', 'task', 'created_at']

class ReportSerializer(serializers.Serializer):
    task_id = serializers.IntegerField()
    url = serializers.URLField()
    pages = serializers.ListField(child=serializers.JSONField())
    components = serializers.DictField(child=serializers.ListField()) 