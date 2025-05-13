import logging
import json
import hashlib
import datetime
import re
import os
from urllib.parse import urlparse
from scrapy import Spider
# 修改导入以避免循环依赖
from django.apps import apps
from django.db.models import Q

class FingerprintMatcherSpider(Spider):
    """
    指纹匹配爬虫 - 第四层爬虫，用于匹配已爬取内容中的组件指纹
    """
    name = 'fingerprint_matcher'
    start_urls = []  # 不需要爬取URL，只需要处理已爬取的内容
    
    def __init__(self, task_id=None, *args, **kwargs):
        super(FingerprintMatcherSpider, self).__init__(*args, **kwargs)
        self.task_id = task_id
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 动态获取模型，避免循环导入
        self.CrawlerResult = apps.get_model('results', 'CrawlerResult')
        self.StaticResource = apps.get_model('results', 'StaticResource')
        self.IdentifiedComponent = apps.get_model('results', 'IdentifiedComponent')
        self.ComponentMatcher = apps.get_model('fingerprints', 'ComponentMatcher')
        
        # 统计信息
        self.total_pages = 0
        self.total_resources = 0
        self.total_components = 0
        
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.info(f"\n[{now}] ========== 指纹匹配爬虫启动 ==========")
        self.logger.info(f"[{now}] 任务ID: {self.task_id}")
        self.logger.info(f"[{now}] ==================================\n")
        
        # 加载所有指纹
        self.reload_fingerprints()
    
    def reload_fingerprints(self):
        """重新加载所有指纹"""
        try:
            # 使用动态导入
            from fingerprints.utils import component_matcher
            component_matcher.load_fingerprints()
            self.logger.info(f"成功加载指纹: {len(component_matcher.fingerprints)}个")
        except Exception as e:
            self.logger.error(f"加载指纹失败: {str(e)}")
    
    def start_requests(self):
        """由于不需要爬取URL，直接开始匹配处理"""
        yield self.process_results_request()
    
    def process_results_request(self):
        """开始处理爬取结果并匹配指纹"""
        try:
            # 查询与任务相关的爬取结果
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.logger.info(f"[{now}] 开始处理任务 {self.task_id} 的爬取结果")
            
            # 获取所有页面爬取结果
            crawler_results = self.CrawlerResult.objects.filter(task_id=self.task_id)
            self.total_pages = crawler_results.count()
            self.logger.info(f"找到 {self.total_pages} 个页面结果")
            
            # 处理HTML内容
            for result in crawler_results:
                self.match_html_content(result)
            
            # 获取所有静态资源
            static_resources = self.StaticResource.objects.filter(task_id=self.task_id)
            self.total_resources = static_resources.count()
            self.logger.info(f"找到 {self.total_resources} 个静态资源")
            
            # 处理静态资源
            for resource in static_resources:
                self.match_resource_content(resource)
            
            # 完成处理
            self.logger.info(f"[{now}] 指纹匹配完成，识别到 {self.total_components} 个组件")
            
        except Exception as e:
            self.logger.error(f"处理结果时出错: {str(e)}")
        
        # 返回一个空请求以完成爬虫
        return None
    
    def match_html_content(self, result):
        """匹配HTML内容中的组件指纹"""
        try:
            if not result.html_source:
                self.logger.warning(f"页面 {result.url} 没有HTML内容，跳过")
                return
            
            # 对HTML内容进行指纹匹配
            from fingerprints.utils import component_matcher
            matches = component_matcher.match(result.html_source)
            
            if matches:
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.logger.info(f"[{now}] 页面 {result.url} 匹配到 {len(matches)} 个组件")
                
                # 保存识别的组件
                for component_name, keyword in matches:
                    # 检查是否已存在相同组件
                    exists = self.IdentifiedComponent.objects.filter(
                        task_id=self.task_id,
                        result=result,
                        component=component_name,
                        keyword=keyword,
                        match_type='html'
                    ).exists()
                    
                    if not exists:
                        self.IdentifiedComponent.objects.create(
                            task_id=self.task_id,
                            result=result,
                            component=component_name,
                            keyword=keyword,
                            match_type='html'
                        )
                        self.total_components += 1
        
        except Exception as e:
            self.logger.error(f"匹配HTML内容时出错 (URL: {result.url}): {str(e)}")
    
    def match_resource_content(self, resource):
        """匹配静态资源内容中的组件指纹"""
        try:
            # 对于图片和图标类型资源，只检查MD5
            if resource.resource_type in ['image', 'ico']:
                if resource.md5_hash:
                    self.match_md5_hash(resource)
                return
            
            # 对于JS和CSS等文本内容，进行内容匹配
            if resource.content and resource.resource_type in ['js', 'css', 'other']:
                try:
                    # 尝试将二进制内容解码为文本
                    content = resource.content.decode('utf-8', errors='ignore')
                    # 对内容进行指纹匹配
                    from fingerprints.utils import component_matcher
                    matches = component_matcher.match(content)
                    
                    if matches:
                        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        self.logger.info(f"[{now}] 资源 {resource.url} 匹配到 {len(matches)} 个组件")
                        
                        # 保存识别的组件
                        for component_name, keyword in matches:
                            # 检查是否已存在相同组件
                            exists = self.IdentifiedComponent.objects.filter(
                                task_id=self.task_id,
                                resource=resource,
                                component=component_name,
                                keyword=keyword,
                                match_type=resource.resource_type
                            ).exists()
                            
                            if not exists:
                                self.IdentifiedComponent.objects.create(
                                    task_id=self.task_id,
                                    resource=resource,
                                    component=component_name,
                                    keyword=keyword,
                                    match_type=resource.resource_type
                                )
                                self.total_components += 1
                except Exception as e:
                    self.logger.error(f"解码资源内容时出错 (URL: {resource.url}): {str(e)}")
        
        except Exception as e:
            self.logger.error(f"匹配资源内容时出错 (URL: {resource.url}): {str(e)}")
    
    def match_md5_hash(self, resource):
        """匹配资源的MD5哈希值"""
        # 这里可以实现与已知MD5指纹的匹配
        # 目前仅记录图标的MD5哈希值
        if resource.resource_type == 'ico' and resource.md5_hash:
            self.logger.info(f"图标资源 {resource.url} 的MD5值: {resource.md5_hash}")
            
            # 检查是否已存在相同图标组件
            exists = self.IdentifiedComponent.objects.filter(
                task_id=self.task_id,
                resource=resource,
                keyword=resource.md5_hash,
                match_type='ico'
            ).exists()
            
            if not exists:
                # 创建一个以MD5为标识的图标组件
                # 这里只是记录MD5，没有具体的组件名称匹配
                # 实际应用中，应该有一个MD5到组件的映射表
                domain = urlparse(resource.url).netloc
                self.IdentifiedComponent.objects.create(
                    task_id=self.task_id,
                    resource=resource,
                    component=f"Icon ({domain})",
                    keyword=resource.md5_hash,
                    match_type='ico'
                )
                self.total_components += 1
    
    def closed(self, reason):
        """爬虫关闭时的回调函数"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.info(f"\n[{now}] ========== 指纹匹配爬虫关闭 ==========")
        self.logger.info(f"[{now}] 任务ID: {self.task_id}")
        self.logger.info(f"[{now}] 处理统计:")
        self.logger.info(f"[{now}] - 页面数: {self.total_pages}")
        self.logger.info(f"[{now}] - 资源数: {self.total_resources}")
        self.logger.info(f"[{now}] - 识别组件数: {self.total_components}")
        self.logger.info(f"[{now}] 关闭原因: {reason}")
        self.logger.info(f"[{now}] ==================================\n") 