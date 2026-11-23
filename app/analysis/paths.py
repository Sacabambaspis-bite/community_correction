"""会话路径构造与目录逃逸防护。"""

from __future__ import annotations

from pathlib import Path, PureWindowsPath

from app.analysis.errors import AnalysisInputError


def session_directory(storage_root: Path, subject_id: str, session_id: str) -> Path:
    return (
        Path(storage_root).expanduser().resolve()
        / "subjects"
        / subject_id
        / "sessions"
        / session_id
    )


def transcript_relative_path(subject_id: str, session_id: str) -> str:
    return "/".join(
        ("subjects", subject_id, "sessions", session_id, "transcript.txt")
    )


def resolve_session_file(
    storage_root: Path,
    subject_id: str,
    session_id: str,
    relative_path: str,
) -> Path:
    """把相对路径限制在本会话目录内，错误消息不回显输入路径。"""
    candidate = Path(relative_path)
    if (
        candidate.is_absolute()
        or PureWindowsPath(relative_path).is_absolute()
        or ".." in candidate.parts
    ):
        raise AnalysisInputError("unsafe_media_path")

    base = session_directory(storage_root, subject_id, session_id)
    resolved = (Path(storage_root).expanduser().resolve() / candidate).resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        raise AnalysisInputError("unsafe_media_path") from None
    return resolved
