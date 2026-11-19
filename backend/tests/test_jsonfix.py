"""jsonfix 模块测试：LaTeX 转义修复 + 矩阵换行兜底 + JSON 解析

这是识别/笔记两条 API 都依赖的纯函数，改一行就可能把某类公式打碎。
注释里列出的每种边界情况都要有测试锚定。"""
import json
import sys
from pathlib import Path

# 允许 pytest 从任意目录跑
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jsonfix import extract_json, fix_latex_escapes


class TestFixLatexEscapes:
    def test_keep_already_doubled_backslash(self):
        """已双写的反斜杠（模型已经转对了）原样保留"""
        assert fix_latex_escapes(r"\\frac{1}{2}") == r"\\frac{1}{2}"

    def test_latex_command_prefix_gets_doubled(self):
        """单反斜杠 + 字母 + 字母 = LaTeX 命令前缀，必须双写"""
        out = fix_latex_escapes(r"\frac{x}{y} + \sin\theta")
        # 解析确认是合法 JSON 字符串里的正确字面反斜杠
        parsed = json.loads('"' + out.replace('"', '\\"') + '"')
        assert "\\frac" in parsed  # 字面两个反斜杠 + frac

    def test_keep_newline_intent(self):
        r"""\n 这种合法 JSON 转义（换行意图）不能被当成 LaTeX 命令。
        输入里的 \n 是字面反斜杠+n（JSON 源文件常见），fix_latex_escapes 对 "n" 分支原样保留，
        后续 json.loads 应成功解析出真实换行"""
        raw = r'{"text": "line1\nline2"}'  # 这里的 \n 是字面反斜杠+n，真实 JSON 源
        out = fix_latex_escapes(raw)
        parsed = json.loads(out)  # 能解析 = \n 没被误吞/改造
        assert parsed["text"] == "line1\nline2"  # 解析后是真实换行

    def test_keep_unicode_escape(self):
        r"""\uXXXX 合法转义原样保留"""
        out = fix_latex_escapes('{"label": "\\u03b1"}')
        assert "\\u03b1" in out

    def test_keep_quote_escape(self):
        r"""反斜杠 + 引号 必须保留，否则 JSON 引号被打断"""
        out = fix_latex_escapes('{"msg": "say \\"hi\\""}')
        assert '\\"' in out

    def test_matrix_backslash_digit(self):
        """反斜杠紧跟数字（矩阵换行少写了一个反斜杠）——fix_latex_escapes 这一层不动，
        由 _fix_matrix_rows 兜底。这里只确认它不炸"""
        out = fix_latex_escapes(r"\\begin{bmatrix} a & b \\ c & d \end{bmatrix}")
        assert out  # 不抛异常


class TestExtractJson:
    def test_strips_markdown_fence(self):
        text = """```json
{"subject": "数学", "question_text": "求 x"}
```"""
        result = extract_json(text)
        assert result["subject"] == "数学"
        assert "x" in result["question_text"]

    def test_strips_plain_json_fence(self):
        """```{...} 不带 json 语言标记也能处理"""
        text = """```
{"a": 1}
```"""
        assert extract_json(text)["a"] == 1

    def test_accepts_raw_json_no_fence(self):
        """纯 JSON 字符串（没包 markdown 围栏）也能解析"""
        assert extract_json('{"x": 1}')["x"] == 1

    def test_dangling_matrix_backslash_fixed(self):
        """模型半吊子输出：\\ 后面接数字（矩阵换行），_fix_matrix_rows 能补成双"""
        text = r'{"matrix": "\\begin{bmatrix} 1 & 2 \\3 & 4 \end{bmatrix}"}'
        result = extract_json(text)
        # 3 前那个单反斜杠被补成 \\——现在反斜杠后不会直接跟数字了
        assert not result["matrix"].rstrip().endswith("\\")
        # 反斜杠后面的数字 3 前面必须有两个反斜杠
        import re
        assert re.search(r"\\\\\s*3", result["matrix"]), "单反斜杠+数字 未被兜底补成双"

    def test_nested_objects(self):
        """嵌套 dict / list 里的矩阵反斜杠也被递归修复"""
        text = r'{"steps": ["line1", "a\\1"], "reason": {"note": "b\\2"}}'
        result = extract_json(text)
        import re
        assert not re.search(r"(?<!\\)\\(?=\d)", json.dumps(result))


class TestFixLatexEscapesRegression:
    """真实用户场景回归——你们曾经踩过的坑"""

    def test_realistic_question_json(self):
        """实际一次识别输出里混着 LaTeX 命令 + \n 换行 + markdown 围栏"""
        raw = '''```json
{
  "subject": "数学",
  "question_text": "计算 \\\\frac{3}{4} + \\\\frac{1}{2} = ?",
  "student_work": "\\\\frac{4}{6}",
  "has_handwriting": true
}
```'''
        result = extract_json(raw)
        assert result["subject"] == "数学"
        assert "3}{4" in result["question_text"]  # \frac 转义正确
        assert "student_work" in result

    def test_empty_after_fence_is_error(self):
        """围栏里空内容 → json.loads 抛错是预期行为，不算 bug"""
        try:
            extract_json("```json\n\n```")
        except json.JSONDecodeError:
            pass
        else:
            raise AssertionError("空 JSON 应当抛 JSONDecodeError")
