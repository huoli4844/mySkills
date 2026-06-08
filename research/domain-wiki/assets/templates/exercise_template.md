---
template_version: v5.1
type: {{type}}
type_tag: {{type_tag}}
name: {{name}}
book_id: {{book_id}}
book_name: {{book_name}}
chapter_num: {{chapter_num}}
confidence: {{confidence}}
confidence_note: "{{confidence_note}}"
bloom_level: {{bloom_level}}
source_chapter: {{source_chapter}}
source_from: {{source_from}}
aliases: {{aliases}}
tags: {{tags}}
---

# {{name}}

## 题目内容

<!-- @prompt 习题原文。≥20字。从源文直接抄录。 -->
{{question}}

## 关联习题解答

<!-- @prompt 关联解答的文件名。格式：'第N章-习题N-解答'。 -->
{{related_answer}}
