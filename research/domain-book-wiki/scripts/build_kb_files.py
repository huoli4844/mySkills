#!/usr/bin/env python3
"""
build_kb_files.py - 知识库L1节点文件工程化生成脚本

设计：
- 直接调用 template_assembler.assemble_md()，跳过 JSON 管道
- LaTeX 公式、Mermaid 图用 Python raw string 直接写，零转义
- 公式如 $$ \frac{1}{2} $$ 在 raw string 中就是 \\frac，无需 \\\\frac
- 每次运行可重复，内置完整性校验
- 输出文件直接写目标目录

用法:
  python3 build_kb_files.py --type ke
  python3 build_kb_files.py --type ke --output-dir $TMP/test
  python3 build_kb_files.py --type concept --chapter 3   # 生成第3章的概念
"""

from __future__ import annotations


import json
import os
import re
import shutil
import sys

import yaml

# 加载 template_assembler
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)
from dag_constants import BUILDER_CONFIG, DIR, REQUIRED_BD_FIELDS  # noqa: E402
from dag_state import WorkspacePaths, get_wiki_root, load_workspace_config  # noqa: E402
from log_utils import get_logger  # noqa: E402
from template_assembler import assemble_md, load_template  # noqa: E402

log = get_logger(__name__)

DATA_DIR = os.path.join(SKILL_DIR, "data")


# ── Mermaid 净化（v37.0 fix）────────────────────────────
# Mermaid 节点文本含括号/下标/运算符时必须用 "..." 包裹，否则 Parse error
_NEEDS_QUOTE = re.compile(r"[()\[\]{}|=<>+\-*/^~;₁₂₃₄₅₆₇₈₉₀ᵢⱼₙₘ↔→←↑↓²³⁴∞θαβγδεζηλμνξπρσφψωΩ]")
_NODE_BRACKET = re.compile(r"(?<!\])(?<!\!)\[([^\[\]]+)\]")  # [text] 节点（排除 markdown 链接）
_NODE_DIAMOND = re.compile(r"(?<!\{)\{([^{}]+)\}(?!\})")  # {text} 菱形
_EDGE_LABEL = re.compile(r"\|([^|]+)\|")  # |text| 边标签


def _split_stmts_bracket_aware(line: str) -> list:
    """拆分号分隔的语句，但括号 [...] / {...} / "..." 内的分号不拆分。"""
    stmts = []
    current = []
    depth_sq = 0  # [ ] 深度
    depth_cu = 0  # { } 深度
    in_dq = False  # "..." 内
    in_sq = False  # '...' 内
    for ch in line:
        if ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == "'" and not in_dq:
            in_sq = not in_sq
        elif not in_dq and not in_sq:
            if ch == "[":
                depth_sq += 1
            elif ch == "]" and depth_sq > 0:
                depth_sq -= 1
            elif ch == "{":
                depth_cu += 1
            elif ch == "}" and depth_cu > 0:
                depth_cu -= 1
        if ch == ";" and depth_sq == 0 and depth_cu == 0 and not in_dq and not in_sq:
            s = "".join(current).strip()
            if s:
                stmts.append(s)
            current = []
        else:
            current.append(ch)
    s = "".join(current).strip()
    if s:
        stmts.append(s)
    return stmts


def _sanitize_mermaid(code: str) -> str:
    """净化 Mermaid 代码块：
    1) 先对完整行的节点文本加引号（括号内的分号安全）
    2) 括号感知拆分号——只拆分 [...] / {...} / "..." 外的分号
    """
    lines = []
    for raw_line in code.split("\n"):
        stripped = raw_line.strip()
        # 保留指令行、空行、graph/flowchart/subgraph/end 声明
        if (
            not stripped
            or stripped.startswith("%%")
            or stripped.startswith("graph")
            or stripped.startswith("flowchart")
            or stripped.startswith("subgraph")
            or stripped == "end"
            or stripped.startswith("style")
            or stripped.startswith("classDef")
            or stripped.startswith("class ")
            or stripped.startswith("click")
        ):
            lines.append(raw_line)
            continue
        indent = raw_line[: len(raw_line) - len(raw_line.lstrip())]
        # ── Step 1: 先在完整行上做引号包裹（此时括号文本完整） ──
        quoted = raw_line

        def _quote_bracket(m):
            text = m.group(1)
            if _NEEDS_QUOTE.search(text) and not text.startswith('"'):
                text = '"' + text.replace('"', "'") + '"'
            return "[" + text + "]"

        quoted = _NODE_BRACKET.sub(_quote_bracket, quoted)

        def _quote_diamond(m):
            text = m.group(1)
            if _NEEDS_QUOTE.search(text) and not text.startswith('"'):
                text = '"' + text.replace('"', "'") + '"'
            return "{" + text + "}"

        quoted = _NODE_DIAMOND.sub(_quote_diamond, quoted)

        def _quote_edge(m):
            text = m.group(1)
            if _NEEDS_QUOTE.search(text) and not text.startswith('"'):
                text = '"' + text.replace('"', "'") + '"'
            return "|" + text + "|"

        quoted = _EDGE_LABEL.sub(_quote_edge, quoted)
        # ── Step 2: 括号感知拆分号 ──
        stmts = _split_stmts_bracket_aware(quoted.strip())
        for stmt in stmts:
            lines.append(indent + stmt)
    return "\n".join(lines)


def _sanitize_file_mermaid(filepath: str) -> int:
    """对生成文件中所有 ```mermaid``` 块执行净化，返回修改数"""
    with open(filepath, encoding="utf-8") as f:
        content = f.read()
    if "```mermaid" not in content:
        return 0

    def _replace_block(m):
        inner = m.group(1)
        sanitized = _sanitize_mermaid(inner)
        return "```mermaid\n" + sanitized + "\n```"

    new_content = re.sub(r"```mermaid\n(.*?)```", _replace_block, content, flags=re.DOTALL)
    if new_content != content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        return new_content.count("```mermaid") // 2 or 1
    return 0


# ── 图集成辅助 ───────────────────────────────────────────
def _get_kg():
    """获取 KGraph 实例（图谱已构建时可用）"""
    try:
        from kb_graph import KGraph

        wiki_root = get_wiki_root(OUTPUT_BASE)
        kg = KGraph(wiki_root)
        if not os.path.exists(kg.db_path):
            return None
        return kg
    except Exception as e:
        log.debug(f"KG 初始化跳过: {e}")
        return None


def _graph_precheck(items, item_type):
    """生成前图检查"""
    results = {"warn": [], "info": []}
    kg = _get_kg()
    if not kg:
        results["info"].append("图谱未构建，跳过生成前检查")
        return results
    # 相似名检查
    incoming_names = {it["name"] for it in items if "name" in it}
    existing = kg.check_similar_names(threshold=0.75)
    for pair in existing.get("pairs", []):
        if pair["name1"] in incoming_names:
            results["warn"].append(
                f"新节点「{pair['name1']}」与已有节点「{pair['name2']}」相似({pair['similarity']})，确认是否重复"
            )
    # 依赖验证
    dep_map = {
        "ke": ("concept", "知识要素应引用至少1个核心概念"),
        "kp": ("knowledge-element", "知识点应引用至少1个知识要素"),
        "sp": ("knowledge", "技能点应引用至少1个知识点"),
        "scene": ("skill", "应用场景应引用至少1个技能点"),
    }
    if item_type in dep_map:
        dep_type, dep_desc = dep_map[item_type]
        with kg._conn() as c:
            dep_count = c.execute("SELECT COUNT(*) FROM nodes WHERE type=?", (dep_type,)).fetchone()[0]
        if dep_count == 0:
            results["warn"].append(f"{dep_desc}，但图谱中无{dep_type}类型节点")
        results["info"].append(f"图谱中已有 {dep_count} 个{dep_type}节点可供引用")
    return results


def _graph_postcheck(item_type, generated_count):
    """生成后图检查"""
    results = {"critical": [], "warning": [], "info": []}
    kg = _get_kg()
    if not kg:
        return results
    try:
        kg.build()
    except Exception as e:
        results["warning"].append(("图重建失败", str(e), ""))
        return results
    quality = kg.check_graph_quality()
    for issue in quality["issues"]:
        sev = issue["severity"]
        cat = issue["category"]
        msg = issue["message"]
        fix = issue.get("fix_hint", "")
        results[sev].append((cat, msg, fix))
    return results


def _report_graph_results(pre_results, post_results):
    """打印图检查报告"""
    log.info("\n  📊 ── 图增强检查报告 ──")
    if pre_results:
        for w in pre_results.get("warn", []):
            log.warning(f"生成前: {w}")
        if not pre_results.get("warn"):
            log.success("生成前检查通过")
        for i in pre_results.get("info", []):
            log.info(f"ℹ️  {i}")
    if post_results:
        crits = post_results.get("critical", [])
        warns = post_results.get("warning", [])
        if crits:
            log.info("🔴 生成后 critical:")
            for cat, msg, _fix in crits[:3]:
                log.error(f"[{cat}] {msg}")
        if warns:
            log.warning("生成后 warning:")
            for cat, msg, _ in warns[:5]:
                log.warning(f"[{cat}] {msg}")
        if not crits and not warns:
            log.success("生成后图质量正常")
        log.info(f"汇总: 🔴 {len(crits)} / ⚠️ {len(warns)}")
    log.info("────────────────────────────────")


# ── v46.0: self_check_questions 格式化器 ──────────────────

def _format_self_check_questions(scq) -> str:
    """将 self_check_questions (list/dict/str) 格式化为 Markdown 编号列表。"""
    import yaml

    if isinstance(scq, str) and scq.strip() and scq != "无":
        if scq.strip()[0].isdigit():
            return scq
        try:
            parsed = yaml.safe_load(scq)
            if isinstance(parsed, list):
                scq = parsed
            else:
                return scq
        except Exception as e:
            log.debug(f"YAML解析失败，使用原始数据: {e}")
            return scq
    if not isinstance(scq, list):
        return str(scq) if scq else "无"

    lines = []
    for i, item in enumerate(scq):
        if isinstance(item, dict):
            q = item.get("question", item.get("q", ""))
            hint = item.get("hint", item.get("answer", item.get("a", "")))
            if hint and hint != q:
                lines.append(f"{i+1}. {q}（提示：{hint}）")
            else:
                lines.append(f"{i+1}. {q}")
        elif isinstance(item, str):
            lines.append(item)
        else:
            lines.append(f"{i+1}. {item}")
    return "\n".join(lines) if lines else "无"


def _format_list_to_numbered(lst: list) -> str:
    """将列表格式化为 Markdown 编号列表。"""
    if not isinstance(lst, list):
        return str(lst)
    lines = []
    for i, item in enumerate(lst):
        if isinstance(item, str):
            lines.append(f"{i+1}. {item}")
        else:
            lines.append(f"{i+1}. {item}")
    return "\n".join(lines) if lines else "无"


def _load_items(filename, output_dir=None, chapter=None):
    """Load items from chapter-specific data directory.

    Priority: .dag/第{chapter}章/data/ → skill data/ fallback.
    """
    path = os.path.join(DATA_DIR, filename)
    yaml_name = filename.rsplit(".", 1)[0] + ".yaml"

    # 首选：.dag/ 内嵌数据
    if output_dir and chapter:
        from dag_state import WorkspacePaths
        ch_data = os.path.join(WorkspacePaths(output_dir).data_dir(chapter), yaml_name)
        if os.path.exists(ch_data):
            import yaml
            with open(ch_data, encoding="utf-8") as f:
                return yaml.safe_load(f) or []

    # 回退到技能目录章节数据
    if chapter:
        skill_ch = os.path.join(DATA_DIR, f"第{chapter}章", yaml_name)
        if os.path.exists(skill_ch):
            import yaml

            with open(skill_ch, encoding="utf-8") as f:
                return yaml.safe_load(f) or []

    # 最后回退到技能目录扁平数据
    yaml_path = os.path.join(DATA_DIR, yaml_name)
    if os.path.exists(yaml_path):
        import yaml

        with open(yaml_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    # v38.4: 数据文件不存在时返回空列表，而非崩溃
    log.warning(f"数据文件不存在: {yaml_name}（跳过该类型）")
    return []


BOOK_ID = os.environ.get("KB_BOOK_ID", "")
BOOK_NAME = os.environ.get("KB_BOOK_NAME", "")
OUTPUT_BASE = os.environ.get("KB_OUTPUT_BASE", "") or None  # 由 CLI 或环境变量决定

# ── v44.0 P1-1: 模板字段预检 ──
# 硬编码 BD 字段（build_type 中显式赋值的 bd 键）
_BD_HARDCODED = {"name", "book_id", "book_name", "chapter_num", "related_directory"}

# ── v48.0: 各类型必填 BD 字段（YAML 缺失时禁止填"无"，必须由 Agent 生成）──
# v50.0: 从 dag_constants.REQUIRED_BD_FIELDS 导入，删除本地定义
# 原 REQUIRED_BD_FIELDS → 直接使用 REQUIRED_BD_FIELDS


def _validate_template_fields(
    cfg: dict,
    type_name: str,
    items: list | None = None,
    output_dir: str | None = None,
    chapter: str | None = None,
) -> None:
    """校验模板占位符与 BUILDER_CONFIG / YAML bd 的覆盖情况。

    v48.0: 新增 YAML bd keys 逐项对比检测，输出 missing_fields.json 到 .dag/

    模板中每个 {{field}} 必须能被以下来源之一覆盖：
      - 硬编码字段 (name/book_id/book_name/chapter_num/related_directory)
      - bd_extra_keys_from_item_fm (从 fm 映射到 bd)
      - bd_extra_keys_from_item_bd (从 bd 直接取出)
      - YAML 数据中的 bd keys（逐 item 检查）
    """
    try:
        tmpl = load_template(cfg["template"])
        placeholders = set(re.findall(r"\{\{([a-z_][a-z0-9_]*)\\}\\}", tmpl))
    except Exception as e:
        log.debug(f"模板加载失败: {e}")
        return  # 模板加载失败时静默跳过，后续 build 循环中会报 warning

    covered = _BD_HARDCODED.copy()
    covered.update(cfg.get("bd_extra_keys_from_item_fm", []))
    covered.update(cfg.get("bd_extra_keys_from_item_bd", []))

    uncovered = placeholders - covered
    if uncovered:
        log.warning(
            f"[{type_name}] 模板 {cfg['template']} 的 {len(uncovered)} 个字段未被 "
            f"BUILDER_CONFIG 覆盖，将自动填充为「无」: {', '.join(sorted(uncovered))}"
        )
        log.info(
            f"  修复: 在 dag_constants.BUILDER_CONFIG['{type_name}'] 的 "
            f"bd_extra_keys_from_item_bd 或 bd_extra_keys_from_item_fm 中添加缺失字段"
        )

    # ── v48.0 P0: YAML bd keys 逐项对比检测 ──
    if items and output_dir and chapter:
        required_for_type = REQUIRED_BD_FIELDS.get(type_name, [])
        all_missing: dict[str, dict] = {}  # {item_name: {missing_required: [...], missing_optional: [...]}}

        for it in items:
            item_name = it.get("name", "?")
            bd_keys = set(it.get("bd", {}).keys())
            # 模板中未被 bd 覆盖的占位符（排除硬编码字段）
            item_missing = placeholders - bd_keys - _BD_HARDCODED

            if item_missing:
                required_missing = [f for f in item_missing if f in required_for_type]
                optional_missing = [f for f in item_missing if f not in required_for_type]
                all_missing[item_name] = {
                    "required": sorted(required_missing),
                    "optional": sorted(optional_missing),
                }
                if required_missing:
                    log.warning(
                        f"  ⚠️  [{type_name}/{item_name}] 必填字段缺失 (YAML bd 无此 key): "
                        f"{', '.join(required_missing)} — 将保留 {{占位符}} 标记，需Agent填充"
                    )

        if all_missing:
            dag_dir = os.path.join(output_dir, ".dag", f"第{chapter}章")
            os.makedirs(dag_dir, exist_ok=True)
            missing_path = os.path.join(dag_dir, "missing_fields.json")
            payload = {
                "type": type_name,
                "chapter": chapter,
                "template": cfg["template"],
                "required_fields_for_type": required_for_type,
                "items": all_missing,
            }
            try:
                with open(missing_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                log.info(
                    f"  📋 模板-YAML 字段同步检测完成: "
                    f"{len(all_missing)} 个 item 有缺失字段 → {missing_path}"
                )
            except Exception as e:
                log.warning(f"  ⚠️  写入 missing_fields.json 失败: {e}")


# BUILDER_CONFIG 已抽取到 dag_utils.py（v36.5），从 dag_utils 导入


def build_type(output_dir, chapter: str | None = None, graph_check=True, type_name=None, staging=True):
    """参数化的类型构建器，由 BUILDER_CONFIG[type_name] 驱动。

    统一替换了原先 6 个独立 builder 函数：
    build_ke / build_kp / build_sp / build_entity / build_scene / build_concept

    staging=True: 先写入 .build_tmp/ ，全部成功后原子 rename（防御半成品）
    """
    cfg = BUILDER_CONFIG[type_name]

    real_dir = os.path.join(output_dir, DIR[cfg["dir_key"]])
    if staging:
        out_dir = os.path.join(output_dir, ".build_tmp", DIR[cfg["dir_key"]])
        # 清理上次可能遗留的临时目录
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)
    else:
        out_dir = real_dir
    os.makedirs(out_dir, exist_ok=True)

    items = _load_items(cfg["data_file"], output_dir, chapter)
    ch_num = chapter if chapter and chapter != "0" else "0"

    # v39.1: 空数据警告升级——明确告知调用者
    if not items:
        log.warning(f"[{type_name}] 数据为空（0 items），跳过构建。")
        log.info(f"数据文件: {cfg['data_file']}")
        if output_dir and chapter:
            log.info(f"工作区数据: .dag/第{chapter}章/data/{cfg['data_file'].rsplit('.', 1)[0]}.yaml")
        if staging:
            shutil.rmtree(out_dir, ignore_errors=True)
        return 0

    pre = _graph_precheck(items, cfg["graph_type"]) if graph_check else None

    # ── v44.0 P1-1: 模板字段 preflight 校验 ──
    _validate_template_fields(cfg, type_name, items=items, output_dir=output_dir, chapter=chapter)

    count = 0
    for it in items:
        # ── 构建 body_replacements ──
        bd = dict(it["bd"])
        # v50.0: 缺失字段统一填"无"，不再保留 {{占位符}}
        try:
            tmpl = load_template(cfg["template"])
            placeholders = re.findall(r"\{\{([a-z_][a-z0-9_]*)\}\}", tmpl)
            required_for_type = REQUIRED_BD_FIELDS.get(type_name, [])
            for ph in placeholders:
                if ph not in bd:
                    if ph in required_for_type:
                        log.warning(
                            f"  ⚠️  [{type_name}/{it.get('name', '?')}] 必填字段 '{ph}' "
                            f"在 YAML bd 中缺失 — 自动填充「无」"
                        )
                    bd[ph] = "无"
        except Exception as e:
            log.warning(f"模板占位符解析失败 ({cfg.get('template','?')}): {e}")
        bd["name"] = it["name"]
        bd["book_id"] = BOOK_ID
        bd["book_name"] = BOOK_NAME
        bd["chapter_num"] = ch_num
        # v35.3: 根据布局动态生成 related_directory wikilink
        _cfg = load_workspace_config(output_dir)
        if _cfg.get("layout") == "flat":
            bd["related_directory"] = f"[[{BOOK_ID}/10_总揽/" f"book_overview_{BOOK_ID}_0|《{BOOK_NAME}》第{ch_num}章]]"
        else:
            # v43.1: 使用 WorkspacePaths 推导 wikilink 路径
            wp = WorkspacePaths(output_dir)
            bd["related_directory"] = (
                f"[[{wp.domain_name}/{wp.book_name}/10_总揽/"
                f"book_overview_{BOOK_ID}_0|《{BOOK_NAME}》第{ch_num}章]]"
            )
        # 附加 BD 字段（从 item 提取，如 entity 需要 source_chapter / entity_type）
        # v37.0: 使用 .get() 容错
        for key in cfg["bd_extra_keys_from_item_fm"]:
            bd[key] = it["fm"].get(key, "无")
        for key in cfg["bd_extra_keys_from_item_bd"]:
            bd[key] = it["bd"].get(key, "无")

        # v46.0: 格式化 self_check_questions — list/dict → Markdown 编号列表
        scq = bd.get("self_check_questions")
        if scq and isinstance(scq, (list, str)) and scq != "无":
            bd["self_check_questions"] = _format_self_check_questions(scq)

        # v49.1: 格式化 learning_objectives — list → Markdown 编号列表
        lo = bd.get("learning_objectives")
        if lo and isinstance(lo, list) and lo != "无":
            bd["learning_objectives"] = _format_list_to_numbered(lo)

        # ── 构建 front_matter_updates ──
        fm = {
            "template_version": cfg["template_version"],
            "type": cfg["fm_type"],
            "type_tags": cfg["type_tags"],
            "name": it["name"],
            "book_id": BOOK_ID,
            "book_name": BOOK_NAME,
            "chapter_num": ch_num,
            # 4 个所有类型共有的 FM 字段，一律从 it["fm"] 提取
            "confidence": it["fm"]["confidence"],
            "confidence_note": it["fm"]["confidence_note"],
            "source_chapter": it["fm"]["source_chapter"],
            "source_from": it["fm"].get("source_from", ""),
        }
        # 静态额外字段（如 ke/concept 的 aliases: []）
        fm.update(cfg["static_fm_extra"])
        # cssclass 样式类（Obsidian 兼容）
        if "cssclass" in cfg:
            fm["cssclass"] = cfg["cssclass"]
        # tags 中的 {{book_id}} 占位符替换为实际值
        if "tags" in fm and isinstance(fm["tags"], list):
            fm["tags"] = [t.replace("{{book_id}}", BOOK_ID) for t in fm["tags"]]
        # 动态额外 FM 字段（如 kp 的 bloom_level，entity 的 entity_type）
        # v37.0: 使用 .get() 容错，旧 YAML 缺少字段时填 "无"
        for key in cfg["fm_extra_keys_from_item_fm"]:
            fm[key] = it["fm"].get(key, "无")
        for key in cfg["fm_extra_keys_from_item_bd"]:
            fm[key] = it["bd"].get(key, "无")

        # v37.0: 自动填充 FM 中模板占位符但未显式设置的字段
        # 1) type_tag (singular) ← 从 type_tags (list) 取首元素
        if "type_tag" not in fm and "type_tags" in fm:
            tags = fm["type_tags"]
            fm["type_tag"] = tags[0] if isinstance(tags, list) and tags else "无"
        # 2) entity_type 等归并字段 — 仅 entity 类型需要，其他类型不填
        for _fm_ph in ["entity_type", "domain", "classification"]:
            if _fm_ph not in fm:
                fm[_fm_ph] = "无" if type_name == "entity" else None

        # v50.0: 标准化习题/解答文件命名 (第N章习题N-xxx → 第N章-习题N)
        if type_name in ("exercise", "solution"):
            import re as _re
            _orig = it["file"]
            # 标准化: 第N章习题N → 第N章-习题N (补连字符)
            _norm = _re.sub(r'^(第\d+章)习题(\d+)', r'\1-习题\2', it["file"])
            if _norm != _orig:
                it["file"] = _norm
                log.info(f"  标准化文件名: {_orig} → {_norm}")
            # v50.0: 习题↔解答自动互链
            if type_name == "exercise":
                bd["related_answer"] = f"[[90_习题/解答/{it['file']}-解答|查看解答]]"
            elif type_name == "solution":
                _ex_file = _re.sub(r'-解答$', '', it["file"])
                bd["exercise_link"] = f"90_习题/{_ex_file}"
                bd["exercise_name"] = _ex_file

        try:
            filepath = assemble_md(
                template_name=cfg["template"],
                front_matter_updates=fm,
                body_replacements=bd,
                output_dir=out_dir,
                filename=it["file"] + ".md",
                strict=True,
                quality_key=cfg.get("quality_key"),  # v37.0: 五大类归并子类型键
            )
            # v37.0: Mermaid 净化——自动修复节点文本中的特殊字符
            _sanitize_file_mermaid(filepath)
            count += 1
            log.info(f"{cfg['print_label']} {it['name']}.md -> {out_dir}")
        except Exception as e:
            log.info(f"{cfg['print_label']} ERROR {it['name']}: {e}")

    if graph_check:
        post = _graph_postcheck(cfg["graph_type"], count)
        _report_graph_results(pre, post)

    # ── Staging commit: 全成功后原子 rename ──
    if staging and count > 0:
        try:
            os.makedirs(real_dir, exist_ok=True)
            # v50.0: 逐文件移动，不替换整个目录（避免删掉其他章的同类文件）
            for fname in os.listdir(out_dir):
                src = os.path.join(out_dir, fname)
                dst = os.path.join(real_dir, fname)
                if os.path.exists(dst):
                    os.remove(dst)
                os.rename(src, dst)
            shutil.rmtree(out_dir)
            log.success(f"  ✓ 原子提交: {count} 文件 → {real_dir}")
        except OSError as e:
            log.error(f"  ✗ 原子提交失败: {e} — 保留 .build_tmp/ 产物")
            raise

    return count


# ── 向后兼容包装器（外部脚本可能 import 这些函数名） ──────────
def build_ke(output_dir, chapter: str | None = None, graph_check=True):
    return build_type(output_dir, chapter=chapter, graph_check=graph_check, type_name="ke")


def build_kp(output_dir, chapter: str | None = None, graph_check=True):
    return build_type(output_dir, chapter=chapter, graph_check=graph_check, type_name="kp")


def build_sp(output_dir, chapter: str | None = None, graph_check=True):
    return build_type(output_dir, chapter=chapter, graph_check=graph_check, type_name="sp")


def build_entity(output_dir, chapter: str | None = None, graph_check=True):
    return build_type(output_dir, chapter=chapter, graph_check=graph_check, type_name="entity")


def build_scene(output_dir, chapter: str | None = None, graph_check=True):
    return build_type(output_dir, chapter=chapter, graph_check=graph_check, type_name="scene")


def build_concept(output_dir, chapter: str | None = None, graph_check=True):
    return build_type(output_dir, chapter=chapter, graph_check=graph_check, type_name="concept")


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument("--type", required=True, choices=list(BUILDER_CONFIG.keys()))
    parser.add_argument("--output-dir", default=OUTPUT_BASE, help="输出目录（默认: 由 BOOK_ID 自动计算）")
    parser.add_argument(
        "--book-id", default=os.environ.get("KB_BOOK_ID", None), help="覆盖 BOOK_ID（可用 KB_BOOK_ID 环境变量）"
    )
    parser.add_argument(
        "--book-name", default=os.environ.get("KB_BOOK_NAME", None), help="覆盖 BOOK_NAME（可用 KB_BOOK_NAME 环境变量）"
    )
    parser.add_argument("--output-base", default=os.environ.get("KB_OUTPUT_BASE", None), help="覆盖 OUTPUT_BASE 路径")
    parser.add_argument("--chapter", default=None, help="过滤章节号，如 '3' 表示第3章")
    parser.add_argument(
        "--graph-check",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="启用图增强检查（默认开启），用 --no-graph-check 禁用",
    )
    parser.add_argument(
        "--auto-fix", action="store_true", default=False, help="构建后自动运行 post_build_fix 修复公式/图引用"
    )
    parser.add_argument("--source-dir", default=None, help="出处章节 .md 目录（用于 auto-fix 的图映射）")
    args = parser.parse_args()

    # 允许 CLI / 环境变量 覆盖 BOOK_ID / BOOK_NAME
    if args.book_id:
        BOOK_ID = args.book_id
        log.info(f"ℹ️  BOOK_ID → {BOOK_ID}")
    if args.book_name:
        BOOK_NAME = args.book_name
        log.info(f"ℹ️  BOOK_NAME → {BOOK_NAME}")
    if not BOOK_ID:
        log.error("BOOK_ID 未设置！请通过 --book-id 参数或 KB_BOOK_ID 环境变量指定。")
        log.info("   示例: python3 build_kb_files.py --type concept --book-id 01_示例书籍 -o $TMP/out")
        exit(1)
    # v49.1: BOOK_NAME 为空时尝试从 book_overview.md frontmatter 自动读取
    if not BOOK_NAME and OUTPUT_BASE:
        # 尝试标准的 book_overview 路径
        for overview_name in [f"book_overview_{BOOK_ID}.md", f"book_overview_{BOOK_ID}_0.md"]:
            ov_path = os.path.join(OUTPUT_BASE, "10_总揽", overview_name)
            if os.path.exists(ov_path):
                try:
                    with open(ov_path, encoding="utf-8") as f:
                        content = f.read()
                    # 简单解析 frontmatter
                    if content.startswith("---"):
                        end = content.find("---", 3)
                        if end > 0:
                            fm_text = content[3:end]
                            for line in fm_text.split("\n"):
                                if line.startswith("book_name:") or line.startswith("name:"):
                                    BOOK_NAME = line.split(":", 1)[1].strip().strip('"').strip("'")
                                    if BOOK_NAME:
                                        log.info(f"ℹ️  BOOK_NAME 从 {overview_name} 自动读取 → {BOOK_NAME}")
                                        break
                except Exception as e:
                    log.debug(f"BOOK_NAME提取失败: {e}")
                    pass
            if BOOK_NAME:
                break
    # --output-dir 优先，否则用 --output-base，最后自动计算
    if args.output_base:
        OUTPUT_BASE = os.path.expanduser(args.output_base)
        log.info(f"ℹ️  OUTPUT_BASE → {OUTPUT_BASE}")
    elif not OUTPUT_BASE:
        # v35.3: 自动检测工作区布局，不再硬编码路径
        cwd = os.getcwd()
        _auto_base = None
        # 优先检查 cwd 或其父目录是否有 .dag/config.yaml
        for _try_dir in [cwd, os.path.dirname(cwd)]:
            _dag_cfg = os.path.join(_try_dir, ".dag", "config.yaml")
            if os.path.exists(_dag_cfg):
                try:
                    with open(_dag_cfg, encoding="utf-8") as f:
                        _dcfg = yaml.safe_load(f) or {}
                    if _dcfg.get("layout") == "flat":
                        # flat: _try_dir 可能已经是 BOOK_ID 本身
                        _auto_base = _try_dir
                    else:
                        # nested: KB_ROOT/01_领域/01_资料库/BOOK_ID
                        _auto_base = os.path.join(_dcfg["kb_root"], "01_领域", "01_资料库", BOOK_ID)
                    break
                except Exception as e:
                    log.debug(f"配置探测跳过: {e}")
        if not _auto_base:
            # 兜底：检测 cwd 是否就是书目录（有 30_核心概念/ 等典型子目录）
            _auto_base = cwd if os.path.isdir(os.path.join(cwd, "assets")) else os.path.join(cwd, BOOK_ID)
        OUTPUT_BASE = os.path.abspath(_auto_base)
        log.info(f"ℹ️  OUTPUT_BASE 自动检测 → {OUTPUT_BASE}")
    if args.output_dir is None:
        args.output_dir = OUTPUT_BASE

    log.info(f"{'='*60}")
    log.info(f"build_kb_files.py --type {args.type}")
    if args.chapter:
        log.info(f"章节: 第{args.chapter}章")
    if args.graph_check:
        log.info("图增强检查: ✅ 已开启")
    else:
        log.info("图增强检查: ❌ 已禁用")
    log.info(f"{'='*60}")

    if args.type in BUILDER_CONFIG:
        n = build_type(args.output_dir, chapter=args.chapter, graph_check=args.graph_check, type_name=args.type)
        log.info(f"\n{'='*60}")
        log.info(f"OK 完成: {n} 个文件")
        log.info(f"{'='*60}")

        # 自动修复后处理
        if args.auto_fix and n > 0:
            try:
                from post_build_fix import (
                    fix_block_formulas,
                    fix_figure_references,
                    fix_mermaid_sources,
                )

                log.info(f"\n{'='*60}")
                log.info("运行 post_build_fix --auto-fix")
                log.info(f"{'='*60}")

                # 公式修复
                formula_fixed, formula_files = fix_block_formulas(args.output_dir)
                log.info(f"📐 公式格式修复: {formula_fixed} 处 ({len(formula_files)} 文件)")

                # 图引用修复（如有 source-dir）
                figure_fixed, figure_files, fig_map = 0, [], {}
                if args.source_dir:
                    figure_fixed, figure_files, fig_map = fix_figure_references(
                        args.output_dir, args.source_dir, "assets"
                    )
                    log.info(f"🖼️ 图引用修复: {figure_fixed} 处 ({len(figure_files)} 文件)")

                # Mermaid 图源修复
                mermaid_fixed, mermaid_files = fix_mermaid_sources(args.output_dir)
                if mermaid_fixed > 0:
                    log.info(f"🧩 Mermaid 图源修复: {mermaid_fixed} 处")

                total = formula_fixed + figure_fixed + mermaid_fixed
                if total > 0:
                    log.info(f"\n  ✅ auto-fix 完成: 共修复 {total} 处")
                else:
                    log.info("ℹ️  auto-fix: 无需修复")

            except ImportError as e:
                log.warning(f"post_build_fix 未找到: {e}")
            except Exception as e:
                log.warning(f"auto-fix 异常: {e}")
    else:
        log.info(f"Unsupported type: {args.type}")
