import logging
import re
import json
import hashlib
import datetime
import urllib.parse
from scrapy import Spider, Request
from scrapy_redis.spiders import RedisSpider
from scrapy_splash import SplashRequest
from scrapy.utils.url import url_is_from_any_domain
from ..items import ContentItem

# Splash Lua脚本，用于动态渲染页面并收集资源信息
SPLASH_LUA_SCRIPT = """
function main(splash, args)
    splash:set_user_agent(args.user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
    
    -- 存储所有资源信息
    local all_resources = {}
    
    -- 资源加载计数器
    local resource_counter = 0
    
    -- 监听所有资源加载
    splash:on_request(function(request)
        resource_counter = resource_counter + 1
    end)
    
    -- 存储资源响应
    splash:on_response(function(response)
        local resource = {
            url = response.url,
            status = response.status,
            content_type = response.headers["Content-Type"] or "",
            headers = response.headers
        }
        table.insert(all_resources, resource)
    end)
    
    -- 设置超时 (默认30秒)
    local timeout = args.timeout or 30
    splash:set_timeout(timeout)
    
    -- 访问URL
    local ok, reason = splash:go(args.url)
    if not ok then
        return {
            error = reason,
            resources = all_resources
        }
    end
    
    -- 等待页面渲染完成
    splash:wait(1.5)
    
    -- 允许JavaScript执行
    splash:autoload([[
        window.wasAjaxCalled = false;
        var originalXHR = window.XMLHttpRequest;
        window.XMLHttpRequest = function() {
            var xhr = new originalXHR();
            xhr.addEventListener('readystatechange', function() {
                if (xhr.readyState === 4) {
                    window.wasAjaxCalled = true;
                }
            });
            return xhr;
        };
    ]])
    
    -- 等待AJAX请求
    splash:wait_for_resume(function(splash)
        splash:evaljs([[
            function checkAjaxFinished() {
                if (window.wasAjaxCalled) {
                    splash.resume();
                } else {
                    setTimeout(checkAjaxFinished, 100);
                }
            }
            setTimeout(checkAjaxFinished, 300);
            setTimeout(function() { splash.resume(); }, 2000);
        ]])
    end)
    
    -- 滚动到页面底部以触发懒加载
    splash:evaljs([[
        function scrollToBottom() {
            window.scrollTo(0, document.body.scrollHeight);
        }
        scrollToBottom();
    ]])
    
    -- 再次等待页面完全加载
    splash:wait(1.0)
    
    -- 收集所有静态资源链接
    local js_links = splash:evaljs([[
        var links = [];
        var scripts = document.querySelectorAll('script[src]');
        for (var i = 0; i < scripts.length; i++) {
            links.push({
                url: scripts[i].src,
                type: 'js'
            });
        }
        return links;
    ]])
    
    local css_links = splash:evaljs([[
        var links = [];
        var styles = document.querySelectorAll('link[rel="stylesheet"], link[type="text/css"]');
        for (var i = 0; i < styles.length; i++) {
            links.push({
                url: styles[i].href,
                type: 'css'
            });
        }
        return links;
    ]])
    
    local image_links = splash:evaljs([[
        var links = [];
        var images = document.querySelectorAll('img[src]');
        for (var i = 0; i < images.length; i++) {
            if(images[i].src && images[i].src.trim() !== '') {
                links.push({
                    url: images[i].src,
                    type: 'image'
                });
            }
        }
        return links;
    ]])
    
    local icon_links = splash:evaljs([[
        var links = [];
        var icons = document.querySelectorAll('link[rel="icon"], link[rel="shortcut icon"]');
        for (var i = 0; i < icons.length; i++) {
            if(icons[i].href && icons[i].href.trim() !== '') {
                links.push({
                    url: icons[i].href,
                    type: 'ico'
                });
            }
        }
        return links;
    ]])
    
    local other_links = splash:evaljs([[
        var links = [];
        var others = document.querySelectorAll('link:not([rel="stylesheet"]):not([rel="icon"]):not([rel="shortcut icon"])');
        for (var i = 0; i < others.length; i++) {
            if(others[i].href && others[i].href.trim() !== '') {
                var ext = others[i].href.split('.').pop().toLowerCase();
                if(['woff', 'woff2', 'ttf', 'eot', 'mp4', 'webm', 'ogg', 'mp3', 'wav', 'pdf'].indexOf(ext) >= 0) {
                    links.push({
                        url: others[i].href,
                        type: 'other'
                    });
                }
            }
        }
        return links;
    ]])
    
    -- 合并所有静态资源链接
    local static_resources = {}
    for _, resource in ipairs(js_links) do
        table.insert(static_resources, resource)
    end
    for _, resource in ipairs(css_links) do
        table.insert(static_resources, resource)
    end
    for _, resource in ipairs(image_links) do
        table.insert(static_resources, resource)
    end
    for _, resource in ipairs(icon_links) do
        table.insert(static_resources, resource)
    end
    for _, resource in ipairs(other_links) do
        table.insert(static_resources, resource)
    end
    
    -- 获取页面标题
    local title = splash:evaljs("document.title")
    
    return {
        html = splash:html(),
        title = title,
        png = splash:png(),
        har = splash:har(),
        url = splash:url(),
        resources = static_resources,
        all_resources = all_resources,
        cookies = splash:get_cookies(),
        headers = splash:get_all_headers()
    }
end
"""

class ContentSpider(RedisSpider):
    """
    内容爬虫 - 第二层爬虫，用于爬取页面内容、标题、响应头和静态资源链接
    使用Splash进行动态渲染
    """
    name = 'content_spider'
    redis_key = "%(spider)s:start_urls"
    
    def __init__(self, *args, **kwargs):
        super(ContentSpider, self).__init__(*args, **kwargs)
        self.task_id = kwargs.get('task_id', None)
        self.urls = kwargs.get('urls', [])
        self.redis_key = kwargs.get('redis_key', None)
        self.timeout = kwargs.get('timeout', 30)
        
        if self.redis_key:
            self.redis_key = f"{self.redis_key}_urls"
            
        # 静态资源集合
        self.all_resources = set()
        
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.info(f"\n[{now}] ========== 内容爬虫启动 ==========")
        self.logger.info(f"[{now}] 任务ID: {self.task_id}")
        self.logger.info(f"[{now}] Redis键: {self.redis_key}")
        self.logger.info(f"[{now}] 初始URL数量: {len(self.urls)}")
        self.logger.info(f"[{now}] ==================================\n")
    
    def make_request_from_data(self, data):
        """
        从Redis获取URL数据并创建请求
        """
        url = data.decode('utf-8')
        self.logger.info(f"从Redis接收到URL: {url}")
        return self.make_requests_to_url(url)
    
    def make_requests_to_url(self, url):
        """
        为URL创建Splash请求
        """
        self.logger.info(f"创建Splash请求: {url}")
        return SplashRequest(
            url=url,
            callback=self.parse,
            endpoint='execute',
            args={
                'lua_source': SPLASH_LUA_SCRIPT,
                'timeout': self.timeout,
                'url': url
            },
            meta={'original_url': url}
        )
        
    def start_requests(self):
        """
        如果提供了URL列表，则直接使用这些URL开始爬取
        否则从Redis获取URL
        """
        if self.urls:
            for url in self.urls:
                self.logger.info(f"使用提供的URL开始爬取: {url}")
                yield self.make_requests_to_url(url)
        else:
            self.logger.info(f"未提供URL列表，等待从Redis ({self.redis_key}) 获取URL")
            # 让父类处理从Redis获取URL
            for req in super(ContentSpider, self).start_requests():
                yield req

    def parse(self, response):
        """解析Splash返回的页面内容、标题、响应头和静态资源链接"""
        original_url = response.meta.get('original_url', response.url)
        
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.info(f"[{now}] 正在解析页面内容: {original_url}")
        
        # 从Splash返回中提取数据
        try:
            # 检查是否有错误
            error = None
            if 'error' in response.data:
                error = response.data['error']
                self.logger.error(f"Splash渲染错误: {error}")
            
            # 提取页面标题
            title = response.data.get('title', '').strip()
            
            # 提取HTML源码
            html_source = response.data.get('html', '')
            
            # 提取响应头
            headers = dict(response.data.get('headers', {}))
            
            # 提取静态资源
            static_resources = []
            resource_map = {}  # 用于去重
            
            # 处理从Splash中获取的资源
            for resource in response.data.get('resources', []):
                url = resource.get('url', '')
                if not url or url in resource_map:
                    continue
                    
                resource_map[url] = True
                resource_type = resource.get('type', 'other')
                
                static_resources.append({
                    'url': url,
                    'type': resource_type
                })
                
                # 添加到全局资源集合
                self.all_resources.add((url, resource_type, original_url))
            
            # 创建内容项
            content_item = ContentItem(
                task_id=self.task_id,
                url=original_url,
                title=title,
                html_source=html_source,
                headers=headers,
                resources=static_resources,
                error=error
            )
            
            self.logger.info(f"解析完成: URL={original_url}, 标题='{title}', 资源数量={len(static_resources)}")
            
            yield content_item
            
        except Exception as e:
            self.logger.error(f"解析页面内容时发生错误: {str(e)}")
            # 创建一个带有错误信息的内容项
            content_item = ContentItem(
                task_id=self.task_id,
                url=original_url,
                title='',
                html_source='',
                headers={},
                resources=[],
                error=str(e)
            )
            yield content_item
    
    def closed(self, reason):
        """爬虫关闭时的回调函数"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.info(f"\n[{now}] ========== 内容爬虫关闭 ==========")
        self.logger.info(f"[{now}] 任务ID: {self.task_id}")
        self.logger.info(f"[{now}] 收集的资源总数: {len(self.all_resources)}")
        self.logger.info(f"[{now}] 关闭原因: {reason}")
        self.logger.info(f"[{now}] ==================================\n")
        
        # 将所有收集到的资源URL推送到Redis，供资源爬虫使用
        if self.redis_key and self.all_resources:
            resource_key = f"{self.redis_key.replace('_urls', '')}_resources"
            self.logger.info(f"将资源URL推送到Redis: {resource_key}, 数量: {len(self.all_resources)}")
            
            # 在pipeline中实现Redis推送 