import sys
print(f"Python version: {sys.version}")
print(f"Python path: {sys.executable}")

try:
    import pyahocorasick
    print(f"pyahocorasick imported successfully, version: {pyahocorasick.__version__ if hasattr(pyahocorasick, '__version__') else 'unknown'}")
    
    # 测试基本功能
    automaton = pyahocorasick.Automaton()
    automaton.add_string("abc", "abc")
    automaton.add_string("xyz", "xyz")
    automaton.make_automaton()
    print("automaton created successfully")
    
    # 测试匹配
    text = "test abc and xyz"
    matches = list(automaton.iter(text))
    print(f"Found matches: {matches}")
    
except ImportError as e:
    print(f"Failed to import pyahocorasick: {e}")
except Exception as e:
    print(f"Error when using pyahocorasick: {e}") 