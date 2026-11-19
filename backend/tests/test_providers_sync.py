"""前后端 PROVIDERS 预设一致性校验脚本。

前端 frontend/src/store/keys.js 和后端 backend/providers.py 各维护一份供应商预设
（provider id、label、base URL、默认模型名）。这个脚本把两边的预设抽出来对比，
发现不一致直接抛错——防止"前端能选、后端报不支持"这种诡异 bug。

运行：  python tests/test_providers_sync.py     或  python -m pytest -k providers

设计选择：用 Python AST + 正则分别解析两边（后端是纯 Python dict，前端纯 dict 文本），
不用启 Node，本地或 CI 都能直接跑。"""
import ast
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_KEYS = BACKEND_ROOT.parent / "frontend" / "src" / "store" / "keys.js"


def _load_backend():
    """从 backend/providers.py 里解析 PROVIDERS dict——import 一次后提取"""
    sys.path.insert(0, str(BACKEND_ROOT))
    import providers as _p  # noqa: E402
    return {k: v for k, v in _p.PROVIDERS.items() if k != "custom"}  # custom 是占位，跳过


def _load_frontend():
    """从 frontend/src/store/keys.js 正则抠出 PROVIDERS = { ... } 块，再逐键正则抽值"""
    src = FRONTEND_KEYS.read_text(encoding="utf-8")
    # 抠出 PROVIDERS = { ... } 整个 dict 文本（到下一个顶层函数/常量为止）
    m = re.search(r"export const PROVIDERS\s*=\s*\{([\s\S]+?)\n\}", src)
    if not m:
        raise RuntimeError("前端 keys.js 里没找到 PROVIDERS dict")
    block = m.group(1)

    result = {}
    # 每个 provider 形如：
    #   zhipu: { label: '...', base: '...', vision: '...', chat: '...', keyFrom: '...' },
    for pm in re.finditer(r"(\w+):\s*\{([^}]+)\}", block):
        pid = pm.group(1)
        if pid == "custom":  # custom 是占位预设，后端跳过，这里也跳过以对齐
            continue
        body = pm.group(2)
        def _g(field):
            gm = re.search(rf"{field}:\s*'([^']*)'", body)
            return gm.group(1) if gm else ""
        result[pid] = {
            "label": _g("label"),
            "base": _g("base"),
            "vision_model": _g("vision"),
            "chat_model": _g("chat"),
        }
    return result


def compare():
    backend = _load_backend()
    frontend = _load_frontend()

    errors = []

    # 检查 provider id 集合一致
    be_ids = set(backend.keys())
    fe_ids = set(frontend.keys())
    if be_ids != fe_ids:
        errors.append(f"provider id 集合不一致：后端有 {sorted(be_ids - fe_ids)}，前端独有 {sorted(fe_ids - be_ids)}")

    for pid in sorted(be_ids & fe_ids):
        b = backend[pid]
        f = frontend[pid]
        # 字段名对齐：后端 vision_model / chat_model / label / base；前端 vision / chat / label / base
        pairs = [
            ("label", b.get("label", ""), f.get("label", "")),
            ("base", b.get("base", ""), f.get("base", "")),
            ("vision_model", b.get("vision_model", ""), f.get("vision_model", "")),
            ("chat_model", b.get("chat_model", ""), f.get("chat_model", "")),
        ]
        for field, be_val, fe_val in pairs:
            if be_val != fe_val:
                errors.append(f"[{pid}] {field} 不一致：后端={be_val!r} 前端={fe_val!r}")

    return errors


if __name__ == "__main__":
    errs = compare()
    if errs:
        print("✗ 前后端 PROVIDERS 不一致：")
        for e in errs:
            print(f"   - {e}")
        sys.exit(1)
    print("✓ 前后端 PROVIDERS 预设一致")
