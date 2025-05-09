"""
URL configuration for project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.http import HttpResponse
from users.views import UserViewSet
from fingerprints.views import FingerprintViewSet
from tasks.views import CrawlerTaskViewSet
from results.views import ResultViewSet
from logs.views import SystemLogViewSet

# 创建简单首页视图
def index(request):
    return HttpResponse("""
    <h1>指纹匹配Web组件识别系统</h1>
    <ul>
        <li><a href="/admin/">管理后台</a></li>
        <li><a href="/api/">API接口</a></li>
    </ul>
    """)

# 创建路由器并注册视图
router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'fingerprints', FingerprintViewSet)
router.register(r'tasks', CrawlerTaskViewSet)
router.register(r'results', ResultViewSet)
router.register(r'logs', SystemLogViewSet)

urlpatterns = [
    path('', index, name='index'),
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls')),
    path('api/', include(router.urls)),
]
