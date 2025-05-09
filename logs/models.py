from django.db import models
from django.contrib.auth.models import User

class SystemLog(models.Model):
    """
    系统日志模型
    """
    ACTION_CHOICES = (
        ('create_task', '创建任务'),
        ('login', '登录'),
        ('logout', '登出'),
        ('submit_fingerprint', '提交指纹'),
        ('approve_fingerprint', '审核指纹'),
        ('task_status_change', '任务状态变更'),
        ('component_identified', '识别组件'),
        ('task_debug', '任务调试'),
        ('user_management', '用户管理'),
        ('other', '其他操作'),
    )
    
    STATUS_CHOICES = (
        ('success', '成功'),
        ('failure', '失败'),
        ('info', '信息'),
    )
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs', verbose_name='用户')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, verbose_name='操作类型')
    target_id = models.IntegerField(null=True, blank=True, verbose_name='目标ID')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, verbose_name='状态')
    message = models.TextField(blank=True, verbose_name='消息内容')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '系统日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        user_str = self.user.username if self.user else '系统'
        return f"{user_str} - {self.get_action_display()} - {self.get_status_display()}"
