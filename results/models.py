from django.db import models
from tasks.models import CrawlerTask

class CrawlerLink(models.Model):
    """
    爬虫链接数据模型 - 记录网站的所有链接
    """
    task = models.ForeignKey(CrawlerTask, on_delete=models.CASCADE, related_name='crawler_links', verbose_name='关联任务')
    url = models.URLField(max_length=255, verbose_name='页面URL')
    internal_links = models.JSONField(default=list, verbose_name='内链列表')
    external_links = models.JSONField(default=list, verbose_name='外链列表')
    internal_nofollow_links = models.JSONField(default=list, verbose_name='内链nofollow列表')
    external_nofollow_links = models.JSONField(default=list, verbose_name='外链nofollow列表')
    is_crawled = models.BooleanField(default=False, verbose_name='是否已爬取内容')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '爬虫链接'
        verbose_name_plural = verbose_name
        unique_together = ('task', 'url')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.task.url} - {self.url}"

class CrawlerResult(models.Model):
    """
    爬虫内容结果数据模型
    """
    task = models.ForeignKey(CrawlerTask, on_delete=models.CASCADE, related_name='crawler_results', verbose_name='关联任务')
    url = models.URLField(max_length=255, verbose_name='页面URL')
    title = models.CharField(max_length=255, blank=True, null=True, verbose_name='页面标题')
    html_source = models.TextField(blank=True, null=True, verbose_name='HTML源码')
    headers = models.JSONField(default=dict, verbose_name='HTTP头信息')
    resources = models.JSONField(default=list, verbose_name='静态资源列表')
    resources_crawled = models.BooleanField(default=False, verbose_name='静态资源是否已爬取')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '爬虫内容结果'
        verbose_name_plural = verbose_name
        unique_together = ('task', 'url')
        ordering = ['-created_at'] 
    
    def __str__(self):
        return f"{self.task.url} - {self.url}"

class StaticResource(models.Model):
    """
    静态资源模型 - 存储JS、CSS、图片等静态资源
    """
    RESOURCE_TYPES = (
        ('js', 'JavaScript'),
        ('css', 'CSS样式表'),
        ('image', '图片'),
        ('ico', '图标'),
        ('other', '其他')
    )
    
    task = models.ForeignKey(CrawlerTask, on_delete=models.CASCADE, related_name='static_resources', verbose_name='关联任务')
    result = models.ForeignKey(CrawlerResult, on_delete=models.CASCADE, related_name='resource_items', verbose_name='关联内容结果')
    url = models.URLField(max_length=255, verbose_name='资源URL')
    resource_type = models.CharField(max_length=10, choices=RESOURCE_TYPES, default='other', verbose_name='资源类型')
    content = models.BinaryField(blank=True, null=True, verbose_name='资源内容')
    md5_hash = models.CharField(max_length=32, blank=True, null=True, verbose_name='MD5哈希值')
    is_matched = models.BooleanField(default=False, verbose_name='是否已匹配指纹')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '静态资源'
        verbose_name_plural = verbose_name
        unique_together = ('task', 'url')
    
    def __str__(self):
        return f"{self.result.url} - {self.url}"

class IdentifiedComponent(models.Model):
    """
    识别出的组件模型
    """
    task = models.ForeignKey(CrawlerTask, on_delete=models.CASCADE, related_name='identified_components', verbose_name='关联任务')
    result = models.ForeignKey(CrawlerResult, on_delete=models.CASCADE, related_name='components', verbose_name='关联爬虫结果', null=True, blank=True)
    resource = models.ForeignKey(StaticResource, on_delete=models.CASCADE, related_name='components', verbose_name='关联静态资源', null=True, blank=True)
    component = models.CharField(max_length=255, verbose_name='组件名称')
    keyword = models.CharField(max_length=255, verbose_name='匹配关键词')
    match_type = models.CharField(max_length=20, default='html', verbose_name='匹配类型', 
                                 choices=(('html', 'HTML内容'), ('js', 'JavaScript'), 
                                          ('css', 'CSS'), ('image', '图片'),
                                          ('ico', '图标'), ('other', '其他')))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '识别组件'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        if self.result:
            return f"{self.result.url} - {self.component}"
        elif self.resource:
            return f"{self.resource.url} - {self.component}"
        else:
            return f"{self.task.id} - {self.component}" 