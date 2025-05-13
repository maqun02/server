#!/usr/bin/env python
import os
import sys
import django
import subprocess
import time

# 设置Django环境
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django.setup()

# 导入所需模型和工具
from tasks.models import CrawlerTask
from tasks.task_runner import TaskRunner
from django.utils import timezone

def debug_task(task_id):
    print(f"\n[DEBUG SCRIPT] === 开始调试任务 ID: {task_id} ===\n")
    
    # 获取任务信息
    try:
        task = CrawlerTask.objects.get(id=task_id)
        print(f"[DEBUG SCRIPT] 找到任务: {task.url}, 状态: {task.status}")
    except CrawlerTask.DoesNotExist:
        print(f"[DEBUG SCRIPT] 错误: 任务ID {task_id} 不存在!")
        return
    
    # 1. 手动创建并执行任务运行器
    print(f"\n[DEBUG SCRIPT] === 第1步: 初始化任务运行器 ===")
    runner = TaskRunner(task_id)
    
    # 2. 运行链接爬虫
    print(f"\n[DEBUG SCRIPT] === 第2步: 运行链接爬虫 ===")
    link_result = runner.run_link_spider()
    print(f"[DEBUG SCRIPT] 链接爬虫结果: {'成功' if link_result else '失败'}")
    
    # 等待片刻
    time.sleep(2)
    task.refresh_from_db()
    print(f"[DEBUG SCRIPT] 任务状态: {task.status}")
    
    # 如果失败则中止
    if not link_result:
        print(f"[DEBUG SCRIPT] 链接爬虫失败，终止调试脚本")
        return
    
    # 3. 运行内容爬虫
    print(f"\n[DEBUG SCRIPT] === 第3步: 运行内容爬虫 ===")
    content_result = runner.run_content_spider()
    print(f"[DEBUG SCRIPT] 内容爬虫结果: {'成功' if content_result else '失败'}")
    
    # 等待片刻
    time.sleep(2)
    task.refresh_from_db()
    print(f"[DEBUG SCRIPT] 任务状态: {task.status}")
    
    # 如果失败则中止
    if not content_result:
        print(f"[DEBUG SCRIPT] 内容爬虫失败，终止调试脚本")
        return
    
    # 4. 运行资源爬虫
    print(f"\n[DEBUG SCRIPT] === 第4步: 运行资源爬虫 ===")
    resource_result = runner.run_resource_spider()
    print(f"[DEBUG SCRIPT] 资源爬虫结果: {'成功' if resource_result else '失败'}")
    
    # 等待片刻
    time.sleep(2)
    task.refresh_from_db()
    print(f"[DEBUG SCRIPT] 任务状态: {task.status}")
    
    # 如果失败则中止
    if not resource_result:
        print(f"[DEBUG SCRIPT] 资源爬虫失败，终止调试脚本")
        return
    
    # 5. 进行指纹匹配
    print(f"\n[DEBUG SCRIPT] === 第5步: 执行指纹匹配 ===")
    fingerprint_result = runner.match_fingerprints()
    print(f"[DEBUG SCRIPT] 指纹匹配结果: {'成功' if fingerprint_result else '失败'}")
    
    # 等待片刻
    time.sleep(2)
    task.refresh_from_db()
    print(f"[DEBUG SCRIPT] 任务状态: {task.status}")
    
    # 6. 完成任务
    print(f"\n[DEBUG SCRIPT] === 第6步: 完成任务 ===")
    runner.update_task_status('completed')
    
    # 等待片刻
    time.sleep(2)
    task.refresh_from_db()
    print(f"[DEBUG SCRIPT] 任务状态: {task.status}")
    
    # 最终统计
    print(f"\n[DEBUG SCRIPT] === 任务执行完成 ===")
    print(f"[DEBUG SCRIPT] 链接数: 已找到 {task.links_found}, 已爬取 {task.links_crawled}")
    print(f"[DEBUG SCRIPT] 资源数: 已找到 {task.resources_found}, 已爬取 {task.resources_crawled}")
    print(f"[DEBUG SCRIPT] 识别组件: {task.components_identified}")
    print(f"[DEBUG SCRIPT] 开始时间: {task.started_at}")
    print(f"[DEBUG SCRIPT] 结束时间: {task.ended_at}")
    print(f"[DEBUG SCRIPT] 耗时: {(task.ended_at - task.started_at).total_seconds():.2f} 秒")
    
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python debug_task.py <任务ID>")
        sys.exit(1)
    
    task_id = int(sys.argv[1])
    debug_task(task_id) 