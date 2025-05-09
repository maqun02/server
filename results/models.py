from django.db import models
from tasks.models import CrawlerTask

class CrawlerResult(models.Model):
    """
    爬虫结果数据模型
    """
    task = models.ForeignKey(CrawlerTask, on_delete=models.CASCADE, related_name='crawler_results', verbose_name='关联任务')
    url = models.URLField(max_length=255, verbose_name='页面URL')
    html_source = models.TextField(blank=True, null=True, verbose_name='HTML源码')
    headers = models.JSONField(default=dict, verbose_name='HTTP头信息')
    resources = models.JSONField(default=list, verbose_name='静态资源URL列表')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '爬虫结果'
        verbose_name_plural = verbose_name
        unique_together = ('task', 'url')
        ordering = ['-created_at'] 
    
    def __str__(self):
        return f"{self.task.url} - {self.url}"

class IdentifiedComponent(models.Model):
    """
    识别出的组件模型
    """
    task = models.ForeignKey(CrawlerTask, on_delete=models.CASCADE, related_name='identified_components', verbose_name='关联任务')
    result = models.ForeignKey(CrawlerResult, on_delete=models.CASCADE, related_name='components', verbose_name='关联爬虫结果')
    component = models.CharField(max_length=255, verbose_name='组件名称')
    keyword = models.CharField(max_length=255, verbose_name='匹配关键词')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '识别组件'
        verbose_name_plural = verbose_name
        unique_together = ('result', 'component')
    
    def __str__(self):
        return f"{self.result.url} - {self.component}"
