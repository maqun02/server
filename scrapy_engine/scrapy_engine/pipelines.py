# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
import json
import django
import os
from .items import LinkItem, ContentItem, StaticResourceItem
import sys
import datetime
import asyncio
from asgiref.sync import sync_to_async

# 设置Django环境
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django.setup()

# 导入Django模型
from tasks.models import CrawlerTask
from results.models import CrawlerLink, CrawlerResult, StaticResource
from logs.utils import log_action
from django.db import transaction

class ScrapyEnginePipeline:
    """
    处理爬虫数据的管道
    将数据保存到Django数据库中
    """
    def __init__(self):
        self.sync_enabled = True
        
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        
        # 打印时间戳
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 根据不同的项类型进行不同的处理
        if isinstance(item, LinkItem):
            print(f"[{now}] 处理链接: {adapter.get('url')}")
            # 在异步环境中运行同步代码
            if 'twisted.internet.reactor' in sys.modules:
                return self.process_link_item_async(adapter, spider)
            else:
                return self.process_link_item(adapter, spider)
        elif isinstance(item, ContentItem):
            print(f"[{now}] 处理内容: {adapter.get('url')}")
            if 'twisted.internet.reactor' in sys.modules:
                return self.process_content_item_async(adapter, spider)
            else:
                return self.process_content_item(adapter, spider)
        elif isinstance(item, StaticResourceItem):
            print(f"[{now}] 处理资源: {adapter.get('url')}")
            if 'twisted.internet.reactor' in sys.modules:
                return self.process_resource_item_async(adapter, spider)
            else:
                return self.process_resource_item(adapter, spider)
        
        return item
    
    async def process_link_item_async(self, adapter, spider):
        """异步处理链接项"""
        @sync_to_async
        def process_link():
            return self.process_link_item(adapter, spider)
        
        return await process_link()
    
    async def process_content_item_async(self, adapter, spider):
        """异步处理内容项"""
        @sync_to_async
        def process_content():
            return self.process_content_item(adapter, spider)
        
        return await process_content()
    
    async def process_resource_item_async(self, adapter, spider):
        """异步处理资源项"""
        @sync_to_async
        def process_resource():
            return self.process_resource_item(adapter, spider)
        
        return await process_resource()
    
    @transaction.atomic
    def process_link_item(self, adapter, spider):
        """处理链接项"""
        task_id = adapter.get('task_id')
        url = adapter.get('url')
        
        try:
            task = CrawlerTask.objects.get(id=task_id)
            
            # 创建或更新链接记录
            link, created = CrawlerLink.objects.update_or_create(
                task=task,
                url=url,
                defaults={
                    'internal_links': adapter.get('internal_links', []),
                    'external_links': adapter.get('external_links', []),
                    'internal_nofollow_links': adapter.get('internal_nofollow_links', []),
                    'external_nofollow_links': adapter.get('external_nofollow_links', []),
                }
            )
            
            # 更新任务统计信息
            if created:
                task.links_found += 1
                task.save(update_fields=['links_found'])
                
                # 打印进度信息到命令行
                print(f"[链接爬取] 任务 {task_id}: 已发现 {task.links_found} 个链接")
                # 每发现10个链接打印一次摘要
                if task.links_found % 10 == 0:
                    print(f"[进度摘要] 任务 {task_id}: 已发现 {task.links_found} 个链接, 已爬取 {task.links_crawled} 个内容, 资源: {task.resources_crawled}/{task.resources_found}")
                
            # 记录日志
            log_action(task.user, "link_crawled", task.id, "success", 
                      f"爬取链接: {url}, 发现 {len(adapter.get('internal_links', []))} 内链, {len(adapter.get('external_links', []))} 外链")
                      
            # 更新任务状态（对于第一个URL）
            if task.links_found == 1 and task.status == 'link_crawling':
                task.status = 'content_crawling'
                task.save(update_fields=['status'])
                print(f"\n[阶段转换] 任务 {task_id}: 链接爬取阶段完成，开始内容爬取阶段\n")
                log_action(task.user, "task_status_change", task.id, "success", 
                         f"任务状态更新: 链接爬取中 -> 内容爬取中")
            
        except CrawlerTask.DoesNotExist:
            print(f"[错误] 无法找到任务ID: {task_id}")
            spider.logger.error(f"无法找到任务ID: {task_id}")
        except Exception as e:
            print(f"[错误] 处理链接项错误: {str(e)}")
            spider.logger.error(f"处理链接项错误: {str(e)}")
            
        return adapter.asdict()
    
    @transaction.atomic
    def process_content_item(self, adapter, spider):
        """处理内容项"""
        task_id = adapter.get('task_id')
        url = adapter.get('url')
        
        try:
            task = CrawlerTask.objects.get(id=task_id)
            
            # 创建或更新内容记录
            result, created = CrawlerResult.objects.update_or_create(
                task=task,
                url=url,
                defaults={
                    'title': adapter.get('title', ''),
                    'html_source': adapter.get('html_content', ''),
                    'headers': adapter.get('headers', {}),
                }
            )
            
            # 更新任务统计信息
            if created:
                task.links_crawled += 1
                
                # 获取静态资源数量
                resources = adapter.get('static_resources', [])
                task.resources_found += len(resources)
                
                task.save(update_fields=['links_crawled', 'resources_found'])
                
                # 打印进度信息到命令行
                print(f"[内容爬取] 任务 {task_id}: 已爬取 {task.links_crawled}/{task.links_found} 个页面，发现 {len(resources)} 个静态资源")
                # 每爬取5个页面打印一次摘要
                if task.links_crawled % 5 == 0:
                    progress = (task.links_crawled / task.links_found * 100) if task.links_found > 0 else 0
                    print(f"[进度摘要] 任务 {task_id}: 页面进度 {progress:.1f}%, 已爬取 {task.links_crawled}/{task.links_found} 个页面, 资源: {task.resources_crawled}/{task.resources_found}")
            
            # 记录日志
            log_action(task.user, "content_crawled", task.id, "success", 
                      f"爬取内容: {url}, 标题: {adapter.get('title', '')[:30]}..., 静态资源: {len(adapter.get('static_resources', []))}")
            
            # 如果所有链接都已爬取完毕，更新任务状态
            if task.links_crawled >= task.links_found and task.status == 'content_crawling':
                task.status = 'resource_crawling'
                task.save(update_fields=['status'])
                print(f"\n[阶段转换] 任务 {task_id}: 内容爬取阶段完成，开始资源爬取阶段\n")
                log_action(task.user, "task_status_change", task.id, "success", 
                         f"任务状态更新: 内容爬取中 -> 资源爬取中")
            
        except CrawlerTask.DoesNotExist:
            print(f"[错误] 无法找到任务ID: {task_id}")
            spider.logger.error(f"无法找到任务ID: {task_id}")
        except Exception as e:
            print(f"[错误] 处理内容项错误: {str(e)}")
            spider.logger.error(f"处理内容项错误: {str(e)}")
            
        return adapter.asdict()
    
    @transaction.atomic
    def process_resource_item(self, adapter, spider):
        """处理资源项"""
        task_id = adapter.get('task_id')
        url = adapter.get('url')
        content_url = adapter.get('content_url')
        
        try:
            task = CrawlerTask.objects.get(id=task_id)
            
            # 获取对应的内容记录
            try:
                result = CrawlerResult.objects.get(task=task, url=content_url)
                
                # 创建或更新资源记录
                resource, created = StaticResource.objects.update_or_create(
                    task=task,
                    url=url,
                    defaults={
                        'result': result,
                        'resource_type': adapter.get('resource_type', 'other'),
                        'content': adapter.get('content', b''),
                        'md5_hash': adapter.get('md5', None),
                    }
                )
                
                # 更新任务统计信息
                if created:
                    task.resources_crawled += 1
                    task.save(update_fields=['resources_crawled'])
                    
                    # 打印进度信息到命令行
                    resource_type = adapter.get('resource_type', 'other')
                    print(f"[资源爬取] 任务 {task_id}: 已爬取 {task.resources_crawled}/{task.resources_found} 个资源，类型: {resource_type}")
                    # 每爬取20个资源打印一次摘要
                    if task.resources_crawled % 20 == 0:
                        progress = (task.resources_crawled / task.resources_found * 100) if task.resources_found > 0 else 0
                        print(f"[进度摘要] 任务 {task_id}: 资源进度 {progress:.1f}%, 已爬取 {task.resources_crawled}/{task.resources_found} 个资源")
                
                # 记录日志
                log_action(task.user, "resource_crawled", task.id, "success", 
                          f"爬取资源: {url}, 类型: {adapter.get('resource_type', 'other')}")
                
                # 如果所有资源都已爬取完毕，更新任务状态
                if task.resources_crawled >= task.resources_found and task.status == 'resource_crawling':
                    task.status = 'fingerprint_matching'
                    task.save(update_fields=['status'])
                    print(f"\n[阶段转换] 任务 {task_id}: 资源爬取阶段完成，开始指纹匹配阶段\n")
                    log_action(task.user, "task_status_change", task.id, "success", 
                             f"任务状态更新: 资源爬取中 -> 指纹匹配中")
                
            except CrawlerResult.DoesNotExist:
                print(f"[错误] 无法找到URL为 {content_url} 的内容记录")
                spider.logger.error(f"无法找到URL为 {content_url} 的内容记录")
                
        except CrawlerTask.DoesNotExist:
            print(f"[错误] 无法找到任务ID: {task_id}")
            spider.logger.error(f"无法找到任务ID: {task_id}")
        except Exception as e:
            print(f"[错误] 处理资源项错误: {str(e)}")
            spider.logger.error(f"处理资源项错误: {str(e)}")
            
        return adapter.asdict()
