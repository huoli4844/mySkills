#!/usr/bin/env python3
"""
generate_outlines.py — 从提纲文档 + 参考书目生成每章写作大纲。

流程：
  1. 读取项目配置（教材名、提纲文件、参考书路径）
  2. 解析提纲文件，提取纲目结构（各章名称和L1节）
  3. 对每章，用 delegate_task 委托 Agent：
     a. 读取参考书对应章节内容
     b. 分析各教材的写作手法和内容侧重
     c. 生成写作大纲（含子节结构、建议体量、素材来源）
  4. 将大纲写入 output/写作大纲/writing-guide-chX.md

用法：
  python3 scripts/generate_outlines.py --project /path/to/教材
  python3 scripts/generate_outlines.py --project /path/to/教材 --chapter 3   # 只生成第3章
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Optional


def _load_chapter_template() -> str:
    """从模板文件加载写作大纲模板"""
    template_path = Path(__file__).resolve().parent.parent / 'templates' / 'chapter-writing-guide-template.md'
    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()

CHAPTER_TEMPLATE = _load_chapter_template()


CHAPTER_NUM_MAP = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
}


def _chinese_to_arabic(text: str) -> Optional[int]:
    """将中文章节号转为阿拉伯数字，如 '一'→1, '十一'→11"""
    for cn, num in sorted(CHAPTER_NUM_MAP.items(), key=lambda x: -len(x[0])):
        if cn in text:
            return num
    return None


def parse_outline_structure(docx_path: str) -> List[dict]:
    """解析提纲 docx 文件，提取各章名称和L1节结构。"""
    if not os.path.exists(docx_path):
        print(f"❌ 提纲文件不存在: {docx_path}")
        return []
    
    try:
        import docx
        doc = docx.Document(docx_path)
        chapters = []
        current_ch = None
        
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            # 匹配 "第X章"（支持中文和阿拉伯数字）
            ch_num = _chinese_to_arabic(text)
            m_arabic = re.match(r'第(\d+)章\s+(.+)', text)
            if ch_num is not None and '章' in text:
                if current_ch:
                    chapters.append(current_ch)
                title = re.sub(r'第[一二三四五六七八九十]+章\s*', '', text)
                title = re.sub(r'第\d+章\s*', '', title)
                current_ch = {"chapter": ch_num, "title": title.strip(), "sections": []}
                continue
            if m_arabic:
                if current_ch:
                    chapters.append(current_ch)
                current_ch = {"chapter": int(m_arabic.group(1)), "title": m_arabic.group(2).strip(), "sections": []}
                continue
            
            # 匹配 L1 节 "X.Y"
            if current_ch:
                m = re.search(r'(\d+\.\d+)\s+(.+)', text)
                if m:
                    sec_num = m.group(1)
                    if sec_num.startswith(f"{current_ch['chapter']}."):
                        current_ch["sections"].append({"num": sec_num, "title": m.group(2).strip()})
        
        if current_ch:
            chapters.append(current_ch)
        
        if chapters:
            return chapters
    except ImportError:
        print("⚠️  python-docx 未安装，尝试用 pandoc 转换...")
    
    return []


def outline_exists(guides_dir: str, chapter: int) -> bool:
    """检查某章大纲是否已存在"""
    path = Path(guides_dir) / f"writing-guide-ch{chapter}.md"
    return path.exists() and path.stat().st_size > 100


def generate_chapter_outline(chapter: int, title: str, sections: List[dict], 
                             source_books: List[dict], output_dir: str):
    """为单章生成写作大纲文件"""
    guides_dir = Path(output_dir) / "写作大纲"
    guides_dir.mkdir(parents=True, exist_ok=True)
    out_path = guides_dir / f"writing-guide-ch{chapter}.md"
    
    content = CHAPTER_TEMPLATE.format(ch=chapter, title=title)
    
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  📝 已创建: writing-guide-ch{chapter}.md")
    return str(out_path)



def main():
    parser = argparse.ArgumentParser(description="从提纲+参考书生成每章写作大纲")
    parser.add_argument("--project", required=True, help="项目根目录")
    parser.add_argument("--chapter", type=int, default=None, help="只生成指定章节（可选）")
    parser.add_argument("--force", action="store_true", help="强制重新生成已有大纲")
    args = parser.parse_args()
    
    project_root = Path(args.project).expanduser().resolve()
    
    # 读取项目配置
    cfg_data = {}
    cfg_path = project_root / "book-build.yaml"
    if cfg_path.exists():
        import yaml
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg_data = yaml.safe_load(f) or {}
    
    textbook_cfg = cfg_data.get("textbook", {})
    outline_file = textbook_cfg.get("outline_file", "教材提纲.docx")
    outline_docx = str(project_root / "input" / outline_file)
    source_book_list = cfg_data.get("source_books", []) or []
    
    if not os.path.exists(outline_docx):
        print(f"❌ 提纲文件不存在: {outline_docx}")
        sys.exit(1)
    
    if not source_book_list:
        print("⚠️  book-build.yaml 中未配置 source_books，大纲将只包含结构骨架")
    
    # 解析提纲结构
    print(f"📖 解析提纲文件: {outline_docx}")
    chapters = parse_outline_structure(outline_docx)
    
    if not chapters:
        print("❌ 无法解析提纲文件")
        sys.exit(1)
    
    print(f"✅ 解析出 {len(chapters)} 章")
    chapters.sort(key=lambda c: c["chapter"])
    
    if args.chapter:
        chapters = [c for c in chapters if c["chapter"] == args.chapter]
        if not chapters:
            print(f"❌ 未找到第{args.chapter}章")
            sys.exit(1)
    
    output_dir = str(project_root / "output")
    existing = 0
    created = 0
    
    for ch_info in chapters:
        ch = ch_info["chapter"]
        title = ch_info["title"]
        sections = ch_info.get("sections", [])
        
        guides_path = Path(output_dir) / "写作大纲"
        if (guides_path / f"writing-guide-ch{ch}.md").exists() and not args.force:
            existing += 1
            continue
        
        path = generate_chapter_outline(ch, title, sections, source_book_list, output_dir)
        created += 1
    
    print("\n--- 完成 ---")
    print(f"总章节: {len(chapters)}")
    print(f"新建: {created}  跳过（已存在）: {existing}")
    
    if created > 0:
        print("\n⚠️  大纲已生成基本骨架，建议：")
        print(f"   1. 运行 validate_outlines.py 检查完整性")
        print(f"   2. 人工调整后，运行 generate_task_list.py 生成写作任务")
        
        # 输出结构化任务清单供 Agent 消费
        outline_tasks = []
        for ch_info in chapters:
            ch = ch_info["chapter"]
            title = ch_info["title"]
            sections = ch_info.get("sections", [])
            
            book_refs = []
            for b in source_book_list:
                book_refs.append({
                    "author": b.get("author", "?"),
                    "display_name": b.get("display_name", "?"),
                    "path": b.get("path", "")
                })
            
            outline_tasks.append({
                "type": "complete_writing_guide",
                "chapter": ch,
                "title": title,
                "guide_path": f"output/写作大纲/writing-guide-ch{ch}.md",
                "outline_sections": sections,
                "source_books": book_refs,
                "status": "pending"
            })
        
        tasks_path = project_root / "output" / "outline_tasks.json"
        with open(tasks_path, 'w', encoding='utf-8') as f:
            json.dump(outline_tasks, f, ensure_ascii=False, indent=2)
        print(f"\n📋 已输出结构化任务: {tasks_path}")
        print(f"   Agent 读取该文件后，对每个 pending 任务：")
        print(f"   1. delegate_task → 分析参考书内容")
        print(f"   2. 完善 writing-guide-chX.md（写作手法、体量目标、素材来源）")
        print(f"   3. 标记 status 为 completed")


if __name__ == "__main__":
    main()
