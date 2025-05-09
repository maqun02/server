from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    """
    用户配置文件扩展内置User模型
    """
    USER_ROLES = (
        ('admin', '管理员'),
        ('user', '普通用户'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=USER_ROLES, default='user')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"
