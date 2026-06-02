"""Per-agent iteration budget — 借鉴 Hermes Agent，线程安全的迭代计数器。"""
from __future__ import annotations

import threading


class IterationBudget:
    """每次对话的工具调用轮次预算。

    借鉴 Hermes Agent 设计：
    - max_total 可通过 AgentConfig 配置
    - consume() 在每轮 LLM→Tool→LLM 前调用
    - refund() 退还失败工具调用的轮次（不计入预算）
    - remaining < 3 时 Agent 应收到"请尽快总结"的系统提示
    """

    def __init__(self, max_total: int):
        self.max_total = max_total
        self._used = 0
        self._lock = threading.Lock()

    def consume(self) -> bool:
        """尝试消耗一轮预算。返回 True 表示还有剩余。"""
        with self._lock:
            if self._used >= self.max_total:
                return False
            self._used += 1
            return True

    def refund(self) -> None:
        """退还一轮预算（工具执行失败时调用）。"""
        with self._lock:
            if self._used > 0:
                self._used -= 1

    @property
    def used(self) -> int:
        with self._lock:
            return self._used

    @property
    def remaining(self) -> int:
        with self._lock:
            return max(0, self.max_total - self._used)

    @property
    def is_low(self) -> bool:
        """剩余 ≤3 轮时提示 Agent 尽快总结。"""
        return self.remaining <= 3
