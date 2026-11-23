"""麦克风录音，WAV 在内存中生成，不落临时文件。"""

from __future__ import annotations

import io
import wave

from .config import SPEECH_FRAME_MS, SPEECH_RMS_THRESHOLD
from .models import AudioResult


def _encode_wav(pcm, sample_rate: int, channels: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(int(channels))
        wav.setsampwidth(2)  # int16
        wav.setframerate(int(sample_rate))
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()


def record_audio(
    duration_sec: float = 30.0,
    sample_rate: int = 16000,
    channels: int = 1,
    mic_index: int = 0,
    min_speech_ratio: float = 0.05,
) -> AudioResult:
    """录制指定时长音频并计算有效语音占比。"""
    try:
        import numpy as np
        import sounddevice as sd
    except Exception:
        return AudioResult(status="error", reason="sounddevice_unavailable")

    try:
        total_frames = int(float(duration_sec) * int(sample_rate))
    except Exception:
        return AudioResult(status="error", reason="invalid_duration")
    if total_frames <= 0 or int(sample_rate) <= 0 or int(channels) <= 0:
        return AudioResult(status="error", reason="invalid_duration")

    try:
        data = sd.rec(
            total_frames,
            samplerate=int(sample_rate),
            channels=int(channels),
            dtype="int16",
            device=mic_index,
        )
        sd.wait()
    except Exception:
        return AudioResult(status="error", reason="mic_unavailable")

    if data is None:
        return AudioResult(status="error", reason="mic_unavailable")

    data = np.asarray(data)
    if data.size == 0:
        return AudioResult(status="no_audio", reason="empty_audio")

    mono = data.astype(np.float64) / 32768.0
    if mono.ndim > 1:
        mono = mono.mean(axis=1)
    duration = round(float(mono.shape[0]) / float(sample_rate), 3)

    # 按 30ms 一帧计算 RMS，归一化后高于阈值视为有效语音帧
    frame_length = max(int(int(sample_rate) * SPEECH_FRAME_MS / 1000), 1)
    total_windows = mono.shape[0] // frame_length
    if total_windows <= 0:
        speech_ratio = 0.0
    else:
        windows = mono[: total_windows * frame_length].reshape(total_windows, frame_length)
        rms = np.sqrt(np.mean(windows**2, axis=1))
        speech_ratio = float((rms > SPEECH_RMS_THRESHOLD).sum()) / float(total_windows)

    if speech_ratio < float(min_speech_ratio):
        return AudioResult(
            status="no_audio",
            duration_sec=duration,
            speech_ratio=round(speech_ratio, 4),
            reason="speech_ratio_too_low",
        )

    wav_bytes = _encode_wav(np.asarray(data, dtype=np.int16), sample_rate, channels)
    return AudioResult(
        status="ok",
        wav_bytes=wav_bytes,
        duration_sec=duration,
        speech_ratio=round(speech_ratio, 4),
    )
