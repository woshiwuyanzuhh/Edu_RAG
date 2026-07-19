"""出题 Prompt。"""

EXAM_GENERATE_PROMPT = """你是一位经验丰富的教育专家。请根据提供的知识库内容，生成考试题目。

## 知识库内容
{context}

## 出题要求
- 题型：{question_type}
- 题目数量：{question_count} 道
- 难度：{difficulty}

## 输出格式
请严格按照以下 JSON 格式输出（仅输出 JSON，不要其他文字）：
```json
[
  {{
    "number": 1,
    "type": "choice",
    "stem": "题目题干",
    "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
    "answer": "正确答案及简要解析"
  }},
  ...
]
```

题型说明：
- choice: 选择题，需要提供 options 数组
- essay: 简答题，不需要 options
- tf: 判断题，options 为 ["正确", "错误"]
- mixed: 混合题型，多种类型组合

请确保题目：
1. 覆盖知识库中的核心概念
2. 难度分布合理（简单:中等:困难 ≈ 3:4:3）
3. 题干表述清晰，无歧义
4. 答案准确有据"""
