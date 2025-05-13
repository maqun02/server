import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from tasks.models import CrawlerTask
from logs.utils import log_action
import redis
import os

class Command(BaseCommand):
    help = '终止运行超过指定时间的爬虫任务'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='终止运行超过多少小时的任务(默认24小时)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='只显示将被终止的任务，但不实际执行终止操作'
        )

    def handle(self, *args, **options):
        hours = options['hours']
        dry_run = options['dry_run']
        
        # 计算时间阈值
        time_threshold = timezone.now() - datetime.timedelta(hours=hours)
        
        # 获取运行时间过长的任务
        running_statuses = ['link_crawling', 'content_crawling', 'resource_crawling', 'fingerprint_matching']
        hanging_tasks = CrawlerTask.objects.filter(
            status__in=running_statuses,
            started_at__lt=time_threshold
        )
        
        if not hanging_tasks.exists():
            self.stdout.write(self.style.SUCCESS(f'没有运行超过{hours}小时的任务'))
            return
        
        # 输出将被终止的任务
        self.stdout.write(self.style.WARNING(f'发现{hanging_tasks.count()}个运行超过{hours}小时的任务:'))
        for task in hanging_tasks:
            runtime = timezone.now() - task.started_at
            self.stdout.write(f'任务ID: {task.id}, URL: {task.url}, 状态: {task.get_status_display()}, 运行时间: {runtime}')
        
        # 如果是演习模式，到此结束
        if dry_run:
            self.stdout.write(self.style.WARNING('演习模式，不实际终止任务'))
            return
        
        # 连接Redis，清理相关队列
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
            
            # 终止每个任务
            for task in hanging_tasks:
                # 1. 更新任务状态为timeout
                old_status = task.status
                task.status = 'timeout'
                task.ended_at = timezone.now()
                task.save()
                
                # 2. 清理Redis中的相关队列
                task_prefix = f'task:{task.id}:'
                for key in r.keys(f'{task_prefix}*'):
                    r.delete(key)
                    self.stdout.write(f'已删除Redis键: {key.decode()}')
                
                # 3. 记录操作日志
                log_action(
                    task.user, 
                    "task_timeout", 
                    task.id, 
                    "info",
                    f"任务因运行超时而终止: {task.url} (状态从 {old_status} 更改为 timeout)"
                )
                
                self.stdout.write(self.style.SUCCESS(f'已终止任务 {task.id}: {task.url}'))
                
            self.stdout.write(self.style.SUCCESS(f'成功终止了 {hanging_tasks.count()} 个运行时间过长的任务'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'终止任务时出错: {str(e)}')) 