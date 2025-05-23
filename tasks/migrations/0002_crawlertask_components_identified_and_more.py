# Generated by Django 5.2 on 2025-05-11 10:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='crawlertask',
            name='components_identified',
            field=models.IntegerField(default=0, verbose_name='识别的组件数'),
        ),
        migrations.AddField(
            model_name='crawlertask',
            name='links_crawled',
            field=models.IntegerField(default=0, verbose_name='已爬取的链接数'),
        ),
        migrations.AddField(
            model_name='crawlertask',
            name='links_found',
            field=models.IntegerField(default=0, verbose_name='发现的链接数'),
        ),
        migrations.AddField(
            model_name='crawlertask',
            name='redis_key_prefix',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Redis键前缀'),
        ),
        migrations.AddField(
            model_name='crawlertask',
            name='resources_crawled',
            field=models.IntegerField(default=0, verbose_name='已爬取的资源数'),
        ),
        migrations.AddField(
            model_name='crawlertask',
            name='resources_found',
            field=models.IntegerField(default=0, verbose_name='发现的资源数'),
        ),
        migrations.AlterField(
            model_name='crawlertask',
            name='mode',
            field=models.CharField(choices=[('simple', '简单模式'), ('deep', '完整模式')], default='simple', max_length=10, verbose_name='爬取模式'),
        ),
        migrations.AlterField(
            model_name='crawlertask',
            name='status',
            field=models.CharField(choices=[('queued', '排队中'), ('link_crawling', '链接爬取中'), ('content_crawling', '内容爬取中'), ('resource_crawling', '资源爬取中'), ('fingerprint_matching', '指纹匹配中'), ('completed', '已完成'), ('failed', '失败')], default='queued', max_length=20, verbose_name='任务状态'),
        ),
    ]
