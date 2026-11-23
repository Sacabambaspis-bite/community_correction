"""端到端采集验收：用真实摄像头 / 麦克风跑一次 run_capture_session 并做契约断言。

只调用 app.capture 的公开接口，不修改采集逻辑；原始帧只留在内存，不落盘。

清量约定（务必遵守）：
    - 调试 / 自检：一律用 --out storage/_debug，产物落到 storage/_debug/subjects/...，可随时丢弃；
    - 正式验证：才写正式目录，用默认 --out storage，产物落到 storage/subjects/...。

用法：
    python scripts/verify_capture.py --device 0 --seconds 5 --out storage/_debug   # 调试/自检
    python scripts/verify_capture.py --device 0 --seconds 10                       # 正式验证（storage/subjects）
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.capture.session import run_capture_session  # noqa: E402

SUBJECT_ID = "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c"
FACE_SIDE = 300
RESOLUTION = (1280, 720)
CAPTURE_STATUSES = {
    "ok",
    "partial",
    "no_face",
    "no_audio",
    "no_face_no_audio",
    "error",
}
NO_ARTIFACT_STATUSES = ("no_face_no_audio", "error")


def _print(text=""):
    print(text)


def _check(passed, ok_text, fail_text, failures, detail=""):
    """打印 PASS / FAIL，失败时记录到 failures。"""
    if passed:
        _print("[PASS] {}".format(ok_text))
    else:
        suffix = "：{}".format(detail) if detail else ""
        _print("[FAIL] {}{}".format(fail_text, suffix))
        failures.append(fail_text)
    return bool(passed)


def _path_kind(path):
    if not path:
        return "无路径"
    return "绝对路径" if Path(path).is_absolute() else "相对路径"


def _read_image_side(path):
    """用 cv2.imread 读取图片边长；非 ASCII 路径读不到时用 imdecode 兜底。"""
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        try:
            data = np.fromfile(str(path), dtype=np.uint8)
        except OSError:
            return None
        if data.size == 0:
            return None
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        return None
    return int(image.shape[1]), int(image.shape[0])


def _artifacts_state(meta):
    face_present = meta.get("face") is not None
    audio_meta = meta.get("audio")
    audio_present = bool(isinstance(audio_meta, dict) and audio_meta.get("recorded"))
    return face_present, audio_present


def check_status(result, failures):
    """a) capture_status 与 coverage，以及状态 / 产物一致性。"""
    _print()
    _print("=== a) 采集状态与覆盖 ===")
    meta = result.meta if isinstance(result.meta, dict) else {}
    status = result.capture_status
    _print("capture_status = {}".format(status))
    _print("meta.coverage = {}".format(meta.get("coverage")))

    _check(
        status in CAPTURE_STATUSES,
        "capture_status 属于契约六值",
        "capture_status 不在契约六值内",
        failures,
        repr(status),
    )
    _check(
        "coverage" in meta,
        "meta 中存在 coverage 键",
        "meta 缺少 coverage 键",
        failures,
    )

    coverage = meta.get("coverage")
    if status in NO_ARTIFACT_STATUSES:
        _check(
            coverage is None,
            "无产物状态 coverage 为 null",
            "无产物状态 coverage 应为 null",
            failures,
            repr(coverage),
        )
    else:
        _check(
            coverage in ("both", "face_only", "audio_only"),
            "有产物状态 coverage 属于三值枚举",
            "有产物状态 coverage 不是三值枚举",
            failures,
            repr(coverage),
        )

    face_present, audio_present = _artifacts_state(meta)
    if status in NO_ARTIFACT_STATUSES:
        expected_coverage = None
    elif face_present and audio_present:
        expected_coverage = "both"
    elif face_present:
        expected_coverage = "face_only"
    elif audio_present:
        expected_coverage = "audio_only"
    else:
        expected_coverage = None
    _check(
        coverage == expected_coverage,
        "coverage 与 meta.face / meta.audio.recorded 一致",
        "coverage 与 meta.face / meta.audio.recorded 不一致",
        failures,
        "coverage={}，按产物应为 {}".format(coverage, expected_coverage),
    )

    if status == "ok":
        _check(
            face_present and audio_present and not meta.get("warnings"),
            "ok 状态两路产物齐全且 warnings 为空",
            "ok 状态产物或 warnings 不符合契约",
            failures,
            "face={} audio={} warnings={}".format(
                face_present, audio_present, len(meta.get("warnings") or [])
            ),
        )
    elif status == "partial":
        _check(
            face_present or audio_present,
            "partial 状态至少一路产物可用",
            "partial 状态没有任何产物",
            failures,
        )
    elif status == "no_face":
        _check(
            (not face_present) and audio_present,
            "no_face 状态无 face.jpg 但有 audio.wav",
            "no_face 状态产物组合不符合契约",
            failures,
        )
    elif status == "no_audio":
        _check(
            face_present and (not audio_present),
            "no_audio 状态有 face.jpg 但无 audio.wav",
            "no_audio 状态产物组合不符合契约",
            failures,
        )
    elif status in NO_ARTIFACT_STATUSES:
        _check(
            (not face_present) and (not audio_present),
            "{} 状态无任何产物".format(status),
            "{} 状态不应有产物".format(status),
            failures,
        )


def check_codes(result, failures):
    """b) result.codes 与 meta.warnings / meta.error 的 code 一致性。"""
    _print()
    _print("=== b) codes 与 warnings ===")
    meta = result.meta if isinstance(result.meta, dict) else {}
    status = result.capture_status
    codes = list(result.codes or [])
    warnings = meta.get("warnings")

    _print("result.codes = {}".format(codes))
    if not isinstance(warnings, list):
        _check(False, "", "meta.warnings 不是数组", failures, repr(type(warnings)))
        return

    warning_codes = []
    for index, warning in enumerate(warnings):
        code = warning.get("code") if isinstance(warning, dict) else None
        _print("warnings[{}].code = {}".format(index, code))
        if not isinstance(warning, dict) or not code:
            _check(False, "", "warnings 元素缺少 code", failures, "下标 {}".format(index))
            continue
        if "reason" not in warning or "detail" not in warning:
            _check(
                False,
                "",
                "warnings 元素缺少 reason / detail 键",
                failures,
                "下标 {}".format(index),
            )
        warning_codes.append(code)

    _check(
        len(codes) == len(set(codes)),
        "result.codes 无重复 code",
        "result.codes 存在重复 code",
        failures,
        repr(codes),
    )
    _check(
        len(warning_codes) == len(set(warning_codes)),
        "meta.warnings 中 code 不重复",
        "meta.warnings 中 code 重复",
        failures,
        repr(warning_codes),
    )

    error = meta.get("error")
    if status == "error":
        error_code = error.get("code") if isinstance(error, dict) else None
        _print("meta.error.code = {}".format(error_code))
        _check(
            bool(error_code),
            "error 状态 meta.error.code 非空",
            "error 状态 meta.error.code 为空",
            failures,
        )
        _check(
            bool(codes) and codes[0] == error_code,
            "error 状态 result.codes 首条等于 meta.error.code",
            "error 状态 result.codes 首条与 meta.error.code 不一致",
            failures,
            "codes={} error={}".format(codes, error_code),
        )
        expected_codes = ([error_code] if error_code else []) + warning_codes
    else:
        _print("meta.error = {}".format(error))
        _check(
            error is None,
            "非 error 状态 meta.error 为 null",
            "非 error 状态 meta.error 应为 null",
            failures,
            repr(error),
        )
        expected_codes = warning_codes

    _check(
        sorted(codes) == sorted(expected_codes),
        "result.codes 与 meta.error / meta.warnings 的 code 集合一致",
        "result.codes 与 meta.error / meta.warnings 的 code 集合不一致",
        failures,
        "codes={} expected={}".format(codes, expected_codes),
    )


def check_artifacts(result, storage_root, failures):
    """c) 产物路径形态、文件存在性、face.jpg 实际边长。"""
    _print()
    _print("=== c) 产物与 face.jpg 尺寸 ===")
    meta = result.meta if isinstance(result.meta, dict) else {}
    face_path = result.face_path
    audio_path = result.audio_path
    face_present, audio_present = _artifacts_state(meta)
    root = Path(storage_root)

    _print("result.face_path = {}（{}）".format(face_path, _path_kind(face_path)))
    _print("result.audio_path = {}（{}）".format(audio_path, _path_kind(audio_path)))

    if face_present:
        _check(
            bool(face_path),
            "meta.face 非空且 face_path 非空",
            "meta.face 非空但 face_path 为空",
            failures,
        )
        if face_path:
            face_file = Path(face_path)
            if not face_file.is_absolute():
                face_file = root / face_file
            face_file = face_file.resolve()
            _print("face.jpg 绝对路径 = {}".format(face_file))
            exists = _check(
                face_file.is_file(),
                "face.jpg 文件存在",
                "face_path 指向的文件不存在",
                failures,
                str(face_file),
            )
            if exists:
                side = _read_image_side(face_file)
                if side is None:
                    _check(False, "", "face.jpg 无法解码", failures, str(face_file))
                else:
                    width, height = side
                    _print("face.jpg 实际边长 = {}x{}".format(width, height))
                    _check(
                        width == FACE_SIDE and height == FACE_SIDE,
                        "face.jpg 边长等于 300x300",
                        "face.jpg 边长不等于 300x300",
                        failures,
                        "实际 {}x{}".format(width, height),
                    )
        output_size = (meta.get("face") or {}).get("output_size")
        _print("meta.face.output_size = {}".format(output_size))
        _check(
            output_size == [FACE_SIDE, FACE_SIDE],
            "meta.face.output_size 为 [300, 300]",
            "meta.face.output_size 不是 [300, 300]",
            failures,
            repr(output_size),
        )
    else:
        _print("无人脸产物（meta.face 为 null），不检查 face.jpg")
        _check(
            face_path is None,
            "无人脸产物时 face_path 为 None",
            "无人脸产物但 face_path 非空",
            failures,
            repr(face_path),
        )

    if audio_present:
        _check(
            bool(audio_path),
            "meta.audio.recorded 为真且 audio_path 非空",
            "meta.audio.recorded 为真但 audio_path 为空",
            failures,
        )
        if audio_path:
            audio_file = Path(audio_path)
            if not audio_file.is_absolute():
                audio_file = root / audio_file
            audio_file = audio_file.resolve()
            _print("audio.wav 绝对路径 = {}".format(audio_file))
            _check(
                audio_file.is_file() and audio_file.stat().st_size > 0,
                "audio.wav 文件存在且非空",
                "audio_path 指向的文件不存在或为空",
                failures,
                str(audio_file),
            )
    else:
        _print("无音频产物（meta.audio.recorded 为假），不检查 audio.wav")
        _check(
            audio_path is None,
            "无音频产物时 audio_path 为 None",
            "无音频产物但 audio_path 非空",
            failures,
            repr(audio_path),
        )


def check_resolution(device_index, meta_resolution):
    """d) 采集结束后独立打开摄像头复核分辨率；失败只提示，不影响退出码。"""
    _print()
    _print("=== d) 摄像头分辨率复核（采集结束后独立读取） ===")
    _print("meta.device.camera_resolution = {}".format(meta_resolution))

    cap = cv2.VideoCapture(int(device_index))
    backend = "默认后端"
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(int(device_index), cv2.CAP_DSHOW)
        backend = "CAP_DSHOW 回退"
    if not cap.isOpened():
        cap.release()
        _print("[SKIP] 无法重新打开摄像头 index={}，跳过分辨率复核".format(device_index))
        return

    frame = None
    prop_width = prop_height = 0
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, RESOLUTION[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, RESOLUTION[1])
        for _ in range(5):
            ok, candidate = cap.read()
            if ok and candidate is not None and candidate.size > 0:
                frame = candidate
        prop_width = int(round(cap.get(cv2.CAP_PROP_FRAME_WIDTH)))
        prop_height = int(round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    finally:
        cap.release()

    _print("独立读取后端 = {}".format(backend))
    _print("CAP_PROP_FRAME_WIDTH/HEIGHT = {}x{}".format(prop_width, prop_height))
    if frame is None:
        _print(
            "[SKIP] 摄像头可打开但读不到帧（CAP_PROP={}x{}），跳过分辨率复核".format(
                prop_width, prop_height
            )
        )
        return

    shape_height, shape_width = int(frame.shape[0]), int(frame.shape[1])
    _print("实测帧 shape = {}（宽 x 高 = {}x{}）".format(
        frame.shape, shape_width, shape_height
    ))

    meta_value = list(meta_resolution or [])
    shape_value = [shape_width, shape_height]
    prop_value = [prop_width, prop_height]

    if meta_value != shape_value:
        _print(
            "[FAIL] meta 分辨率 {} 与实测帧 {} 不一致（该项不影响退出码）".format(
                meta_value, shape_value
            )
        )
        return
    if prop_value != shape_value:
        _print(
            "[WARN] CAP_PROP {} 与实测帧 {} 不一致，以实测帧为准，meta 与实测帧一致".format(
                prop_value, shape_value
            )
        )
        return
    _print(
        "[PASS] meta 分辨率与 CAP_PROP、实测帧一致：{}".format(shape_value)
    )


def _out_purpose(storage_root):
    """按输出根目录给出用途标签，落实清量约定。"""
    lowered = str(storage_root).replace("\\", "/").lower().rstrip("/")
    if lowered.endswith("/_debug") or "/_debug/" in lowered + "/":
        return "调试/自检（产物可随时丢弃）"
    return "正式验证（写入 storage/subjects，请勿随意清理）"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "端到端采集验收：真实摄像头 / 麦克风跑一次采集并断言契约字段。"
            "清量约定：调试与自检一律用 --out storage/_debug；"
            "正式验证才用默认 --out storage（产物落在 storage/subjects）。"
        )
    )
    parser.add_argument("--device", type=int, default=0, help="摄像头设备索引，默认 0")
    parser.add_argument("--seconds", type=float, default=10.0, help="录音时长（秒），默认 10")
    parser.add_argument(
        "--out",
        default="storage",
        help=(
            "采集存储根目录（相对或绝对路径均可），默认 storage；"
            "不存在会自动创建。约定：调试/自检用 storage/_debug，"
            "正式验证用默认 storage（产物落在 storage/subjects）"
        ),
    )
    args = parser.parse_args(argv)

    subject_id = SUBJECT_ID
    session_id = str(uuid.uuid4())
    storage_root = Path(args.out)
    storage_abs = storage_root.resolve()
    try:
        storage_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _print("[FAIL] 无法创建输出目录 {}：{}".format(storage_abs, type(exc).__name__))
        _print("退出码 = 1")
        return 1

    _print("[INFO] out 根目录（绝对路径）= {}".format(storage_abs))
    _print("[INFO] 本次用途 = {}".format(_out_purpose(storage_abs)))
    _print("subject_id = {}".format(subject_id))
    _print("session_id = {}".format(session_id))
    _print("storage_root = {}".format(storage_abs))
    _print("device_index = {}，duration_sec = {}".format(args.device, args.seconds))
    _print("开始采集（约 {} 秒）...".format(args.seconds))

    try:
        result = run_capture_session(
            subject_id,
            session_id,
            str(storage_root),
            device_index=args.device,
            duration_sec=args.seconds,
            resolution=RESOLUTION,
        )
    except Exception as exc:  # 采集层本应不抛异常，这里只兜底
        _print("[FAIL] run_capture_session 抛出异常：{}".format(type(exc).__name__))
        return 1

    failures = []
    check_status(result, failures)
    check_codes(result, failures)
    check_artifacts(result, storage_root, failures)
    check_resolution(args.device, result.meta.get("device", {}).get("camera_resolution"))

    session_dir = (
        storage_root / "subjects" / subject_id / "sessions" / session_id
    ).resolve()
    _print()
    _print("=== 汇总 ===")
    _print("session 目录（绝对路径）= {}".format(session_dir))
    meta_file = session_dir / "meta.json"
    _check(
        meta_file.is_file(),
        "meta.json 存在：{}".format(meta_file),
        "meta.json 不存在",
        failures,
        str(meta_file),
    )

    if failures:
        _print("断言失败 {} 项：".format(len(failures)))
        for item in failures:
            _print(" - {}".format(item))
        _print("退出码 = 1")
        return 1
    _print("全部断言通过")
    _print("退出码 = 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
