from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone
import os
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '执行系统维护任务（适合作为定时任务运行）'

    def handle(self, *args, **options):
        self.stdout.write(f'开始执行系统维护任务 - {timezone.now()}')
        
        try:
            # 1. 终止运行超过2小时的任务
            self.stdout.write('1. 终止运行过长的任务:')
            call_command('terminate_hanging_tasks', hours=2)
            
            # 2. 清理Redis过期队列
            self.stdout.write('\n2. 清理Redis过期队列:')
            call_command('cleanup_redis_queues')
            
            # 3. 检查并输出系统状态
            self.stdout.write('\n3. 检查系统状态:')
            call_command('check_queue_status')
            
            self.stdout.write(self.style.SUCCESS(f'\n维护任务完成 - {timezone.now()}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'维护任务执行失败: {str(e)}'))
            logger.error(f'维护任务执行失败: {str(e)}', exc_info=True)
            
        # 提示如何设置定时任务
        self.stdout.write('\n要设置定时任务，请添加以下crontab条目:')
        self.stdout.write('# 每小时执行一次系统维护')
        self.stdout.write('0 * * * * cd /path/to/project && python manage.py maintenance_cron > /path/to/logs/maintenance.log 2>&1') 