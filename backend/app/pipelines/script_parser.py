"""剧本解析管线 — 向后兼容代理。

实际实现已拆分到子模块：
- _llm_utils.py: LLM 调用工具
- _extraction_stages.py: 提取阶段逻辑
- _orchestrator.py: 主编排入口
"""
from app.pipelines._orchestrator import parse_script_async

__all__ = ["parse_script_async"]
