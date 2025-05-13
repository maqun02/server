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
    redis_key = None  # 禁用自动从Redis读取起始URL
    
    def __init__(self, *args, **kwargs):
        super(LinkSpider, self).__init__(*args, **kwargs)
        self.task_id = kwargs.get('task_id', None)
        self.start_url = kwargs.get('url', None)
        self.mode = kwargs.get('mode', 'simple')
        self.redis_key = kwargs.get('redis_key', None)
        self.allowed_domains = []
        
        print(f"[DEBUG - LINK SPIDER INIT] 初始化爬虫: 任务ID={self.task_id}, URL={self.start_url}, 模式={self.mode}")
        
        # 设置允许的域名
        if self.start_url:
            parsed_url = urlparse(self.start_url)
            self.domain = parsed_url.netloc
            self.allowed_domains = [self.domain]
            self.scheme = parsed_url.scheme
            self.base_url = f"{self.scheme}://{self.domain}"
            print(f"[DEBUG - LINK SPIDER DOMAIN] 允许域名: {self.domain}")
        
        # 初始化已访问URL集合
        self.visited_urls = set()
        
        # 初始化所有收集到的链接（包括已处理和未处理的）
        self.all_links = {
            'internal_links': set(),
            'external_links': set(),
            'internal_nofollow_links': set(),
            'external_nofollow_links': set()
        }
        
        # 打印爬虫启动信息
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now}] ========== 链接爬虫启动 ==========")
        print(f"[{now}] 任务ID: {self.task_id}")
        print(f"[{now}] 起始URL: {self.start_url}")
        print(f"[{now}] 爬取模式: {self.mode}")
        print(f"[{now}] 允许的域名: {self.allowed_domains}")
        print(f"[{now}] ==================================\n")
    
    def start_requests(self):
        """
        重写start_requests方法，确保使用命令行参数的起始URL
        """
        if not self.start_url:
            print("[ERROR] 未提供起始URL，爬虫无法启动")
            return
            
        print(f"[DEBUG - LINK SPIDER START] 开始请求起始URL: {self.start_url}")
        yield scrapy.Request(url=self.start_url, callback=self.parse)

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
        
        # 内部 URL 集合
        internal_links = set()
        external_links = set()
        internal_nofollow_links = set()
        external_nofollow_links = set()
        
        # 提取所有链接
        for a_tag in response.css('a'):
            href = a_tag.css('::attr(href)').get()
            if not href or href.startswith('#') or href.startswith('javascript:') or href.startswith('mailto:'):
                continue
                
            # 获取绝对URL
            absolute_url = response.urljoin(href)
            parsed_url = urlparse(absolute_url)
            
            # 规范化URL，移除锚点片段
            if parsed_url.fragment:
                absolute_url = absolute_url.split('#')[0]
            
            # 检查是否为nofollow链接
            is_nofollow = 'nofollow' in a_tag.css('::attr(rel)').get('') or \
                          'nofollow' in response.xpath(f"//a[@href='{href}']/@rel").get('')
            
            # 根据域名和nofollow属性分类链接
            if parsed_url.netloc == self.domain:
                if is_nofollow:
                    internal_nofollow_links.add(absolute_url)
                    self.all_links['internal_nofollow_links'].add(absolute_url)
                else:
                    internal_links.add(absolute_url)
                    self.all_links['internal_links'].add(absolute_url)
            else:
                if is_nofollow:
                    external_nofollow_links.add(absolute_url)
                    self.all_links['external_nofollow_links'].add(absolute_url)
                else:
                    external_links.add(absolute_url)
                    self.all_links['external_links'].add(absolute_url)
        
        # 创建链接项
        item = LinkItem()
        item['task_id'] = self.task_id
        item['url'] = response.url
        item['internal_links'] = list(internal_links)
        item['external_links'] = list(external_links)
        item['internal_nofollow_links'] = list(internal_nofollow_links)
        item['external_nofollow_links'] = list(external_nofollow_links)
        
        print(f"[{now}] 页面 {response.url} 解析完成")
        print(f"[{now}] 发现内链: {len(internal_links)}, 外链: {len(external_links)}")
        print(f"[{now}] 发现nofollow内链: {len(internal_nofollow_links)}, nofollow外链: {len(external_nofollow_links)}")
        
        yield item
        
        # 仅在深度模式下跟随内部链接
        if self.mode == 'deep':
            for url in internal_links:
                if url not in self.visited_urls:
                    print(f"[{now}] 将爬取内部链接: {url}")
                    yield scrapy.Request(url=url, callback=self.parse)
        else:
            print(f"[{now}] 简单模式，不跟随内部链接")
    
    def closed(self, reason):
        """爬虫关闭时的回调函数"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now}] ========== 链接爬虫关闭 ==========")
        print(f"[{now}] 任务ID: {self.task_id}")
        print(f"[{now}] 处理的URL数量: {len(self.visited_urls)}")
        print(f"[{now}] 总计收集链接:")
        print(f"[{now}] - 内链: {len(self.all_links['internal_links'])}")
        print(f"[{now}] - 外链: {len(self.all_links['external_links'])}")
        print(f"[{now}] - nofollow内链: {len(self.all_links['internal_nofollow_links'])}")
        print(f"[{now}] - nofollow外链: {len(self.all_links['external_nofollow_links'])}")
        print(f"[{now}] 关闭原因: {reason}")
        print(f"[{now}] ==================================\n")
        
        # 将所有收集到的链接写入Redis，以便后续内容爬虫使用
        if self.redis_key:
            all_urls = set()
            # 确保首先爬取起始URL
            all_urls.add(self.start_url)
            # 添加所有内链和外链（包括nofollow）
            all_urls.update(self.all_links['internal_links'])
            all_urls.update(self.all_links['internal_nofollow_links'])
            if self.mode == 'deep':  # 深度模式下也爬取外链
                all_urls.update(self.all_links['external_links'])
                all_urls.update(self.all_links['external_nofollow_links'])
            
            # 将URL列表写入Redis
            print(f"[{now}] 将收集到的URL推送到Redis: {self.redis_key}_urls")
            
            # 这里没有实际实现Redis推送，但会在pipeline中处理
            print(f"[{now}] 总计推送URL数量: {len(all_urls)}") 