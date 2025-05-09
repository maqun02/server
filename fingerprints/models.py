from django.db import models
from django.contrib.auth.models import User

class Fingerprint(models.Model):
    """
    组件指纹模型
    """
    STATUS_CHOICES = (
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
    )
    
    keyword = models.CharField(max_length=255, verbose_name='关键词')
    component = models.CharField(max_length=255, verbose_name='组件名称')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    submitter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submitted_fingerprints', verbose_name='提交者')
    admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_fingerprints', verbose_name='审核管理员')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '组件指纹'
        verbose_name_plural = verbose_name
        unique_together = ('keyword', 'component')
        
    def __str__(self):
        return f"{self.component} - {self.keyword} ({self.get_status_display()})"
