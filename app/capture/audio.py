"""麦克风录音，WAV 在内存中生成，不落临时文件。"""

from __future__ import annotations

import io
import threading
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
    duration_sec: float | None = 30.0,
    sample_rate: int = 16000,
    channels: int = 1,
    mic_index: int = 0,
    min_speech_ratio: float = 0.05,
    stop_event: threading.Event | None = None,
) -> AudioResult:
    """定时或手动录制音频，并计算有效语音占比。

    手动模式（``duration_sec is None``）只由 ``stop_event`` 结束；
    分块大小仅控制读取粒度，不承担超时或自动终止语义。
    """
    if duration_sec is None and stop_event is None:
        raise ValueError("stop_event is required when duration_sec is None")

    try:
        import numpy as np
        import sounddevice as sd
    except Exception:
        return AudioResult(status="error", reason="sounddevice_unavailable")

    try:
        sample_rate = int(sample_rate)
        channels = int(channels)
        total_frames = (
            None
            if duration_sec is None
            else int(float(duration_sec) * sample_rate)
        )
    except Exception:
        return AudioResult(status="error", reason="audio_record_failed")
    if (
        sample_rate <= 0
        or channels <= 0
        or (total_frames is not None and total_frames <= 0)
    ):
        return AudioResult(status="error", reason="audio_record_failed")

    # 先校验输入设备，设备不存在/不可用时记 audio_device_unavailable
    try:
        checker = getattr(sd, "check_input_settings", None)
        if checker is not None:
            checker(
                device=mic_index,
                samplerate=sample_rate,
                channels=channels,
            )
    except Exception:
        return AudioResult(status="error", reason="audio_device_unavailable")

    if duration_sec is None:
        chunks = []
        # 100ms 一块，置位后最多在当前块读取结束时收尾，不设置任何超时。
        blocksize = max(int(sample_rate * 0.1), 1)
        try:
            with sd.InputStream(
                samplerate=sample_rate,
                channels=channels,
                dtype="int16",
                device=mic_index,
                blocksize=blocksize,
            ) as stream:
                while not stop_event.is_set():
                    block, _overflowed = stream.read(blocksize)
                    block = np.asarray(block)
                    if block.size:
                        chunks.append(block.copy())
                    if stop_event.is_set():
                        break
        except Exception:
            return AudioResult(status="error", reason="audio_record_failed")

        data = (
            np.concatenate(chunks, axis=0)
            if chunks
            else np.empty((0, channels), dtype=np.int16)
        )
    else:
        try:
            data = sd.rec(
                total_frames,
                samplerate=sample_rate,
                channels=channels,
                dtype="int16",
                device=mic_index,
            )
            sd.wait()
        except Exception:
            return AudioResult(status="error", reason="audio_record_failed")

    if data is None:
        return AudioResult(status="error", reason="audio_record_failed")

    data = np.asarray(data)
    if data.size == 0:
        return AudioResult(status="no_audio", reason="empty_audio")

    mono = data.astype(np.float64) / 32768.0
    if mono.ndim > 1:
        mono = mono.mean(axis=1)
    duration = round(float(mono.shape[0]) / float(sample_rate), 3)

    # 按 30ms 一帧计算 RMS，归一化后高于阈值视为有效语音帧
    frame_length = max(int(sample_rate * SPEECH_FRAME_MS / 1000), 1)
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
