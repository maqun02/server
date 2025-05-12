from django.db import models
from django.contrib.auth.models import User

class CrawlerTask(models.Model):
    """
    爬虫任务模型
    """
    MODE_CHOICES = (
        ('simple', '简单模式'),  # 只爬取指定URL
        ('deep', '完整模式'),    # 爬取所有链接和资源
    )
    
    STATUS_CHOICES = (
        ('queued', '排队中'),
        ('link_crawling', '链接爬取中'),     # 第一阶段：爬取所有链接
        ('content_crawling', '内容爬取中'),   # 第二阶段：爬取页面内容
        ('resource_crawling', '资源爬取中'),  # 第三阶段：爬取静态资源
        ('fingerprint_matching', '指纹匹配中'), # 第四阶段：进行指纹匹配
        ('completed', '已完成'),
        ('failed', '失败'),
    )
    
    url = models.URLField(max_length=255, verbose_name='目标URL')
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='simple', verbose_name='爬取模式')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued', verbose_name='任务状态')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='crawler_tasks', verbose_name='创建用户')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    depth = models.IntegerField(default=2, verbose_name='爬取深度（已废弃）')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    # 新增任务跟踪字段
    links_found = models.IntegerField(default=0, verbose_name='发现的链接数')
    links_crawled = models.IntegerField(default=0, verbose_name='已爬取的链接数')
    resources_found = models.IntegerField(default=0, verbose_name='发现的资源数')
    resources_crawled = models.IntegerField(default=0, verbose_name='已爬取的资源数') 
    components_identified = models.IntegerField(default=0, verbose_name='识别的组件数')
    
    # Redis相关字段
    redis_key_prefix = models.CharField(max_length=50, blank=True, null=True, verbose_name='Redis键前缀')
    
    class Meta:
        verbose_name = '爬虫任务'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.url} - {self.get_mode_display()} ({self.get_status_display()})"
    
    def get_progress(self):
        """获取任务进度百分比"""
        if self.status == 'queued':
            return 0
        elif self.status == 'link_crawling':
            # 链接爬取阶段占总进度的20%
            return 20 if self.links_found == 0 else min(20, (self.links_crawled / self.links_found) * 20)
        elif self.status == 'content_crawling':
            # 内容爬取阶段占总进度的40%
            content_progress = 0 if self.links_found == 0 else min(40, (self.links_crawled / self.links_found) * 40)
            return 20 + content_progress
        elif self.status == 'resource_crawling':
            # 资源爬取阶段占总进度的30%
            resource_progress = 0 if self.resources_found == 0 else min(30, (self.resources_crawled / self.resources_found) * 30)
            return 60 + resource_progress
        elif self.status == 'fingerprint_matching':
            # 指纹匹配阶段占总进度的10%
            return 90
        elif self.status == 'completed':
            return 100
        elif self.status == 'failed':
            return -1  # 表示失败
        return 0
