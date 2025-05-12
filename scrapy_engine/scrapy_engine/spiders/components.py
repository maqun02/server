import scrapy
import json
from urllib.parse import urljoin, urlparse
import os
from scrapy.linkextractors import LinkExtractor
from scrapy_redis.spiders import RedisSpider
from tasks.models import CrawlerTask
from results.models import CrawlerLink
import hashlib
from results.models import CrawlerResult, StaticResource
import datetime


class ComponentsSpider(scrapy.Spider):
    name = "components"
    allowed_domains = ["example.com"]
    start_urls = ["http://example.com"]

    def __init__(self, url=None, mode='simple', task_id=None, *args, **kwargs):
        super(ComponentsSpider, self).__init__(*args, **kwargs)
        self.url = url
        self.mode = mode  # 'simple'表示简单模式，'deep'表示完整模式
        self.visited_urls = set()
        self.task_id = task_id
        
        # 如果提供了task_id，则获取任务对象
        if task_id:
            from tasks.models import CrawlerTask
            try:
                self.task = CrawlerTask.objects.get(id=task_id)
            except CrawlerTask.DoesNotExist:
                self.task = None
        else:
            self.task = None
        
        # 如果提供了URL，则覆盖默认起始URL
        if url:
            self.start_urls = [url]
            # 从URL中提取允许的域名
            parsed_url = urlparse(url)
            self.allowed_domains = [parsed_url.netloc]

    def parse(self, response):
        """
        解析响应并提取数据
        简单模式：只爬取指定URL的页面内容
        完整模式：进行深度爬取，跟随网站内链接进行爬取
        """
        # 已访问的URL记录
        self.visited_urls.add(response.url)
        
        # 提取静态资源URL
        script_urls = response.css('script::attr(src)').getall()
        css_urls = response.css('link[rel="stylesheet"]::attr(href)').getall()
        img_urls = response.css('img::attr(src)').getall()
        
        # 规范化URL
        resources = []
        for url in script_urls + css_urls + img_urls:
            if url:
                absolute_url = urljoin(response.url, url.strip())
                resources.append(absolute_url)
        
        # 转换headers从bytes到str
        headers_dict = {}
        for key, value in response.headers.items():
            str_key = key.decode('utf-8', errors='ignore')
            str_value = [v.decode('utf-8', errors='ignore') for v in value]
            headers_dict[str_key] = str_value
        
        # 构建结果项
        yield {
            'url': response.url,
            'html_source': response.text,
            'headers': headers_dict,
            'resources': resources,
        }
        
        # 只有在完整模式下才继续爬取链接
        if self.mode == 'deep':
            # 提取页面中的链接
            link_extractor = LinkExtractor()
            links = link_extractor.extract_links(response)
            
            # 对每个链接进行处理
            for link in links:
                url = link.url
                text = link.text
                
                # 检查是否为内链或外链
                domain = urlparse(url).netloc
                is_internal = domain == self.allowed_domains[0]
                
                # 检查是否包含nofollow属性
                nofollow = 'nofollow' in link.attrs.get('rel', '')
                
                # 分类链接
                link_type = 'internal' if is_internal else 'external'
                if nofollow:
                    link_type += '_nofollow'
                
                # 存储链接
                CrawlerLink.objects.create(
                    task=self.task,
                    url=url,
                    internal_links=[],
                    external_links=[],
                    internal_nofollow_links=[],
                    external_nofollow_links=[]
                )
                
                # 如果是内链，继续爬取
                if is_internal and not nofollow and url not in self.visited_urls:
                    yield scrapy.Request(url, callback=self.parse)
        # 简单模式下不爬取其他链接，只处理当前URL

# Redis配置
REDIS_HOST = 'redis'  # 使用Docker容器名
REDIS_PORT = 6379

# 启用Scrapy-Redis组件
SCHEDULER = "scrapy_redis.scheduler.Scheduler"
DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"
SCHEDULER_PERSIST = True
SCHEDULER_QUEUE_CLASS = 'scrapy_redis.queue.PriorityQueue'

# Redis项目存储
ITEM_PIPELINES = {
    'scrapy_redis.pipelines.RedisPipeline': 300,
    'scrapy_engine.pipelines.DatabaseStoragePipeline': 400,
}

# 自定义Redis键
REDIS_START_URLS_KEY = '%(name)s:start_urls'
REDIS_START_URLS_AS_SET = False

# 爬虫并发设置
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 8

class LinkCollectorSpider(RedisSpider):
    name = "link_collector"
    redis_key = "link_collector:start_urls"
    
    def __init__(self, task_id=None, *args, **kwargs):
        super(LinkCollectorSpider, self).__init__(*args, **kwargs)
        self.task_id = task_id
        self.task = CrawlerTask.objects.get(id=task_id) if task_id else None
        self.start_domain = urlparse(self.task.url).netloc if self.task else None
        # 初始化已访问URL集合
        self.visited_urls = set()
    
    def parse(self, response):
        # 当前URL处理信息
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] 正在解析链接页面: {response.url}")
        
        # 检查URL是否已处理
        if response.url in self.visited_urls:
            print(f"[{now}] 跳过已处理的URL: {response.url}")
            return
            
        # 标记URL为已访问
        self.visited_urls.add(response.url)
        
        # 提取所有链接
        link_extractor = LinkExtractor()
        links = link_extractor.extract_links(response)
        
        for link in links:
            url = link.url
            text = link.text
            
            # 检查是否为内链或外链
            domain = urlparse(url).netloc
            is_internal = domain == self.start_domain
            
            # 检查是否包含nofollow属性
            nofollow = 'nofollow' in link.attrs.get('rel', '')
            
            # 分类链接
            link_type = 'internal' if is_internal else 'external'
            if nofollow:
                link_type += '_nofollow'
            
            # 存储链接
            CrawlerLink.objects.create(
                task=self.task,
                url=url,
                internal_links=[],
                external_links=[],
                internal_nofollow_links=[],
                external_nofollow_links=[]
            )
            
            # 如果是内链，继续爬取
            if is_internal and not nofollow and url not in self.visited_urls:
                yield scrapy.Request(url, callback=self.parse)
    
    def closed(self, reason):
        """爬虫关闭时的回调函数"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now}] ========== 链接收集爬虫关闭 ==========")
        print(f"[{now}] 任务ID: {self.task_id}")
        print(f"[{now}] 处理的URL数量: {len(self.visited_urls)}")
        print(f"[{now}] 关闭原因: {reason}")
        
        try:
            from tasks.task_runner import task_runner
            
            # 确保起始URL被标记为已处理
            if self.task and self.task.url:
                link, created = CrawlerLink.objects.get_or_create(
                    task=self.task,
                    url=self.task.url,
                    defaults={
                        'internal_links': [],
                        'external_links': [],
                        'internal_nofollow_links': [],
                        'external_nofollow_links': []
                    }
                )
                
            # 启动内容爬取阶段
            print(f"[{now}] 启动内容爬取阶段...")
            task_runner.start_content_crawling(self.task_id)
            
        except Exception as e:
            print(f"[{now}] 启动内容爬取阶段出错: {str(e)}")
        
        print(f"[{now}] ==================================\n")

class ContentCrawlerSpider(RedisSpider):
    name = "content_crawler"
    redis_key = "content_crawler:start_urls"
    
    def __init__(self, task_id=None, *args, **kwargs):
        super(ContentCrawlerSpider, self).__init__(*args, **kwargs)
        self.task_id = task_id
        self.task = CrawlerTask.objects.get(id=task_id) if task_id else None
    
    def parse(self, response):
        # 获取网页标题
        title = response.css('title::text').get()
        
        # 提取静态资源URL
        js_urls = response.css('script::attr(src)').getall()
        css_urls = response.css('link[rel="stylesheet"]::attr(href)').getall()
        img_urls = response.css('img::attr(src)').getall()
        ico_urls = response.css('link[rel="icon"], link[rel="shortcut icon"]::attr(href)').getall()
        
        # 规范化URL
        static_resources = []
        for url in js_urls + css_urls + img_urls + ico_urls:
            if url:
                absolute_url = urljoin(response.url, url.strip())
                resource_type = self._get_resource_type(absolute_url)
                static_resources.append({
                    'url': absolute_url,
                    'type': resource_type
                })
        
        # 转换headers
        headers_dict = {}
        for key, value in response.headers.items():
            str_key = key.decode('utf-8', errors='ignore')
            str_value = [v.decode('utf-8', errors='ignore') for v in value]
            headers_dict[str_key] = str_value
        
        # 保存爬取结果
        result = CrawlerResult.objects.create(
            task=self.task,
            url=response.url,
            title=title,
            html_source=response.text,
            headers=headers_dict,
            resources=static_resources
        )
        
        # 将静态资源URL添加到Redis队列进行爬取
        for resource in static_resources:
            StaticResource.objects.create(
                result=result,
                url=resource['url'],
                resource_type=resource['type'],
                status='pending'
            )
            
            # 添加到静态资源爬虫的Redis队列
            self.server.lpush(
                'static_crawler:start_urls', 
                json.dumps({
                    'url': resource['url'],
                    'result_id': result.id,
                    'resource_type': resource['type']
                })
            )
    
    def _get_resource_type(self, url):
        """根据URL确定资源类型"""
        path = urlparse(url).path.lower()
        if path.endswith(('.js')):
            return 'javascript'
        elif path.endswith(('.css')):
            return 'css'
        elif path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')):
            return 'image'
        elif path.endswith(('.ico', '.icon')):
            return 'icon'
        else:
            return 'other'

class StaticResourceSpider(RedisSpider):
    name = "static_crawler"
    redis_key = "static_crawler:start_urls"
    
    def parse(self, response):
        # 从队列获取元数据
        data = json.loads(response.meta.get('redis_meta'))
        result_id = data['result_id']
        resource_type = data['resource_type']
        
        # 获取静态资源
        try:
            resource = StaticResource.objects.get(
                result_id=result_id,
                url=response.url
            )
            
            # 计算内容的MD5哈希值
            content_hash = hashlib.md5(response.body).hexdigest()
            
            # 处理不同类型的资源
            if resource_type in ['javascript', 'css']:
                # 保存文本内容
                resource.content = response.text
                resource.content_hash = content_hash
            elif resource_type in ['image', 'icon']:
                # 仅保存二进制内容的哈希值
                resource.content = None  # 可选存储二进制内容
                resource.content_hash = content_hash
            
            # 更新头信息
            headers_dict = {}
            for key, value in response.headers.items():
                str_key = key.decode('utf-8', errors='ignore')
                str_value = [v.decode('utf-8', errors='ignore') for v in value]
                headers_dict[str_key] = str_value
            
            resource.headers = headers_dict
            resource.status = 'completed'
            resource.save()
            
            # 触发指纹匹配
            from fingerprints.utils import perform_resource_matching
            perform_resource_matching(resource)
            
        except StaticResource.DoesNotExist:
            pass  # 资源记录不存在
        except Exception as e:
            # 记录错误
            if 'resource' in locals():
                resource.status = 'failed'
                resource.error_message = str(e)
                resource.save()
