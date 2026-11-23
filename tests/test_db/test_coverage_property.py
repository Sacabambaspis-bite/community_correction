"""`sessions.coverage` 只读属性的推导规则。

纯模型对象构造，不连库、不写 storage。对应 capture.md §3.1 的 coverage 双向断言。
"""

from __future__ import annotations

from typing import Optional

import pytest

from app.db.models import CaptureSession

_FACE = "subjects/s/sessions/x/face.jpg"
_AUDIO = "subjects/s/sessions/x/audio.wav"


@pytest.mark.parametrize(
    ("capture_status", "face_path", "audio_path", "expected"),
    [
        ("ok", _FACE, _AUDIO, "both"),
        ("partial", _FACE, None, "face_only"),
        ("partial", None, _AUDIO, "audio_only"),
        ("no_face", None, _AUDIO, "audio_only"),
        ("no_audio", _FACE, None, "face_only"),
        ("no_face_no_audio", None, None, None),
        ("error", None, None, None),
    ],
)
def test_coverage_property(
    capture_status: str,
    face_path: Optional[str],
    audio_path: Optional[str],
    expected: Optional[str],
) -> None:
    session = CaptureSession(
        capture_status=capture_status,
        face_path=face_path,
        audio_path=audio_path,
    )
    assert session.coverage == expected
