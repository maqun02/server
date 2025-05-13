import logging
import hashlib
import json
import datetime
import urllib.parse
from scrapy import Spider, Request
from scrapy_redis.spiders import RedisSpider
from ..items import ResourceItem

class ResourceSpider(RedisSpider):
    """
    资源爬虫 - 第三层爬虫，用于下载静态资源内容并计算MD5哈希
    支持通过Redis分布式处理
    """
    name = 'resource_spider'
    redis_key = "%(spider)s:start_urls"
    
    def __init__(self, *args, **kwargs):
        super(ResourceSpider, self).__init__(*args, **kwargs)
        self.task_id = kwargs.get('task_id', None)
        self.resources = kwargs.get('resources', [])
        self.redis_key = kwargs.get('redis_key', None)
        self.timeout = kwargs.get('timeout', 15)
        
        if self.redis_key:
            self.redis_key = f"{self.redis_key}_resources"
        
        # 资源计数器
        self.resource_count = 0
        self.success_count = 0
        self.error_count = 0
        
        # 初始化URL映射
        self.url_to_type = {}
        self.url_to_page = {}
        
        # 从提供的资源列表中解析映射关系
        if self.resources:
            for resource in self.resources:
                if isinstance(resource, tuple) and len(resource) >= 3:
                    url, resource_type, page_url = resource
                    self.url_to_type[url] = resource_type
                    self.url_to_page[url] = page_url
                elif isinstance(resource, dict) and 'url' in resource:
                    url = resource['url']
                    self.url_to_type[url] = resource.get('type', 'other')
                    self.url_to_page[url] = resource.get('page_url', '')
        
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.info(f"\n[{now}] ========== 资源爬虫启动 ==========")
        self.logger.info(f"[{now}] 任务ID: {self.task_id}")
        self.logger.info(f"[{now}] Redis键: {self.redis_key}")
        self.logger.info(f"[{now}] 初始资源数量: {len(self.resources)}")
        self.logger.info(f"[{now}] ==================================\n")
    
    def make_request_from_data(self, data):
        """
        从Redis获取资源数据并创建请求
        数据格式: JSON字符串 {"url": "...", "type": "...", "page_url": "..."}
        """
        try:
            resource_data = json.loads(data.decode('utf-8'))
            url = resource_data.get('url', '')
            resource_type = resource_data.get('type', 'other')
            page_url = resource_data.get('page_url', '')
            
            if not url:
                self.logger.error(f"无效的资源数据: {data}")
                return None
                
            self.url_to_type[url] = resource_type
            self.url_to_page[url] = page_url
            
            self.logger.info(f"从Redis接收到资源URL: {url}, 类型: {resource_type}")
            return self.make_requests_to_url(url)
        except Exception as e:
            self.logger.error(f"解析Redis数据时出错: {e}, 数据: {data}")
            return None
    
    def make_requests_to_url(self, url):
        """
        为URL创建请求
        """
        resource_type = self.url_to_type.get(url, 'other')
        page_url = self.url_to_page.get(url, '')
        
        return Request(
            url=url, 
            callback=self.parse_resource,
            errback=self.handle_error,
            meta={
                'resource_type': resource_type,
                'page_url': page_url,
                'download_timeout': self.timeout
            }
        )
    
    def start_requests(self):
        """
        如果提供了资源列表，则直接使用这些资源开始爬取
        否则从Redis获取资源
        """
        if self.resources:
            for resource in self.resources:
                if isinstance(resource, tuple) and len(resource) >= 3:
                    url, _, _ = resource
                    self.logger.info(f"使用提供的资源URL开始爬取: {url}")
                    yield self.make_requests_to_url(url)
                elif isinstance(resource, dict) and 'url' in resource:
                    url = resource['url']
                    self.logger.info(f"使用提供的资源URL开始爬取: {url}")
                    yield self.make_requests_to_url(url)
        else:
            self.logger.info(f"未提供资源列表，等待从Redis ({self.redis_key}) 获取资源")
            # 让父类处理从Redis获取资源
            for req in super(ResourceSpider, self).start_requests():
                yield req
    
    def parse_resource(self, response):
        """解析资源内容并计算MD5哈希"""
        self.resource_count += 1
        resource_type = response.meta.get('resource_type', 'other')
        page_url = response.meta.get('page_url', '')
        
        # 获取资源内容
        content = response.body
        
        # 计算MD5哈希值
        md5_hash = hashlib.md5(content).hexdigest()
        
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.info(f"[{now}] 已下载资源: {response.url}, 类型: {resource_type}, MD5: {md5_hash}")
        
        self.success_count += 1
        
        # 创建资源项
        resource_item = ResourceItem(
            task_id=self.task_id,
            page_url=page_url,
            url=response.url,
            resource_type=resource_type,
            content=content,
            md5_hash=md5_hash,
            headers=dict(response.headers)
        )
        
        yield resource_item
    
    def handle_error(self, failure):
        """处理下载错误"""
        self.resource_count += 1
        self.error_count += 1
        
        request = failure.request
        url = request.url
        resource_type = request.meta.get('resource_type', 'other')
        page_url = request.meta.get('page_url', '')
        
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.error(f"[{now}] 下载资源失败: {url}, 类型: {resource_type}, 错误: {repr(failure)}")
        
        # 创建错误资源项
        resource_item = ResourceItem(
            task_id=self.task_id,
            page_url=page_url,
            url=url,
            resource_type=resource_type,
            content=None,
            md5_hash=None,
            headers={},
            error=repr(failure)
        )
        
        return resource_item
    
    def closed(self, reason):
        """爬虫关闭时的回调函数"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.info(f"\n[{now}] ========== 资源爬虫关闭 ==========")
        self.logger.info(f"[{now}] 任务ID: {self.task_id}")
        self.logger.info(f"[{now}] 资源处理统计:")
        self.logger.info(f"[{now}] - 总资源数: {self.resource_count}")
        self.logger.info(f"[{now}] - 成功数: {self.success_count}")
        self.logger.info(f"[{now}] - 失败数: {self.error_count}")
        self.logger.info(f"[{now}] 关闭原因: {reason}")
        self.logger.info(f"[{now}] ==================================\n") 