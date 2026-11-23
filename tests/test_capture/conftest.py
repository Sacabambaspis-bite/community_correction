"""确保从仓库根导入 `app`。

pytest 默认把测试文件所在目录加入 sys.path，这里显式补上仓库根，
使 `pytest tests/test_capture/ -q` 在任意工作目录下都能 import app。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
