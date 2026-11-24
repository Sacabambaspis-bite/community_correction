"""capture@1.2 face_only 签到采集测试。"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from app.capture import session as capture_session
from app.capture.models import FaceResult, FrameResult

SUBJECT_ID = "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c"
SESSION_ID = "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f"


def _session_dir(storage_root: Path) -> Path:
    return (
        Path(storage_root)
        / "subjects"
        / SUBJECT_ID
        / "sessions"
        / SESSION_ID
    )


def test_face_only_fake_capture_ok(monkeypatch, tmp_path):
    monkeypatch.setenv("CAPTURE_FAKE", "1")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("face_only 假采集不应触达真实设备")

    monkeypatch.setattr(capture_session, "capture_frame", fail_if_called)
    monkeypatch.setattr(capture_session, "record_audio", fail_if_called)

    result = capture_session.run_capture_session(
        SUBJECT_ID,
        SESSION_ID,
        tmp_path,
        mode="face_only",
    )
    session_dir = _session_dir(tmp_path)

    assert result.capture_status == "ok"
    assert result.face_path is not None
    assert result.audio_path is None
    assert result.codes == []
    assert (session_dir / "face.jpg").is_file()
    assert not (session_dir / "audio.wav").exists()
    assert (session_dir / "meta.json").is_file()

    on_disk = json.loads((session_dir / "meta.json").read_text(encoding="utf-8"))
    assert on_disk["mode"] == "face_only"
    assert on_disk["capture_status"] == "ok"
    assert on_disk["coverage"] == "face_only"
    assert on_disk["audio"]["audio_path"] is None


def test_face_only_no_face(monkeypatch, tmp_path):
    monkeypatch.delenv("CAPTURE_FAKE", raising=False)
    audio_calls = []

    def fake_capture_frame(device_index=0, resolution=(1280, 720), **kwargs):
        return FrameResult(
            status="ok",
            frame=np.zeros((720, 1280, 3), dtype=np.uint8),
            resolution=(1280, 720),
        )

    def fake_detect_face(frame):
        return FaceResult(status="no_face")

    def fake_record_audio(*args, **kwargs):
        audio_calls.append(True)
        raise AssertionError("face_only 不应启动音频录制")

    monkeypatch.setattr(capture_session, "capture_frame", fake_capture_frame)
    monkeypatch.setattr(capture_session, "detect_face", fake_detect_face)
    monkeypatch.setattr(capture_session, "record_audio", fake_record_audio)

    result = capture_session.run_capture_session(
        SUBJECT_ID,
        SESSION_ID,
        tmp_path,
        mode="face_only",
    )
    session_dir = _session_dir(tmp_path)

    assert result.capture_status == "no_face"
    assert result.face_path is None
    assert result.audio_path is None
    assert result.meta["coverage"] is None
    assert result.meta["error"] is None
    assert result.codes == ["no_face"]
    assert [entry["code"] for entry in result.meta["warnings"]] == ["no_face"]
    assert audio_calls == []
    assert not (session_dir / "face.jpg").exists()
    assert not (session_dir / "audio.wav").exists()
    assert (session_dir / "meta.json").is_file()

    on_disk = json.loads((session_dir / "meta.json").read_text(encoding="utf-8"))
    assert on_disk["mode"] == "face_only"
    assert on_disk["capture_status"] == "no_face"
