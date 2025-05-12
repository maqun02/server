import scrapy
import re
import json
import uuid
import datetime
from urllib.parse import urlparse, urljoin
from scrapy_redis.spiders import RedisSpider
from ..items import LinkItem

class LinkSpider(RedisSpider):
    """
    爬取网站所有链接的爬虫
    记录内链、外链、nofollow链接等
    """
    name = "link_spider"
    
    def __init__(self, *args, **kwargs):
        super(LinkSpider, self).__init__(*args, **kwargs)
        self.task_id = kwargs.get('task_id', None)
        self.start_url = kwargs.get('start_url', None)
        self.allowed_domains = []
        
        # 设置允许的域名
        if self.start_url:
            parsed_url = urlparse(self.start_url)
            self.domain = parsed_url.netloc
            self.allowed_domains = [self.domain]
            self.scheme = parsed_url.scheme
            self.base_url = f"{self.scheme}://{self.domain}"
        
        # 初始化已访问URL集合
        self.visited_urls = set()
        
        # 打印爬虫启动信息
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now}] ========== 链接爬虫启动 ==========")
        print(f"[{now}] 任务ID: {self.task_id}")
        print(f"[{now}] 起始URL: {self.start_url}")
        print(f"[{now}] 允许的域名: {self.allowed_domains}")
        print(f"[{now}] ==================================\n")

    def parse(self, response):
        """
        解析页面中的链接
        分类为内链、外链、nofollow链接等
        """
        # 当前URL处理信息
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] 正在解析链接页面: {response.url}")
        
        # 检查URL是否已处理
        if response.url in self.visited_urls:
            print(f"[{now}] 跳过已处理的URL: {response.url}")
            return
        
        # 标记URL为已访问
        self.visited_urls.add(response.url)
        
        # 处理链接
        internal_links = []
        external_links = []
        internal_nofollow_links = []
        external_nofollow_links = []
        
        # 提取所有链接
        for href in response.css('a::attr(href)').getall():
            if not href or href.startswith('#') or href.startswith('javascript:'):
                continue
                
            # 获取绝对URL
            absolute_url = response.urljoin(href)
            parsed_url = urlparse(absolute_url)
            
            # 检查是否为nofollow链接
            is_nofollow = False
            for a_tag in response.css('a[href="{}"]'.format(href)):
                if 'nofollow' in a_tag.css('::attr(rel)').get(''):
                    is_nofollow = True
                    break
            
            # 根据域名和nofollow属性分类链接
            if parsed_url.netloc == self.domain:
                if is_nofollow:
                    internal_nofollow_links.append(absolute_url)
                else:
                    internal_links.append(absolute_url)
            else:
                if is_nofollow:
                    external_nofollow_links.append(absolute_url)
                else:
                    external_links.append(absolute_url)
        
        # 创建链接项
        item = LinkItem()
        item['task_id'] = self.task_id
        item['url'] = response.url
        item['internal_links'] = internal_links
        item['external_links'] = external_links
        item['internal_nofollow_links'] = internal_nofollow_links
        item['external_nofollow_links'] = external_nofollow_links
        
        print(f"[{now}] 页面 {response.url} 解析完成")
        print(f"[{now}] 发现内链: {len(internal_links)}, 外链: {len(external_links)}")
        print(f"[{now}] 发现nofollow内链: {len(internal_nofollow_links)}, nofollow外链: {len(external_nofollow_links)}")
        
        yield item
        
        # 仅跟随内部链接
        for url in internal_links:
            if url not in self.visited_urls:
                yield scrapy.Request(url=url, callback=self.parse)
                
    def closed(self, reason):
        """爬虫关闭时的回调函数"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now}] ========== 链接爬虫关闭 ==========")
        print(f"[{now}] 任务ID: {self.task_id}")
        print(f"[{now}] 处理的URL数量: {len(self.visited_urls)}")
        print(f"[{now}] 关闭原因: {reason}")
        
        # 导入任务运行器，确保起始URL被爬取内容
        try:
            from tasks.task_runner import task_runner
            from tasks.models import CrawlerTask
            from results.models import CrawlerLink
            
            # 获取任务信息
            task = CrawlerTask.objects.get(id=self.task_id)
            
            # 确保起始URL被添加到链接表中
            if self.start_url:
                link, created = CrawlerLink.objects.get_or_create(
                    task=task,
                    url=self.start_url,
                    defaults={
                        'internal_links': [],
                        'external_links': [],
                        'internal_nofollow_links': [],
                        'external_nofollow_links': []
                    }
                )
                
                # 如果起始URL尚未被标记为已处理，则将其标记
                if not link.is_crawled:
                    print(f"[{now}] 确保起始URL: {self.start_url} 已添加到链接表中")
            
            # 启动内容爬取阶段
            print(f"[{now}] 启动内容爬取阶段...")
            task_runner.start_content_crawling(self.task_id)
            
        except Exception as e:
            print(f"[{now}] 启动内容爬取阶段出错: {str(e)}")
            
        print(f"[{now}] ==================================\n") 