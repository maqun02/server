from rest_framework import serializers
from .models import Fingerprint
from django.contrib.auth.models import User

class UserSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']

class FingerprintSerializer(serializers.ModelSerializer):
    submitter = UserSimpleSerializer(read_only=True)
    admin = UserSimpleSerializer(read_only=True)
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Fingerprint
        fields = ['id', 'keyword', 'component', 'status', 'status_display', 'submitter', 'admin', 'created_at', 'updated_at']
        read_only_fields = ['id', 'status', 'submitter', 'admin', 'created_at', 'updated_at']
    
    def get_status_display(self, obj):
        return obj.get_status_display()

class FingerprintSubmitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fingerprint
        fields = ['keyword', 'component']
    
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        
        fingerprint = Fingerprint.objects.create(
            submitter=user,
            **validated_data
        )
        
        return fingerprint

class FingerprintApproveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fingerprint
        fields = ['status']
        
    def validate_status(self, value):
        if value not in ['approved', 'rejected']:
            raise serializers.ValidationError("状态只能是'approved'或'rejected'")
        return value
    
    def update(self, instance, validated_data):
        request = self.context.get('request')
        admin = request.user if request else None
        
        instance.status = validated_data.get('status', instance.status)
        instance.admin = admin
        instance.save()
        
        return instance

class BatchFingerprintSubmitSerializer(serializers.Serializer):
    fingerprints = FingerprintSubmitSerializer(many=True)
    
    def create(self, validated_data):
        fingerprints_data = validated_data.get('fingerprints', [])
        request = self.context.get('request')
        user = request.user if request else None
        
        result = {
            'total': len(fingerprints_data),
            'successful': 0,
            'failed': 0,
            'failed_items': []
        }
        
        for fingerprint_data in fingerprints_data:
            try:
                Fingerprint.objects.create(
                    submitter=user,
                    **fingerprint_data
                )
                result['successful'] += 1
            except Exception as e:
                result['failed'] += 1
                result['failed_items'].append({
                    **fingerprint_data,
                    'error': str(e)
                })
                
        return result 