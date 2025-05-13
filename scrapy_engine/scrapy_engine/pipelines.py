# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
import json
import django
import os
from .items import LinkItem, ContentItem, ResourceItem
import sys
import datetime
import asyncio
from asgiref.sync import sync_to_async
import logging
import hashlib
import redis
from scrapy.exceptions import DropItem
from django.db import transaction
from django.utils import timezone
from tasks.models import CrawlerTask
from results.models import CrawlerLink, CrawlerResult, StaticResource, IdentifiedComponent
from fingerprints.utils import ComponentMatcher

# 设置Django环境
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django.setup()

# 导入Django模型
from tasks.models import CrawlerTask
from results.models import CrawlerLink, CrawlerResult, StaticResource
from logs.utils import log_action
from django.db import transaction

class BasePipeline:
    """基础管道类，提供共用功能"""
    
    def __init__(self, redis_host, redis_port, redis_db):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.redis_conn = None
        self.logger = logging.getLogger(__name__)
        
    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            redis_host=crawler.settings.get('REDIS_HOST', 'localhost'),
            redis_port=crawler.settings.get('REDIS_PORT', 6379),
            redis_db=crawler.settings.get('REDIS_DB', 0)
        )
    
    def open_spider(self, spider):
        """爬虫启动时连接Redis"""
        try:
            self.redis_conn = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True  # 自动将字节解码为字符串
            )
            self.logger.info(f"已连接到Redis: {self.redis_host}:{self.redis_port}")
        except Exception as e:
            self.logger.error(f"Redis连接失败: {str(e)}")
            self.redis_conn = None

class LinkPipeline(BasePipeline):
    """处理链接爬虫的结果管道"""
    
    def process_item(self, item, spider):
        """处理链接项，保存到数据库并添加到Redis队列"""
        if not hasattr(spider, 'task_id') or not spider.task_id:
            raise DropItem(f"缺少task_id，丢弃链接项: {item['url']}")
        
        if spider.name != 'link_spider':
            return item
        
        try:
            with transaction.atomic():
                task_id = item['task_id']
                task = CrawlerTask.objects.get(id=task_id)
                
                # 更新任务状态
                if task.status == 'queued':
                    task.status = 'link_crawling'
                    task.started_at = timezone.now()
                    task.save()
                
                # 保存链接到数据库
                crawler_link, created = CrawlerLink.objects.update_or_create(
                    task=task,
                    url=item['url'],
                    defaults={
                        'internal_links': item['internal_links'],
                        'external_links': item['external_links'],
                        'internal_nofollow_links': item['internal_nofollow_links'],
                        'external_nofollow_links': item['external_nofollow_links'],
                    }
                )
                
                # 更新任务链接计数
                links_found = (
                    len(item['internal_links']) + 
                    len(item['external_links']) +
                    len(item['internal_nofollow_links']) + 
                    len(item['external_nofollow_links'])
                )
                task.links_found += links_found
                task.save()
                
                self.logger.info(f"已保存链接: {item['url']}, 找到{links_found}个链接")
                
                # 如果启用了Redis，将内容爬取任务添加到队列
                if self.redis_conn and spider.redis_key:
                    # 如果是简单模式，只添加起始URL
                    # 如果是深度模式，添加所有内链
                    urls_to_crawl = []
                    
                    if spider.mode == 'simple':
                        # 简单模式只爬取当前URL
                        urls_to_crawl.append(item['url'])
                    else:
                        # 深度模式爬取当前URL和内链
                        urls_to_crawl.append(item['url'])
                        urls_to_crawl.extend(item['internal_links'])
                    
                    # 将URL添加到Redis队列
                    content_redis_key = f"{spider.redis_key}:content"
                    for url in urls_to_crawl:
                        self.redis_conn.sadd(f"{content_redis_key}:urls", url)
                        # 生成Scrapy-Redis需要的请求格式
                        request = json.dumps({"url": url})
                        self.redis_conn.lpush(content_redis_key, request)
                    
                    self.logger.info(f"已将{len(urls_to_crawl)}个URL添加到内容爬取队列: {content_redis_key}")
                
                return item
                
        except Exception as e:
            self.logger.error(f"保存链接失败: {str(e)}")
            raise DropItem(f"保存链接失败: {str(e)}")

class ContentPipeline(BasePipeline):
    """处理内容爬虫的结果管道"""
    
    def process_item(self, item, spider):
        """处理内容项，保存到数据库并添加静态资源到Redis队列"""
        if not hasattr(spider, 'task_id') or not spider.task_id:
            return item
        
        if spider.name != 'content_spider':
            return item
        
        try:
            with transaction.atomic():
                task_id = item['task_id']
                task = CrawlerTask.objects.get(id=task_id)
                
                # 更新任务状态
                if task.status == 'link_crawling':
                    task.status = 'content_crawling'
                    task.save()
                
                # 保存内容到数据库
                crawler_result, created = CrawlerResult.objects.update_or_create(
                    task=task,
                    url=item['url'],
                    defaults={
                        'title': item['title'],
                        'html_source': item['html_source'],
                        'headers': item['headers'],
                        'resources': item['resources'],
                    }
                )
                
                # 更新链接状态为已爬取
                CrawlerLink.objects.filter(task=task, url=item['url']).update(is_crawled=True)
                
                # 更新任务计数
                task.links_crawled += 1
                task.resources_found += len(item['resources'])
                task.save()
                
                self.logger.info(f"已保存内容: {item['url']}, 标题: {item['title'][:30]}..., 资源数: {len(item['resources'])}")
                
                # 如果启用了Redis，将静态资源爬取任务添加到队列
                if self.redis_conn and spider.redis_key and item['resources']:
                    # 准备资源爬取任务
                    resource_redis_key = f"{spider.redis_key}:resource"
                    
                    # 为每个资源添加所属页面URL
                    resources_with_page = []
                    for resource in item['resources']:
                        resource_with_page = resource.copy()
                        resource_with_page['page_url'] = item['url']
                        resources_with_page.append(resource_with_page)
                    
                    # 将资源添加到Redis队列
                    for resource in resources_with_page:
                        self.redis_conn.sadd(f"{resource_redis_key}:urls", resource['url'])
                        # 生成Scrapy-Redis需要的请求格式，包含额外元数据
                        request = json.dumps({
                            "url": resource['url'],
                            "meta": {
                                "resource_type": resource['type'],
                                "page_url": resource['page_url']
                            }
                        })
                        self.redis_conn.lpush(resource_redis_key, request)
                    
                    self.logger.info(f"已将{len(resources_with_page)}个资源添加到资源爬取队列: {resource_redis_key}")
                
                return item
                
        except Exception as e:
            self.logger.error(f"保存内容失败: {str(e)}")
            raise DropItem(f"保存内容失败: {str(e)}")

class ResourcePipeline(BasePipeline):
    """处理资源爬虫的结果管道"""
    
    def __init__(self, redis_host, redis_port, redis_db):
        super().__init__(redis_host, redis_port, redis_db)
        self.component_matcher = None
    
    def open_spider(self, spider):
        """爬虫启动时加载组件匹配器"""
        super().open_spider(spider)
        if spider.name == 'resource_spider':
            self.component_matcher = ComponentMatcher()
            try:
                self.component_matcher.load_fingerprints()
                self.logger.info("已加载组件指纹库")
            except Exception as e:
                self.logger.error(f"加载组件指纹库失败: {str(e)}")
    
    def process_item(self, item, spider):
        """处理资源项，保存到数据库并进行指纹匹配"""
        if not hasattr(spider, 'task_id') or not spider.task_id:
            return item
        
        if spider.name != 'resource_spider':
            return item
        
        try:
            with transaction.atomic():
                task_id = item['task_id']
                task = CrawlerTask.objects.get(id=task_id)
                
                # 更新任务状态
                if task.status == 'content_crawling':
                    task.status = 'resource_crawling'
                    task.save()
                
                # 查找对应的内容结果
                try:
                    result = CrawlerResult.objects.get(task=task, url=item['page_url'])
                except CrawlerResult.DoesNotExist:
                    self.logger.warning(f"找不到对应的内容结果: {item['page_url']}，使用任务作为关联")
                    result = None
                
                # 保存资源到数据库
                static_resource = StaticResource(
                    task=task,
                    result=result,
                    url=item['url'],
                    resource_type=item['resource_type'],
                    content=item['content'] if item['content'] else None,
                    md5_hash=item['md5_hash']
                )
                static_resource.save()
                
                # 更新任务计数
                task.resources_crawled += 1
                task.save()
                
                self.logger.info(f"已保存资源: {item['url']}, 类型: {item['resource_type']}, MD5: {item['md5_hash']}")
                
                # 进行指纹匹配
                if self.component_matcher and self.component_matcher.loaded:
                    # 为不同类型的资源选择不同的匹配方法
                    if item['resource_type'] in ['js', 'css']:
                        # 对于文本资源，使用内容进行匹配
                        if item['content']:
                            try:
                                content_text = item['content'].decode('utf-8', errors='ignore')
                                matches = self.component_matcher.match(content_text)
                                
                                # 保存匹配结果
                                for component, keyword in matches:
                                    IdentifiedComponent.objects.create(
                                        task=task,
                                        resource=static_resource,
                                        component=component,
                                        keyword=keyword,
                                        match_type=item['resource_type']
                                    )
                                    task.components_identified += 1
                                    task.save()
                                
                                static_resource.is_matched = True
                                static_resource.save()
                                
                                self.logger.info(f"资源 {item['url']} 匹配到 {len(matches)} 个组件")
                            except Exception as e:
                                self.logger.error(f"资源内容匹配失败: {str(e)}")
                    
                    elif item['resource_type'] in ['image', 'ico']:
                        # 对于二进制资源，使用MD5进行匹配
                        if item['md5_hash']:
                            # 如果有指纹MD5匹配功能，在这里实现
                            pass
                
                return item
                
        except Exception as e:
            self.logger.error(f"处理资源失败: {str(e)}")
            raise DropItem(f"处理资源失败: {str(e)}")

class FingerprintPipeline(BasePipeline):
    """处理指纹匹配的管道"""
    
    def process_item(self, item, spider):
        """处理指纹匹配"""
        # 指纹匹配爬虫的结果直接处理为IdentifiedComponent对象
        if not hasattr(spider, 'task_id') or not spider.task_id:
            return item
            
        if spider.name != 'fingerprint_matcher':
            return item
            
        # 由于指纹匹配爬虫直接在数据库操作，不需要处理items
        return item
