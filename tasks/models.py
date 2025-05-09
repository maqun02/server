from django.db import models
from django.contrib.auth.models import User

class CrawlerTask(models.Model):
    """
    爬虫任务模型
    """
    MODE_CHOICES = (
        ('simple', '简单模式'),
        ('deep', '深度模式'),
    )
    
    STATUS_CHOICES = (
        ('queued', '排队中'),
        ('running', '运行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    )
    
    url = models.URLField(max_length=255, verbose_name='目标URL')
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='simple', verbose_name='爬取模式')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='queued', verbose_name='任务状态')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='crawler_tasks', verbose_name='创建用户')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    depth = models.IntegerField(default=1, verbose_name='爬取深度')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '爬虫任务'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.url} - {self.get_mode_display()} ({self.get_status_display()})"
