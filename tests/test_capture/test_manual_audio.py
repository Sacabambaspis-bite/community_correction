"""capture@1.2 手动录音与定时模式兼容性测试。"""

from __future__ import annotations

import io
import json
import sys
import threading
import time
import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.capture import session as capture_session
from app.capture.audio import record_audio
from app.capture.models import AudioResult, FaceResult, FrameResult

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


def _wav_bytes(seconds: float, sample_rate: int = 16000) -> bytes:
    frames = max(int(seconds * sample_rate), 1)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(np.full(frames, 10000, dtype=np.int16).tobytes())
    return buffer.getvalue()


def _patch_face_branch(monkeypatch, face_result: FaceResult) -> None:
    monkeypatch.setattr(
        capture_session,
        "capture_frame",
        lambda **kwargs: FrameResult(
            status="ok",
            frame=np.zeros((720, 1280, 3), dtype=np.uint8),
            resolution=(1280, 720),
        ),
    )
    monkeypatch.setattr(capture_session, "detect_face", lambda frame: face_result)
    monkeypatch.setattr(capture_session, "crop_face", lambda *args, **kwargs: b"jpeg")


def test_manual_mode_requires_stop_event(tmp_path):
    with pytest.raises(ValueError):
        record_audio(duration_sec=None)

    with pytest.raises(ValueError):
        capture_session.run_capture_session(
            SUBJECT_ID,
            SESSION_ID,
            tmp_path,
            duration_sec=None,
        )


def test_record_audio_manual_waits_for_stop_event(monkeypatch):
    """未置位时持续分块读取；置位后才返回 WAV。"""
    stop_event = threading.Event()
    first_block_read = threading.Event()

    class FakeInputStream:
        def __init__(self, *, samplerate, channels, blocksize, **kwargs):
            self.samplerate = samplerate
            self.channels = channels
            self.blocksize = blocksize

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self, frames):
            first_block_read.set()
            time.sleep(frames / self.samplerate)
            return np.full((frames, self.channels), 10000, dtype=np.int16), False

    fake_sounddevice = SimpleNamespace(
        check_input_settings=lambda **kwargs: None,
        InputStream=FakeInputStream,
    )
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sounddevice)

    results = []
    errors = []

    def target():
        try:
            results.append(record_audio(duration_sec=None, stop_event=stop_event))
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    try:
        assert first_block_read.wait(timeout=2.0)
        time.sleep(0.15)
        assert thread.is_alive()
        assert results == []
    finally:
        stop_event.set()
        thread.join(timeout=2.0)

    assert not thread.is_alive()
    assert errors == []
    assert len(results) == 1
    result = results[0]
    assert result.status == "ok"
    assert result.wav_bytes is not None
    assert result.duration_sec >= 0.1
    assert result.speech_ratio == 1.0
    with wave.open(io.BytesIO(result.wav_bytes), "rb") as wav:
        assert wav.getframerate() == 16000
        assert wav.getnchannels() == 1
        assert wav.getnframes() / wav.getframerate() == pytest.approx(
            result.duration_sec, abs=0.001
        )


@pytest.mark.parametrize(
    "face_result, expected_status, expected_codes, face_exists",
    [
        (
            FaceResult(status="ok", bbox=(400, 160, 240, 240), detector="haar"),
            "ok",
            [],
            True,
        ),
        (
            FaceResult(status="error", reason="detector_unavailable"),
            "partial",
            ["detector_unavailable"],
            False,
        ),
    ],
)
def test_manual_session_stops_only_on_event(
    monkeypatch,
    tmp_path,
    face_result,
    expected_status,
    expected_codes,
    face_exists,
):
    _patch_face_branch(monkeypatch, face_result)
    stop_event = threading.Event()
    recording_started = threading.Event()
    recording_started_at = []
    session_dir = _session_dir(tmp_path)

    def fake_record_audio(
        duration_sec=30.0,
        sample_rate=16000,
        channels=1,
        mic_index=0,
        min_speech_ratio=0.05,
        stop_event=None,
    ):
        assert duration_sec is None
        assert stop_event is not None
        recording_started_at.append(time.monotonic())
        recording_started.set()
        stop_event.wait()
        elapsed = max(time.monotonic() - recording_started_at[0], 0.001)
        return AudioResult(
            status="ok",
            wav_bytes=_wav_bytes(elapsed, sample_rate),
            duration_sec=round(elapsed, 3),
            speech_ratio=1.0,
        )

    monkeypatch.setattr(capture_session, "record_audio", fake_record_audio)
    results = []
    errors = []

    def target():
        try:
            results.append(
                capture_session.run_capture_session(
                    SUBJECT_ID,
                    SESSION_ID,
                    tmp_path,
                    duration_sec=None,
                    stop_event=stop_event,
                )
            )
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    try:
        assert recording_started.wait(timeout=2.0)
        time.sleep(0.12)
        assert thread.is_alive()
        assert not (session_dir / "audio.wav").exists()
        assert not (session_dir / "meta.json").exists()
        stop_requested_at = time.monotonic()
    finally:
        stop_event.set()
        thread.join(timeout=2.0)

    assert not thread.is_alive()
    assert errors == []
    assert len(results) == 1
    result = results[0]
    assert result.capture_status == expected_status
    assert result.codes == expected_codes
    assert (session_dir / "face.jpg").is_file() is face_exists
    assert (session_dir / "audio.wav").is_file()
    assert (session_dir / "meta.json").is_file()
    assert result.audio_path is not None
    assert result.meta["audio"]["manual"] is True
    assert result.meta["audio"]["recorded"] is True
    assert result.meta["audio"]["duration_sec"] >= 0.1
    assert result.meta["audio"]["duration_sec"] == pytest.approx(
        stop_requested_at - recording_started_at[0], abs=0.08
    )


def test_fake_both_manual_capture_closed_loop(monkeypatch, tmp_path):
    """CAPTURE_FAKE=1 支持开始 → 等待 → stop → captured 所需产物。"""
    monkeypatch.setenv("CAPTURE_FAKE", "1")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("假采集不应触达真实设备")

    monkeypatch.setattr(capture_session, "capture_frame", fail_if_called)
    monkeypatch.setattr(capture_session, "record_audio", fail_if_called)
    stop_event = threading.Event()
    session_dir = _session_dir(tmp_path)
    results = []
    errors = []

    def target():
        try:
            results.append(
                capture_session.run_capture_session(
                    SUBJECT_ID,
                    SESSION_ID,
                    tmp_path,
                    duration_sec=None,
                    stop_event=stop_event,
                )
            )
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 2.0
        while not (session_dir / "face.jpg").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert (session_dir / "face.jpg").is_file()
        time.sleep(0.08)
        assert thread.is_alive()
        assert not (session_dir / "audio.wav").exists()
        assert not (session_dir / "meta.json").exists()
    finally:
        stop_event.set()
        thread.join(timeout=2.0)

    assert not thread.is_alive()
    assert errors == []
    assert len(results) == 1
    result = results[0]
    assert result.capture_status == "ok"
    assert result.codes == []
    assert result.face_path is not None
    assert result.audio_path is not None
    assert (session_dir / "audio.wav").is_file()
    assert (session_dir / "meta.json").is_file()
    assert result.meta["audio"]["manual"] is True
    assert result.meta["audio"]["duration_sec"] >= 0.05

    on_disk = json.loads((session_dir / "meta.json").read_text(encoding="utf-8"))
    assert on_disk["capture_status"] == "ok"
    assert on_disk["coverage"] == "both"
    assert on_disk["audio"]["duration_sec"] == result.meta["audio"]["duration_sec"]


def test_fake_timed_mode_keeps_existing_call_and_meta(monkeypatch, tmp_path):
    monkeypatch.setenv("CAPTURE_FAKE", "1")
    _patch_face_branch(
        monkeypatch,
        FaceResult(status="ok", bbox=(400, 160, 240, 240), detector="haar"),
    )
    calls = []

    def fake_record_audio(
        duration_sec=30.0,
        sample_rate=16000,
        channels=1,
        mic_index=0,
        min_speech_ratio=0.05,
    ):
        calls.append(duration_sec)
        return AudioResult(
            status="ok",
            wav_bytes=_wav_bytes(duration_sec, sample_rate),
            duration_sec=duration_sec,
            speech_ratio=1.0,
        )

    monkeypatch.setattr(capture_session, "record_audio", fake_record_audio)
    already_stopped = threading.Event()
    already_stopped.set()
    result = capture_session.run_capture_session(
        SUBJECT_ID,
        SESSION_ID,
        tmp_path,
        duration_sec=0.25,
        stop_event=already_stopped,
    )

    assert result.capture_status == "ok"
    assert calls == [0.25]
    assert result.meta["audio"]["duration_sec"] == 0.25
    assert "manual" not in result.meta["audio"]
    assert (_session_dir(tmp_path) / "audio.wav").is_file()
