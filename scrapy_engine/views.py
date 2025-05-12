from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, action
from django.shortcuts import get_object_or_404
from tasks.models import CrawlerTask
from results.models import CrawlerLink, CrawlerResult, StaticResource, IdentifiedComponent
from tasks.task_runner import task_runner
from tasks.serializers import CrawlerTaskSerializer
from users.permissions import IsOwnerOrAdmin
from django.db.models import Count, Q
from fingerprints.utils import component_matcher
from fingerprints.models import Fingerprint
import redis
import os
from urllib.parse import urlparse
from rest_framework.views import APIView

class ScrapyViewSet(viewsets.ViewSet):
    """
    爬虫引擎操作视图集
    提供与Scrapy爬虫引擎交互的API接口
    """
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    
    def _get_redis_client(self):
        """获取Redis客户端连接"""
        redis_host = os.environ.get('REDIS_HOST', 'scrapyredis-redis.ns-6k0uv9r0.svc')
        redis_port = int(os.environ.get('REDIS_PORT', 6379))
        redis_username = os.environ.get('REDIS_USERNAME', 'default')
        redis_password = os.environ.get('REDIS_PASSWORD', '7sxxq74x')
        return redis.Redis(
            host=redis_host, 
            port=redis_port, 
            db=0,
            username=redis_username,
            password=redis_password,
            socket_timeout=5
        )
    
    @action(detail=True, methods=['post'])
    def start_crawl(self, request, pk=None):
        """
        启动爬虫任务
        
        URL: /api/scrapy/{task_id}/start_crawl/
        """
        task = get_object_or_404(CrawlerTask, id=pk)
        
        # 检查任务状态
        if task.status not in ['queued', 'failed']:
            return Response({
                "success": False,
                "message": f"任务不能启动，当前状态: {task.get_status_display()}"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 启动任务
        success = task_runner.run_task(task.id)
        
        if success:
            return Response({
                "success": True,
                "message": "爬虫任务已成功启动",
                "task": CrawlerTaskSerializer(task).data
            })
        else:
            return Response({
                "success": False,
                "message": "启动爬虫任务失败"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def stop_crawl(self, request, pk=None):
        """
        停止爬虫任务
        
        URL: /api/scrapy/{task_id}/stop_crawl/
        """
        task = get_object_or_404(CrawlerTask, id=pk)
        
        # 检查任务状态
        if task.status in ['completed', 'failed']:
            return Response({
                "success": False,
                "message": f"任务已经处于终止状态: {task.get_status_display()}"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 获取Redis连接
        redis_client = self._get_redis_client()
        
        # 清空任务相关的所有Redis队列
        if task.redis_key_prefix:
            keys = redis_client.keys(f"{task.redis_key_prefix}*")
            if keys:
                redis_client.delete(*keys)
        
        # 更新任务状态
        task.status = 'failed'
        task.save()
        
        return Response({
            "success": True,
            "message": "爬虫任务已停止",
            "task": CrawlerTaskSerializer(task).data
        })
    
    @action(detail=True, methods=['post'])
    def restart_crawl(self, request, pk=None):
        """
        重启爬虫任务
        
        URL: /api/scrapy/{task_id}/restart_crawl/
        """
        task = get_object_or_404(CrawlerTask, id=pk)
        
        # 清空任务相关的所有数据
        CrawlerLink.objects.filter(task=task).delete()
        CrawlerResult.objects.filter(task=task).delete()
        StaticResource.objects.filter(task=task).delete()
        IdentifiedComponent.objects.filter(task=task).delete()
        
        # 重置任务状态和计数
        task.status = 'queued'
        task.links_found = 0
        task.links_crawled = 0
        task.resources_found = 0
        task.resources_crawled = 0
        task.components_identified = 0
        task.started_at = None
        task.ended_at = None
        task.save()
        
        # 启动任务
        success = task_runner.run_task(task.id)
        
        if success:
            return Response({
                "success": True,
                "message": "爬虫任务已成功重启",
                "task": CrawlerTaskSerializer(task).data
            })
        else:
            return Response({
                "success": False,
                "message": "重启爬虫任务失败"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """
        获取爬虫任务状态
        
        URL: /api/scrapy/{task_id}/status/
        """
        task = get_object_or_404(CrawlerTask, id=pk)
        
        # 获取统计信息
        stats = {
            "links_total": task.links_found,
            "links_crawled": task.links_crawled,
            "resources_total": task.resources_found,
            "resources_crawled": task.resources_crawled,
            "components_identified": task.components_identified,
            "progress": task.get_progress(),
        }
        
        return Response({
            "task_id": task.id,
            "url": task.url,
            "status": task.status,
            "status_display": task.get_status_display(),
            "mode": task.mode,
            "mode_display": task.get_mode_display(),
            "started_at": task.started_at,
            "ended_at": task.ended_at,
            "stats": stats
        })
    
    @action(detail=True, methods=['get'])
    def components(self, request, pk=None):
        """
        获取爬虫任务识别出的组件
        
        URL: /api/scrapy/{task_id}/components/
        参数:
        - page: 页码
        - page_size: 每页数量
        """
        task = get_object_or_404(CrawlerTask, id=pk)
        
        # 获取组件，按组件名称分组计数
        components = IdentifiedComponent.objects.filter(task=task)\
            .values('component')\
            .annotate(count=Count('id'))\
            .order_by('-count')
            
        # 检索特定组件的匹配详情
        component_filter = request.query_params.get('component')
        if component_filter:
            details = IdentifiedComponent.objects.filter(
                task=task, 
                component=component_filter
            ).values('match_type', 'keyword').annotate(count=Count('id'))
            
            # 获取匹配到的URL
            urls = []
            for item in IdentifiedComponent.objects.filter(task=task, component=component_filter):
                url = None
                if item.result:
                    url = item.result.url
                elif item.resource:
                    url = item.resource.url
                
                if url and url not in urls:
                    urls.append(url)
            
            return Response({
                "component": component_filter,
                "total_matches": IdentifiedComponent.objects.filter(
                    task=task, 
                    component=component_filter
                ).count(),
                "match_details": details,
                "urls": urls
            })
        
        return Response({
            "task_id": task.id,
            "components": components,
            "total": components.count()
        })
        
    @action(detail=True, methods=['get'])
    def queue_stats(self, request, pk=None):
        """
        获取爬虫队列状态
        
        URL: /api/scrapy/{task_id}/queue_stats/
        """
        task = get_object_or_404(CrawlerTask, id=pk)
        
        # 如果没有Redis键前缀，返回空结果
        if not task.redis_key_prefix:
            return Response({
                "success": False,
                "message": "任务没有Redis键前缀"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 获取Redis连接
        redis_client = self._get_redis_client()
        
        # 获取所有相关的Redis键
        keys = redis_client.keys(f"{task.redis_key_prefix}*")
        
        # 统计各队列长度
        queues = {}
        for key in keys:
            key_str = key.decode('utf-8')
            queue_len = redis_client.llen(key)
            queues[key_str] = queue_len
        
        return Response({
            "task_id": task.id,
            "queues": queues,
            "total_keys": len(keys)
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        获取爬虫系统整体统计信息
        
        URL: /api/scrapy/stats/
        """
        # 检查权限
        if not request.user.is_staff and not hasattr(request.user, 'profile') or request.user.profile.role != 'admin':
            return Response({"detail": "您没有权限查看此信息"}, status=status.HTTP_403_FORBIDDEN)
        
        # 获取统计信息
        tasks_count = CrawlerTask.objects.count()
        active_tasks = CrawlerTask.objects.filter(
            ~Q(status__in=['completed', 'failed', 'queued'])
        ).count()
        completed_tasks = CrawlerTask.objects.filter(status='completed').count()
        failed_tasks = CrawlerTask.objects.filter(status='failed').count()
        
        links_count = CrawlerLink.objects.count()
        pages_count = CrawlerResult.objects.count()
        resources_count = StaticResource.objects.count()
        components_count = IdentifiedComponent.objects.count()
        
        # 获取Redis连接
        redis_host = os.environ.get('REDIS_HOST', 'scrapyredis-redis.ns-6k0uv9r0.svc')
        redis_port = int(os.environ.get('REDIS_PORT', 6379))
        redis_username = os.environ.get('REDIS_USERNAME', 'default')
        redis_password = os.environ.get('REDIS_PASSWORD', '7sxxq74x')
        
        redis_status = "未连接"
        redis_keys = 0
        try:
            redis_client = self._get_redis_client()
            if redis_client.ping():
                redis_status = "已连接"
                redis_keys = len(redis_client.keys("*"))
        except Exception as e:
            redis_status = f"连接失败: {str(e)}"
        
        return Response({
            "tasks": {
                "total": tasks_count,
                "active": active_tasks,
                "completed": completed_tasks,
                "failed": failed_tasks,
            },
            "data": {
                "links": links_count,
                "pages": pages_count,
                "resources": resources_count,
                "components": components_count,
            },
            "redis": {
                "status": redis_status,
                "host": redis_host,
                "port": redis_port,
                "username": redis_username,
                "keys": redis_keys
            }
        })
        
    @action(detail=True, methods=['post'])
    def run_fingerprint_matching(self, request, pk=None):
        """
        手动运行指纹匹配
        
        URL: /api/scrapy/{task_id}/run_fingerprint_matching/
        """
        task = get_object_or_404(CrawlerTask, id=pk)
        
        # 检查任务状态
        if task.status not in ['resource_crawling', 'content_crawling', 'fingerprint_matching', 'completed', 'failed']:
            return Response({
                "success": False,
                "message": f"任务不能进行指纹匹配，当前状态: {task.get_status_display()}"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 启动指纹匹配
        success = task_runner.start_fingerprint_matching(task.id)
        
        if success:
            return Response({
                "success": True,
                "message": "指纹匹配过程已启动",
                "task": CrawlerTaskSerializer(task).data
            })
        else:
            return Response({
                "success": False,
                "message": "启动指纹匹配失败"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def match_content(self, request):
        """
        对提供的内容进行组件指纹匹配
        
        URL: /api/scrapy/match_content/
        参数:
        - content: 需要匹配的内容
        - reload_fingerprints: 是否重新加载指纹库 (默认false)
        """
        content = request.data.get('content', '')
        reload_fingerprints = request.data.get('reload_fingerprints', False)
        
        if not content:
            return Response({
                "success": False,
                "message": "请提供需要匹配的内容"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 获取已通过审核的指纹数量
        approved_fingerprints_count = Fingerprint.objects.filter(status='approved').count()
        
        if approved_fingerprints_count == 0:
            return Response({
                "success": False,
                "message": "指纹库中没有已通过审核的指纹"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 重新加载指纹库
        if reload_fingerprints:
            component_matcher.load_fingerprints()
        
        # 进行匹配
        matches = component_matcher.match(content)
        
        # 返回匹配结果
        return Response({
            "success": True,
            "content_length": len(content),
            "content_preview": content[:100] + ('...' if len(content) > 100 else ''),
            "fingerprints_count": approved_fingerprints_count,
            "matches": [{"component": comp, "keyword": kw} for comp, kw in matches],
            "matches_count": len(matches)
        })
    
    @action(detail=False, methods=['get'])
    def fingerprint_stats(self, request):
        """
        获取指纹库统计信息
        
        URL: /api/scrapy/fingerprint_stats/
        """
        # 获取指纹统计
        total_fingerprints = Fingerprint.objects.count()
        approved_fingerprints = Fingerprint.objects.filter(status='approved').count()
        pending_fingerprints = Fingerprint.objects.filter(status='pending').count()
        rejected_fingerprints = Fingerprint.objects.filter(status='rejected').count()
        
        # 获取匹配算法信息
        ac_stats = {
            "is_loaded": component_matcher.loaded,
            "fingerprints_loaded": len(component_matcher.fingerprints) if hasattr(component_matcher, 'fingerprints') else 0,
            "simple_fingerprints": len(component_matcher.simple_fingerprints) if hasattr(component_matcher, 'simple_fingerprints') else 0,
            "use_simple_matching": component_matcher.use_simple_matching if hasattr(component_matcher, 'use_simple_matching') else False
        }
        
        return Response({
            "total": total_fingerprints,
            "approved": approved_fingerprints,
            "pending": pending_fingerprints,
            "rejected": rejected_fingerprints,
            "matcher": ac_stats
        })
    
    @action(detail=True, methods=['get'])
    def links(self, request, pk=None):
        """
        获取爬虫任务的所有链接
        
        URL: /api/scrapy/{task_id}/links/
        参数:
        - page: 页码
        - page_size: 每页数量
        - is_internal: 筛选内部链接(true)或外部链接(false)，可选
        """
        task = get_object_or_404(CrawlerTask, id=pk)
        
        # 过滤条件
        is_internal = request.query_params.get('is_internal')
        
        # 构建查询
        links_query = CrawlerLink.objects.filter(task=task)
        
        # 应用过滤条件
        if is_internal is not None:
            is_internal = is_internal.lower() == 'true'
            if is_internal:
                links_query = links_query.filter(url__contains=urlparse(task.url).netloc)
            else:
                links_query = links_query.exclude(url__contains=urlparse(task.url).netloc)
        
        # 获取总数
        total_count = links_query.count()
        
        # 分页
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        start = (page - 1) * page_size
        end = start + page_size
        
        # 获取链接列表
        links = links_query.order_by('id')[start:end]
        
        # 构建结果
        links_data = []
        for link in links:
            # 检查是否有对应的爬取结果
            has_result = CrawlerResult.objects.filter(task=task, url=link.url).exists()
            
            # 检查是否有识别出组件
            component_count = IdentifiedComponent.objects.filter(
                task=task, 
                result__url=link.url
            ).count()
            
            links_data.append({
                "id": link.id,
                "url": link.url,
                "is_internal": urlparse(link.url).netloc == urlparse(task.url).netloc,
                "has_content": has_result,
                "component_count": component_count
            })
        
        return Response({
            "task_id": task.id,
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "links": links_data
        })
    
    @action(detail=True, methods=['get'])
    def link_detail(self, request, pk=None):
        """
        获取特定链接的详细信息，包括响应头和识别的组件
        
        URL: /api/scrapy/{task_id}/link_detail/
        参数:
        - url: 链接URL(必填)
        """
        task = get_object_or_404(CrawlerTask, id=pk)
        url = request.query_params.get('url')
        
        if not url:
            return Response({
                "success": False,
                "message": "请提供url参数"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 获取链接和爬取结果
        link = get_object_or_404(CrawlerLink, task=task, url=url)
        
        try:
            # 获取爬取结果
            result = CrawlerResult.objects.get(task=task, url=url)
            
            # 获取该页面上识别的组件
            components = IdentifiedComponent.objects.filter(
                task=task, 
                result=result
            ).values('component', 'keyword', 'match_type')
            
            # 获取静态资源
            static_resources = StaticResource.objects.filter(result=result).values('url', 'resource_type')
            
            # 获取响应头
            headers = result.headers or {}
            
            # 获取状态码
            status_code = None
            if headers and 'Status' in headers:
                status_parts = headers['Status'][0].split(' ', 1)
                if len(status_parts) > 0:
                    try:
                        status_code = int(status_parts[0])
                    except ValueError:
                        pass
            
            return Response({
                "task_id": task.id,
                "url": url,
                "title": result.title,
                "status_code": status_code,
                "headers": headers,
                "static_resources": static_resources,
                "components": components,
                "components_count": components.count()
            })
            
        except CrawlerResult.DoesNotExist:
            # 如果没有爬取结果，只返回链接信息
            return Response({
                "task_id": task.id,
                "url": url,
                "error": "该链接未爬取内容或爬取失败"
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['get'])
    def task_summary(self, request, pk=None):
        """
        获取爬虫任务的摘要信息，包括链接数、已爬取内容数、识别组件数等
        
        URL: /api/scrapy/{task_id}/task_summary/
        """
        task = get_object_or_404(CrawlerTask, id=pk)
        
        # 获取统计信息
        total_links = CrawlerLink.objects.filter(task=task).count()
        internal_links = CrawlerLink.objects.filter(
            task=task, 
            url__contains=urlparse(task.url).netloc
        ).count()
        external_links = total_links - internal_links
        
        crawled_content = CrawlerResult.objects.filter(task=task).count()
        components = IdentifiedComponent.objects.filter(task=task)
        components_count = components.count()
        
        # 获取识别出的组件类型及数量
        component_types = components.values('component').annotate(
            count=Count('component')
        ).order_by('-count')
        
        return Response({
            "task_id": task.id,
            "url": task.url,
            "mode": task.mode,
            "mode_display": task.get_mode_display(),
            "status": task.status,
            "status_display": task.get_status_display(),
            "started_at": task.started_at,
            "ended_at": task.ended_at,
            "links": {
                "total": total_links,
                "internal": internal_links,
                "external": external_links
            },
            "crawled_content": crawled_content,
            "components": {
                "total": components_count,
                "types": component_types[:10]  # 返回前10种组件
            },
            "progress": task.get_progress()
        })

class CrawlerTaskCreateAPIView(APIView):
    """
    创建爬虫任务API
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, format=None):
        """
        创建爬虫任务
        
        参数:
        - url: 要爬取的URL
        - mode: 爬取模式，simple(简单模式)或deep(完整模式)
        
        简单模式：只爬取指定URL的页面内容
        完整模式：进行深度爬取，跟随网站内链接进行爬取
        """
        # 获取参数
        url = request.data.get('url')
        mode = request.data.get('mode', 'simple')
        
        # 验证参数
        if not url:
            return Response(
                {'error': '缺少参数: url'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if mode not in ['simple', 'deep']:
            return Response(
                {'error': '无效的爬取模式，请使用simple(简单模式)或deep(完整模式)'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 创建任务
        task = CrawlerTask.objects.create(
            url=url,
            mode=mode,
            user=request.user,
            status='pending'
        )
        
        # 启动任务
        task_runner.run_task(task.id)
        
        return Response(
            {
                'task_id': task.id,
                'url': task.url,
                'mode': task.mode,
                'status': task.status,
                'created_at': task.created_at
            }, 
            status=status.HTTP_201_CREATED
        ) 