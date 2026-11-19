"""pytest 配置：让 tests/ 下的测试能 import 后端同级模块（jsonfix / providers / routers 等）"""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
TESTS_ROOT = Path(__file__).resolve().parent
for p in (str(BACKEND_ROOT), str(TESTS_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)
