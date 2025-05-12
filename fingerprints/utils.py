import unicodedata
import html
import re
import binascii
from .models import Fingerprint
from logs.utils import log_action

# 纯Python实现的Aho-Corasick算法
class Node:
    def __init__(self):
        self.goto = {}  # 转移函数
        self.out = []   # 输出函数
        self.value = None  # 存储关联的值
        self.fail = None  # 失效函数

class AhoCorasick:
    """纯Python实现的Aho-Corasick算法"""
    def __init__(self):
        self.root = Node()
        self.finalized = False
        self.keywords = {}  # 存储所有关键词及其关联值
        
    def add_string(self, string, value):
        """
        添加一个字符串及其关联值到自动机
        """
        if self.finalized:
            raise ValueError("Automaton is finalized. Cannot add new strings.")
        
        self.keywords[string] = value
        node = self.root
        for symbol in string:
            node = node.goto.setdefault(symbol, Node())
        node.value = value
        node.out.append(string)
        
        self.finalized = False
        return self
        
    def make_automaton(self):
        """
        构建失效函数
        """
        # 利用BFS构建失效函数
        queue = []
        
        # 初始化根节点的所有直接子节点
        for symbol, node in self.root.goto.items():
            queue.append(node)
            node.fail = self.root  # 第一层节点的失效指针指向根
        
        # BFS遍历所有节点，构建失效函数
        while queue:
            current = queue.pop(0)  # 出队
            
            # 将当前节点的所有子节点加入队列
            for symbol, child in current.goto.items():
                queue.append(child)
                
                # 寻找当前节点的失效节点
                fail_node = current.fail
                
                # 寻找失效节点的转移
                while fail_node is not None and symbol not in fail_node.goto:
                    fail_node = fail_node.fail
                
                # 设置子节点的失效指针
                child.fail = fail_node.goto[symbol] if fail_node else self.root
                
                # 将失效节点的输出添加到当前节点
                if child.fail.out:
                    child.out.extend(child.fail.out)
        
        self.finalized = True
        return self
        
    def iter(self, text):
        """
        在文本中查找所有匹配项
        """
        if not self.finalized:
            raise ValueError("Automaton not finalized. Call make_automaton() first.")
        
        results = []  # 存储结果，格式为(end_pos, value)
        current = self.root
        
        # 遍历文本的每个字符
        for i, symbol in enumerate(text):
            # 如果当前字符没有匹配的转移，则按失效函数跳转
            while current is not None and symbol not in current.goto:
                current = current.fail
            
            # 如果走到了根节点还没匹配，重新开始
            if current is None:
                current = self.root
                continue
            
            # 转移到下一个状态
            current = current.goto[symbol]
            
            # 收集所有匹配结果
            for pattern in current.out:
                end_pos = i
                results.append((end_pos, self.keywords[pattern]))
        
        return sorted(results)  # 按照结束位置排序

# 为了向后兼容，保留旧命名
PurePyAhoCorasick = AhoCorasick 
SimplePyAhoCorasick = AhoCorasick

class ComponentMatcher:
    """
    使用Aho-Corasick算法进行多模式匹配的组件匹配器
    """
    def __init__(self):
        self.automaton = AhoCorasick()  # 使用纯Python实现的AC自动机
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
        
        # 重置自动机状态
        self.automaton = AhoCorasick()
        
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
        
        # 对内容进行预处理
        processed_content = self._preprocess_text(content)
        
        matches = []
        
        # 首先进行简单匹配
        if self.use_simple_matching and self.simple_fingerprints:
            simple_matches = self._simple_match(processed_content)
            matches.extend(simple_matches)
            
        # 使用自动机进行多模式匹配
        if self.loaded:
            try:
                for match in self.automaton.iter(processed_content):
                    idx, (_, fingerprint) = match
                    match_position = match[0] - len(fingerprint.keyword) + 1
                    context = processed_content[max(0, match_position-10):match_position + len(fingerprint.keyword) + 10]
                    
                    matches.append((fingerprint.component, fingerprint.keyword))
            except Exception as e:
                log_action(None, "task_debug", None, "failure", 
                         f"自动机匹配过程发生异常: {str(e)}")
        
        # 去重
        unique_matches = list(set(matches))
        
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