#!/usr/bin/env python3
"""JSON → MD template assembler: reads JSON items → fills template → writes .md files

Simplified entry point. Engine functions → template_engine.py, config → template_config.py.
"""

import datetime
import json
import os
import re
import sys
import tempfile as _tmp

from dag_constants import PipelineError
from log_utils import get_logger

from template_config import ASSEMBLER_CONFIG, NODE_CONFIG, _STD_BD, _STD_FM, C
from template_engine import (
    _fix_mermaid_block_boundaries,
    _strip_wu_sections,
    _wrap_mermaid_fields,
    add_mermaid_init,
    check_placeholders,
    fill_template,
    load_template,
    parse_template,
)

log = get_logger(__name__)

sys.dont_write_bytecode = True


# ── 文件名安全化 ──
# safe_filename 已从 parse_utils 导入（v38.0 统一）— 保留别名供外部引用
from parse_utils import safe_filename  # noqa: E402
safe_filename = safe_filename

# ── 从 tac_constants re-export ──
from tac_constants import (  # noqa: E402, F401
    ALLOWED_TEMPLATES,
    CONFIDENCE_LEVELS,
    DEFINITION_MARKERS,
    DEFINITION_MARKERS_SORTED,
    REQUIRED_FRONTMATTER,
    TYPE_QUALITY_CHECKS,
    verify_definition,
)

# ── 从 tac_quality re-export ──
from tac_quality import (  # noqa: E402, F401
    _CHECK_HANDLERS,
    _register_check,
    comprehensive_content_check,
    run_type_quality_checks,
    validate_frontmatter,
)


def _f(s):
    """Parse field spec: 'key'→(k,k,'') or 'key:src'→(k,src,'') or 'key::default'→(k,k,default)"""
    if "::" in s:
        k, d = s.split("::", 1)
        return (k, k, d)
    if ":" in s:
        k, src = s.split(":", 1)
        return (k, src, "")
    return (s, s, "")


def _v(cfg, k, kwargs):
    """Get value from kwargs or config default"""
    return kwargs.get(k, cfg.get(k, ""))


def _fn(v):
    """Safe filename from concept/entity name"""
    safe = re.sub(r"[\\/:*?\"<>|]", "_", str(v))
    safe = safe.replace(" ", "_")
    return safe[:128]


# ---------------------------------------------------------------------------
# 组装入口
# ---------------------------------------------------------------------------
def assemble_by_config(config, **kwargs):
    """通用组装函数：读取JSON数据 → 组装所有items → 写入文件"""

    c = config["t"]  # template name
    tmpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "templates", c)
    if not os.path.exists(tmpl_path):
        alt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "templates", c)
        if os.path.exists(alt):
            tmpl_path = alt

    with open(tmpl_path, encoding="utf-8") as f:
        template = f.read()

    items = kwargs.get("items", [])
    res = []
    for idx, item in enumerate(items):
        try:
            out = _assemble_one(config, template, item, kwargs, idx)
            res.append(out)
        except Exception as e:
            log.error(f"  ❌ {item.get('name','?')}: 生成失败 — {e}")
    return res


def _assemble_one(config, template, item, kwargs, idx):
    """Assemble a single item"""

    ver = config["v"]
    type_val = config["p"]
    id_field = config["i"]
    tag_list = config["g"]
    conf_default = config["c"]
    (name_only, is_long, is_id_based) = config["n"]
    extra_fm = config.get("x", [])
    extra_bd = config.get("y", [])
    cn = config.get("cn", "")

    # Build frontmatter
    fm = {}
    for s in _STD_FM:
        if s == "template_version":
            fm[s] = ver
        elif s == "type":
            if (isinstance(type_val, tuple) and type_val[0] == "override_type") or (isinstance(type_val, tuple) and type_val[0] == "_S"):
                fm[s] = type_val[1]
            else:
                fm[s] = type_val
        elif s == "type_tags":
            fm[s] = json.dumps(tag_list, ensure_ascii=False)
        elif s == "name":
            fm[s] = item.get("name", "")
        elif s == "book_id":
            fm[s] = kwargs.get("book_id", "")
        elif s == "book_name":
            fm[s] = kwargs.get("book_name", "")
        elif s == "chapter_num":
            fm[s] = str(kwargs.get("chapter_num", ""))
        elif s == "id_field":
            if is_id_based:
                fm[s] = item.get(id_field, f"{id_field}_{idx:03d}")
            else:
                fm[s] = f"{id_field}_{idx:03d}"
        elif s == "confidence":
            fm[s] = float(item.get("confidence", conf_default))
        elif s == "confidence_note":
            fm[s] = item.get("confidence_note", cn)
        elif s == "source_chapter":
            fm[s] = item.get("source_chapter", "")
        elif s == "source_page":
            fm[s] = item.get("source_page", "")
        elif s == "source_from":
            fm[s] = item.get("source_from", "")
        elif s == "reviewer":
            fm[s] = item.get("reviewer", "系统自动")
        elif s == "review_date":
            fm[s] = item.get("review_date", datetime.date.today().isoformat())
        elif s == "aliases":
            fm[s] = json.dumps(item.get("aliases", []), ensure_ascii=False)
        elif s == "tags":
            fm[s] = json.dumps(item.get("tags", []), ensure_ascii=False)

    # Extra frontmatter fields
    for s in extra_fm:
        if isinstance(s, tuple):
            if s[0] == "_S":
                fm[s[1]] = s[2]
            elif s[0] == "_D":
                fm[s[1]] = datetime.datetime.now().strftime(s[2])
            continue
        k, src, d = _f(s)
        v = item.get(src, d)
        if v == "" and d != "":
            v = d
        fm[k] = v

    # Build body data
    bd = {}
    for s in _STD_BD:
        if s == "name":
            bd["name"] = item.get("name", "")
        elif s == "id_field":
            bd["id_field"] = item.get(id_field, f"{id_field}_{idx:03d}")
        elif s == "book_id":
            bd["book_id"] = kwargs.get("book_id", "")
        elif s == "book_name":
            bd["book_name"] = kwargs.get("book_name", "")
        elif s == "chapter_num":
            bd["chapter_num"] = str(kwargs.get("chapter_num", ""))
        elif s == "source_chapter":
            bd["source_chapter"] = item.get("source_chapter", "")
        elif s == "source_page":
            bd["source_page"] = item.get("source_page", "")
        elif s == "source_from":
            bd["source_from"] = item.get("source_from", "")
        elif s == "reviewer":
            bd["reviewer"] = item.get("reviewer", "系统自动")
        elif s == "review_date":
            bd["review_date"] = item.get("review_date", datetime.date.today().isoformat())

    for s in extra_bd:
        if isinstance(s, tuple):
            if s[0] == "_S":
                bd[s[1]] = s[2]
            elif s[0] == "_D":
                bd[s[1]] = datetime.datetime.now().strftime(s[2])
            continue
        k, src, d = _f(s)
        v = item.get(src, d)
        if v == "" and d != "":
            v = d
        bd[k] = v

    # Verify definition if applicable
    name = item.get("name", "")
    definition = item.get("definition", "")
    source_file = item.get("source_file", "")

    if definition:
        if re.search(r"是指|称为|即|就是|指", definition):
            log.success(f"  ✅ {name}: 含标记词「是指」")
        else:
            log.info(f"  ⛔ {name}: 定义中无定义标记词，可能不是有效定义")

        if source_file and os.path.exists(source_file):
            with open(source_file, encoding="utf-8") as sf:
                src_text = sf.read()
            check_text = definition.replace("\n", "")[:80]
            if check_text in src_text:
                log.success(f"  ✅ {name}: 精准释义可检索（含标记词）")
            else:
                def strip_punct(t):
                    return re.sub(r'[，。、；：""\u2018\u2019！？（）【】《》\s]', "", t)

                stripped = strip_punct(check_text)
                if any(stripped in s for s in [src_text, strip_punct(src_text[:500])]):
                    log.warning(f"  ⚠️  {name}: 去标点后匹配成功，定义基本一致")
                else:
                    log.error(f"  ❌ {name}: 精准释义在出处中不可检索！可尝试放宽 source_file 或手动核验")
                    log.info(f"  ⛔ {name}: 定义验证失败，跳过")
                    return None
        elif source_file:
            log.warning(f"  ⚠️  {name}: source_file不存在: {source_file}")
        else:
            log.warning(f"  ⚠️  {name}: 无 source_file，跳过出处检索验证")

    # Render template
    bd["definition_sentence"] = bd.get("definition_sentence", "")
    all_vars = dict(kwargs)
    all_vars.update(fm)
    all_vars.update(bd)
    all_vars.update(item)

    output = fill_template(template, all_vars)

    # Determine output path
    safe_name = _fn(name) if name_only else f"{_fn(name)}_{kwargs.get('book_id','')}_{kwargs.get('chapter_num','')}"
    if is_long and not name_only:
        safe_name = f"{_fn(name)}_{kwargs.get('book_id','')}_{kwargs.get('chapter_num','')}"
    output_file = os.path.join(kwargs.get("output_dir", "."), f"{safe_name}.md")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    fd, tmpname = _tmp.mkstemp(dir=os.path.dirname(output_file), prefix="." + safe_name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(output)
        os.replace(tmpname, output_file)
    except OSError:
        if os.path.exists(tmpname):
            os.unlink(tmpname)
        raise
    log.success(f"  ✅ {name}.md")
    return output_file


# =====================================================================
# v50.7: 文件写入 + 索引渲染 + CLI 已拆分到 template_writers.py
# 向后兼容的 re-export（用 try/except 解决 circular import）
# =====================================================================
try:
    from template_writers import (  # noqa: E402, F401
        _assemble_index,
        assemble_book_overview_md,
        assemble_concept_md,
        assemble_md,
        main as _tw_main,
    )
except ImportError:
    _tw_main = None  # type: ignore

# ── CLI 入口（v52.2: 恢复 __main__，此前拆分时丢失）──
if __name__ == "__main__":
    if _tw_main:
        _tw_main()
    else:
        sys.exit("ERROR: template_writers.main() not available (circular import?)")
