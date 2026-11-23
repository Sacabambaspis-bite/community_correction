"""硬件自检：只验证摄像头和麦克风是否可用，不碰业务代码。"""
import time
import wave
import numpy as np
import cv2
import sounddevice as sd

SAMPLE_RATE = 16000
DURATION = 5.0


def check_camera(index):
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)   # Windows 用 DSHOW，比默认 MSMF 稳
    if not cap.isOpened():
        print(f"[FAIL] 摄像头 index={index} 打不开")
        return None
    frame = None
    for _ in range(10):                            # 丢弃前几帧，等自动曝光
        ok, frame = cap.read()
        time.sleep(0.05)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    if not ok or frame is None:
        print(f"[FAIL] 摄像头 index={index} 打开了但读不到帧")
        return None
    mean = frame.mean()
    print(f"[OK] 摄像头 index={index}  分辨率={w}x{h}  形状={frame.shape}  平均亮度={mean:.1f}")
    if mean < 15:
        print("      ⚠ 画面几乎全黑，检查镜头是否被遮挡或设备被其他程序占用")
    cv2.imwrite(f"hw_check_camera_{index}.jpg", frame)
    print(f"      已保存 hw_check_camera_{index}.jpg，请打开确认是清晰正脸")
    return frame


def check_audio(seconds=DURATION):
    print("\n=== 可用输入设备 ===")
    print(sd.query_devices())
    try:
        dev = sd.query_devices(kind="input")
    except Exception as e:
        print(f"[FAIL] 找不到输入设备: {e}")
        return
    print(f"\n默认输入设备: {dev['name']}  通道={dev['max_input_channels']}")
    rec = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                 channels=1, dtype="int16")
    sd.wait()
    peak = int(np.abs(rec).max())
    rms = float(np.sqrt((rec.astype(np.float64) ** 2).mean()))
    print(f"[{'OK' if peak > 0 else 'FAIL'}] 录音 {seconds}s  峰值={peak}  RMS={rms:.1f}")
    if peak == 0:
        print("      ⚠ 全是静音：检查 Windows 设置 > 隐私 > 麦克风 是否允许桌面应用访问")
    with wave.open("hw_check_audio.wav", "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(rec.tobytes())
    print("      已保存 hw_check_audio.wav")


if __name__ == "__main__":
    print("=== 摄像头 ===")
    for i in range(3):
        if check_camera(i) is not None:
            print(f"\n→ 可用设备索引：{i}")
            break
    else:
        print("[FAIL] index 0/1/2 全部不可用")
    check_audio()
