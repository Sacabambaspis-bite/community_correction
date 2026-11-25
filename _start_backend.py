"""Backend launcher: load local .env into process env, then start uvicorn.

Usage: python _start_backend.py

密钥只保存在本地 .env（已被 .gitignore 忽略），脚本本身不含任何明文凭据。
"""
import os
from pathlib import Path


def load_env_file(path: Path) -> None:
    """把 .env 中的键注入当前进程；已存在的非空环境变量优先，不覆盖。"""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # 空字符串也视为未设置，避免上层 shell 预置空值导致注入失效
        if key and not os.environ.get(key):
            os.environ[key] = value


load_env_file(Path(__file__).with_name(".env"))

# INTENTIONALLY NOT setting CAPTURE_FAKE -> real microphone capture
os.environ["APP_ENV"] = "development"

from app.analysis.providers import sensevoice_configured  # noqa: E402

print("=" * 55)
print("  Community Correction - Backend Launcher")
print("=" * 55)
print(f"  SENSEVOICE_API_URL  = {os.environ.get('SENSEVOICE_API_URL', '(MISSING)')}")
print(f"  SENSEVOICE_API_KEY  = {'(set)' if os.environ.get('SENSEVOICE_API_KEY') else '(MISSING)'}")
print(f"  sensevoice_configured = {sensevoice_configured()}")
print(f"  DEEPSEEK_API_KEY      = {'(set)' if os.environ.get('DEEPSEEK_API_KEY') else '(MISSING)'}")
print(f"  CAPTURE_FAKE = {os.environ.get('CAPTURE_FAKE', '(not set -> real)')}")
print()

import uvicorn  # noqa: E402

uvicorn.run("app.api.main:app", host="127.0.0.1", port=8000, log_level="info")
