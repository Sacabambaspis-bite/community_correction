"""capture@1.2 会话状态机测试。

只断言 `capture_status`、`codes` / `warnings[].code`、`coverage`、
`meta.error` 与文件存在性；不断言任何 `reason` 文案。
摄像头帧、人脸检测、麦克风录音全部用 monkeypatch 伪造，存储根目录用 tmp_path，
不访问真实设备。
"""

from __future__ import annotations

import io
import json
import wave
from pathlib import Path

import numpy as np

from app.capture import session as capture_session
from app.capture.models import AudioResult, FaceResult, FrameResult

SUBJECT_ID = "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c"
SESSION_ID = "8f3c1b2e-4a5d-4c6e-9f10-1a2b3c4d5e6f"

FACE_OK = FaceResult(status="ok", bbox=(400, 160, 240, 240), detector="haar")


def _session_dir(storage_root: Path) -> Path:
    return (
        Path(storage_root)
        / "subjects"
        / SUBJECT_ID
        / "sessions"
        / SESSION_ID
    )


def _fake_frame(width: int = 1280, height: int = 720):
    return np.zeros((height, width, 3), dtype=np.uint8)


def _wav_bytes(seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(
            np.zeros(int(seconds * sample_rate), dtype=np.int16).tobytes()
        )
    return buffer.getvalue()


def _audio_ok() -> AudioResult:
    return AudioResult(
        status="ok",
        wav_bytes=_wav_bytes(),
        duration_sec=1.0,
        speech_ratio=0.62,
    )


def _warning_codes(meta: dict) -> list:
    return [entry["code"] for entry in meta["warnings"]]


def _run(monkeypatch, storage_root, *, frame_result, face_result, audio_result,
         device_index=0, mic_index=0):
    """用假帧 / 假检测 / 假录音跑一次会话，返回 CaptureResult。"""

    def fake_capture_frame(device_index=0, resolution=(1280, 720), **kwargs):
        return frame_result

    def fake_detect_face(frame):
        return face_result

    def fake_record_audio(duration_sec=30.0, sample_rate=16000, channels=1,
                          mic_index=0, min_speech_ratio=0.05):
        return audio_result

    monkeypatch.setattr(capture_session, "capture_frame", fake_capture_frame)
    monkeypatch.setattr(capture_session, "detect_face", fake_detect_face)
    monkeypatch.setattr(capture_session, "record_audio", fake_record_audio)

    return capture_session.run_capture_session(
        SUBJECT_ID,
        SESSION_ID,
        storage_root,
        device_index=device_index,
        mic_index=mic_index,
    )


def test_ok(monkeypatch, tmp_path):
    result = _run(
        monkeypatch,
        tmp_path,
        frame_result=FrameResult(
            status="ok", frame=_fake_frame(), resolution=(1280, 720)
        ),
        face_result=FACE_OK,
        audio_result=_audio_ok(),
    )
    session_dir = _session_dir(tmp_path)

    assert result.capture_status == "ok"
    assert result.codes == []
    assert result.meta["coverage"] == "both"
    assert result.meta["warnings"] == []
    assert result.meta["error"] is None
    assert (session_dir / "face.jpg").is_file()
    assert (session_dir / "audio.wav").is_file()
    assert (session_dir / "meta.json").is_file()

    on_disk = json.loads((session_dir / "meta.json").read_text(encoding="utf-8"))
    assert on_disk["capture_status"] == "ok"


def test_audio_too_short_yields_no_audio(monkeypatch, tmp_path):
    """契约 §3 / §7：音频过短是业务性缺失，判 no_audio，不是 partial。"""
    result = _run(
        monkeypatch,
        tmp_path,
        frame_result=FrameResult(
            status="ok", frame=_fake_frame(), resolution=(1280, 720)
        ),
        face_result=FACE_OK,
        audio_result=AudioResult(
            status="no_audio",
            duration_sec=1.0,
            speech_ratio=0.0,
            reason="speech_ratio_too_low",
        ),
    )
    session_dir = _session_dir(tmp_path)

    assert result.capture_status == "no_audio"
    assert result.meta["coverage"] == "face_only"
    assert result.meta["error"] is None
    assert "audio_too_short" in result.codes
    assert "audio_too_short" in _warning_codes(result.meta)
    assert (session_dir / "face.jpg").is_file()
    assert not (session_dir / "audio.wav").exists()
    assert (session_dir / "meta.json").is_file()


def test_partial_when_audio_device_unavailable(monkeypatch, tmp_path):
    result = _run(
        monkeypatch,
        tmp_path,
        frame_result=FrameResult(
            status="ok", frame=_fake_frame(), resolution=(1280, 720)
        ),
        face_result=FACE_OK,
        audio_result=AudioResult(
            status="error", duration_sec=0.0, reason="audio_device_unavailable"
        ),
    )
    session_dir = _session_dir(tmp_path)

    assert result.capture_status == "partial"
    assert result.meta["coverage"] == "face_only"
    assert result.meta["error"] is None
    assert "audio_device_unavailable" in result.codes
    assert "audio_device_unavailable" in _warning_codes(result.meta)
    assert (session_dir / "face.jpg").is_file()
    assert not (session_dir / "audio.wav").exists()
    assert (session_dir / "meta.json").is_file()


def test_no_face(monkeypatch, tmp_path):
    result = _run(
        monkeypatch,
        tmp_path,
        frame_result=FrameResult(
            status="ok", frame=_fake_frame(), resolution=(1280, 720)
        ),
        face_result=FaceResult(status="no_face"),
        audio_result=_audio_ok(),
    )
    session_dir = _session_dir(tmp_path)

    assert result.capture_status == "no_face"
    assert result.meta["coverage"] == "audio_only"
    assert result.meta["face"] is None
    assert result.meta["error"] is None
    assert "no_face" in result.codes
    assert "no_face" in _warning_codes(result.meta)
    assert not (session_dir / "face.jpg").exists()
    assert (session_dir / "audio.wav").is_file()
    assert (session_dir / "meta.json").is_file()


def test_no_face_no_audio(monkeypatch, tmp_path):
    result = _run(
        monkeypatch,
        tmp_path,
        frame_result=FrameResult(
            status="ok", frame=_fake_frame(), resolution=(1280, 720)
        ),
        face_result=FaceResult(status="no_face"),
        audio_result=AudioResult(
            status="no_audio",
            duration_sec=1.0,
            speech_ratio=0.0,
            reason="speech_ratio_too_low",
        ),
    )
    session_dir = _session_dir(tmp_path)

    assert result.capture_status == "no_face_no_audio"
    assert result.meta["coverage"] is None
    assert result.meta["face"] is None
    assert result.meta["error"] is None
    assert "no_face" in result.codes
    assert "audio_too_short" in result.codes
    assert "no_face" in _warning_codes(result.meta)
    assert "audio_too_short" in _warning_codes(result.meta)
    assert not (session_dir / "face.jpg").exists()
    assert not (session_dir / "audio.wav").exists()
    assert (session_dir / "meta.json").is_file()


def test_error_when_camera_unavailable(monkeypatch, tmp_path):
    result = _run(
        monkeypatch,
        tmp_path,
        frame_result=FrameResult(
            status="error", frame=None, reason="camera_unavailable"
        ),
        face_result=FACE_OK,
        audio_result=_audio_ok(),
        device_index=99,
    )
    session_dir = _session_dir(tmp_path)

    assert result.capture_status == "error"
    assert result.meta["coverage"] is None
    assert result.meta["face"] is None
    assert result.meta["error"] is not None
    assert result.meta["error"]["code"] == "camera_unavailable"
    assert result.codes[0] == "camera_unavailable"
    assert not (session_dir / "face.jpg").exists()
    assert not (session_dir / "audio.wav").exists()
    assert (session_dir / "meta.json").is_file()
