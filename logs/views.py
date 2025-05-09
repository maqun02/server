from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import SystemLog
from .serializers import SystemLogSerializer
from users.permissions import IsAdminUser
from django.db.models import Q
from datetime import datetime

# Create your views here.

class SystemLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    系统日志视图集（只读）
    """
    queryset = SystemLog.objects.all()
    serializer_class = SystemLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """只有管理员可以查看所有日志，普通用户只能查看自己的日志"""
        user = self.request.user
        if user.is_authenticated and hasattr(user, 'profile'):
            if user.profile.role == 'admin':
                return SystemLog.objects.all()
        return SystemLog.objects.filter(Q(user=user) | Q(user=None))
        
    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        系统日志搜索接口
        支持用户ID、操作类型、状态、日期范围和消息内容筛选
        """
        queryset = self.get_queryset()
        
        # 用户ID过滤
        user_id = request.query_params.get('user_id', None)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
            
        # 操作类型过滤
        action = request.query_params.get('action', None)
        if action:
            queryset = queryset.filter(action=action)
            
        # 状态过滤
        status_filter = request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        # 日期范围过滤
        start_date = request.query_params.get('start_date', None)
        if start_date:
            try:
                start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                queryset = queryset.filter(created_at__gte=start_datetime)
            except ValueError:
                return Response({"detail": "开始日期格式错误，正确格式为YYYY-MM-DD"}, 
                               status=status.HTTP_400_BAD_REQUEST)
                
        end_date = request.query_params.get('end_date', None)
        if end_date:
            try:
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
                # 设置为当天结束时间23:59:59
                end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
                queryset = queryset.filter(created_at__lte=end_datetime)
            except ValueError:
                return Response({"detail": "结束日期格式错误，正确格式为YYYY-MM-DD"}, 
                               status=status.HTTP_400_BAD_REQUEST)
                
        # 消息内容模糊搜索
        message = request.query_params.get('message', None)
        if message:
            queryset = queryset.filter(message__icontains=message)
            
        # 分页返回结果
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = SystemLogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = SystemLogSerializer(queryset, many=True)
        return Response(serializer.data)
