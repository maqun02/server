try:
    import pyahocorasick
    PYAHOCORASICK_AVAILABLE = True
except ImportError:
    PYAHOCORASICK_AVAILABLE = False
    print("Warning: pyahocorasick module not available, using simple matching instead")

import unicodedata
import html
import re
import binascii
from .models import Fingerprint
from logs.utils import log_action

# 添加纯Python实现的简化版Aho-Corasick算法
class SimplePyAhoCorasick:
    """简化的纯Python Aho-Corasick实现，用作后备"""
    def __init__(self):
        self.keywords = {}
        self.finalized = False
        
    def add_string(self, string, value):
        self.keywords[string] = value
        self.finalized = False
        
    def make_automaton(self):
        self.finalized = True
        
    def iter(self, text):
        if not self.finalized:
            raise ValueError("Automaton not finalized. Call make_automaton() first.")
        results = []
        for keyword, value in self.keywords.items():
            start = 0
            while True:
                pos = text.find(keyword, start)
                if pos == -1:
                    break
                results.append((pos + len(keyword) - 1, value))
                start = pos + 1
        # 按照匹配位置排序，模拟真实的AC自动机输出
        return sorted(results)

class ComponentMatcher:
    """
    使用Aho-Corasick算法进行多模式匹配的组件匹配器
    """
    def __init__(self):
        if PYAHOCORASICK_AVAILABLE:
            self.automaton = pyahocorasick.Automaton()
        else:
            self.automaton = SimplePyAhoCorasick()  # 使用我们的纯Python实现
        self.loaded = False
        self.fingerprints = {}
        self.simple_fingerprints = []  # 备用的简单指纹列表
        self.use_simple_matching = True  # 同时使用简单匹配
    
    def load_fingerprints(self):
        """
        从数据库加载已通过审核的指纹到自动机中
        """
        # 清空简单指纹列表
        self.simple_fingerprints = []
            
        # 获取所有已通过审核的指纹
        fingerprints = Fingerprint.objects.filter(status='approved')
        
        log_action(None, "task_debug", None, "info", 
                 f"加载指纹开始: 从数据库加载了{fingerprints.count()}个已通过审核的指纹")
        
        # 添加到简单指纹列表
        for fingerprint in fingerprints:
            processed_keyword = self._preprocess_text(fingerprint.keyword)
            if processed_keyword:
                self.simple_fingerprints.append((processed_keyword, fingerprint))
                
        # log_action(None, "task_debug", None, "info", 
        #         f"简单指纹加载完成: 已加载{len(self.simple_fingerprints)}个指纹")
        
        # 重置自动机状态
        if PYAHOCORASICK_AVAILABLE:
            # 使用原生pyahocorasick
            self.automaton = pyahocorasick.Automaton()
        else: 
            # 使用我们的简化实现
            self.automaton = SimplePyAhoCorasick()
        
        self.fingerprints = {}
        
        # 添加指纹到自动机
        for i, fingerprint in enumerate(fingerprints):
            # 对指纹进行预处理：小写转换、HTML实体解码、Unicode规范化
            processed_keyword = self._preprocess_text(fingerprint.keyword)
            
            if not processed_keyword:
                log_action(None, "task_debug", None, "warning", 
                         f"跳过空指纹: ID={fingerprint.id}, 组件={fingerprint.component}, 原关键词='{fingerprint.keyword}'")
                continue
                
            try:
                self.automaton.add_string(processed_keyword, (i, fingerprint))
                self.fingerprints[i] = fingerprint
                
                # 记录指纹处理信息
                # if processed_keyword != fingerprint.keyword.lower():
                #     log_action(None, "task_debug", None, "info", 
                #              f"指纹预处理: 组件='{fingerprint.component}', 原关键词='{fingerprint.keyword}' -> 处理后='{processed_keyword}'")
            except Exception as e:
                log_action(None, "task_debug", None, "failure", 
                         f"添加指纹到自动机失败: ID={fingerprint.id}, 组件={fingerprint.component}, 关键词='{fingerprint.keyword}', 错误: {str(e)}")
        
        # 构建自动机的失效函数
        if self.fingerprints:
            try:
                self.automaton.make_automaton()
                self.loaded = True
                log_action(None, "task_debug", None, "success", 
                         f"指纹加载完成: 成功加载了{len(self.fingerprints)}个指纹到自动机")
                
                if not PYAHOCORASICK_AVAILABLE:
                    log_action(None, "task_debug", None, "info", 
                            "使用纯Python实现的Aho-Corasick算法")
            except Exception as e:
                self.loaded = False
                log_action(None, "task_debug", None, "failure", 
                         f"构建自动机失败: {str(e)}")
        else:
            self.loaded = False
            log_action(None, "task_debug", None, "warning", 
                     f"没有可用的指纹: 自动机未构建")
    
    def _preprocess_text(self, text):
        """
        对文本进行预处理：小写转换、HTML实体解码、Unicode规范化
        """
        if not text:
            return ""
            
        # 转为小写
        text = text.lower()
        
        # 解码HTML实体（如 &lt; -> <）
        try:
            text = html.unescape(text)
        except Exception as e:
            log_action(None, "task_debug", None, "warning", 
                     f"HTML实体解码失败: '{text[:30]}...', 错误: {str(e)}")
        
        # Unicode规范化（NFKC模式处理兼容字符和组合字符）
        try:
            text = unicodedata.normalize('NFKC', text)
        except Exception as e:
            log_action(None, "task_debug", None, "warning", 
                     f"Unicode规范化失败: '{text[:30]}...', 错误: {str(e)}")
        
        # 处理特殊的空白字符，统一为单个空格
        try:
            text = re.sub(r'\s+', ' ', text)
        except Exception as e:
            log_action(None, "task_debug", None, "warning", 
                     f"空白字符处理失败: '{text[:30]}...', 错误: {str(e)}")
        
        return text
    
    def _hexdump(self, text, max_len=100):
        """
        将文本转换为十六进制表示，方便调试特殊字符问题
        """
        if not text:
            return "(empty string)"
        
        # 截取前max_len字符
        sample = text[:max_len]
        hex_repr = binascii.hexlify(sample.encode('utf-8')).decode('ascii')
        
        # 格式化显示：每两个十六进制字符一组，用空格分隔
        formatted_hex = ' '.join(hex_repr[i:i+2] for i in range(0, len(hex_repr), 2))
        
        return f"{sample} (hex: {formatted_hex})"
    
    def _simple_match(self, content):
        """
        使用简单的字符串搜索进行匹配
        """
        matches = []
        
        for processed_keyword, fingerprint in self.simple_fingerprints:
            if processed_keyword in content:
                # 获取匹配上下文
                start_pos = content.find(processed_keyword)
                context_start = max(0, start_pos - 10)
                context_end = min(len(content), start_pos + len(processed_keyword) + 10)
                context = content[context_start:context_end]
                
                matches.append((fingerprint.component, fingerprint.keyword))
                # log_action(None, "task_debug", None, "success", 
                #          f"简单匹配成功: 找到组件'{fingerprint.component}', 关键词='{fingerprint.keyword}', 上下文='{context}'")
        
        # log_action(None, "task_debug", None, "info", 
        #          f"简单匹配完成: 找到{len(matches)}个匹配项")
                
        return matches
        
    def match(self, content):
        """
        在内容中匹配所有指纹
        
        Args:
            content: 待匹配内容字符串
        
        Returns:
            匹配到的组件列表 [(组件名称, 关键词), ...]
        """
        # 如果指纹未加载，加载指纹
        if not self.loaded and not self.simple_fingerprints:
            log_action(None, "task_debug", None, "info", 
                     "指纹未加载，首次加载指纹")
            self.load_fingerprints()
        
        if not self.fingerprints and not self.simple_fingerprints:
            log_action(None, "task_debug", None, "warning", 
                     "没有可用的指纹，匹配过程中止")
            return []
        
        if not content:
            log_action(None, "task_debug", None, "warning", 
                     "匹配内容为空，跳过匹配")
            return []
        
        # 记录匹配的内容样本（使用十六进制表示）
        # hex_sample = self._hexdump(content)
        # log_action(None, "task_debug", None, "info", 
        #          f"原始内容样本: {hex_sample}")
        
        # 对内容进行预处理
        processed_content = self._preprocess_text(content)
        
        # 记录处理后的内容样本
        # processed_hex = self._hexdump(processed_content)
        # log_action(None, "task_debug", None, "info", 
        #          f"处理后内容: {processed_hex}")
        
        # 如果预处理后内容变化较大，记录日志
        # if processed_content and content and len(processed_content) / len(content) < 0.9:
        #     log_action(None, "task_debug", None, "info", 
        #              f"内容预处理导致长度变化: {len(content)} -> {len(processed_content)}")
        
        matches = []
        
        # 首先进行简单匹配
        if self.use_simple_matching and self.simple_fingerprints:
            # log_action(None, "task_debug", None, "info", 
            #          f"启动简单匹配: 内容长度={len(processed_content)}, 指纹数量={len(self.simple_fingerprints)}")
            simple_matches = self._simple_match(processed_content)
            matches.extend(simple_matches)
            
        # 使用自动机进行多模式匹配
        if self.loaded:
            try:
                # log_action(None, "task_debug", None, "info", 
                #          f"启动自动机匹配: 内容长度={len(processed_content)}, 指纹数量={len(self.fingerprints)}")
                
                for match in self.automaton.iter(processed_content):
                    idx, (_, fingerprint) = match
                    match_position = match[0] - len(fingerprint.keyword) + 1
                    context = processed_content[max(0, match_position-10):match_position + len(fingerprint.keyword) + 10]
                    
                    matches.append((fingerprint.component, fingerprint.keyword))
                    # log_action(None, "task_debug", None, "success", 
                    #          f"自动机匹配成功: 找到组件'{fingerprint.component}', 关键词='{fingerprint.keyword}', 上下文='{context}'")
                
                # log_action(None, "task_debug", None, "info", 
                #          f"自动机匹配完成: 找到{len(matches) - (len(simple_matches) if self.use_simple_matching else 0)}个匹配项")
            except Exception as e:
                log_action(None, "task_debug", None, "failure", 
                         f"自动机匹配过程发生异常: {str(e)}")
        
        # 去重
        unique_matches = list(set(matches))
        # if len(unique_matches) != len(matches):
        #     log_action(None, "task_debug", None, "info", 
        #              f"去重: 从{len(matches)}个匹配项中去除了{len(matches) - len(unique_matches)}个重复项")
        
        # 如果没有匹配项，记录信息
        if not unique_matches:
            log_action(None, "task_debug", None, "warning", 
                     f"未找到任何匹配项")
        else:
            log_action(None, "task_debug", None, "success", 
                     f"总计找到{len(unique_matches)}个唯一匹配项")
        
        return unique_matches


# 创建一个单例实例，用于全局共享
component_matcher = ComponentMatcher() 