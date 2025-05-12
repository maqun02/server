import scrapy
import re
import json
import hashlib
import datetime
from urllib.parse import urlparse, urljoin
from scrapy_redis.spiders import RedisSpider
from ..items import ContentItem

class ContentSpider(RedisSpider):
    """
    爬取网页内容的爬虫
    获取网页标题、HTML源码、响应头和静态资源
    """
    name = "content_spider"
    
    def __init__(self, *args, **kwargs):
        super(ContentSpider, self).__init__(*args, **kwargs)
        self.task_id = kwargs.get('task_id', None)
        self.content_url = kwargs.get('content_url', None)
        
        # 打印爬虫启动信息
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now}] ========== 内容爬虫启动 ==========")
        print(f"[{now}] 任务ID: {self.task_id}")
        if self.content_url:
            print(f"[{now}] 内容URL: {self.content_url}")
        print(f"[{now}] ==================================\n")

    def parse(self, response):
        """解析页面内容"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] 正在爬取页面内容: {response.url}")
        
        # 获取页面标题
        title = response.css('title::text').get() or ""
        
        # 提取静态资源链接
        static_resources = []
        
        # 1. 提取JavaScript文件
        for script in response.css('script[src]'):
            src = script.css('::attr(src)').get()
            if src:
                abs_url = response.urljoin(src)
                static_resources.append({
                    'url': abs_url,
                    'type': 'js'
                })
                
        # 2. 提取CSS样式表
        for css in response.css('link[rel="stylesheet"]'):
            href = css.css('::attr(href)').get()
            if href:
                abs_url = response.urljoin(href)
                static_resources.append({
                    'url': abs_url,
                    'type': 'css'
                })
                
        # 3. 提取图片
        for img in response.css('img'):
            src = img.css('::attr(src)').get()
            if src:
                abs_url = response.urljoin(src)
                static_resources.append({
                    'url': abs_url,
                    'type': 'image'
                })
                
        # 4. 提取图标
        for icon in response.css('link[rel="icon"], link[rel="shortcut icon"]'):
            href = icon.css('::attr(href)').get()
            if href:
                abs_url = response.urljoin(href)
                static_resources.append({
                    'url': abs_url,
                    'type': 'ico'
                })
        
        # 转换响应头
        headers = {}
        for name, value in response.headers.items():
            name = name.decode('utf-8', errors='ignore')
            values = []
            for v in value:
                try:
                    values.append(v.decode('utf-8', errors='ignore'))
                except:
                    values.append(str(v))
            headers[name] = values
        
        # 创建内容项
        item = ContentItem()
        item['task_id'] = self.task_id
        item['url'] = response.url
        item['title'] = title
        item['headers'] = headers
        item['html_content'] = response.text
        item['static_resources'] = static_resources
        item['status'] = response.status
        
        print(f"[{now}] 页面 {response.url} 爬取完成")
        print(f"[{now}] 标题: {title[:50]}{'...' if len(title) > 50 else ''}")
        print(f"[{now}] 静态资源: JS={len([r for r in static_resources if r['type'] == 'js'])}, CSS={len([r for r in static_resources if r['type'] == 'css'])}, 图片={len([r for r in static_resources if r['type'] == 'image'])}, 图标={len([r for r in static_resources if r['type'] == 'ico'])}")
        
        yield item
        
    def closed(self, reason):
        """爬虫关闭时的回调函数"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now}] ========== 内容爬虫关闭 ==========")
        print(f"[{now}] 任务ID: {self.task_id}")
        print(f"[{now}] 关闭原因: {reason}")
        print(f"[{now}] ==================================\n") 