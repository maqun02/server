import os
import json
import datetime
import subprocess
from django.conf import settings
from django.utils import timezone
from .models import CrawlerTask
from results.models import CrawlerResult, IdentifiedComponent
from fingerprints.utils import component_matcher
from logs.utils import log_action

class TaskRunner:
    """
    爬虫任务运行器
    """
    def run_task(self, task_id):
        """
        运行指定ID的爬虫任务
        """
        try:
            # 获取任务
            task = CrawlerTask.objects.get(id=task_id)
            
            # 更新任务状态为运行中
            task.status = 'running'
            task.started_at = timezone.now()
            task.save()
            
            log_action(task.user, "task_status_change", task.id, "success", 
                      f"任务状态更新: 排队中 -> 运行中")
            
            # 使用环境变量中的scrapy命令
            scrapy_path = 'scrapy'
            log_action(task.user, "task_debug", task.id, "info", 
                      f"使用环境变量中的scrapy命令: {scrapy_path}")
            
            # 构建Scrapy命令
            command = [
                scrapy_path, 'crawl', 'components',
                '-a', f'url={task.url}',
                '-a', f'mode={task.mode}',
                '-a', f'depth={task.depth}',
                '-o', f'output_{task_id}.json'
            ]
            
            # 在scrapy_engine目录中运行命令
            scrapy_dir = os.path.join(settings.BASE_DIR, 'scrapy_engine')
            log_action(task.user, "task_debug", task.id, "info", 
                      f"执行命令: {' '.join(command)}, 工作目录: {scrapy_dir}")
            
            # 运行进程
            process = subprocess.Popen(
                command,
                cwd=scrapy_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # 等待进程完成
            stdout, stderr = process.communicate()
            stdout_str = stdout.decode('utf-8', errors='ignore')
            stderr_str = stderr.decode('utf-8', errors='ignore')
            
            # 记录输出
            log_action(task.user, "task_debug", task.id, "info", 
                      f"标准输出: {stdout_str[:500]}...")
            
            # 检查是否成功
            if process.returncode != 0:
                # 爬虫运行失败
                task.status = 'failed'
                task.ended_at = timezone.now()
                task.save()
                
                log_action(task.user, "task_status_change", task.id, "failure", 
                          f"任务失败: {stderr_str}")
                return False
            
            # 处理爬虫输出结果
            output_file = os.path.join(scrapy_dir, f'output_{task_id}.json')
            if not os.path.exists(output_file):
                log_action(task.user, "task_status_change", task.id, "failure", 
                          f"输出文件不存在: {output_file}")
                task.status = 'failed'
                task.ended_at = timezone.now()
                task.save()
                return False
                
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    results = json.load(f)
                
                # 检查结果是否为空
                if not results:
                    log_action(task.user, "task_status_change", task.id, "failure", 
                              f"爬虫结果为空")
                    task.status = 'failed'
                    task.ended_at = timezone.now()
                    task.save()
                    return False
                    
                # 存储爬虫结果到数据库
                for result_data in results:
                    # 创建爬虫结果记录
                    result = CrawlerResult.objects.create(
                        task=task,
                        url=result_data.get('url', ''),
                        html_source=result_data.get('html_source', ''),
                        headers=result_data.get('headers', {}),
                        resources=result_data.get('resources', [])
                    )
                    
                    # 使用Aho-Corasick算法进行组件识别
                    html_content = result_data.get('html_source', '')
                    matched_components = component_matcher.match(html_content)
                    
                    # 存储识别到的组件
                    if matched_components:
                        for component, keyword in matched_components:
                            IdentifiedComponent.objects.create(
                                task=task,
                                result=result,
                                component=component,
                                keyword=keyword
                            )
                            
                            log_action(task.user, "component_identified", result.id, "success", 
                                    f"在 {result.url} 中识别到组件: {component}")
                    else:
                        # 未识别到组件，创建特殊记录
                        IdentifiedComponent.objects.create(
                            task=task,
                            result=result,
                            component="未识别到组件",
                            keyword="无匹配关键词"
                        )
                        
                        log_action(task.user, "component_identified", result.id, "info", 
                                f"在 {result.url} 中未识别到组件")
                
                # 更新任务状态为已完成
                task.status = 'completed'
                task.ended_at = timezone.now()
                task.save()
                
                log_action(task.user, "task_status_change", task.id, "success", 
                          f"任务状态更新: 运行中 -> 已完成")
                
                # 删除临时文件
                try:
                    os.remove(output_file)
                except Exception as e:
                    log_action(task.user, "task_debug", task.id, "info", 
                              f"删除临时文件失败: {str(e)}")
                
                return True
            except json.JSONDecodeError as e:
                log_action(task.user, "task_status_change", task.id, "failure", 
                          f"解析JSON失败: {str(e)}")
                task.status = 'failed'
                task.ended_at = timezone.now()
                task.save()
                return False
        
        except CrawlerTask.DoesNotExist:
            return False
        except Exception as e:
            # 发生异常时，更新任务状态为失败
            try:
                task = CrawlerTask.objects.get(id=task_id)
                task.status = 'failed'
                task.ended_at = timezone.now()
                task.save()
                
                log_action(task.user, "task_status_change", task.id, "failure", 
                          f"任务异常: {str(e)}")
            except:
                pass
            
            return False


# 创建单例实例
task_runner = TaskRunner() 