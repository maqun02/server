from django.shortcuts import render
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from .models import UserProfile
from .serializers import UserSerializer, UserRegistrationSerializer, LoginSerializer, ResetPasswordSerializer
from .permissions import IsAdminUser
from logs.utils import log_action

class UserViewSet(viewsets.ModelViewSet):
    """
    用户管理视图集
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        """只有管理员可以查看所有用户，普通用户只能查看自己"""
        user = self.request.user
        if user.is_authenticated and hasattr(user, 'profile'):
            if user.profile.role == 'admin':
                return User.objects.all()
        return User.objects.filter(id=user.id)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def register(self, request):
        """
        用户注册接口
        """
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            log_action(None, "other", None, "success", f"新用户注册: {user.username}")
            return Response({"detail": "注册成功"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def login(self, request):
        """
        用户登录接口
        """
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                log_action(user, "login", None, "success", "用户登录成功")
                return Response({"detail": "登录成功"}, status=status.HTTP_200_OK)
            else:
                log_action(None, "login", None, "failure", f"用户 {username} 登录失败")
                return Response({"detail": "用户名或密码错误"}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def logout(self, request):
        """
        用户登出接口
        """
        log_action(request.user, "logout", None, "success", "用户登出")
        logout(request)
        return Response({"detail": "登出成功"}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """
        获取当前登录用户信息
        """
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
        
    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def reset_password(self, request):
        """
        管理员重置用户密码接口
        """
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            target_id = serializer.validated_data.get('target_id')
            
            if not target_id:
                return Response({"detail": "请提供用户ID或用户名"}, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                # 尝试查找用户，首先假设target_id是数字ID
                try:
                    user_id = int(target_id)
                    user = User.objects.get(id=user_id)
                except (ValueError, User.DoesNotExist):
                    # 如果不是有效的ID，则尝试作为用户名查找
                    user = User.objects.get(username=target_id)
                
                user.set_password('123456')
                user.save()
                log_action(request.user, "user_management", user.id, "success", f"管理员重置用户 {user.username} 的密码")
                return Response({"detail": f"用户 {user.username} 的密码已重置为123456"}, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                return Response({"detail": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
