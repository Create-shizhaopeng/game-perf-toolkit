"""perfetto_analysis 测试配置。

Agent 核心重构（2026-05-26，DES-001）将模块内的 agent 编排 / 结果压缩 /
MCP 客户端等逻辑迁移到 ``toolkit/agent`` 与 ``toolkit/core/mcp``，
以下测试文件 import 的模块（``src.agent``、``src.result_compressor``、
``src.mcp_client``、``src.analysis_toolkit`` 等）已不存在。

保留文件备查但不收集；若 ``toolkit/agent`` 有等价实现，应迁移测试而非恢复此文件。
详见 docs/PROGRESS.md「2026-08-06」条目。
"""

collect_ignore = [
    "test_compressor.py",
    "test_g0_reasoning_chain.py",
    "test_g2_similar_case.py",
    "test_g3_eviction_promotion.py",
    "test_g5_skill_knowledge.py",
    "test_mcp_client.py",
    "test_orchestrator_degradation.py",
    "test_regression.py",
    "test_result_compressor.py",
    "test_tool_return.py",
    "test_toolkit.py",
]
