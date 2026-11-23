"""`APP_ENV=production` 时的启动守卫（子进程验证，避免污染当前进程环境）。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def _env_without_tokens() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if key not in {"USER_TOKEN", "ADMIN_TOKEN", "APP_ENV"}
    }


def test_production_rejects_demo_or_missing_tokens():
    env = _env_without_tokens()
    env["APP_ENV"] = "production"

    result = subprocess.run(
        [sys.executable, "-c", "import app.api.deps"],
        cwd=str(_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "RuntimeError" in result.stderr
    assert "USER_TOKEN" in result.stderr
    assert "ADMIN_TOKEN" in result.stderr


def test_production_accepts_real_tokens():
    env = _env_without_tokens()
    env["APP_ENV"] = "Production"
    env["USER_TOKEN"] = "prod_user_token_7f3a"
    env["ADMIN_TOKEN"] = "prod_admin_token_9c1b"

    result = subprocess.run(
        [sys.executable, "-c", "import app.api.deps; print('ok')"],
        cwd=str(_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
