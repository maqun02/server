from django.shortcuts import render
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from .models import CrawlerTask
from .serializers import CrawlerTaskSerializer, CrawlerTaskCreateSerializer
from users.permissions import IsOwnerOrAdmin
from logs.utils import log_action
from .task_runner import task_runner
import threading
from fingerprints.utils import component_matcher
from fingerprints.models import Fingerprint

class CrawlerTaskViewSet(viewsets.ModelViewSet):
    """
    爬虫任务管理视图集
    """
    queryset = CrawlerTask.objects.all()
    serializer_class = CrawlerTaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CrawlerTaskCreateSerializer
        return CrawlerTaskSerializer
    
    def get_queryset(self):
        """只有管理员可以查看所有任务，普通用户只能查看自己的任务"""
        user = self.request.user
        if user.is_authenticated and hasattr(user, 'profile'):
            if user.profile.role == 'admin':
                return CrawlerTask.objects.all()
        return CrawlerTask.objects.filter(user=user)
    
    def create(self, request, *args, **kwargs):
        """创建爬虫任务"""
        # 验证URL
        url = request.data.get('url')
        if not url:
            return Response({'error': '缺少URL参数'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 验证模式
        mode = request.data.get('mode', 'simple')
        if mode not in ['simple', 'deep']:
            return Response({'error': '无效的爬取模式，请使用simple(简单模式)或deep(完整模式)'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # 创建任务并返回序列化结果
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # 启动爬虫任务
        from tasks.task_runner import task_runner
        task_runner.run_task(serializer.instance.id)
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def perform_create(self, serializer):
        """创建任务时设置用户"""
        task = serializer.save(user=self.request.user)
        
        # 记录任务创建信息，包括爬取模式说明
        mode_desc = "简单模式(仅爬取指定URL)" if task.mode == 'simple' else "完整模式(深度爬取内链)"
        log_action(self.request.user, "create_task", task.id, "success", 
                  f"创建爬虫任务: {task.url} ({mode_desc})")
        
        # 在后台线程中运行爬虫任务
        thread = threading.Thread(target=task_runner.run_task, args=(task.id,))
        thread.daemon = True
        thread.start()
    
    @action(detail=True, methods=['post'])
    def restart(self, request, pk=None):
        """
        重新启动任务
        """
        task = self.get_object()
        
        # 只有已完成或失败的任务才能重启
        if task.status not in ['completed', 'failed']:
            return Response({"detail": "只有已完成或失败的任务才能重启"}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        # 重置任务状态
        task.status = 'queued'
        task.started_at = None
        task.ended_at = None
        task.save()
        
        log_action(request.user, "task_status_change", task.id, "success", 
                  f"重启任务: {task.url}")
        
        # 在后台线程中运行爬虫任务
        thread = threading.Thread(target=task_runner.run_task, args=(task.id,))
        thread.daemon = True
        thread.start()
        
        return Response({"detail": "任务已重新启动"}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """
        获取任务状态
        """
        task = self.get_object()
        return Response({
            "id": task.id,
            "status": task.status,
            "status_display": task.get_status_display(),
            "started_at": task.started_at,
            "ended_at": task.ended_at
        })
        
    @action(detail=False, methods=['post'])
    def test_fingerprint_matching(self, request):
        """
        测试指纹匹配功能
        
        POST参数：
        - html_content: 要进行匹配测试的HTML内容
        - reload_fingerprints: 是否重新加载指纹库（默认True）
        """
        html_content = request.data.get('html_content', '')
        reload_fingerprints = request.data.get('reload_fingerprints', True)
        
        if not html_content:
            return Response({
                "error": "请提供html_content参数"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 获取所有已通过审核的指纹
        approved_fingerprints = Fingerprint.objects.filter(status='approved')
        
        # 如果没有已通过的指纹，返回错误
        if not approved_fingerprints.exists():
            return Response({
                "error": "指纹库中没有已通过审核的指纹",
                "suggestion": "请先添加指纹并设置状态为approved"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # 输出指纹库信息
        fingerprint_info = []
        for fp in approved_fingerprints:
            processed = component_matcher._preprocess_text(fp.keyword)
            fingerprint_info.append({
                "id": fp.id,
                "component": fp.component,
                "keyword": fp.keyword,
                "processed_keyword": processed,
                "status": fp.status
            })
        
        # 重新加载指纹库（确保使用最新的指纹）
        if reload_fingerprints:
            component_matcher.load_fingerprints()
            
        # 获取前100个字符的样本
        sample = html_content[:100] + ("..." if len(html_content) > 100 else "")
        
        # 进行指纹匹配
        matches = component_matcher.match(html_content)
        
        # 记录测试结果
        log_action(request.user, "task_debug", None, "info", 
                  f"指纹匹配测试: 内容样本「{sample}」, 匹配结果: {matches}")
        
        # 返回结果
        return Response({
            "fingerprint_count": approved_fingerprints.count(),
            "fingerprints": fingerprint_info,
            "content_sample": sample,
            "content_length": len(html_content),
            "processed_content_sample": component_matcher._preprocess_text(html_content)[:100],
            "matches": [{"component": comp, "keyword": kw} for comp, kw in matches],
            "match_count": len(matches)
        })

    @action(detail=False, methods=['post'])
    def simple_match_test(self, request):
        """
        直接测试简单字符串匹配（不使用复杂算法）
        
        POST参数：
        - content: 要测试的内容
        - keywords: 要搜索的关键词列表
        """
        content = request.data.get('content', '')
        keywords = request.data.get('keywords', [])
        
        if not content:
            return Response({"error": "请提供content参数"}, status=status.HTTP_400_BAD_REQUEST)
            
        if not keywords:
            return Response({"error": "请提供keywords参数"}, status=status.HTTP_400_BAD_REQUEST)
        
        # 处理内容
        processed_content = component_matcher._preprocess_text(content)
        
        # 直接进行简单字符串匹配测试
        results = []
        for keyword in keywords:
            processed_keyword = component_matcher._preprocess_text(keyword)
            found = processed_keyword in processed_content
            position = processed_content.find(processed_keyword) if found else -1
            
            # 如果找到匹配，提取上下文
            context = ""
            if found:
                start_pos = max(0, position - 10)
                end_pos = min(len(processed_content), position + len(processed_keyword) + 10)
                context = processed_content[start_pos:end_pos]
            
            results.append({
                "keyword": keyword,
                "processed_keyword": processed_keyword,
                "found": found,
                "position": position,
                "context": context
            })
        
        # 返回结果
        return Response({
            "content_length": len(content),
            "processed_content_length": len(processed_content),
            "processed_content_sample": processed_content[:100] + ("..." if len(processed_content) > 100 else ""),
            "results": results
        })