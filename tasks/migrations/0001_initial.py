# Generated by Django 5.2 on 2025-05-05 15:11

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CrawlerTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.URLField(max_length=255, verbose_name='目标URL')),
                ('mode', models.CharField(choices=[('simple', '简单模式'), ('deep', '深度模式')], default='simple', max_length=10, verbose_name='爬取模式')),
                ('status', models.CharField(choices=[('queued', '排队中'), ('running', '运行中'), ('completed', '已完成'), ('failed', '失败')], default='queued', max_length=10, verbose_name='任务状态')),
                ('started_at', models.DateTimeField(blank=True, null=True, verbose_name='开始时间')),
                ('ended_at', models.DateTimeField(blank=True, null=True, verbose_name='结束时间')),
                ('depth', models.IntegerField(default=1, verbose_name='爬取深度')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='crawler_tasks', to=settings.AUTH_USER_MODEL, verbose_name='创建用户')),
            ],
            options={
                'verbose_name': '爬虫任务',
                'verbose_name_plural': '爬虫任务',
                'ordering': ['-created_at'],
            },
        ),
    ]
