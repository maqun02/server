# Scrapy settings for scrapy_engine project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = "scrapy_engine"

SPIDER_MODULES = ["scrapy_engine.spiders"]
NEWSPIDER_MODULE = "scrapy_engine.spiders"

# Django集成设置
import os
import sys
import django

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../../')

# 设置Django环境
os.environ['DJANGO_SETTINGS_MODULE'] = 'project.settings'
django.setup()

# Crawl responsibly by identifying yourself (and your website) on the user-agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Configure maximum concurrent requests performed by Scrapy (default: 16)
CONCURRENT_REQUESTS = 32

# Configure a delay for requests for the same website (default: 0)
DOWNLOAD_DELAY = 0.25

# Enable or disable downloader middlewares
DOWNLOADER_MIDDLEWARES = {
   "scrapy_engine.middlewares.CustomUserAgentMiddleware": 543,
   "scrapy_engine.middlewares.CustomRetryMiddleware": 550,
   # Splash中间件
   'scrapy_splash.SplashCookiesMiddleware': 723,
   'scrapy_splash.SplashMiddleware': 725,
   'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware': 810,
}

# Configure item pipelines
ITEM_PIPELINES = {
   "scrapy_engine.pipelines.LinkPipeline": 100,
   "scrapy_engine.pipelines.ContentPipeline": 200,
   "scrapy_engine.pipelines.ResourcePipeline": 300,
   "scrapy_engine.pipelines.FingerprintPipeline": 400,
}

# Redis设置（从环境变量中获取）
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_USERNAME = os.environ.get('REDIS_USERNAME', '')
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', '')
REDIS_DB = int(os.environ.get('REDIS_DB', 0))

# 启用Scrapy-Redis支持
SCHEDULER = "scrapy_redis.scheduler.Scheduler"
DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"
SCHEDULER_PERSIST = True
SCHEDULER_QUEUE_CLASS = 'scrapy_redis.queue.SpiderPriorityQueue'
SCHEDULER_FLUSH_ON_START = True  # 启动时清空队列
REDIS_START_URLS_AS_SET = False  # 使用列表存储起始URL

# Redis URL（包含认证信息）
if REDIS_USERNAME and REDIS_PASSWORD:
    REDIS_URL = f'redis://{REDIS_USERNAME}:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
else:
    REDIS_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'

# Splash设置
SPLASH_URL = os.environ.get('SPLASH_URL', 'http://splash:8050')
DUPEFILTER_CLASS = 'scrapy_splash.SplashAwareDupeFilter'
HTTPCACHE_STORAGE = 'scrapy_splash.SplashAwareFSCacheStorage'
SPLASH_COOKIES_DEBUG = False
SPIDER_MIDDLEWARES = {
    'scrapy_splash.SplashDeduplicateArgsMiddleware': 100,
}

# 请求超时设置
DOWNLOAD_TIMEOUT = 30

# 重试设置
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429, 403]

# Cookie设置
COOKIES_ENABLED = True  # 启用Cookie支持

# 允许重定向
REDIRECT_ENABLED = True
REDIRECT_MAX_TIMES = 5

# 并发设置
CONCURRENT_REQUESTS_PER_DOMAIN = 8
CONCURRENT_REQUESTS_PER_IP = 8

# 禁用HTTP缓存
HTTPCACHE_ENABLED = False

# 默认请求头
DEFAULT_REQUEST_HEADERS = {
   "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
   "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
   "Connection": "keep-alive",
   "Accept-Encoding": "gzip, deflate, br",
   "Upgrade-Insecure-Requests": "1",
   "Sec-Fetch-Dest": "document",
   "Sec-Fetch-Mode": "navigate",
   "Sec-Fetch-Site": "none",
   "Sec-Fetch-User": "?1"
}

# 禁用某些页面特性，提高性能
MEDIA_ALLOW_REDIRECTS = True
URLLENGTH_LIMIT = 5000

# 设置日志级别
LOG_LEVEL = 'INFO'  # 正式环境使用INFO级别，开发时使用DEBUG
LOG_ENABLED = True

# 启用自动限速
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 3.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 5.0
AUTOTHROTTLE_DEBUG = False

# 设置请求处理范围
DEPTH_LIMIT = 3  # 限制爬取深度
DEPTH_PRIORITY = 1  # 广度优先爬取
DEPTH_STATS_VERBOSE = True

# 允许的图片格式
IMAGES_THUMBS = {
    'small': (50, 50),
    'medium': (100, 100),
}

# 启用UTF-8编码
FEED_EXPORT_ENCODING = 'utf-8'
