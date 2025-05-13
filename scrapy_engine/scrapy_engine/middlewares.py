# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals
import random
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message

# useful for handling different item types with a single interface
from itemadapter import is_item, ItemAdapter


class ScrapyEngineSpiderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    def process_spider_output(self, response, result, spider):
        # Called with the results returned from the Spider, after
        # it has processed the response.

        # Must return an iterable of Request, or item objects.
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Request or item objects.
        pass

    def process_start_requests(self, start_requests, spider):
        # Called with the start requests of the spider, and works
        # similarly to the process_spider_output() method, except
        # that it doesn't have a response associated.

        # Must return only requests (not items).
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class ScrapyEngineDownloaderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the downloader middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        # Called for each request that goes through the downloader
        # middleware.

        # Must either:
        # - return None: continue processing this request
        # - or return a Response object
        # - or return a Request object
        # - or raise IgnoreRequest: process_exception() methods of
        #   installed downloader middleware will be called
        return None

    def process_response(self, request, response, spider):
        # Called with the response returned from the downloader.

        # Must either;
        # - return a Response object
        # - return a Request object
        # - or raise IgnoreRequest
        return response

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        pass

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class CustomUserAgentMiddleware:
    """
    自定义User-Agent中间件
    在每个请求中随机设置UA，避免被目标网站封锁
    """
    
    user_agents = [
        # Chrome
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
        # Firefox
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0',
        # Edge
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59',
        # Safari
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    ]
    
    def __init__(self, user_agent=''):
        self.user_agent = user_agent
    
    @classmethod
    def from_crawler(cls, crawler):
        o = cls(crawler.settings.get('USER_AGENT'))
        return o
    
    def process_request(self, request, spider):
        if self.user_agent:
            request.headers['User-Agent'] = random.choice(self.user_agents)
            spider.logger.debug(f'使用随机User-Agent: {request.headers["User-Agent"]}')


class CustomRetryMiddleware(RetryMiddleware):
    """
    自定义重试中间件
    扩展默认的重试机制，添加自定义重试逻辑
    """
    
    def __init__(self, settings):
        super(CustomRetryMiddleware, self).__init__(settings)
        self.retry_http_codes = settings.getlist('RETRY_HTTP_CODES')
        self.max_retry_times = settings.getint('RETRY_TIMES', 3)
        spider_exceptions = [
            'twisted.internet.timeout.TimeoutError',
            'twisted.internet.error.ConnectionRefusedError',
            'twisted.internet.error.ConnectionLost',
            'twisted.internet.error.TCPTimedOutError',
        ]
        
    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings)
    
    def process_response(self, request, response, spider):
        if request.meta.get('dont_retry', False):
            return response
        
        # 处理重试HTTP状态码
        if response.status in self.retry_http_codes:
            reason = f'重试 ({response.status})'
            return self._retry(request, reason, spider) or response
        
        # 处理其他需要重试的情况，如内容过小
        if response.status == 200 and len(response.body) < 100:
            # 响应太小，可能是被拦截或限制了
            reason = f'响应内容过小 ({len(response.body)} bytes)'
            return self._retry(request, reason, spider) or response
            
        return response
    
    def process_exception(self, request, exception, spider):
        # 调用父类的处理方法
        retry_request = super(CustomRetryMiddleware, self).process_exception(request, exception, spider)
        if retry_request:
            spider.logger.info(f'因异常重试: {exception.__class__.__name__} - {request.url}')
        return retry_request
