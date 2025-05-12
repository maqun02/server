# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class LinkItem(scrapy.Item):
    """链接爬取结果项"""
    task_id = scrapy.Field()  # 关联的任务ID
    url = scrapy.Field()  # 原始URL
    internal_links = scrapy.Field()  # 内链列表
    external_links = scrapy.Field()  # 外链列表
    internal_nofollow_links = scrapy.Field()  # 内链nofollow列表
    external_nofollow_links = scrapy.Field()  # 外链nofollow列表
    status = scrapy.Field()  # 状态码


class ContentItem(scrapy.Item):
    """内容爬取结果项"""
    task_id = scrapy.Field()  # 关联的任务ID
    url = scrapy.Field()  # 原始URL
    title = scrapy.Field()  # 网页标题
    headers = scrapy.Field()  # 响应头
    html_content = scrapy.Field()  # HTML内容
    status = scrapy.Field()  # 状态码
    static_resources = scrapy.Field()  # 静态资源链接列表


class StaticResourceItem(scrapy.Item):
    """静态资源爬取结果项"""
    task_id = scrapy.Field()  # 关联的任务ID
    url = scrapy.Field()  # 资源URL
    content_url = scrapy.Field()  # 来源内容页URL
    resource_type = scrapy.Field()  # 资源类型: js, css, image, ico等
    content = scrapy.Field()  # 资源内容
    md5 = scrapy.Field()  # MD5哈希值 (用于图片和ico)
    status = scrapy.Field()  # 状态码
