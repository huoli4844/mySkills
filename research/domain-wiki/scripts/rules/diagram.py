"""rules/diagram.py — Mermaid 图检查 + 图片引用检查"""

import os
import re

from log_utils import get_logger

log = get_logger(__name__)

__all__ = [
    "_resolve_image_path",
    "check_mermaid_quality",
    "check_self_generated_diagrams",
    "check_image_required",
    "check_image_references",
]

_VALID_DIAGRAM_DIRECTIONS = (
    "graph ", "flowchart ", "sequenceDiagram", "classDiagram", "stateDiagram",
    "stateDiagram-v2", "gantt", "pie ", "erDiagram", "journey", "gitgraph",
    "mindmap", "timeline", "quadrantChart", "requirementDiagram", "block-beta",
)


def check_mermaid_quality(body, file_label):
    """检查 Mermaid 图语法质量，返回 (FAIL列表, WARN列表)"""
    fails, warns = [], []

    # 嵌套 mermaid fence 检测
    fence_lines = re.findall(r"^```(?:mermaid)?\s*$", body, re.MULTILINE)
    depth = 0
    inner_fence_count = 0
    for fl in fence_lines:
        if fl.startswith("```mermaid"):
            if depth > 0:
                inner_fence_count += 1
            depth += 1
        elif fl == "```":
            depth = max(0, depth - 1)
    if inner_fence_count > 0:
        fails.append(
            f"[{file_label}] Mermaid嵌套fence: 检测到 {inner_fence_count} 个 "
            f"嵌套 ```mermaid``` 块，需检查 _wrap_mermaid_fields 处理逻辑"
        )

    # %%{init} Obsidian 兼容性检查
    init_blocks = re.findall(r'^%%\{init:[^\n]+', body, re.MULTILINE)
    for ib in init_blocks:
        if "'" in ib:
            fails.append(
                f"[{file_label}] Mermaid %%{{init}} 使用单引号JSON，Obsidian无法渲染。"
                f'修复: 改为双引号 {{\\"theme\\": \\"base\\", ...}}'
            )
            break
    for ib in init_blocks:
        if not ib.rstrip().endswith("%%"):
            fails.append(
                f"[{file_label}] Mermaid %%{{init}} 缺末尾 }}%% 闭合，Obsidian报No diagram type。"
                f"修复: 末尾加 }}%%"
            )
            break

    mermaid_blocks = re.findall(r"```mermaid\n(.*?)```", body, re.DOTALL)
    for i, block in enumerate(mermaid_blocks):
        content = block.strip()
        if not content:
            fails.append(f"[{file_label}] Mermaid#{i+1}: 空的 mermaid 块")
            continue

        lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
        diag_lines = [ln for ln in lines if not ln.startswith("%%{init")]

        if not diag_lines:
            fails.append(f"[{file_label}] Mermaid#{i+1}: 仅含 %%{{init}} 配置，无图内容")
            continue

        first = diag_lines[0]
        if not first.startswith(_VALID_DIAGRAM_DIRECTIONS):
            warns.append(f"[{file_label}] Mermaid#{i+1}: 首行非标准指令 ('{first[:40]}...')")

        # 检查 Mermaid 块内是否误吞了 Markdown 标题
        for j, line in enumerate(diag_lines):
            if line.startswith("##"):
                fails.append(
                    f"[{file_label}] Mermaid#{i+1}: 第{j+1}行含 Markdown 标题 "
                    f"'{line[:40]}' — Mermaid 块闭合 ``` 位置错误"
                )

        # 检查节点标签内是否含 → 等与 Mermaid 箭头语法冲突的字符
        for j, line in enumerate(diag_lines):
            if "[" in line and "]" in line:
                label_match = re.search(r"\[([^\]]*)\]", line)
                if label_match:
                    label = label_match.group(1)
                    if "→" in label:
                        fails.append(
                            f"[{file_label}] Mermaid#{i+1}: 第{j+1}行节点标签含'→'（与箭头语法冲突），请用 '>' 替代"
                        )

        # 检查是否只有孤立节点无箭头
        has_arrow = any(
            "-->" in ln or "==>" in ln or "-.->" in ln or "x-->" in ln or "o--o" in ln
            for ln in diag_lines
        )
        if not has_arrow and len(diag_lines) > 2:
            warns.append(f"[{file_label}] Mermaid#{i+1}: 无箭头连接 ({len(diag_lines)} 行)")

        # 检查 classDef/class 语句
        for j, line in enumerate(diag_lines):
            if ("classDef " in line or line.strip().startswith("class ")) and ";" in line:
                fails.append(
                    f"[{file_label}] Mermaid#{i+1}: 第{j+1}行含 classDef/class 语句与 ; 链式拼接，Mermaid 不支持此语法"
                )

        # 检查 classDef 完整性
        defined_classes = set()
        refd_classes = set()
        for dl in diag_lines:
            if dl.startswith("%%"):
                continue
            for part in dl.split(";"):
                p = part.strip()
                m = re.match(r"classDef\s+(\w+)", p)
                if m:
                    defined_classes.add(m.group(1))
                m2 = re.match(r"class\s+[\w,]+\s+(\w+)", p)
                if m2:
                    refd_classes.add(m2.group(1))
        missing = refd_classes - defined_classes - {"default"}
        if missing:
            fails.append(f"[{file_label}] Mermaid#{i+1}: classDef 缺失 {sorted(missing)}（引用但未定义）")

    return fails, warns


def check_self_generated_diagrams(body, file_label, node_type):
    """检查自生 Mermaid 图完备性，返回 (FAIL列表, WARN列表)"""
    fails, warns = [], []

    mermaid_blocks = list(re.finditer(r"```mermaid\n(.*?)```", body, re.DOTALL))
    if not mermaid_blocks:
        return fails, warns

    for i, m in enumerate(mermaid_blocks):
        block_content = m.group(1).strip()
        if not block_content:
            fails.append(f"[{file_label}] Mermaid#{i+1}: 图内容为空")
            continue

        node_names = set()
        for nm in re.findall(r'\w+\["?([^"\]\]]+)"?\]', block_content):
            node_names.add(nm.strip())
        for nm in re.findall(r"\w+\{([^\}]+)\}", block_content):
            node_names.add(nm.strip())
        for nm in re.findall(r"\w+\(([^\)]+)\)", block_content):
            node_names.add(nm.strip())
        for nm in re.findall(r"---\|\s*([^|]+?)\s*\|", block_content):
            node_names.add(nm.strip())
        for nm in re.findall(r'subgraph\s+\w+\["?([^"\]\]]+)"?\]', block_content):
            node_names.add(nm.strip())

        after_block = body[m.end():]
        analysis_section = re.search(
            r"#{1,3}\s+.*?(?:图谱解析|脉络图解析|图解析)[：:]*\s*\n(.*?)(?=\n#{1,4}\s)",
            after_block, re.DOTALL,
        )
        if analysis_section:
            analysis_text = analysis_section.group(1).strip()
        else:
            next_section = re.search(r"\n#{1,3}\s", after_block)
            analysis_text = after_block[: next_section.start()] if next_section else after_block
            analysis_text = analysis_text.strip()

        stripped_analysis = re.sub(r"```.*?```", "", analysis_text, flags=re.DOTALL)
        stripped_analysis = re.sub(r"\s", "", stripped_analysis)
        stripped_analysis = re.sub(r">.*?(\n|$)", "", stripped_analysis)
        stripped_analysis = re.sub(
            r"[，。、；：！？（）【】《》\u201c\u201d\u2018\u2019「」『』—…*#\n\r\t-]",
            "", stripped_analysis,
        )

        if not stripped_analysis or stripped_analysis.strip() in ("无", "暂无", "无。", ""):
            fails.append(f'[{file_label}] Mermaid#{i+1}: 有图无说明（缺少文字解析或仅含"无"）')

        if node_names and stripped_analysis:
            mentioned = [n for n in node_names if n in analysis_text]
            if not mentioned:
                relaxed = []
                for n in sorted(node_names, key=len, reverse=True):
                    for j in range(len(n) - 1):
                        seg = n[j: j + 2]
                        if len(seg) >= 2 and seg in analysis_text:
                            relaxed.append((n, seg))
                            break
                if not relaxed:
                    fails.append(
                        f"[{file_label}] Mermaid#{i+1}: 文字解析未提及图中任何节点名 {sorted(node_names)[:3]}"
                    )
                else:
                    warns.append(
                        f"[{file_label}] Mermaid#{i+1}: 文字解析使用缩写提及节点 ({relaxed[0][1]})，建议补全节点全名"
                    )

    if node_type == "concept" and re.search(r"```excalidraw", body, re.IGNORECASE):
        fails.append(f"[{file_label}] 概念文件禁止使用 Excalidraw 图")

    src_match = re.search(r"core_concept_map_source[：:]\s*(.+?)(?:\n|$)", body)
    if not src_match:
        src_match = re.search(r"core_concept_map_source:\s*(.+?)(?:\n|$)", body[:200])
    if src_match:
        src_val = src_match.group(1).strip().strip("'\"")
        if src_val == "无" or not src_val:
            warns.append(f'[{file_label}] Mermaid 图源为"无"，建议补充出处引用')

    return fails, warns


def _resolve_image_path(img_path, file_dir, wiki_root):
    """解析图片路径：先相对文件目录，再相对 wiki_root，再相对 assets"""
    if os.path.isabs(img_path):
        return img_path
    candidate = os.path.normpath(os.path.join(file_dir, img_path))
    if os.path.exists(candidate):
        return candidate
    candidate = os.path.normpath(os.path.join(wiki_root, img_path.lstrip("/")))
    if os.path.exists(candidate):
        return candidate
    assets_dir = os.path.join(wiki_root, "assets")
    candidate = os.path.normpath(os.path.join(assets_dir, img_path))
    if os.path.exists(candidate):
        return candidate
    return candidate


def check_image_references(body, file_path, file_label, wiki_root):
    """检查 Markdown 图片/HTML 图片引用是否存在，返回 (FAIL列表, WARN列表)"""
    fails, warns = [], []

    file_dir = os.path.dirname(file_path)

    md_imgs = re.findall(r"!\[.*?\]\((.*?)\)", body)
    for img_path in md_imgs:
        img_path = img_path.split(" ")[0]
        if img_path.startswith(("http://", "https://", "data:")):
            continue
        resolved = _resolve_image_path(img_path, file_dir, wiki_root)
        if not os.path.exists(resolved):
            fails.append(f"[{file_label}] 图片文件不存在: {img_path}")

    html_imgs = re.findall(r'<img[^>]*src="(.*?)"', body)
    for img_path in html_imgs:
        if img_path.startswith(("http://", "https://", "data:")):
            continue
        resolved = _resolve_image_path(img_path, file_dir, wiki_root)
        if not os.path.exists(resolved):
            fails.append(f"[{file_label}] 图片(HTML)文件不存在: {img_path}")

    return fails, warns


def check_image_required(body, file_label, node_type):
    """检查概念/KE 文件是否包含至少一张图片引用，返回 (FAIL列表, WARN列表)"""
    fails, warns = [], []

    image_required_types = {"concept", "knowledge-element"}
    if node_type not in image_required_types:
        return fails, warns

    fig_ref_match = re.search(
        r"#{2,4}\s+(?:\d+\.\s*)?公式引用.*?\n.*?\n+\s*#{2,4}\s+(?:\d+\.\s*)?图引用[：:]*\s*\n"
        r"(.*?)(?=\n#{1,4}\s|\Z)",
        body, re.DOTALL,
    )
    if not fig_ref_match:
        fig_ref_match = re.search(
            r"#{2,4}\s+(?:\d+\.\s*)?图引用[：:]*\s*\n(.*?)(?=\n#{1,4}\s|\Z)",
            body, re.DOTALL,
        )
    fig_refs_content = fig_ref_match.group(1).strip() if fig_ref_match else None
    if fig_refs_content is not None and (not fig_refs_content or fig_refs_content in ("无", "无。")):
        return fails, warns

    md_imgs = re.findall(r"!\[.*?\]\((.*?)\)", body)
    html_imgs = re.findall(r'<img[^>]*src="(.*?)"', body)
    total_imgs = len(md_imgs) + len(html_imgs)

    if total_imgs == 0:
        text_refs = re.findall(r">\s*图\d+[-–]-\d+", body)
        if text_refs:
            warns.append(
                f"[{file_label}] 图片引用缺失: 发现 {len(text_refs)} 处文本图引用 (> 图X-X)，未转为 Markdown 图片格式"
            )
        else:
            warns.append(f"[{file_label}] 图片引用缺失: 文件中无任何图片引用，建议补充出处相关图片")

    return fails, warns
