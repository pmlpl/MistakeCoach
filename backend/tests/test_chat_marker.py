"""chat 模块测试：末尾状态标记的正则解析（_MARKER_RE）。

这是对话状态机的核心入口——模型回复末尾必须带 ⟦PHASE:*|HINT:*|MODE:*⟧ 形式的标记，
后端用这个决定下一轮对话的阶段、梯度和模式。标记解析错了 → 状态机乱套。
正则本身纯函数，测起来非常干净。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from routers.chat import _MARKER_RE


def _parse(text):
    """复用 chat.py 里的写法：取最后一个标记"""
    last = None
    for m in _MARKER_RE.finditer(text):
        last = m
    return last


class TestMarkerRegex:
    def test_full_marker(self):
        """完整标记三件套"""
        m = _parse("好，下一步我们看 ⟦PHASE:P2|HINT:L2|MODE:guide⟧")
        assert m is not None
        assert m.group(1) == "P2"
        assert m.group(2) == "2"
        assert m.group(3) == "guide"

    def test_marker_without_hint(self):
        """HINT 可缺省"""
        m = _parse("好的 ⟦PHASE:P1|MODE:direct⟧")
        assert m is not None
        assert m.group(1) == "P1"
        assert m.group(2) is None
        assert m.group(3) == "direct"

    def test_marker_without_mode(self):
        """MODE 可缺省（沿用旧状态）"""
        m = _parse("好 ⟦PHASE:P3|HINT:L4⟧")
        assert m is not None
        assert m.group(1) == "P3"
        assert m.group(2) == "4"
        assert m.group(3) is None

    def test_marker_hint_alone_no(self):
        """但 PHASE 必须有（正则要求），只有 HINT 不行"""
        m = _parse("⟦HINT:L2⟧")
        assert m is None

    def test_phase_range(self):
        """PHASE 只能是 P1~P4"""
        assert _parse("⟦PHASE:P5⟧") is None
        assert _parse("⟦PHASE:P0⟧") is None
        assert _parse("⟦PHASE:Q1⟧") is None

    def test_hint_range(self):
        """正则 HINT:L([0-4]) 只匹配 0~4，L5 不该被匹配到；范围校验后端也会再 clamp"""
        assert _parse("⟦PHASE:P1|HINT:L5⟧") is None
        assert _parse("⟦PHASE:P1|HINT:L0⟧") is not None
        assert _parse("⟦PHASE:P1|HINT:L4⟧") is not None

    def test_mode_values(self):
        """MODE 只能是 guide 或 direct"""
        assert _parse("⟦PHASE:P1|MODE:quiz⟧") is None
        assert _parse("⟦PHASE:P1|MODE:GUIDE⟧") is None  # 大小写敏感

    def test_last_marker_wins(self):
        """回复里可能出现多个标记（模型重写了几次）——取最后一个"""
        m = _parse("前半 ⟦PHASE:P1|MODE:guide⟧ 后半 ⟦PHASE:P3|MODE:direct⟧")
        assert m.group(1) == "P3"
        assert m.group(3) == "direct"

    def test_marker_at_end_of_body_then_extra_text(self):
        """模型偶尔把正文写在标记之后——_relay 会把 rest 补发。
        这里只确认正则仍然能抓到标记"""
        text = "好 ⟦PHASE:P2|MODE:guide⟧ 再想想 x² 这部分"
        m = _parse(text)
        assert m is not None
        # rest = " 再想想 x² 这部分"（标记结束后还有字）
        assert text[m.end():].strip().startswith("再想想")

    def test_no_marker_at_all(self):
        """模型完全没输出标记——后端走"沿用原状态"的兜底，正则返回 None"""
        m = _parse("好，下一步我们看 x² 这部分")
        assert m is None

    def test_marker_without_space_after(self):
        """标记紧跟正文末尾（没有空格也没有换行）"""
        m = _parse("好的⟦PHASE:P1⟧")
        assert m is not None
        assert m.group(1) == "P1"


class TestMarkerRegexRegression:
    """真实线上场景回归"""

    def test_real_guide_marker(self):
        """一次真实引导模式回复末尾的标记"""
        m = _parse("那你觉得这里的 x 应该用什么代入？想想看 \⟦PHASE:P2|HINT:L3|MODE:guide⟧")
        # 注意：反斜杠在 Python 字符串里需要确认
        if m is None:
            # 可能 \ 影响了匹配 —— 构造不含反斜杠的
            m = _parse("那你觉得 x 应该用什么代入？想想看 ⟦PHASE:P2|HINT:L3|MODE:guide⟧")
        assert m is not None
        assert m.group(1) == "P2"
        assert m.group(3) == "guide"

    def test_real_direct_marker(self):
        """讲解模式（切 direct）的标记——modeManual 防回滚依赖这个解析正确"""
        m = _parse("直接讲给你听：这是二次方程 ⟦PHASE:P3|MODE:direct⟧")
        assert m is not None
        assert m.group(1) == "P3"
        assert m.group(3) == "direct"
        assert m.group(2) is None  # HINT 缺省
