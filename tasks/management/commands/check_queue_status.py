import redis
import os
import json
from django.core.management.base import BaseCommand
from django.utils import timezone
from tasks.models import CrawlerTask
from results.models import CrawlerLink, CrawlerResult, StaticResource, IdentifiedComponent

class Command(BaseCommand):
    help = '检查Redis队列状态和任务处理机制'

    def handle(self, *args, **options):
        # 连接Redis
        redis_host = os.environ.get('REDIS_HOST', 'scrapyredis-redis.ns-6k0uv9r0.svc')
        redis_port = os.environ.get('REDIS_PORT', '6379')
        redis_username = os.environ.get('REDIS_USERNAME', 'default')
        redis_password = os.environ.get('REDIS_PASSWORD', '7sxxq74x')
        
        try:
            r = redis.Redis(
                host=redis_host,
                port=int(redis_port),
                username=redis_username,
                password=redis_password
            )
            
            self.stdout.write(self.style.SUCCESS(f'已连接到Redis: {redis_host}:{redis_port}'))
            
            # 检查所有Redis键
            keys = r.keys('*')
            self.stdout.write(f'Redis中共有 {len(keys)} 个键')
            
            # 分类统计键
            key_counts = {
                'start_urls': 0,
                'requests': 0,
                'items': 0,
                'dupefilter': 0,
                'other': 0
            }
            
            for key in keys:
                key_str = key.decode()
                if ':start_urls' in key_str:
                    key_counts['start_urls'] += 1
                elif ':requests' in key_str:
                    key_counts['requests'] += 1
                elif ':items' in key_str:
                    key_counts['items'] += 1
                elif ':dupefilter' in key_str:
                    key_counts['dupefilter'] += 1
                else:
                    key_counts['other'] += 1
            
            self.stdout.write('Redis键分类统计:')
            for category, count in key_counts.items():
                self.stdout.write(f'  - {category}: {count}个')
            
            # 检查任务队列
            for key in r.keys('*:requests'):
                key_str = key.decode()
                queue_length = r.llen(key)
                self.stdout.write(f'队列 {key_str}: {queue_length}个待处理请求')
            
            # 检查数据库中的任务状态
            self.stdout.write('\n数据库任务状态统计:')
            task_stats = {}
            for status, display in CrawlerTask.STATUS_CHOICES:
                count = CrawlerTask.objects.filter(status=status).count()
                task_stats[display] = count
                
            for status, count in task_stats.items():
                self.stdout.write(f'  - {status}: {count}个任务')
            
            # 检查活跃任务
            active_tasks = CrawlerTask.objects.filter(
                status__in=['link_crawling', 'content_crawling', 'resource_crawling', 'fingerprint_matching']
            ).order_by('-started_at')
            
            if active_tasks.exists():
                self.stdout.write('\n活跃任务详情:')
                for task in active_tasks[:5]:  # 只显示前5个任务
                    runtime = timezone.now() - task.started_at if task.started_at else timezone.timedelta(0)
                    self.stdout.write(f'  - 任务ID: {task.id}, URL: {task.url}, 状态: {task.get_status_display()}, 运行时间: {runtime}')
                    
                    # 检查任务进度
                    self.stdout.write(f'    进度: {task.get_progress()}%')
                    self.stdout.write(f'    链接: 发现={task.links_found}, 已爬取={task.links_crawled}')
                    self.stdout.write(f'    资源: 发现={task.resources_found}, 已爬取={task.resources_crawled}')
                    
                    # 检查Redis中的队列
                    task_keys = list(filter(lambda k: f'task:{task.id}:' in k.decode(), keys))
                    if task_keys:
                        self.stdout.write(f'    Redis键: {len(task_keys)}个')
                        for k in task_keys:
                            k_str = k.decode()
                            if r.type(k) == b'list':
                                self.stdout.write(f'      - {k_str}: {r.llen(k)}个元素')
                            else:
                                self.stdout.write(f'      - {k_str}: {r.type(k).decode()}类型')
                    
                    # 检查数据库记录
                    links = CrawlerLink.objects.filter(task=task).count()
                    results = CrawlerResult.objects.filter(task=task).count()
                    resources = StaticResource.objects.filter(task=task).count()
                    components = IdentifiedComponent.objects.filter(task=task).count()
                    
                    self.stdout.write(f'    数据库记录: 链接={links}, 结果={results}, 资源={resources}, 组件={components}\n')
            
            # 提供健康状态评估
            self.stdout.write('\n系统健康状态评估:')
            
            # 检查僵尸任务
            zombie_tasks = CrawlerTask.objects.filter(
                status__in=['link_crawling', 'content_crawling', 'resource_crawling'],
                started_at__lt=timezone.now() - timezone.timedelta(hours=1)
            )
            
            if zombie_tasks.exists():
                self.stdout.write(self.style.WARNING(f'警告: 发现{zombie_tasks.count()}个运行超过1小时的任务，可能存在处理延迟'))
            else:
                self.stdout.write(self.style.SUCCESS('任务处理正常: 没有发现长时间运行的任务'))
                
            # 检查Redis队列积压
            large_queues = []
            for key in r.keys('*:requests'):
                if r.llen(key) > 100:
                    large_queues.append((key.decode(), r.llen(key)))
                    
            if large_queues:
                self.stdout.write(self.style.WARNING(f'警告: 发现{len(large_queues)}个队列中的请求数量过多:'))
                for queue, size in large_queues:
                    self.stdout.write(f'  - {queue}: {size}个请求')
            else:
                self.stdout.write(self.style.SUCCESS('队列处理正常: 没有过度积压的请求队列'))
                
            # 检查整体完成率
            total_tasks = CrawlerTask.objects.count()
            completed_tasks = CrawlerTask.objects.filter(status='completed').count()
            failed_tasks = CrawlerTask.objects.filter(status__in=['failed', 'timeout']).count()
            
            if total_tasks > 0:
                completion_rate = (completed_tasks / total_tasks) * 100
                failure_rate = (failed_tasks / total_tasks) * 100
                
                self.stdout.write(f'任务完成率: {completion_rate:.2f}%')
                self.stdout.write(f'任务失败率: {failure_rate:.2f}%')
                
                if completion_rate < 50:
                    self.stdout.write(self.style.WARNING('警告: 任务完成率较低，可能存在系统问题'))
                elif failure_rate > 20:
                    self.stdout.write(self.style.WARNING('警告: 任务失败率较高，建议检查爬虫错误日志'))
                else:
                    self.stdout.write(self.style.SUCCESS('任务处理正常: 完成率和失败率在合理范围内'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'检查队列状态时出错: {str(e)}')) 