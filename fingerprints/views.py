from django.shortcuts import render
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db.models import Q
from .models import Fingerprint
from .serializers import (FingerprintSerializer, FingerprintSubmitSerializer, 
                         FingerprintApproveSerializer, BatchFingerprintSubmitSerializer)
from users.permissions import IsAdminUser, IsOwnerOrAdmin
from logs.utils import log_action
from .utils import component_matcher

class FingerprintViewSet(viewsets.ModelViewSet):
    """
    指纹管理视图集
    """
    queryset = Fingerprint.objects.all()
    serializer_class = FingerprintSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'submit':
            return FingerprintSubmitSerializer
        elif self.action == 'approve':
            return FingerprintApproveSerializer
        elif self.action == 'batch_submit':
            return BatchFingerprintSubmitSerializer
        return FingerprintSerializer
    
    def get_queryset(self):
        """只有管理员可以查看所有指纹，普通用户只能查看自己提交的指纹"""
        user = self.request.user
        if user.is_authenticated and hasattr(user, 'profile'):
            if user.profile.role == 'admin':
                return Fingerprint.objects.all()
        return Fingerprint.objects.filter(submitter=user)
    
    def create(self, request, *args, **kwargs):
        """只有管理员可以直接创建指纹"""
        if request.user.profile.role == 'admin':
            return super().create(request, *args, **kwargs)
        return Response({"detail": "无权限直接创建指纹，请使用提交接口"}, status=status.HTTP_403_FORBIDDEN)
    
    def update(self, request, *args, **kwargs):
        """只有管理员可以更新指纹"""
        if request.user.profile.role == 'admin':
            return super().update(request, *args, **kwargs)
        return Response({"detail": "无权限更新指纹"}, status=status.HTTP_403_FORBIDDEN)
    
    @action(detail=False, methods=['post'])
    def submit(self, request):
        """
        提交指纹接口（所有用户可用）
        """
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            fingerprint = serializer.save()
            log_action(request.user, "submit_fingerprint", fingerprint.id, "success", 
                      f"提交指纹: {fingerprint.component} - {fingerprint.keyword}")
            return Response({"detail": "指纹提交成功，等待管理员审核"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['put'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """
        审核指纹接口（仅管理员可用）
        """
        fingerprint = self.get_object()
        serializer = self.get_serializer(fingerprint, data=request.data, partial=True)
        
        if serializer.is_valid():
            fingerprint = serializer.save()
            status_str = "通过" if fingerprint.status == "approved" else "拒绝"
            log_action(request.user, "approve_fingerprint", fingerprint.id, "success", 
                      f"审核指纹: {fingerprint.component} - {fingerprint.keyword} ({status_str})")
            
            # 如果指纹被批准，刷新组件匹配器
            if fingerprint.status == "approved":
                component_matcher.load_fingerprints()
            
            return Response({"detail": f"指纹审核{status_str}"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def pending(self, request):
        """
        获取待审核的指纹列表（仅管理员可用）
        """
        pending_fingerprints = Fingerprint.objects.filter(status='pending')
        page = self.paginate_queryset(pending_fingerprints)
        if page is not None:
            serializer = FingerprintSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = FingerprintSerializer(pending_fingerprints, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def approved(self, request):
        """
        获取已通过审核的指纹列表（所有用户可用）
        """
        approved_fingerprints = Fingerprint.objects.filter(status='approved')
        page = self.paginate_queryset(approved_fingerprints)
        if page is not None:
            serializer = FingerprintSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = FingerprintSerializer(approved_fingerprints, many=True)
        return Response(serializer.data)
        
    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        指纹数据查询接口
        支持关键词、组件名称和状态筛选
        """
        keyword = request.query_params.get('keyword', None)
        component = request.query_params.get('component', None)
        status_filter = request.query_params.get('status', None)
        
        queryset = self.get_queryset()
        
        # 关键词搜索
        if keyword:
            queryset = queryset.filter(keyword__icontains=keyword)
            
        # 组件名称搜索
        if component:
            queryset = queryset.filter(component__icontains=component)
            
        # 状态筛选
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = FingerprintSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = FingerprintSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def batch_submit(self, request):
        """
        批量提交指纹接口
        """
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            
            # 记录日志
            log_action(request.user, "submit_fingerprint", None, 
                      "success",
                      f"批量提交指纹: 成功 {result['successful']}, 跳过 {result['skipped']}")
            
            message = f"成功添加 {result['successful']} 条指纹数据"
            if result['skipped'] > 0:
                message += f", 跳过 {result['skipped']} 条已存在的指纹"
            
            return Response({
                "success": True,
                "message": message,
                "results": {
                    "total": result['total'],
                    "successful": result['successful'],
                    "skipped": result['skipped']
                }
            }, status=status.HTTP_200_OK)
        
        return Response({
            "detail": "请求格式错误",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
