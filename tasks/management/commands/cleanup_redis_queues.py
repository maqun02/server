import redis
import os
import re
from django.core.management.base import BaseCommand
from tasks.models import CrawlerTask

class Command(BaseCommand):
    help = '清理Redis中的过期队列和无关键数据'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='只显示将被清理的键，但不实际删除'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
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
            
            # 获取所有Redis键
            keys = r.keys('*')
            self.stdout.write(f'Redis中共有 {len(keys)} 个键')
            
            # 获取所有活跃任务的ID
            active_task_ids = set(CrawlerTask.objects.filter(
                status__in=['queued', 'link_crawling', 'content_crawling', 'resource_crawling', 'fingerprint_matching']
            ).values_list('id', flat=True))
            
            # 匹配任务ID的正则表达式
            task_id_pattern = re.compile(r'task:(\d+):')
            
            # 按类别分类键
            to_delete = []
            orphaned_task_keys = []
            active_task_keys = []
            spider_keys = []
            other_keys = []
            
            for key in keys:
                key_str = key.decode()
                
                # 检查是否为任务相关的键
                match = task_id_pattern.search(key_str)
                if match:
                    task_id = int(match.group(1))
                    
                    if task_id in active_task_ids:
                        active_task_keys.append((key, task_id))
                    else:
                        orphaned_task_keys.append((key, task_id))
                        to_delete.append(key)
                # 检查是否为爬虫相关的键
                elif ':items' in key_str or ':dupefilter' in key_str:
                    spider_keys.append(key)
                    # 这些键可以保留，因为它们可能是全局爬虫队列
                else:
                    other_keys.append(key)
                    # 对于不属于任何类别的键，暂时保留
            
            # 输出统计信息
            self.stdout.write(f'活跃任务键: {len(active_task_keys)}个')
            self.stdout.write(f'孤立任务键: {len(orphaned_task_keys)}个')
            self.stdout.write(f'爬虫队列键: {len(spider_keys)}个')
            self.stdout.write(f'其他键: {len(other_keys)}个')
            
            # 显示将被删除的键
            self.stdout.write(f'\n将删除 {len(to_delete)} 个键:')
            
            task_ids = {}
            for key, task_id in orphaned_task_keys:
                if task_id not in task_ids:
                    task_ids[task_id] = []
                task_ids[task_id].append(key.decode())
            
            for task_id, keys in task_ids.items():
                self.stdout.write(f'任务ID {task_id} 相关的键 ({len(keys)}个):')
                for key in keys[:5]:  # 只显示前5个
                    self.stdout.write(f'  - {key}')
                if len(keys) > 5:
                    self.stdout.write(f'  ... 以及其他 {len(keys) - 5} 个键')
            
            # 如果是演习模式，到此结束
            if dry_run:
                self.stdout.write(self.style.WARNING('演习模式，不实际删除键'))
                return
            
            # 实际删除键
            if to_delete:
                for key in to_delete:
                    r.delete(key)
                    
                self.stdout.write(self.style.SUCCESS(f'已删除 {len(to_delete)} 个键'))
            else:
                self.stdout.write('没有需要删除的键')
            
            # 压缩Redis数据库
            self.stdout.write('正在压缩Redis数据库...')
            try:
                r.bgrewriteaof()
                self.stdout.write(self.style.SUCCESS('已启动后台AOF重写过程'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'压缩数据库时出错: {str(e)}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'清理Redis队列时出错: {str(e)}')) 