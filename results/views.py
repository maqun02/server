from django.shortcuts import render
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from .models import CrawlerResult, IdentifiedComponent
from tasks.models import CrawlerTask
from .serializers import CrawlerResultSerializer, FullResultSerializer, ReportSerializer
from users.permissions import IsOwnerOrAdmin
from collections import defaultdict

class ResultViewSet(viewsets.ReadOnlyModelViewSet):
    """
    爬虫结果视图集（只读）
    """
    queryset = CrawlerResult.objects.all()
    serializer_class = CrawlerResultSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return FullResultSerializer
        return CrawlerResultSerializer
    
    def get_queryset(self):
        """只有管理员可以查看所有结果，普通用户只能查看自己任务的结果"""
        user = self.request.user
        if user.is_authenticated and hasattr(user, 'profile'):
            if user.profile.role == 'admin':
                return CrawlerResult.objects.all()
        return CrawlerResult.objects.filter(task__user=user)
    
    @action(detail=False, methods=['get'])
    def by_task(self, request):
        """
        获取指定任务的所有结果
        """
        task_id = request.query_params.get('task_id')
        if not task_id:
            return Response({"detail": "请提供task_id参数"}, status=status.HTTP_400_BAD_REQUEST)
        
        # 检查用户是否有权限查看该任务的结果
        task = get_object_or_404(CrawlerTask, id=task_id)
        if not IsOwnerOrAdmin().has_object_permission(request, self, task):
            return Response({"detail": "没有权限查看该任务的结果"}, status=status.HTTP_403_FORBIDDEN)
        
        results = CrawlerResult.objects.filter(task_id=task_id)
        page = self.paginate_queryset(results)
        if page is not None:
            serializer = CrawlerResultSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = CrawlerResultSerializer(results, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def report(self, request):
        """
        获取任务报告
        """
        task_id = request.query_params.get('task_id')
        if not task_id:
            return Response({"detail": "请提供task_id参数"}, status=status.HTTP_400_BAD_REQUEST)
        
        # 检查用户是否有权限查看该任务的结果
        task = get_object_or_404(CrawlerTask, id=task_id)
        if not IsOwnerOrAdmin().has_object_permission(request, self, task):
            return Response({"detail": "没有权限查看该任务的报告"}, status=status.HTTP_403_FORBIDDEN)
        
        # 获取任务的所有结果和识别的组件
        results = CrawlerResult.objects.filter(task_id=task_id)
        components = IdentifiedComponent.objects.filter(task_id=task_id)
        
        # 构建报告数据
        pages = []
        for result in results:
            page_data = {
                "url": result.url,
                "resources": result.resources,
                "components": [comp.component for comp in result.components.all()]
            }
            pages.append(page_data)
        
        # 统计组件分布
        component_stats = defaultdict(list)
        for comp in components:
            component_stats[comp.component].append(comp.result.url)
        
        # 构建报告
        report_data = {
            "task_id": int(task_id),
            "url": task.url,
            "pages": pages,
            "components": dict(component_stats)
        }
        
        serializer = ReportSerializer(report_data)
        return Response(serializer.data)
