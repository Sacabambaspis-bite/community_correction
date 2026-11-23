"""四路 Provider 的统一接口。"""

from __future__ import annotations

from typing import Any, Protocol

from app.analysis.models import ProviderInput


class BaseProvider(Protocol):
    name: str
    version: str

    def available(self) -> bool:
        """返回当前 Provider 是否可执行。"""

    def analyze(self, input: ProviderInput) -> dict[str, Any]:
        """返回 status/output/confidence/latency_ms/reason 五键字典。"""
