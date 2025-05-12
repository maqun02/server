import scrapy
import re
import json
import hashlib
import datetime
from urllib.parse import urlparse, urljoin
from scrapy_redis.spiders import RedisSpider
from ..items import StaticResourceItem

class ResourceSpider(RedisSpider):
    """
    爬取静态资源的爬虫
    JS和CSS保存源码，图片和图标保存MD5值
    """
    name = "resource_spider"
    
    def __init__(self, *args, **kwargs):
        super(ResourceSpider, self).__init__(*args, **kwargs)
        self.task_id = kwargs.get('task_id', None)
        self.content_url = kwargs.get('content_url', None)
        
        # 打印爬虫启动信息
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now}] ========== 资源爬虫启动 ==========")
        print(f"[{now}] 任务ID: {self.task_id}")
        if self.content_url:
            print(f"[{now}] 内容URL: {self.content_url}")
        print(f"[{now}] ==================================\n")

    def parse(self, response):
        """解析静态资源"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] 正在爬取资源: {response.url}")
        
        url = response.url
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        
        # 确定资源类型
        if path.endswith(('.js')):
            resource_type = 'js'
        elif path.endswith(('.css')):
            resource_type = 'css'
        elif path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')):
            resource_type = 'image'
        elif path.endswith(('.ico', '.icon')):
            resource_type = 'ico'
        else:
            resource_type = 'other'
        
        # 计算MD5哈希
        content = response.body
        md5_hash = hashlib.md5(content).hexdigest()
        
        # 创建资源项
        item = StaticResourceItem()
        item['task_id'] = self.task_id
        item['url'] = url
        item['content_url'] = self.content_url
        item['resource_type'] = resource_type
        
        # 对于JS和CSS，保存源码；对于图片和图标，只保存MD5值
        if resource_type in ['js', 'css']:
            item['content'] = content
            print(f"[{now}] 已获取{resource_type}源码，长度: {len(content)} 字节")
        else:
            item['content'] = None  # 不保存图片和图标内容
            print(f"[{now}] 已计算{resource_type}的MD5值: {md5_hash}")
            
        item['md5'] = md5_hash
        item['status'] = response.status
        
        print(f"[{now}] 资源 {url} 爬取完成，类型: {resource_type}")
        
        yield item
        
    def closed(self, reason):
        """爬虫关闭时的回调函数"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now}] ========== 资源爬虫关闭 ==========")
        print(f"[{now}] 任务ID: {self.task_id}")
        print(f"[{now}] 关闭原因: {reason}")
        print(f"[{now}] ==================================\n") 