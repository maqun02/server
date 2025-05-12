#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import django
import argparse
import time
import datetime

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from tasks.models import CrawlerTask
from users.models import User, UserProfile
from tasks.task_runner import task_runner

def create_test_task(url, mode='simple', username='admin'):
    """创建测试爬虫任务"""
    # 获取或创建用户
    user, created = User.objects.get_or_create(
        username=username,
        defaults={'email': f'{username}@example.com'}
    )
    
    if created:
        # 设置密码
        user.set_password('123456')
        user.save()
        
        # 创建用户资料
        UserProfile.objects.create(
            user=user,
            nickname=username,
            role='admin'
        )
    
    # 创建爬虫任务
    task = CrawlerTask.objects.create(
        user=user,
        url=url,
        mode=mode,
        status='pending'
    )
    
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] 创建测试爬虫任务成功:")
    print(f"[{now}] 任务ID: {task.id}")
    print(f"[{now}] URL: {task.url}")
    print(f"[{now}] 模式: {task.get_mode_display()}")
    
    return task.id

def run_task(task_id):
    """运行指定的爬虫任务"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] 开始运行爬虫任务 {task_id}")
    
    # 启动任务
    task_runner.run_task(task_id)
    
    # 等待任务完成
    seconds = 0
    while True:
        # 每10秒检查一次任务状态
        time.sleep(10)
        seconds += 10
        
        # 刷新任务状态
        task = CrawlerTask.objects.get(id=task_id)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] 任务状态: {task.get_status_display()} (已运行{seconds}秒)")
        
        # 如果任务完成或失败，退出循环
        if task.status in ['completed', 'failed']:
            break
    
    # 打印最终状态
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] 任务结束，最终状态: {task.get_status_display()}")
    print(f"[{now}] 任务运行时间: {seconds}秒")
    
    # 打印统计信息
    from results.models import CrawlerLink, CrawlerResult, StaticResource, IdentifiedComponent
    
    links_count = CrawlerLink.objects.filter(task_id=task_id).count()
    results_count = CrawlerResult.objects.filter(task_id=task_id).count()
    resources_count = StaticResource.objects.filter(task_id=task_id).count()
    components_count = IdentifiedComponent.objects.filter(task_id=task_id).count()
    
    print(f"[{now}] 统计信息:")
    print(f"[{now}] - 爬取链接数: {links_count}")
    print(f"[{now}] - 爬取内容数: {results_count}")
    print(f"[{now}] - 爬取资源数: {resources_count}")
    print(f"[{now}] - 识别组件数: {components_count}")
    
    return task

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='爬虫测试工具')
    parser.add_argument('--url', required=True, help='要爬取的URL')
    parser.add_argument('--mode', choices=['simple', 'deep'], default='simple', help='爬取模式: simple(简单模式)或deep(完整模式)')
    parser.add_argument('--task-id', type=int, help='直接运行已有任务ID')
    
    args = parser.parse_args()
    
    if args.task_id:
        # 运行已有任务
        run_task(args.task_id)
    else:
        # 创建并运行新任务
        task_id = create_test_task(args.url, args.mode)
        run_task(task_id)

if __name__ == '__main__':
    main() 