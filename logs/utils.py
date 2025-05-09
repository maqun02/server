from .models import SystemLog

def log_action(user=None, action="other", target_id=None, status="success", message=""):
    """
    记录系统日志
    
    Args:
        user: 用户对象，可以为None表示系统操作
        action: 操作类型，必须是SystemLog.ACTION_CHOICES中定义的值之一
        target_id: 操作目标对象的ID，可以为None
        status: 操作状态，必须是SystemLog.STATUS_CHOICES中定义的值之一
        message: 详细消息内容
    
    Returns:
        创建的日志对象
    """
    log = SystemLog.objects.create(
        user=user,
        action=action,
        target_id=target_id,
        status=status,
        message=message
    )
    return log 