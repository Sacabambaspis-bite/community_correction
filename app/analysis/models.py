"""分析管线的公开输入与独立运行状态包装。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

AnalysisStatus = Literal["done", "degraded", "failed"]


@dataclass(frozen=True)
class ProviderInput:
    """单路 Provider 所需的只读上下文；媒体路径均为相对路径。"""

    session_id: str
    subject_id: str
    storage_root: Path
    face_path: str | None = None
    audio_path: str | None = None
    transcript_path: str | None = None
    duration_sec: float = 0.0
    speech_ratio: float = 0.0


@dataclass(frozen=True)
class AnalysisInput:
    """总管输入。coverage 应由 CaptureSession.coverage 传入。"""

    session_id: str
    subject_id: str
    capture_status: str
    coverage: str | None
    storage_root: Path
    face_path: str | None = None
    audio_path: str | None = None
    duration_sec: float = 0.0
    speech_ratio: float = 0.0
    session_status: str = "captured"


@dataclass(frozen=True)
class AnalysisRunResult:
    """运行状态与纯 AnalysisResult 分离，失败时不产出 grading 输入。"""

    analysis_status: AnalysisStatus
    result: dict[str, Any] | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_status": self.analysis_status,
            "result": self.result,
            "error": self.error,
        }
