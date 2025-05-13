import os
import json
import uuid
import redis
import hashlib
import datetime
import subprocess
from django.conf import settings
from django.utils import timezone
from .models import CrawlerTask
from results.models import CrawlerResult, CrawlerLink, StaticResource, IdentifiedComponent
from fingerprints.utils import component_matcher
from fingerprints.models import Fingerprint
from logs.utils import log_action
import threading
import time
import traceback
import sys
import logging
from django.db import transaction
from django.db.models import Count, Q

logger = logging.getLogger(__name__)

class TaskRunner:
    """
    爬虫任务运行器，负责协调爬虫的执行流程
    实现四层爬虫的顺序执行：
    1. 链接爬虫：获取所有链接
    2. 内容爬虫：使用Splash进行动态渲染，获取页面内容和静态资源链接
    3. 资源爬虫：获取静态资源内容并计算MD5哈希
    4. 指纹匹配爬虫：对获取的内容和资源进行指纹匹配
    """
    
    def __init__(self, task_id=None):
        self.task_id = task_id
        self.task = None
        self.redis_key_prefix = None
        self.redis_client = None
        
        # 初始化Redis客户端
        try:
            redis_host = settings.REDIS_HOST
            redis_port = settings.REDIS_PORT
            redis_db = settings.REDIS_DB
            self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db)
            logger.info(f"已连接Redis: {redis_host}:{redis_port}/{redis_db}")
        except Exception as e:
            logger.error(f"连接Redis失败: {str(e)}")
        
        # 如果提供了任务ID，加载任务
        if task_id:
            try:
                self.task = CrawlerTask.objects.get(id=task_id)
                self.redis_key_prefix = self.task.redis_key_prefix or f"task:{task_id}:{uuid.uuid4().hex[:8]}"
                self.task.redis_key_prefix = self.redis_key_prefix
                self.task.save(update_fields=['redis_key_prefix'])
                logger.info(f"初始化任务 {task_id}, redis_key_prefix: {self.redis_key_prefix}")
            except CrawlerTask.DoesNotExist:
                logger.error(f"任务 {task_id} 不存在")
    
    def run(self):
        """
        运行爬虫任务的主函数
        """
        if not self.task:
            logger.error("没有指定任务，无法执行")
            return False
        
        try:
            # 开始执行任务
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{now}] ========== 开始执行任务 ==========")
            print(f"[{now}] 任务ID: {self.task_id}")
            print(f"[{now}] URL: {self.task.url}")
            print(f"[{now}] 模式: {self.task.mode}")
            print(f"[{now}] Redis键前缀: {self.redis_key_prefix}")
            print(f"[{now}] ==================================\n")
            
            self.update_task_status('queued')
            
            # 清理Redis中的任务数据
            self.clean_redis_keys()
            
            # 1. 链接爬虫阶段
            logger.info(f"开始运行链接爬虫: {self.task.url}")
            success = self.run_link_spider()
            if not success:
                self.update_task_status('failed')
                log_action(self.task.user, "task_failed", self.task.id, "failure", 
                         f"链接爬虫失败: {self.task.url}")
                return False
            
            # 2. 内容爬虫阶段
            logger.info(f"开始运行内容爬虫")
            success = self.run_content_spider()
            if not success:
                self.update_task_status('failed')
                log_action(self.task.user, "task_failed", self.task.id, "failure", 
                         f"内容爬虫失败: {self.task.url}")
                return False
            
            # 3. 资源爬虫阶段
            logger.info(f"开始运行资源爬虫")
            success = self.run_resource_spider()
            if not success:
                self.update_task_status('failed')
                log_action(self.task.user, "task_failed", self.task.id, "failure", 
                         f"资源爬虫失败: {self.task.url}")
                return False
            
            # 4. 指纹匹配阶段
            logger.info(f"开始运行指纹匹配")
            success = self.run_fingerprint_matcher()
            if not success:
                self.update_task_status('failed')
                log_action(self.task.user, "task_failed", self.task.id, "failure", 
                         f"指纹匹配失败: {self.task.url}")
                return False
            
            # 5. 完成任务
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{now}] ========== 任务执行完成 ==========")
            print(f"[{now}] 任务ID: {self.task_id}")
            print(f"[{now}] URL: {self.task.url}")
            print(f"[{now}] 模式: {self.task.mode}")
            print(f"[{now}] ==================================\n")
            
            self.update_task_status('completed')
            log_action(self.task.user, "task_completed", self.task.id, "success", 
                     f"任务完成: {self.task.url}")
            
            return True
            
        except Exception as e:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{now}] ========== 任务执行异常 ==========")
            print(f"[{now}] 任务ID: {self.task_id}")
            print(f"[{now}] 错误: {str(e)}")
            print(f"[{now}] ==================================\n")
            
            logger.exception(f"任务 {self.task_id} 执行出错: {str(e)}")
            self.update_task_status('failed')
            log_action(self.task.user, "task_error", self.task.id, "failure", 
                     f"任务执行错误: {str(e)}")
            return False
    
    def clean_redis_keys(self):
        """清理Redis中的任务相关键"""
        if not self.redis_client or not self.redis_key_prefix:
            return
            
        try:
            # 查找并删除所有与任务相关的键
            pattern = f"{self.redis_key_prefix}*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"已清理Redis中的 {len(keys)} 个与任务 {self.task_id} 相关的键")
        except Exception as e:
            logger.error(f"清理Redis键失败: {str(e)}")
    
    def run_link_spider(self):
        """
        运行链接爬虫
        """
        try:
            self.update_task_status('link_crawling')
            
            # 准备爬虫命令
            cmd = [
                'scrapy', 'crawl', 'link_spider',
                '-a', f'task_id={self.task_id}',
                '-a', f'url={self.task.url}',
                '-a', f'mode={self.task.mode}',
                '-a', f'redis_key={self.redis_key_prefix}'
            ]
            
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 执行链接爬虫命令: {' '.join(cmd)}")
            
            # 执行爬虫
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                cwd=os.path.join(settings.BASE_DIR, 'scrapy_engine')
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                stderr_text = stderr.decode('utf-8', errors='ignore')
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{now}] 链接爬虫执行失败: {stderr_text[:500]}...")
                logger.error(f"链接爬虫执行失败: {stderr_text}")
                return False
            
            stdout_text = stdout.decode('utf-8', errors='ignore')
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 链接爬虫执行完成")
            logger.info(f"链接爬虫执行完成，退出码: {process.returncode}")
            
            # 更新任务状态
            links = CrawlerLink.objects.filter(task=self.task)
            link_count = links.count()
            self.task.links_found = link_count
            self.task.links_crawled = link_count
            self.task.save(update_fields=['links_found', 'links_crawled'])
            
            print(f"[{now}] 共发现 {link_count} 个链接")
            
            return True
            
        except Exception as e:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 运行链接爬虫异常: {str(e)}")
            logger.exception(f"运行链接爬虫出错: {str(e)}")
            return False
    
    def run_content_spider(self):
        """
        运行内容爬虫 - 使用Splash进行动态渲染
        """
        try:
            self.update_task_status('content_crawling')
            
            # 准备爬虫命令
            cmd = [
                'scrapy', 'crawl', 'content_spider',
                '-a', f'task_id={self.task_id}',
                '-a', f'redis_key={self.redis_key_prefix}',
                '-a', f'timeout={self.task.link_timeout}'
            ]
            
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 执行内容爬虫命令: {' '.join(cmd)}")
            
            # 执行爬虫
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                cwd=os.path.join(settings.BASE_DIR, 'scrapy_engine')
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                stderr_text = stderr.decode('utf-8', errors='ignore')
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{now}] 内容爬虫执行失败: {stderr_text[:500]}...")
                logger.error(f"内容爬虫执行失败: {stderr_text}")
                return False
            
            stdout_text = stdout.decode('utf-8', errors='ignore')
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 内容爬虫执行完成")
            logger.info(f"内容爬虫执行完成，退出码: {process.returncode}")
            
            # 更新任务状态
            results = CrawlerResult.objects.filter(task=self.task)
            results_count = results.count()
            
            # 计算资源数量
            resources_count = 0
            for result in results:
                resources_count += len(result.resources)
            
            self.task.links_crawled = results_count
            self.task.resources_found = resources_count
            self.task.save(update_fields=['links_crawled', 'resources_found'])
            
            print(f"[{now}] 共爬取 {results_count} 个页面, 发现 {resources_count} 个资源")
            
            return True
            
        except Exception as e:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 运行内容爬虫异常: {str(e)}")
            logger.exception(f"运行内容爬虫出错: {str(e)}")
            return False
    
    def run_resource_spider(self):
        """
        运行资源爬虫
        """
        try:
            self.update_task_status('resource_crawling')
            
            # 准备爬虫命令
            cmd = [
                'scrapy', 'crawl', 'resource_spider',
                '-a', f'task_id={self.task_id}',
                '-a', f'redis_key={self.redis_key_prefix}',
                '-a', f'timeout={self.task.resource_timeout}'
            ]
            
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 执行资源爬虫命令: {' '.join(cmd)}")
            
            # 执行爬虫
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                cwd=os.path.join(settings.BASE_DIR, 'scrapy_engine')
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                stderr_text = stderr.decode('utf-8', errors='ignore')
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{now}] 资源爬虫执行失败: {stderr_text[:500]}...")
                logger.error(f"资源爬虫执行失败: {stderr_text}")
                return False
            
            stdout_text = stdout.decode('utf-8', errors='ignore')
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 资源爬虫执行完成")
            logger.info(f"资源爬虫执行完成，退出码: {process.returncode}")
            
            # 更新任务状态
            resources = StaticResource.objects.filter(task=self.task)
            resources_count = resources.count()
            
            self.task.resources_crawled = resources_count
            self.task.save(update_fields=['resources_crawled'])
            
            print(f"[{now}] 共爬取 {resources_count} 个资源")
            
            return True
            
        except Exception as e:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 运行资源爬虫异常: {str(e)}")
            logger.exception(f"运行资源爬虫出错: {str(e)}")
            return False
    
    def run_fingerprint_matcher(self):
        """
        运行指纹匹配爬虫
        """
        try:
            self.update_task_status('fingerprint_matching')
            
            # 准备爬虫命令
            cmd = [
                'scrapy', 'crawl', 'fingerprint_matcher',
                '-a', f'task_id={self.task_id}'
            ]
            
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 执行指纹匹配命令: {' '.join(cmd)}")
            
            # 执行爬虫
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                cwd=os.path.join(settings.BASE_DIR, 'scrapy_engine')
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                stderr_text = stderr.decode('utf-8', errors='ignore')
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{now}] 指纹匹配执行失败: {stderr_text[:500]}...")
                logger.error(f"指纹匹配执行失败: {stderr_text}")
                return False
            
            stdout_text = stdout.decode('utf-8', errors='ignore')
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 指纹匹配执行完成")
            logger.info(f"指纹匹配执行完成，退出码: {process.returncode}")
            
            # 更新任务状态
            components = IdentifiedComponent.objects.filter(task=self.task)
            components_count = components.count()
            
            self.task.components_identified = components_count
            self.task.save(update_fields=['components_identified'])
            
            print(f"[{now}] 共识别 {components_count} 个组件")
            
            return True
            
        except Exception as e:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 运行指纹匹配异常: {str(e)}")
            logger.exception(f"运行指纹匹配出错: {str(e)}")
            return False
    
    def update_task_status(self, status):
        """
        更新任务状态
        """
        if not self.task:
            return
        
        try:
            # 更新开始时间（如果是第一次状态变更）
            if self.task.status == 'queued' and status != 'queued':
                self.task.started_at = timezone.now()
            
            # 更新结束时间（如果任务完成或失败）
            if status in ['completed', 'failed']:
                self.task.ended_at = timezone.now()
            
            # 更新状态
            old_status = self.task.status
            self.task.status = status
            self.task.save(update_fields=['status', 'started_at', 'ended_at'])
            
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 任务 {self.task_id} 状态从 '{old_status}' 更新为 '{status}'")
            
            # 记录状态变更日志
            if old_status != status:
                log_action(
                    self.task.user, 
                    "task_status_change", 
                    self.task.id, 
                    "success" if status != 'failed' else "failure",
                    f"任务状态更新: {self.task.get_status_display()} -> {dict(CrawlerTask.STATUS_CHOICES)[status]}"
                )
                
            logger.info(f"任务 {self.task_id} 状态更新: {old_status} -> {status}")
            
        except Exception as e:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 更新任务状态失败: {str(e)}")
            logger.error(f"更新任务状态失败: {str(e)}")

def run_task(task_id):
    """
    运行指定ID的爬虫任务
    """
    runner = TaskRunner(task_id)
    return runner.run()

def cleanup_old_tasks():
    """
    清理历史任务数据
    """
    try:
        # 清理一周前的任务
        one_week_ago = timezone.now() - datetime.timedelta(days=7)
        old_tasks = CrawlerTask.objects.filter(created_at__lt=one_week_ago)
        
        for task in old_tasks:
            # 删除相关数据
            CrawlerLink.objects.filter(task=task).delete()
            CrawlerResult.objects.filter(task=task).delete()
            StaticResource.objects.filter(task=task).delete()
            IdentifiedComponent.objects.filter(task=task).delete()
            
            # 记录日志
            log_action(None, "task_cleanup", task.id, "success", 
                     f"清理历史任务: {task.url} (创建于 {task.created_at})")
            
            # 删除任务
            task.delete()
        
        logger.info(f"已清理 {len(old_tasks)} 个历史任务")
        
    except Exception as e:
        logger.error(f"清理历史任务失败: {str(e)}")

# 创建单例实例
task_runner = TaskRunner() 