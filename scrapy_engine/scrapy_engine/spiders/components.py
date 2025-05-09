import scrapy
import json
from urllib.parse import urljoin


class ComponentsSpider(scrapy.Spider):
    name = "components"
    allowed_domains = ["example.com"]
    start_urls = ["http://example.com"]

    def __init__(self, url=None, mode='simple', depth=1, *args, **kwargs):
        super(ComponentsSpider, self).__init__(*args, **kwargs)
        self.url = url
        self.mode = mode
        self.depth = int(depth)
        self.visited_urls = set()
        
        # 如果提供了URL，则覆盖默认起始URL
        if url:
            self.start_urls = [url]
            # 从URL中提取允许的域名
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            self.allowed_domains = [parsed_url.netloc]

    def parse(self, response):
        """
        解析响应并提取数据
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
        
        # 如果是深度模式且当前深度未达到限制，则继续爬取链接
        if self.mode == 'deep' and len(self.visited_urls) < self.depth * 10:
            # 提取页面中的链接
            links = response.css('a::attr(href)').getall()
            
            # 对每个链接进行处理
            for link in links:
                if link:
                    # 将相对URL转为绝对URL
                    absolute_url = urljoin(response.url, link.strip())
                    
                    # 仅跟踪同域名下未访问过的URL
                    from urllib.parse import urlparse
                    parsed_url = urlparse(absolute_url)
                    
                    if (parsed_url.netloc in self.allowed_domains and 
                        absolute_url not in self.visited_urls and
                        not absolute_url.endswith(('.pdf', '.doc', '.xls', '.zip', '.rar', '.jpg', '.png', '.gif'))):
                        yield scrapy.Request(absolute_url, callback=self.parse)
