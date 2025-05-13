# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class LinkItem(scrapy.Item):
    """
    链接爬虫的数据项 - 存储网页中的链接信息
    """
    task_id = scrapy.Field()  # 任务ID
    url = scrapy.Field()  # 页面URL
    internal_links = scrapy.Field()  # 内链列表
    external_links = scrapy.Field()  # 外链列表
    internal_nofollow_links = scrapy.Field()  # 内链nofollow列表
    external_nofollow_links = scrapy.Field()  # 外链nofollow列表


class ContentItem(scrapy.Item):
    """
    内容爬虫的数据项 - 存储网页内容
    """
    task_id = scrapy.Field()  # 任务ID
    url = scrapy.Field()  # 页面URL
    title = scrapy.Field()  # 页面标题
    html_source = scrapy.Field()  # HTML源码
    headers = scrapy.Field()  # HTTP响应头
    resources = scrapy.Field()  # 静态资源列表 [{url, type}, ...]
    error = scrapy.Field()  # 错误信息（如有）


class ResourceItem(scrapy.Item):
    """
    资源爬虫的数据项 - 存储静态资源内容
    """
    task_id = scrapy.Field()  # 任务ID
    page_url = scrapy.Field()  # 所属页面URL
    url = scrapy.Field()  # 资源URL
    resource_type = scrapy.Field()  # 资源类型：js, css, image, ico, other
    content = scrapy.Field()  # 资源内容
    md5_hash = scrapy.Field()  # MD5哈希值
    headers = scrapy.Field()  # 资源响应头
    error = scrapy.Field()  # 错误信息（如有）
