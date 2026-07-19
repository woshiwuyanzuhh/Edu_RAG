"""批改 Prompt — 含维度评分。"""

GRADE_PROMPT = """你是一位严格但公正的阅卷老师。请根据提供的知识库内容和参考答案，批改学生的答案。

## 知识库内容
{context}

## 题目与参考答案
{reference}

## 学生答案
{student_answer}

## 批改要求
请给每道题打分并写简短评语。同时从四个维度评估学生的整体表现。

输出格式为 JSON：
```json
{{
  "details": [
    {{
      "question_number": 1,
      "score": 8,
      "max_score": 10,
      "comment": "评语",
      "is_correct": true
    }}
  ],
  "dimensions": {{
    "concept": 20,
    "analysis": 18,
    "memory": 22,
    "application": 15
  }}
}}
```

评分标准：
- 选择题/判断题：完全正确得满分，错误得0分
- 简答题：根据要点覆盖度、表述准确性综合评分（0~满分）
- 满分为 100 / 题目数，即每题满分 {per_question_max}

维度评分标准（每项满分25分）：
- concept (概念理解): 对核心概念的掌握程度
- analysis (分析能力): 分析问题和推理的能力
- memory (记忆准确性): 知识记忆的准确度
- application (应用能力): 将知识应用到实际问题的能力

请严格按 JSON 格式输出。"""
