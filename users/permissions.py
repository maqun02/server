from rest_framework import permissions

class IsAdminUser(permissions.BasePermission):
    """
    仅允许管理员访问
    """
    def has_permission(self, request, view):
        return bool(request.user and hasattr(request.user, 'profile') and request.user.profile.role == 'admin')

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    仅允许对象拥有者或管理员访问
    """
    def has_object_permission(self, request, view, obj):
        # 管理员可以访问任何对象
        if request.user and hasattr(request.user, 'profile') and request.user.profile.role == 'admin':
            return True
        
        # 对象拥有者可以访问自己的对象
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'submitter'):
            return obj.submitter == request.user
        
        return False 