"""模型 JSON 输出的 LaTeX 转义修复与解析（recognize / note 共用）"""
import json
import re


def fix_latex_escapes(text: str) -> str:
    """模型输出的 JSON 字符串里，LaTeX 反斜杠大多不是合法 JSON 转义，json.loads
    直接报错。修复策略（逐字符扫描）：
    - 已双写的反斜杠、合法转义（引号/斜杠/u/n）原样保留（换行意图优先于 \nabla 类命令）
    - 反斜杠+字母且后面还是字母（\\frac、\\tan 这类命令前缀）双写为字面反斜杠
    - 其余（反斜杠后跟非字母或结尾）原样保留"""
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "\\":  # 已是双反斜杠，原样保留
                out.append("\\\\")
                i += 2
                continue
            if nxt in '"/u' or nxt == "n":  # 合法 JSON 转义 / 换行意图，原样保留
                out.append(c + nxt)
                i += 2
                continue
            if nxt.isalpha() and i + 2 < n and text[i + 2].isalpha():  # LaTeX 命令前缀
                out.append("\\\\" + nxt)
                i += 2
                continue
            out.append(c + nxt)
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _fix_matrix_rows(obj):
    """解析后再兜底一层：公式字符串里反斜杠紧跟数字，必是模型少写一个的矩阵换行
    （LaTeX 命令从不以数字开头，合法场景不存在反斜杠加数字）。模型半吊子输出
    （命令未转义但换行已双写）经 fix_latex_escapes 后换行只剩单反斜杠，这里补成双"""
    if isinstance(obj, str):
        # (?<!\\)：正确的换行 \+数字 前面还有反斜杠，不能误补；只补真正缺一个的
        return re.sub(r"(?<!\\)\\(?=\d)", r"\\\\", obj)
    if isinstance(obj, list):
        return [_fix_matrix_rows(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _fix_matrix_rows(v) for k, v in obj.items()}
    return obj


def extract_json(text: str) -> dict:
    """从模型回复中剥离 markdown 围栏等杂质，修复 LaTeX 转义后解析 JSON"""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    return _fix_matrix_rows(json.loads(fix_latex_escapes(text)))
