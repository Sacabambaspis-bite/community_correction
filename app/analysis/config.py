"""分析 mock 配置；grading 阈值暂不反向依赖。"""

from __future__ import annotations

import os

# TODO: 待 grading-engineer 提供 app/grading/config.py 后统一适配。
CONFIDENCE_THRESHOLD = 0.6
THRESHOLD_PROFILE = "default@v1"


def get_mock_scenario() -> str:
    return os.environ.get("MOCK_SCENARIO", "normal").strip() or "normal"
