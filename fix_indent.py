#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

# 读取原文件
with open('tasks/task_runner.py', 'r') as file:
    content = file.read()

# 修复链接爬虫启动部分的缩进问题
content = re.sub(r'(\s+print\(f"\[{now}\] 链接爬虫已启动"\))', r'\nprint(f"[{now}] 链接爬虫已启动")', content)

# 写入修复后的文件
with open('tasks/task_runner.py', 'w') as file:
    file.write(content)

print("修复完成，tasks/task_runner.py已更新") 