import os
import json
import uuid
import redis
import hashlib
import datetime
import subprocess
from django.conf import settings
from django.utils import timezone
from .models import CrawlerTask
from results.models import CrawlerResult, CrawlerLink, StaticResource, IdentifiedComponent
from fingerprints.utils import component_matcher
from fingerprints.models import Fingerprint
from logs.utils import log_action
import threading
import time
import traceback

class TaskRunner:
    """
    爬虫任务运行器
    支持基于Redis的分布式爬取
    """
    def __init__(self):
        # 连接Redis
        redis_host = os.environ.get('REDIS_HOST', 'scrapyredis-redis.ns-6k0uv9r0.svc')
        redis_port = int(os.environ.get('REDIS_PORT', 6379))
        redis_username = os.environ.get('REDIS_USERNAME', 'default')
        redis_password = os.environ.get('REDIS_PASSWORD', '7sxxq74x')
        self.redis_client = redis.Redis(
            host=redis_host, 
            port=redis_port, 
            db=0,
            username=redis_username,
            password=redis_password
        )
        
    def run_task(self, task_id):
        """
        运行指定ID的爬虫任务
        """
        try:
            # 获取任务
            task = CrawlerTask.objects.get(id=task_id)
            
            # 打印任务启动信息
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{now}] ========== 爬虫任务启动 ==========")
            print(f"[{now}] 任务ID: {task_id}")
            print(f"[{now}] 目标URL: {task.url}")
            print(f"[{now}] 爬取模式: {task.get_mode_display()}")
            print(f"[{now}] 用户: {task.user.username}")
            print(f"[{now}] ==================================\n")
            
            # 生成任务的Redis键前缀
            task_key_prefix = f"task:{task_id}:{uuid.uuid4().hex[:8]}"
            task.redis_key_prefix = task_key_prefix
            
            # 根据模式设置不同的任务状态和处理流程
            if task.mode == 'simple':
                # 简单模式：直接进入内容爬取阶段，只爬取指定URL
                task.status = 'content_crawling'
                task.started_at = timezone.now()
                task.save()
                
                print(f"[{now}] 简单模式：直接爬取指定URL内容")
                print(f"[{now}] 任务状态更新: 排队中 -> 内容爬取中")
                print(f"[{now}] Redis键前缀: {task_key_prefix}")
                
                log_action(task.user, "task_status_change", task.id, "success", 
                          f"任务状态更新: 排队中 -> 内容爬取中 (简单模式)")
                
                # 创建起始URL的链接记录
                CrawlerLink.objects.create(
                    task=task,
                    url=task.url,
                    internal_links=[],
                    external_links=[],
                    internal_nofollow_links=[],
                    external_nofollow_links=[]
                )
                
                # 直接启动内容爬取
                content_queue_key = f"{task_key_prefix}:content_spider:start_urls"
                self.redis_client.lpush(content_queue_key, task.url)
                
                print(f"[{now}] 将URL添加到内容爬取队列: {content_queue_key}")
                print(f"[{now}] 启动内容爬虫...")
                
                # 启动内容爬虫
                self._run_spider(
                    spider_name="content_spider",
                    redis_key=content_queue_key,
                    task_id=task.id
                )
                
                print(f"[{now}] 内容爬虫已启动")
                
            else:
                # 完整模式：先爬取所有链接，再爬取内容
                task.status = 'link_crawling'
                task.started_at = timezone.now()
            task.save()
            
            print(f"[{now}] 完整模式：先爬取所有链接，再爬取内容")
            print(f"[{now}] 任务状态更新: 排队中 -> 链接爬取中")
            print(f"[{now}] Redis键前缀: {task_key_prefix}")
        
            log_action(task.user, "task_status_change", task.id, "success", 
                  f"任务状态更新: 排队中 -> 链接爬取中 (完整模式)")
        
            # 第一阶段：爬取网站内所有链接
            # 将起始URL添加到Redis队列
            link_queue_key = f"{task_key_prefix}:link_spider:start_urls"
            self.redis_client.lpush(link_queue_key, task.url)
            
            print(f"[{now}] 将起始URL添加到Redis队列: {link_queue_key}")
            print(f"[{now}] 启动链接爬虫...")
            
            # 启动链接爬虫
            self._run_spider(
                    spider_name="link_spider",
                    redis_key=link_queue_key,
                    task_id=task.id,
                    start_url=task.url
                )
print(f"[{now}] 链接爬虫已启动")
            
            # 后续阶段将由管道触发
            return True
            
        except CrawlerTask.DoesNotExist:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 错误: 找不到任务ID {task_id}")
            return False
        except Exception as e:
            # 发生异常时，更新任务状态为失败
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 错误: 任务启动失败 - {str(e)}")
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
    
    def _run_spider(self, spider_name, redis_key=None, task_id=None, start_url=None, content_url=None):
        """
        启动爬虫进程
        """
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] 正在启动爬虫: {spider_name}")
        print(f"[{now}] 参数: task_id={task_id}, redis_key={redis_key}, start_url={start_url}")
        
        try:
            # 构建命令
            command = [
                "python", 
                "manage.py", 
                "scrapy", 
                "crawl", 
                spider_name
            ]
            
            # 添加参数
            if task_id:
                command.extend(["-a", f"task_id={task_id}"])
            
            if redis_key:
                command.extend(["-a", f"redis_key={redis_key}"])
            
            if start_url:
                command.extend(["-a", f"url={start_url}"])
                
            if content_url:
                command.extend(["-a", f"content_url={content_url}"])
            
            # 添加日志设置
            log_dir = os.path.join(settings.BASE_DIR, 'logs', 'spider_logs')
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"{spider_name}_{task_id}_{int(time.time())}.log")
            command.extend(["-s", f"LOG_FILE={log_file}"])
            
            # 启动进程
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # 记录进程信息
            print(f"[{now}] 爬虫进程已启动，PID: {process.pid}")
            
            # 后台等待进程完成
            def wait_for_process():
                stdout, stderr = process.communicate()
                returncode = process.wait()
                end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                if returncode != 0:
                    print(f"[{end_time}] 爬虫异常退出，返回码: {returncode}")
                    if stderr:
                        print(f"[{end_time}] 错误信息: {stderr[:500]}...")
                else:
                    print(f"[{end_time}] 爬虫正常结束，返回码: {returncode}")
            
            # 启动后台线程等待进程完成
            thread = threading.Thread(target=wait_for_process)
            thread.daemon = True
            thread.start()
            
            return True
            
        except Exception as e:
            print(f"[{now}] 启动爬虫失败: {str(e)}")
            traceback.print_exc()
            return False
    
    def start_content_crawling(self, task_id):
        """
        开始内容爬取阶段
        """
        try:
            task = CrawlerTask.objects.get(id=task_id)
            
            # 获取所有需要爬取内容的链接
            links = CrawlerLink.objects.filter(task_id=task_id, is_crawled=False)
            
            if not links.exists():
                # 如果没有链接，也要确保起始URL被爬取
                links = CrawlerLink.objects.filter(task_id=task_id, url=task.url)
                if not links.exists():
                    # 创建起始URL的链接记录
                    CrawlerLink.objects.create(
                        task=task,
                        url=task.url,
                        internal_links=[],
                        external_links=[],
                        internal_nofollow_links=[],
                        external_nofollow_links=[]
                    )
                    links = CrawlerLink.objects.filter(task_id=task_id, url=task.url)
                
                if not links.exists():
                    log_action(task.user, "task_debug", task.id, "warning", 
                             f"没有可爬取的链接，包括起始URL")
                    return False
            
            # 将链接URL添加到Redis队列
            content_queue_key = f"{task.redis_key_prefix}:content_spider:start_urls"
            
            # 确保起始URL在队列的前面
            start_url_added = False
            
            # 先添加起始URL确保它被首先爬取
            for link in links:
                if link.url == task.url:
                    self.redis_client.lpush(content_queue_key, link.url)
                    start_url_added = True
                    
                    # 记录日志
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{now}] 将起始URL添加到内容爬取队列: {link.url}")
                    break
            
            # 然后添加其他链接
            for link in links:
                if link.url != task.url or not start_url_added:
                    self.redis_client.lpush(content_queue_key, link.url)
            
            # 记录日志
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] ========== 开始内容爬取阶段 ==========")
            print(f"[{now}] 任务ID: {task_id}")
            print(f"[{now}] 需要爬取的链接数: {links.count()}")
            print(f"[{now}] Redis键: {content_queue_key}")
            print(f"[{now}] ====================================\n")
                
            # 更新任务状态
            task.status = 'content_crawling'
            task.save()
                
            log_action(task.user, "task_status_change", task.id, "success", 
                     f"任务状态更新: 链接爬取中 -> 内容爬取中")
            
            # 启动内容爬虫
            self._run_spider(
                spider_name="content_spider",
                redis_key=content_queue_key,
                task_id=task.id
            )
            
            return True
            
        except CrawlerTask.DoesNotExist:
            return False
        except Exception as e:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 错误: 启动内容爬取失败 - {str(e)}")
            log_action(None, "task_debug", task_id, "failure", 
                     f"启动内容爬取失败: {str(e)}")
            return False
    
    def start_resource_crawling(self, task_id):
        """
        开始静态资源爬取阶段
        """
        try:
            task = CrawlerTask.objects.get(id=task_id)
            
            # 获取所有已爬取内容的页面
            results = CrawlerResult.objects.filter(task_id=task_id, resources_crawled=False)
            
            if not results.exists():
                log_action(task.user, "task_debug", task.id, "warning", 
                         f"没有可爬取的静态资源")
                self.start_fingerprint_matching(task_id)
                return False
            
            # 为每个内容页面启动资源爬虫
            for result in results:
                # 解析静态资源
                resources = []
                try:
                    # 查找HTML中的静态资源链接
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(result.html_source, 'html.parser')
                    
                    # 提取JS脚本
                    for script in soup.find_all('script', src=True):
                        resources.append({
                            'url': script['src'],
                            'type': 'js'
                        })
                    
                    # 提取CSS样式表
                    for css in soup.find_all('link', rel='stylesheet', href=True):
                        resources.append({
                            'url': css['href'],
                            'type': 'css'
                        })
                    
                    # 提取图片
                    for img in soup.find_all('img', src=True):
                        resources.append({
                            'url': img['src'],
                            'type': 'image'
                        })
                    
                    # 提取favicon
                    for icon in soup.find_all('link', rel=lambda r: r and ('icon' in r), href=True):
                        resources.append({
                            'url': icon['href'],
                            'type': 'ico'
                        })
                except Exception as e:
                    log_action(task.user, "task_debug", task.id, "warning", 
                             f"解析静态资源失败: {str(e)}")
                
                # 将资源URL添加到Redis队列
                if resources:
                    resource_queue_key = f"{task.redis_key_prefix}:resource_spider:{result.id}:start_urls"
                    
                    from urllib.parse import urljoin
                    base_url = result.url
                    
                    for resource in resources:
                        # 将相对URL转为绝对URL
                        abs_url = urljoin(base_url, resource['url'])
                        self.redis_client.lpush(resource_queue_key, abs_url)
                    
                    # 启动资源爬虫
                    self._run_spider(
                        spider_name="resource_spider",
                        redis_key=resource_queue_key,
                        task_id=task.id,
                        content_url=result.url
                    )
                
                # 标记内容页面已爬取资源
                result.resources_crawled = True
                result.save()
                
            # 更新任务状态
            task.status = 'resource_crawling'
            task.save()
            
            log_action(task.user, "task_status_change", task.id, "success", 
                     f"任务状态更新: 内容爬取中 -> 资源爬取中")
            
            return True
            
        except CrawlerTask.DoesNotExist:
            return False
        except Exception as e:
            log_action(None, "task_debug", task_id, "failure", 
                     f"启动资源爬取失败: {str(e)}")
            return False
    
    def start_fingerprint_matching(self, task_id):
        """
        开始指纹匹配阶段
        """
        try:
            task = CrawlerTask.objects.get(id=task_id)
            
            # 添加进度提示
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{now}] ========== 开始指纹匹配阶段 ==========")
            print(f"[{now}] 任务ID: {task_id}")
            print(f"[{now}] 页面数量: {CrawlerLink.objects.filter(task=task).count()}")
            print(f"[{now}] 资源数量: {StaticResource.objects.filter(task=task).count()}")
            
            # 更新任务状态
            task.status = 'fingerprint_matching'
            task.save()
            
            print(f"[{now}] 任务状态更新: 资源爬取中 -> 指纹匹配中")
            
            log_action(task.user, "task_status_change", task.id, "success", 
                     f"任务状态更新: 资源爬取中 -> 指纹匹配中")
            
            # 在后台线程中进行指纹匹配
            thread = threading.Thread(target=self._run_fingerprint_matching, args=(task_id,))
            thread.daemon = True
            thread.start()
            
            print(f"[{now}] 指纹匹配线程已启动")
            print(f"[{now}] ========================================\n")
            
            return True
            
        except CrawlerTask.DoesNotExist:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 错误: 找不到任务ID {task_id}")
            return False
        except Exception as e:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 错误: 启动指纹匹配失败 - {str(e)}")
            log_action(None, "task_debug", task_id, "failure", 
                     f"启动指纹匹配失败: {str(e)}")
            return False
                    
    def _run_fingerprint_matching(self, task_id):
        """
        运行指纹匹配过程
        """
        try:
            task = CrawlerTask.objects.get(id=task_id)
            
            # 添加进度提示
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 开始指纹匹配...")
            
            # 确保指纹库已加载
            print(f"[{now}] 正在加载指纹库...")
            component_matcher.load_fingerprints()
            
            # 获取指纹数量
            fingerprint_count = len(component_matcher.fingerprints) if hasattr(component_matcher, 'fingerprints') else 0
            print(f"[{now}] 已加载 {fingerprint_count} 个指纹")
            
            # 1. 匹配HTML内容
            results = CrawlerResult.objects.filter(task_id=task_id)
            print(f"[{now}] 开始处理 {results.count()} 个HTML页面...")
            html_match_count = 0
            
            for idx, result in enumerate(results):
                # 使用Aho-Corasick算法进行组件识别
                html_content = result.html_source
                matched_components = component_matcher.match(html_content)
                
                # 存储识别到的组件
                for component, keyword in matched_components:
                        IdentifiedComponent.objects.create(
                    task=task,
                        result=result,
                        component=component,
                        keyword=keyword,
                        match_type='html'
                    )
                task.components_identified += 1
                    html_match_count += 1
                
                # 每处理10个页面打印一次进度
                if (idx + 1) % 10 == 0 or idx == len(results) - 1:
                    print(f"[{now}] HTML进度: {idx + 1}/{results.count()} 页面, 匹配: {html_match_count} 个组件")
            
            # 2. 匹配JS内容
            js_resources = StaticResource.objects.filter(task_id=task_id, resource_type='js')
            print(f"[{now}] 开始处理 {js_resources.count()} 个JS资源...")
            js_match_count = 0
            
            for idx, resource in enumerate(js_resources):
                if resource.content:
                    try:
                        # 将二进制内容解码为文本
                        js_content = resource.content.decode('utf-8', errors='ignore')
                        matched_components = component_matcher.match(js_content)
                    
                    # 存储识别到的组件
                        for component, keyword in matched_components:
                                IdentifiedComponent.objects.create(
                    task=task,
                                resource=resource,
                                component=component,
                                keyword=keyword,
                                match_type='js'
                            )
                task.components_identified += 1
                            js_match_count += 1
                    except Exception as e:
                        print(f"[{now}] 错误: 匹配JS内容失败: {resource.url}, 错误: {str(e)}")
                        log_action(task.user, "task_debug", task.id, "warning", 
                                 f"匹配JS内容失败: {resource.url}, 错误: {str(e)}")
                
                # 每处理10个资源打印一次进度
                if (idx + 1) % 10 == 0 or idx == len(js_resources) - 1:
                    print(f"[{now}] JS进度: {idx + 1}/{js_resources.count()} 资源, 匹配: {js_match_count} 个组件")
            
            # 3. 匹配CSS内容
            css_resources = StaticResource.objects.filter(task_id=task_id, resource_type='css')
            print(f"[{now}] 开始处理 {css_resources.count()} 个CSS资源...")
            css_match_count = 0
            
            for idx, resource in enumerate(css_resources):
                if resource.content:
                    try:
                        # 将二进制内容解码为文本
                        css_content = resource.content.decode('utf-8', errors='ignore')
                        matched_components = component_matcher.match(css_content)
                        
                        # 存储识别到的组件
                        for component, keyword in matched_components:
                                    IdentifiedComponent.objects.create(
                task=task,
                                resource=resource,
                                component=component,
                                keyword=keyword,
                                match_type='css'
                            )
            task.components_identified += 1
                            css_match_count += 1
                    except Exception as e:
                        print(f"[{now}] 错误: 匹配CSS内容失败: {resource.url}, 错误: {str(e)}")
                        log_action(task.user, "task_debug", task.id, "warning", 
                                 f"匹配CSS内容失败: {resource.url}, 错误: {str(e)}")
                
                # 每处理10个资源打印一次进度
                if (idx + 1) % 10 == 0 or idx == len(css_resources) - 1:
                    print(f"[{now}] CSS进度: {idx + 1}/{css_resources.count()} 资源, 匹配: {css_match_count} 个组件")
            
            # 4. 匹配图片和图标的MD5哈希
            image_resources = StaticResource.objects.filter(
                task_id=task_id, 
                resource_type__in=['image', 'ico'], 
                md5_hash__isnull=False
            )
            print(f"[{now}] 开始处理 {image_resources.count()} 个图片/图标资源...")
            
            # 获取基于MD5的指纹
            md5_fingerprints = Fingerprint.objects.filter(
                status='approved', 
                keyword__regex=r'^[0-9a-f]{32}$'
            )
            print(f"[{now}] 找到 {md5_fingerprints.count()} 个MD5指纹")
            
            # 使用字典优化查找
            md5_to_component = {fp.keyword.lower(): fp.component for fp in md5_fingerprints}
            md5_match_count = 0
            
            for idx, resource in enumerate(image_resources):
                if resource.md5_hash and resource.md5_hash.lower() in md5_to_component:
                    component = md5_to_component[resource.md5_hash.lower()]
                IdentifiedComponent.objects.create(
                            task=task,
                        resource=resource,
                        component=component,
                        keyword=resource.md5_hash,
                        match_type=resource.resource_type
                    )
                    task.components_identified += 1
                    md5_match_count += 1
                
                # 每处理20个资源打印一次进度
                if (idx + 1) % 20 == 0 or idx == len(image_resources) - 1:
                    print(f"[{now}] 图片进度: {idx + 1}/{image_resources.count()} 资源, 匹配: {md5_match_count} 个组件")
            
            # 打印匹配结果摘要
            print(f"\n[{now}] ========== 指纹匹配完成 ==========")
            print(f"[{now}] HTML匹配: {html_match_count} 个组件")
            print(f"[{now}] JS匹配: {js_match_count} 个组件")
            print(f"[{now}] CSS匹配: {css_match_count} 个组件")
            print(f"[{now}] 图片匹配: {md5_match_count} 个组件")
            print(f"[{now}] 总匹配组件: {task.components_identified} 个")
            
            # 保存任务计数
            task.save()
            
    # 更新任务状态为已完成
    task.status = 'completed'
    task.ended_at = timezone.now()
    task.save()
    
    print(f"[{now}] 任务状态更新: 指纹匹配中 -> 已完成")
    print(f"[{now}] 任务完成时间: {task.ended_at}")
    print(f"[{now}] ===================================\n")
    
    log_action(task.user, "task_status_change", task.id, "success", 
              f"任务状态更新: 指纹匹配中 -> 已完成")
    
    return True
        
        except CrawlerTask.DoesNotExist:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 错误: 找不到任务ID {task_id}")
            return False
        except Exception as e:
            # 发生异常时，更新任务状态为失败
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] 错误: 指纹匹配失败 - {str(e)}")
            try:
                task = CrawlerTask.objects.get(id=task_id)
                task.status = 'failed'
                task.ended_at = timezone.now()
                task.save()
                
                log_action(task.user, "task_status_change", task.id, "failure", 
                          f"指纹匹配失败: {str(e)}")
            except:
                pass
            
            return False

# 创建单例实例
task_runner = TaskRunner() 