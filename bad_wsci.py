from pathlib import Path
from ollama import chat

MODEL = "qwen2.5:7b"

question = """
I changed my university password this morning.
Now my Windows laptop won't connect to campus Wi-Fi,
but my phone still works.
"""

context = ""

for file in Path("knowledge").glob("*.txt"):
    context += file.read_text(encoding="utf-8")
    context += "\n\n"

prompt = f"""你是校园 IT 支持助手。请只根据下面提供的知识库内容回答学生问题。
如果知识库中没有足够信息，请说明还需要检查什么，不要编造。

【知识库】
{context}

【学生问题】
{question}

请给出：
1. 最可能的原因
2. 判断依据
3. 解决步骤
4. 需要进一步检查的项
"""

response = chat(
    model=MODEL,
    messages=[
        {"role": "user", "content": prompt}
    ]
)

print("Context characters:", len(context))
print(response.message.content)