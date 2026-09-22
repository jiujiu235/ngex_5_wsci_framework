from pathlib import Path
from ollama import chat
import json
import re

MODEL = "qwen2.5:7b"  # 根据你本地 ollama list 调整
KNOWLEDGE_DIR = Path("knowledge")

question = """
I changed my university password this morning.
Now my Windows laptop won't connect to campus Wi-Fi,
but my phone still works.
"""


# -----------------------------
# SELECT：根据关键词选择文件
# -----------------------------
def select_context(question: str):
    q = question.lower()

    rules = [
        (
            ["wi-fi", "wifi", "eduroam", "wireless", "wlan"],
            ["wifi_setup.txt", "service_status.txt"]
        ),
        (
            ["password", "credential", "credentials", "密码"],
            ["password_changes.txt"]
        ),
        (
            ["email", "webmail", "outlook", "邮件"],
            ["email_setup.txt"]
        ),
        (
            ["vpn"],
            ["vpn.txt"]
        ),
        (
            ["print", "printer", "打印"],
            ["printing.txt"]
        ),
        (
            ["projector", "display", "投影"],
            ["classroom_projectors.txt"]
        ),
    ]

    selected = set()

    for keywords, files in rules:
        if any(keyword in q for keyword in keywords):
            selected.update(files)

    # 组合规则：密码 + Wi-Fi
    if (
        any(k in q for k in ["wi-fi", "wifi", "eduroam"])
        and any(k in q for k in ["password", "密码", "credential"])
    ):
        selected.update([
            "password_changes.txt",
            "wifi_setup.txt",
            "service_status.txt",
        ])

    return [KNOWLEDGE_DIR / name for name in sorted(selected)]


selected_files = select_context(question)
print("Selected files:", [str(p) for p in selected_files])


# -----------------------------
# READ：读取选中文件
# -----------------------------
context = ""

for path in selected_files:
    if path.exists():
        context += path.read_text(encoding="utf-8").strip()
        context += "\n\n"
    else:
        print(f"[警告] 文件不存在: {path}")


# -----------------------------
# COMPRESS：压缩上下文
# -----------------------------
def compress_context(context: str, question: str) -> str:
    prompt = f"""你是一个上下文压缩器。
请从下面的知识库内容中，只提取与“学生问题”直接相关的信息。
删除无关内容，保留设备、原因、操作步骤、注意事项。
不要编造。输出简洁中文要点。

【学生问题】
{question}

【原始知识库】
{context}
"""

    response = chat(
        model=MODEL,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.message.content


compressed_context = compress_context(context, question)
print("Compressed context characters:", len(compressed_context))


# -----------------------------
# 第二次 Qwen 调用：结构化输出
# -----------------------------
system_prompt = (
    "你是校园 IT 支持助手。"
    "只根据给定上下文回答。"
    "输出必须是合法 JSON，不要 Markdown，不要多余解释。"
)

user_prompt = f"""【学生问题】
{question}

【压缩后的相关上下文】
{compressed_context}

请输出如下 JSON 结构：
{{
  "problem": "学生问题摘要",
  "diagnosis": "最可能原因",
  "evidence": ["依据1", "依据2"],
  "solution_steps": ["步骤1", "步骤2"],
  "need_check": ["需要进一步检查的项"],
  "confidence": 0.0
}}
"""

response = chat(
    model=MODEL,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
)

raw = response.message.content
print("Raw response:", raw)


# -----------------------------
# 解析 JSON，尽量健壮
# -----------------------------
def parse_json_safely(text: str):
    text = text.strip()

    # 去掉 ```json ... ``` 包裹
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return {
            "problem": question,
            "diagnosis": None,
            "evidence": [],
            "solution_steps": [],
            "need_check": [],
            "confidence": 0.0,
            "raw": text,
        }


state = parse_json_safely(raw)
state["selected_files"] = [str(p) for p in selected_files]
state["compressed_context"] = compressed_context


# -----------------------------
# WRITE：写入 state.json
# -----------------------------
with open("state.json", "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)

print("Wrote state.json")
print(json.dumps(state, ensure_ascii=False, indent=2))


# -----------------------------
# ISOLATE：后续只取相关字段
# -----------------------------
with open("state.json", "r", encoding="utf-8") as f:
    saved_state = json.load(f)

diagnostic_context = {
    "problem": saved_state.get("problem"),
    "diagnosis": saved_state.get("diagnosis"),
    "evidence": saved_state.get("evidence"),
    "solution_steps": saved_state.get("solution_steps"),
    "need_check": saved_state.get("need_check"),
    "confidence": saved_state.get("confidence"),
}

followup_prompt = f"""根据下面的诊断状态，用简洁中文给学生一个最终答复。
不要使用未出现在状态中的信息。

【诊断状态】
{json.dumps(diagnostic_context, ensure_ascii=False, indent=2)}
"""

followup_response = chat(
    model=MODEL,
    messages=[
        {"role": "user", "content": followup_prompt}
    ]
)

print("Final answer:")
print(followup_response.message.content)