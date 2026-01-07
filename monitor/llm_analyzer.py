import os
import json
import random
from typing import Dict, Any, Optional

from openai import OpenAI
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config

class LLMAnalyzer:
    """
    AI 分析模块，用于分析日志错误原因并提供修复建议。
    目前支持：
    1. 模拟模式 (Mock): 用于演示和测试，不消耗 Token。
    2. DeepSeek 模式: 使用 OpenAI SDK 调用兼容接口。
    """
    
    def __init__(self, provider="deepseek"):
        self.provider = provider
        # 从配置中加载
        self.api_key = Config.LLM_API_KEY
        self.base_url = Config.LLM_BASE_URL
        self.model = Config.LLM_MODEL
        
        if self.provider == "deepseek":
            try:
                self.client = OpenAI(
                    base_url=self.base_url,
                    api_key=self.api_key
                )
            except Exception as e:
                print(f"Failed to initialize OpenAI client: {e}")
                self.client = None

    def analyze_error(self, log_entry: Dict[str, Any]) -> str:
        """
        分析单条错误日志。
        
        Args:
            log_entry: 包含日志完整信息的字典 (message, metadata, error_stack等)。
            
        Returns:
            str: Markdown 格式的分析报告。
        """
        if self.provider == "mock":
            return self._mock_analysis(log_entry)
        else:
            return self._deepseek_analysis(log_entry)

    def _deepseek_analysis(self, log_entry: Dict[str, Any]) -> str:
        if not self.client:
            return "⚠️ AI 客户端初始化失败，请检查 API 配置。"

        # 构建 Prompt
        error_stack = log_entry.get("metadata", {}).get("error_stack", "无堆栈信息")
        prompt = f"""
你是一个资深的 Python 运维专家。请分析以下错误日志，并给出简短的分析报告。

**日志信息**:
- 服务: {log_entry.get('service_name')}
- 错误消息: {log_entry.get('message')}
- 堆栈追踪:
```
{error_stack}
```

**要求**:
1. 使用 Markdown 格式。
2. 包含三个部分：核心问题、原因分析、修复建议。
3. 修复建议中最好包含代码示例。
4. 保持简洁，不要废话。
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2048,
                temperature=0.3,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"⚠️ AI 分析请求失败: {str(e)}\n\n(已回退到 Mock 模式)\n\n" + self._mock_analysis(log_entry)

    def _mock_analysis(self, log_entry: Dict[str, Any]) -> str:
        """
        生成模拟的 AI 分析结果。
        根据日志内容关键词返回预设的分析模板。
        """
        message = log_entry.get("message", "").lower()
        error_stack = log_entry.get("metadata", {}).get("error_stack", "")
        
        # 模拟思考过程延迟
        import time
        time.sleep(1.5) 
        
        if "division by zero" in error_stack or "zero" in message:
            return """
### 🤖 AI 智能分析报告

**核心问题**: 除零异常 (ZeroDivisionError)

**原因分析**:
代码尝试将一个数字除以零。这通常发生在计算比率或百分比时，分母变量（如 `total_count` 或 `duration`）意外为 0。

**定位建议**:
1. 检查 `simulation/generate_logs.py` 中的模拟逻辑。
2. 验证业务逻辑中分母的来源，确保其在计算前已正确初始化且不为 0。

**修复代码示例**:
```python
if total > 0:
    ratio = count / total
else:
    ratio = 0  # 处理边界情况
```
"""
        elif "connection" in message or "timeout" in message:
             return """
### 🤖 AI 智能分析报告

**核心问题**: 网络连接故障

**原因分析**:
服务无法连接到下游依赖（如数据库或外部 API）。可能是由于网络波动、防火墙拦截或目标服务宕机。

**建议步骤**:
1. 检查目标服务的健康状态。
2. 确认安全组/防火墙规则是否允许出站流量。
3. 增加重试机制 (Retry Logic)。
"""
        else:
            return f"""
### 🤖 AI 智能分析报告

**初步诊断**: 未知运行时错误

**日志摘要**:
> {log_entry.get('message')}

**通用建议**:
该错误模式较为通用。建议查看 `metadata.error_stack` 中的详细堆栈跟踪，定位到具体代码行。从上下文看，这可能是一个随机生成的模拟错误。
"""

# 单例模式，方便导入使用
analyzer = LLMAnalyzer()
