from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from tasks.models import CrawlerTask
from logs.utils import log_action
import threading

class Command(BaseCommand):
    help = '创建一个新的爬虫任务'

    def add_arguments(self, parser):
        parser.add_argument('url', type=str, help='要爬取的URL')
        parser.add_argument(
            '--mode',
            choices=['simple', 'deep'],
            default='simple',
            help='爬取模式: simple(简单模式)或deep(完整模式)'
        )
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='创建任务的用户名，默认为admin'
        )
        parser.add_argument(
            '--task-timeout',
            type=int,
            default=1800,
            help='任务超时时间(秒)，默认30分钟'
        )
        parser.add_argument(
            '--link-timeout',
            type=int,
            default=30,
            help='链接超时时间(秒)，默认30秒'
        )
        parser.add_argument(
            '--resource-timeout',
            type=int,
            default=15,
            help='资源超时时间(秒)，默认15秒'
        )

    def handle(self, *args, **options):
        url = options['url']
        mode = options['mode']
        username = options['username']
        task_timeout = options['task_timeout']
        link_timeout = options['link_timeout']
        resource_timeout = options['resource_timeout']
        
        try:
            # 获取用户
            user = User.objects.get(username=username)
            
            # 创建任务
            task = CrawlerTask.objects.create(
                url=url,
                mode=mode,
                user=user,
                task_timeout=task_timeout,
                link_timeout=link_timeout,
                resource_timeout=resource_timeout
            )
            
            self.stdout.write(self.style.SUCCESS(f'成功创建任务 (ID: {task.id}):'))
            self.stdout.write(f'URL: {task.url}')
            self.stdout.write(f'模式: {task.get_mode_display()}')
            self.stdout.write(f'状态: {task.get_status_display()}')
            self.stdout.write(f'创建用户: {user.username}')
            self.stdout.write(f'超时设置: 任务={task_timeout}秒, 链接={link_timeout}秒, 资源={resource_timeout}秒')
            
            # 记录任务创建日志
            mode_desc = "简单模式(仅爬取指定URL)" if mode == 'simple' else "完整模式(深度爬取内链)"
            log_action(user, "create_task", task.id, "success", 
                     f"创建爬虫任务: {task.url} ({mode_desc})")
            
            # 启动任务
            self.stdout.write('开始运行任务...')
            
            def run_task_thread():
                from tasks.task_runner import TaskRunner
                runner = TaskRunner(task.id)
                runner.run()
                
            thread = threading.Thread(target=run_task_thread)
            thread.daemon = True
            thread.start()
            
            self.stdout.write(self.style.SUCCESS('任务已在后台启动'))
            
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'用户 {username} 不存在'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'创建任务时出错: {str(e)}')) 