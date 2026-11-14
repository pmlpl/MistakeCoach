"""模型 JSON 输出的 LaTeX 转义修复与解析（recognize / note 共用）"""
import json
import re


def fix_latex_escapes(text: str) -> str:
    """模型输出的 JSON 字符串里，LaTeX 反斜杠（\\frac、\\sqrt、\\tan 等）大多不是
    合法 JSON 转义，json.loads 直接报错。修复策略：
    - 已双写的 \\\\、合法转义 \\" \\/ \\u、换行 \\n 原样保留（换行意图 >> \\nabla 命令）
    - 反斜杠+字母且后面还是字母（\\frac、\\tan、\\sqrt...）判为 LaTeX 命令，双写为字面反斜杠
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


def extract_json(text: str) -> dict:
    """从模型回复中剥离 markdown 围栏等杂质，修复 LaTeX 转义后解析 JSON"""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    return json.loads(fix_latex_escapes(text))
