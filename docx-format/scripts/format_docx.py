#!/usr/bin/env python3
"""
docx 格式化脚本 - 通用版
功能：
1. 标题识别：第X章 → Heading1, X.X → Heading2, X.X.X → Heading3
2. Unicode文本公式转换：下标/上标字符 → Word OMML 可编辑公式
3. 题注转换：图X-X 描述 → Figure Caption, 表X-X 描述 → Table Caption
4. 图片公式OCR识别 + LaTeX→OMML替换（可选，需安装pix2tex）

用法：
  python3 format_docx.py <input.docx> <output.docx> [选项]

选项：
  --no-ocr          跳过图片公式OCR
  --heading1 PATTERN    自定义Heading1正则 (默认: ^第\s*\d+\s*章\s+\S)
  --heading2 PATTERN    自定义Heading2正则 (默认: ^\d+\.\d+\s+\S)
  --heading3 PATTERN    自定义Heading3正则 (默认: ^\d+\.\d+\.\d+\s+\S)
  --fig-pattern PATTERN 自定义图题注正则 (默认: ^图\s*(\d+-\d+)\s*(.*))
  --tab-pattern PATTERN 自定义表题注正则 (默认: ^表\s*(\d+-\d+)\s*(.*))
  --work-dir DIR    指定临时解包目录 (默认: 系统临时目录)

依赖：
  pip install lxml Pillow
  可选(OCR): pip install pix2tex
"""
import re
import copy
import os
import sys
import shutil
import tempfile
import zipfile
import argparse
from lxml import etree
from PIL import Image

# ─── 命名空间 ───────────────────────────────────────────────────────
W  = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
M  = '{http://schemas.openxmlformats.org/officeDocument/2006/math}'
XML_NS = '{http://www.w3.org/XML/1998/namespace}'
R_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
WP = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
A  = '{http://schemas.openxmlformats.org/drawingml/2006/main}'

NSMAP = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'xml': 'http://www.w3.org/XML/1998/namespace',
}

# ─── Unicode 下标/上标映射 ──────────────────────────────────────────
SUB_CHARS = '\u2080\u2081\u2082\u2083\u2084\u2085\u2086\u2087\u2088\u2089\u2090\u2091\u2092\u2093\u2099\u2098'
SUP_CHARS = '\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079\u207f'
SUB_MAP = str.maketrans(SUB_CHARS, '0123456789aeonxm')
SUP_MAP = str.maketrans(SUP_CHARS, '0123456789n')

def has_sub_sup(text):
    return any(c in SUB_CHARS or c in SUP_CHARS for c in text)

# ─── OMML 构建 ────────────────────────────────────────────────────
def _e(tag, attrib=None, text=None):
    el = etree.Element(tag, attrib or {})
    if text is not None:
        el.text = text
    return el

def omml_r(text):
    r = _e(M + 'r')
    t = _e(M + 't')
    if ' ' in text or text.startswith(' ') or text.endswith(' '):
        t.set(XML_NS + 'space', 'preserve')
    t.text = text
    r.append(t)
    return r

def omml_sub_el(base_text, sub_text):
    sSub = _e(M + 'sSub')
    e = _e(M + 'e'); e.append(omml_r(base_text)); sSub.append(e)
    sub = _e(M + 'sub'); sub.append(omml_r(sub_text)); sSub.append(sub)
    return sSub

def omml_sup_el(base_text, sup_text):
    sSup = _e(M + 'sSup')
    e = _e(M + 'e'); e.append(omml_r(base_text)); sSup.append(e)
    sup = _e(M + 'sup'); sup.append(omml_r(sup_text)); sSup.append(sup)
    return sSup

def omml_subsup_el(base_text, sub_text, sup_text):
    sSubSup = _e(M + 'sSubSup')
    e = _e(M + 'e'); e.append(omml_r(base_text)); sSubSup.append(e)
    sub = _e(M + 'sub'); sub.append(omml_r(sub_text)); sSubSup.append(sub)
    sup = _e(M + 'sup'); sub.append(omml_r(sup_text)); sSubSup.append(sup)
    return sSubSup

def build_omml(text):
    oMath = _e(M + 'oMath')
    i = 0
    current = ''
    while i < len(text):
        ch = text[i]
        if ch in SUB_CHARS or ch in SUP_CHARS:
            if current:
                base = current[-1]
                prefix = current[:-1]
            else:
                base = ''
                prefix = ''
            sub_str = ''
            while i < len(text) and text[i] in SUB_CHARS:
                sub_str += text[i].translate(SUB_MAP)
                i += 1
            sup_str = ''
            while i < len(text) and text[i] in SUP_CHARS:
                sup_str += text[i].translate(SUP_MAP)
                i += 1
            if prefix:
                oMath.append(omml_r(prefix))
            if base:
                if sub_str and sup_str:
                    oMath.append(omml_subsup_el(base, sub_str, sup_str))
                elif sub_str:
                    oMath.append(omml_sub_el(base, sub_str))
                elif sup_str:
                    oMath.append(omml_sup_el(base, sup_str))
                else:
                    oMath.append(omml_r(base))
            else:
                if sub_str:
                    oMath.append(omml_r(sub_str))
                if sup_str:
                    oMath.append(omml_r(sup_str))
            current = ''
        else:
            current += ch
            i += 1
    if current:
        oMath.append(omml_r(current))
    return oMath


# ─── styles.xml 修改：添加 Heading1/2/3 和 Caption ──────────────────
def add_styles(styles_path):
    parser = etree.XMLParser(remove_blank_text=False, recover=True)
    tree = etree.parse(styles_path, parser)
    root = tree.getroot()
    existing_ids = set()
    for s in root.findall(W + 'style'):
        sid = s.get(W + 'styleId', '')
        existing_ids.add(sid)

    if 'Heading1' not in existing_ids:
        h1 = _e(W + 'style')
        h1.set(W + 'type', 'paragraph'); h1.set(W + 'styleId', 'Heading1')
        name = _e(W + 'name'); name.set(W + 'val', 'heading 1'); h1.append(name)
        basedOn = _e(W + 'basedOn'); basedOn.set(W + 'val', 'Normal'); h1.append(basedOn)
        next_el = _e(W + 'next'); next_el.set(W + 'val', 'Normal'); h1.append(next_el)
        qFormat = _e(W + 'qFormat'); h1.append(qFormat)
        pPr = _e(W + 'pPr')
        keepNext = _e(W + 'keepNext'); pPr.append(keepNext)
        keepLines = _e(W + 'keepLines'); pPr.append(keepLines)
        spacing = _e(W + 'spacing'); spacing.set(W + 'before', '340'); spacing.set(W + 'after', '340'); pPr.append(spacing)
        jc = _e(W + 'jc'); jc.set(W + 'val', 'center'); pPr.append(jc)
        outlineLvl = _e(W + 'outlineLvl'); outlineLvl.set(W + 'val', '0'); pPr.append(outlineLvl)
        h1.append(pPr)
        rPr = _e(W + 'rPr')
        b = _e(W + 'b'); rPr.append(b)
        bCs = _e(W + 'bCs'); rPr.append(bCs)
        rFonts = _e(W + 'rFonts'); rFonts.set(W + 'ascii', 'SimHei'); rFonts.set(W + 'hAnsi', 'SimHei'); rFonts.set(W + 'eastAsia', 'SimHei'); rPr.append(rFonts)
        sz = _e(W + 'sz'); sz.set(W + 'val', '32'); rPr.append(sz)
        szCs = _e(W + 'szCs'); szCs.set(W + 'val', '32'); rPr.append(szCs)
        h1.append(rPr)
        root.append(h1)

    if 'Heading2' not in existing_ids:
        h2 = _e(W + 'style')
        h2.set(W + 'type', 'paragraph'); h2.set(W + 'styleId', 'Heading2')
        name = _e(W + 'name'); name.set(W + 'val', 'heading 2'); h2.append(name)
        basedOn = _e(W + 'basedOn'); basedOn.set(W + 'val', 'Normal'); h2.append(basedOn)
        next_el = _e(W + 'next'); next_el.set(W + 'val', 'Normal'); h2.append(next_el)
        qFormat = _e(W + 'qFormat'); h2.append(qFormat)
        pPr = _e(W + 'pPr')
        keepNext = _e(W + 'keepNext'); pPr.append(keepNext)
        keepLines = _e(W + 'keepLines'); pPr.append(keepLines)
        spacing = _e(W + 'spacing'); spacing.set(W + 'before', '260'); spacing.set(W + 'after', '160'); pPr.append(spacing)
        outlineLvl = _e(W + 'outlineLvl'); outlineLvl.set(W + 'val', '1'); pPr.append(outlineLvl)
        h2.append(pPr)
        rPr = _e(W + 'rPr')
        b = _e(W + 'b'); rPr.append(b)
        bCs = _e(W + 'bCs'); rPr.append(bCs)
        rFonts = _e(W + 'rFonts'); rFonts.set(W + 'ascii', 'SimHei'); rFonts.set(W + 'hAnsi', 'SimHei'); rFonts.set(W + 'eastAsia', 'SimHei'); rPr.append(rFonts)
        sz = _e(W + 'sz'); sz.set(W + 'val', '28'); rPr.append(sz)
        szCs = _e(W + 'szCs'); szCs.set(W + 'val', '28'); rPr.append(szCs)
        h2.append(rPr)
        root.append(h2)

    if 'Heading3' not in existing_ids:
        h3 = _e(W + 'style')
        h3.set(W + 'type', 'paragraph'); h3.set(W + 'styleId', 'Heading3')
        name = _e(W + 'name'); name.set(W + 'val', 'heading 3'); h3.append(name)
        basedOn = _e(W + 'basedOn'); basedOn.set(W + 'val', 'Normal'); h3.append(basedOn)
        next_el = _e(W + 'next'); next_el.set(W + 'val', 'Normal'); h3.append(next_el)
        qFormat = _e(W + 'qFormat'); h3.append(qFormat)
        pPr = _e(W + 'pPr')
        keepNext = _e(W + 'keepNext'); pPr.append(keepNext)
        keepLines = _e(W + 'keepLines'); pPr.append(keepLines)
        spacing = _e(W + 'spacing'); spacing.set(W + 'before', '160'); spacing.set(W + 'after', '80'); pPr.append(spacing)
        outlineLvl = _e(W + 'outlineLvl'); outlineLvl.set(W + 'val', '2'); pPr.append(outlineLvl)
        h3.append(pPr)
        rPr = _e(W + 'rPr')
        b = _e(W + 'b'); rPr.append(b)
        bCs = _e(W + 'bCs'); rPr.append(bCs)
        rFonts = _e(W + 'rFonts'); rFonts.set(W + 'ascii', 'SimHei'); rFonts.set(W + 'hAnsi', 'SimHei'); rFonts.set(W + 'eastAsia', 'SimHei'); rPr.append(rFonts)
        sz = _e(W + 'sz'); sz.set(W + 'val', '24'); rPr.append(sz)
        szCs = _e(W + 'szCs'); szCs.set(W + 'val', '24'); rPr.append(szCs)
        h3.append(rPr)
        root.append(h3)

    if 'Caption' not in existing_ids:
        cap = _e(W + 'style')
        cap.set(W + 'type', 'paragraph'); cap.set(W + 'styleId', 'Caption')
        name = _e(W + 'name'); name.set(W + 'val', 'caption'); cap.append(name)
        basedOn = _e(W + 'basedOn'); basedOn.set(W + 'val', 'Normal'); cap.append(basedOn)
        next_el = _e(W + 'next'); next_el.set(W + 'val', 'Normal'); cap.append(next_el)
        qFormat = _e(W + 'qFormat'); cap.append(qFormat)
        pPr = _e(W + 'pPr')
        spacing = _e(W + 'spacing'); spacing.set(W + 'before', '120'); spacing.set(W + 'after', '120'); pPr.append(spacing)
        jc = _e(W + 'jc'); jc.set(W + 'val', 'center'); pPr.append(jc)
        cap.append(pPr)
        rPr = _e(W + 'rPr')
        rFonts = _e(W + 'rFonts'); rFonts.set(W + 'ascii', 'SimSun'); rFonts.set(W + 'hAnsi', 'SimSun'); rFonts.set(W + 'eastAsia', 'SimSun'); rPr.append(rFonts)
        sz = _e(W + 'sz'); sz.set(W + 'val', '21'); rPr.append(sz)
        szCs = _e(W + 'szCs'); szCs.set(W + 'val', '21'); rPr.append(szCs)
        cap.append(rPr)
        root.append(cap)

    tree.write(styles_path, xml_declaration=True, encoding='UTF-8', standalone=True)
    print("[OK] styles.xml: 已添加 Heading1/2/3 和 Caption 样式")


# ─── 题注构建 ─────────────────────────────────────────────────────
def build_caption(cap_type, num_str, desc_text, orig_pPr):
    """构建题注段落，cap_type 为 'Figure' 或 'Table'"""
    cn_label = '\u56fe' if cap_type == 'Figure' else '\u8868'
    para = _e(W + 'p')
    pPr = _e(W + 'pPr')
    pStyle = _e(W + 'pStyle'); pStyle.set(W + 'val', 'Caption'); pPr.append(pStyle)
    if orig_pPr is not None:
        for child in orig_pPr:
            local = child.tag.split('}')[-1]
            if local not in ('pStyle', 'outlineLvl'):
                try:
                    pPr.append(copy.deepcopy(child))
                except Exception:
                    pass
    para.append(pPr)
    r0 = _e(W + 'r'); t0 = _e(W + 't'); t0.text = cn_label; r0.append(t0); para.append(r0)
    r1 = _e(W + 'r'); fc1 = _e(W + 'fldChar'); fc1.set(W + 'fldCharType', 'begin'); r1.append(fc1); para.append(r1)
    r2 = _e(W + 'r'); instr = _e(W + 'instrText'); instr.set(XML_NS + 'space', 'preserve'); instr.text = ' SEQ {0} \\* ARABIC '.format(cap_type); r2.append(instr); para.append(r2)
    r3 = _e(W + 'r'); fc3 = _e(W + 'fldChar'); fc3.set(W + 'fldCharType', 'separate'); r3.append(fc3); para.append(r3)
    r4 = _e(W + 'r'); t4 = _e(W + 't'); t4.text = num_str; r4.append(t4); para.append(r4)
    r5 = _e(W + 'r'); fc5 = _e(W + 'fldChar'); fc5.set(W + 'fldCharType', 'end'); r5.append(fc5); para.append(r5)
    if desc_text:
        r6 = _e(W + 'r'); t6 = _e(W + 't'); t6.set(XML_NS + 'space', 'preserve'); t6.text = '\u2003' + desc_text; r6.append(t6); para.append(r6)
    return para


# ─── 辅助 ──────────────────────────────────────────────────────────
def para_text(p):
    parts = [t.text for t in p.iter(W + 't') if t.text]
    return ''.join(parts).strip()

def is_toc_entry(text):
    """检测是否为目录条目（含连续点号或章号+页码格式）"""
    if '\u2026\u2026' in text:
        return True
    if re.match(r'^\u7b2c\s*\d+\s*\u7ae0\s+.*\(\d+\)\s*$', text):
        return True
    return False

# 非题注起始词：以这些词开头的"图/表X-X"描述不是独立题注
NON_CAPTION_STARTS = ['\u7ed9\u51fa', '\u793a\u51fa', '\u662f', '\u4e2d\uff0c', '\u4e2d,', '\u6240\u793a', '\u6240\u793a\u51fa',
                       '\u8868\u793a', '\u63cf\u8ff0', '\u5217\u51fa', '\u8bf4\u660e', '\u4e3a', '\u4e2d\u7ed9', '\u4e2d\u793a']

def is_true_caption(match_obj, full_text=''):
    """判断正则匹配是否真的是题注（而非正文中提及图/表）"""
    if not match_obj:
        return False
    desc = match_obj.group(2).strip() if match_obj.lastindex >= 2 else ''
    num  = match_obj.group(1).strip() if match_obj.lastindex >= 1 else ''
    for s in NON_CAPTION_STARTS:
        if desc.startswith(s):
            return False
    # 比率检测：题注占段落60%以上，或段落总长<=120 → 认为是题注
    if full_text:
        cap_len = len(num) + 1 + len(desc)
        ratio  = cap_len / max(len(full_text), 1)
        if ratio < 0.6 and len(full_text) > 120:
            return False
    return True


# ─── 图片公式替换 ──────────────────────────────────────────────────
def replace_drawing_with_omml(drawing, omml_element):
    """将 w:drawing 元素替换为 m:oMath 元素"""
    run = drawing.getparent()
    if run is None:
        return False
    run_parent = run.getparent()
    if run_parent is None:
        return False
    try:
        run_idx = list(run_parent).index(run)
        run_parent.remove(run)
        run_parent.insert(run_idx, omml_element)
        return True
    except (ValueError, AttributeError) as e:
        print(f"  替换失败: {e}")
        return False


# ─── 主处理 ──────────────────────────────────────────────────────────
def process(xml_path, out_path, do_ocr=True,
            h1_pattern=None, h2_pattern=None, h3_pattern=None,
            fig_pattern=None, tab_pattern=None):
    """
    处理 document.xml，完成标题、题注、公式转换。

    参数:
      xml_path: 源 document.xml 路径
      out_path: 输出 document.xml 路径
      do_ocr: 是否进行图片公式OCR
      h1_pattern/h2_pattern/h3_pattern: 标题正则
      fig_pattern/tab_pattern: 题�注正则
    """
    # 默认正则模式
    if h1_pattern is None:
        h1_pattern = r'^\u7b2c\s*\d+\s*\u7ae0\s+\S'  # 第X章
    if h2_pattern is None:
        h2_pattern = r'^\d+\.\d+\s+\S'  # X.X
    if h3_pattern is None:
        h3_pattern = r'^\d+\.\d+\.\d+\s+\S'  # X.X.X
    if fig_pattern is None:
        fig_pattern = r'^\u56fe\s*(\d+-\d+)\s*(.*)'  # 图X-X
    if tab_pattern is None:
        tab_pattern = r'^\u8868\s*(\d+-\d+)\s*(.*)'  # 表X-X

    h1_re = re.compile(h1_pattern)
    h2_re = re.compile(h2_pattern)
    h3_re = re.compile(h3_pattern)
    fig_re = re.compile(fig_pattern)
    tab_re = re.compile(tab_pattern)

    # 需要排除 Heading2 匹配 Heading3 的情况
    h3_check = re.compile(r'^\d+\.\d+\.\d+')

    parser = etree.XMLParser(remove_blank_text=False, recover=True)
    tree = etree.parse(xml_path, parser)
    root = tree.getroot()
    body = root.find(W + 'body')
    base_dir = os.path.dirname(out_path)

    cnt = {'h1': 0, 'h2': 0, 'h3': 0, 'formula': 0, 'fig': 0, 'tab': 0,
           'toc_skipped': 0, 'img_formula': 0, 'img_formula_ok': 0}

    to_replace_caption = []
    to_replace_formula = []

    # ── Pass 1: 标题、题注、Unicode文本公式 ──
    for p in list(body.iter(W + 'p')):
        text = para_text(p)
        if not text:
            continue

        if is_toc_entry(text):
            cnt['toc_skipped'] += 1
            continue

        # ── 标题识别 ──
        h_level = None
        if h1_re.match(text):
            h_level = 'Heading1'; cnt['h1'] += 1
        elif h3_re.match(text):
            h_level = 'Heading3'; cnt['h3'] += 1
        elif h2_re.match(text) and not h3_check.match(text):
            h_level = 'Heading2'; cnt['h2'] += 1

        if h_level:
            pPr = p.find(W + 'pPr')
            if pPr is None:
                pPr = _e(W + 'pPr'); p.insert(0, pPr)
            pStyle = pPr.find(W + 'pStyle')
            if pStyle is None:
                pStyle = _e(W + 'pStyle'); pPr.insert(0, pStyle)
            pStyle.set(W + 'val', h_level)
            for ol in pPr.findall(W + 'outlineLvl'):
                pPr.remove(ol)
            # 标题段落也检查公式（不continue）

        # ── 题注识别 ──
        fig_m = fig_re.match(text)
        tab_m = tab_re.match(text)

        if is_true_caption(fig_m, text):
            new_p = build_caption('Figure', fig_m.group(1), fig_m.group(2).strip(), p.find(W + 'pPr'))
            parent = p.getparent()
            to_replace_caption.append((parent, p, new_p))
            cnt['fig'] += 1
            # 不continue，继续检查公式

        if is_true_caption(tab_m, text):
            new_p = build_caption('Table', tab_m.group(1), tab_m.group(2).strip(), p.find(W + 'pPr'))
            parent = p.getparent()
            to_replace_caption.append((parent, p, new_p))
            cnt['tab'] += 1
            # 不continue，继续检查公式

        # ── Unicode文本公式转换 ──
        if has_sub_sup(text):
            for run in list(p.findall(W + 'r')):
                t_elem = run.find(W + 't')
                if t_elem is None or not t_elem.text:
                    continue
                run_text = t_elem.text
                if not has_sub_sup(run_text):
                    continue
                clean_text = run_text.rstrip()
                oMath = build_omml(clean_text)
                to_replace_formula.append((p, run, oMath))
                cnt['formula'] += 1

    # 执行题注替换
    for parent, old, new in to_replace_caption:
        if parent is not None:
            idx = list(parent).index(old)
            parent.remove(old)
            parent.insert(idx, new)

    # 执行Unicode公式替换
    for parent, old_run, new_oMath in to_replace_formula:
        if parent is not None:
            try:
                idx = list(parent).index(old_run)
                parent.remove(old_run)
                parent.insert(idx, new_oMath)
            except ValueError:
                pass

    # ── Pass 2: 图片公式OCR + 替换 ──
    if do_ocr:
        print("\n--- 图片公式OCR识别 ---")

        # 加载关系映射
        rels_path = os.path.join(base_dir, '_rels', 'document.xml.rels')
        if not os.path.exists(rels_path):
            print("  警告: 未找到 document.xml.rels，跳过图片公式OCR")
        else:
            rels_tree = etree.parse(rels_path, parser)
            rid_map = {}
            for rel in rels_tree.getroot():
                rid = rel.get('Id')
                target = rel.get('Target')
                if rid and target and 'media' in (target or ''):
                    rid_map[rid] = os.path.basename(target)

            # 在当前XML树上找所有图片公式
            formula_entries = []
            for p in list(body.iter(W + 'p')):
                # 跳过已有oMath的段落
                if p.find('.//' + M + 'oMath') is not None:
                    continue

                for drawing in list(p.iter(W + 'drawing')):
                    inline = drawing.find(WP + 'inline')
                    if inline is None:
                        continue
                    extent = inline.find(WP + 'extent')
                    if extent is None:
                        continue
                    cy = int(extent.get('cy', '0'))
                    h_pt = cy / 12700
                    if h_pt < 3 or h_pt > 30:
                        continue
                    blip = inline.find('.//' + A + 'blip')
                    if blip is None:
                        continue
                    embed = blip.get(R_NS + 'embed')
                    if not embed or embed not in rid_map:
                        continue
                    img_file = rid_map[embed]
                    img_path = os.path.join(base_dir, 'media', img_file)
                    if not os.path.exists(img_path):
                        continue

                    formula_entries.append({
                        'drawing': drawing,
                        'image_file': img_file,
                        'image_path': img_path,
                        'h_pt': h_pt,
                    })

            cnt['img_formula'] = len(formula_entries)
            print(f"发现图片公式候选: {len(formula_entries)} 个")

            if formula_entries:
                # 加载pix2tex模型
                try:
                    import torch
                    original_load = torch.load
                    def patched_load(*args, **kwargs):
                        if 'weights_only' not in kwargs:
                            kwargs['weights_only'] = False
                        return original_load(*args, **kwargs)
                    torch.load = patched_load

                    from pix2tex.cli import LatexOCR
                    from latex_to_omml import latex_to_omml

                    print("加载pix2tex模型...")
                    model = LatexOCR()
                    print("模型加载完成，开始OCR...")

                    # OCR识别并替换
                    seen_images = {}
                    for entry in formula_entries:
                        img_path = entry['image_path']
                        drawing = entry['drawing']

                        if img_path in seen_images:
                            latex = seen_images[img_path]
                        else:
                            try:
                                im = Image.open(img_path)
                                latex = model(im)
                                seen_images[img_path] = latex
                                print(f"  OCR: {entry['image_file']} -> {latex[:80]}")
                            except Exception as e:
                                print(f"  OCR失败: {entry['image_file']}: {e}")
                                latex = None
                                seen_images[img_path] = None

                        if latex:
                            try:
                                omml = latex_to_omml(latex)
                                if replace_drawing_with_omml(drawing, omml):
                                    cnt['img_formula_ok'] += 1
                            except Exception as e:
                                print(f"  OMML转换失败: {latex}: {e}")
                except ImportError as e:
                    print(f"  跳过OCR: pix2tex未安装 ({e})")
                    print("  安装方法: pip install pix2tex")

    # 保存最终结果
    tree.write(out_path, xml_declaration=True, encoding='UTF-8', standalone=True)

    print("\n处理统计:")
    print("  标题: H1={0}, H2={1}, H3={2}".format(cnt['h1'], cnt['h2'], cnt['h3']))
    print("  目录跳过: {0}".format(cnt['toc_skipped']))
    print("  文本公式runs转换: {0}".format(cnt['formula']))
    print("  题注: 图={0}, 表={1}".format(cnt['fig'], cnt['tab']))
    print("  图片公式: 发现={0}, 成功替换={1}".format(cnt['img_formula'], cnt['img_formula_ok']))
    print("document.xml 已写出: {0}".format(out_path))
    return cnt


# ─── docx 打包/解包 ──────────────────────────────────────────────
def unpack_docx(docx_path, work_dir):
    """将docx解包到工作目录"""
    unpack_dir = os.path.join(work_dir, 'unpacked')
    if os.path.exists(unpack_dir):
        shutil.rmtree(unpack_dir)
    with zipfile.ZipFile(docx_path, 'r') as zf:
        zf.extractall(unpack_dir)
    print(f"[OK] 解包: {docx_path} -> {unpack_dir}")
    return unpack_dir


def pack_docx(unpack_dir, output_path):
    """将解包目录重新打包为docx"""
    unpack_dir = os.path.abspath(unpack_dir)
    output_path = os.path.abspath(output_path)

    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(unpack_dir):
            dirs.sort()
            files.sort()
            for fname in files:
                if fname == '.DS_Store':
                    continue
                fpath = os.path.join(root, fname)
                arcname = os.path.relpath(fpath, unpack_dir)
                zf.write(fpath, arcname)

    size = os.path.getsize(output_path)
    print(f"[OK] 打包: {output_path} ({size/1024/1024:.1f} MB)")

    # 验证关键文件
    with zipfile.ZipFile(output_path, 'r') as zf:
        names = zf.namelist()
        checks = {
            '[Content_Types].xml': '[Content_Types].xml' in names,
            '_rels/.rels': '_rels/.rels' in names,
            'word/document.xml': 'word/document.xml' in names,
        }
        for name, ok in checks.items():
            status = "OK" if ok else "MISSING"
            print(f"  [{status}] {name}")
        if not all(checks.values()):
            print("  警告: 关键文件缺失，docx可能无法正常打开！")

    return output_path


# ─── 完整流程 ──────────────────────────────────────────────────────
def format_docx(input_path, output_path, do_ocr=True,
                h1_pattern=None, h2_pattern=None, h3_pattern=None,
                fig_pattern=None, tab_pattern=None,
                work_dir=None):
    """
    完整的docx格式化流程：解包→修改styles.xml→处理document.xml→打包

    参数:
      input_path: 输入docx文件路径
      output_path: 输出docx文件路径
      do_ocr: 是否进行图片公式OCR
      h1_pattern/h2_pattern/h3_pattern: 标题识别正则
      fig_pattern/tab_pattern: 题注识别正则
      work_dir: 临时工作目录 (默认: 系统临时目录)
    """
    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)

    if not os.path.exists(input_path):
        print(f"错误: 输入文件不存在: {input_path}")
        sys.exit(1)

    # 创建工作目录
    if work_dir is None:
        work_dir = tempfile.mkdtemp(prefix='docx_format_')
    os.makedirs(work_dir, exist_ok=True)

    print(f"输入: {input_path}")
    print(f"输出: {output_path}")
    print(f"工作目录: {work_dir}")
    print(f"OCR: {'开启' if do_ocr else '关闭'}")

    # 1. 解包
    unpack_dir = unpack_docx(input_path, work_dir)
    word_dir = os.path.join(unpack_dir, 'word')

    # 2. 备份 document.xml
    doc_xml = os.path.join(word_dir, 'document.xml')
    doc_bak = os.path.join(word_dir, 'document.xml.bak')
    if not os.path.exists(doc_bak):
        shutil.copy2(doc_xml, doc_bak)
        print(f"[OK] 备份: document.xml -> document.xml.bak")

    # 3. 修改 styles.xml
    styles_path = os.path.join(word_dir, 'styles.xml')
    if os.path.exists(styles_path):
        add_styles(styles_path)

    # 4. 处理 document.xml
    src = doc_bak
    dst = doc_xml
    cnt = process(src, dst, do_ocr=do_ocr,
                   h1_pattern=h1_pattern, h2_pattern=h2_pattern, h3_pattern=h3_pattern,
                   fig_pattern=fig_pattern, tab_pattern=tab_pattern)

    # 5. 重新打包
    pack_docx(unpack_dir, output_path)

    # 6. 清理（保留.bak方便调试）
    # 不自动删除工作目录，方便调试
    print(f"\n完成! 工作目录保留在: {work_dir}")
    print(f"如需清理: rm -rf {work_dir}")

    return cnt


# ─── 命令行入口 ──────────────────────────────────────────────────
if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='docx格式化工具 - 标题/题注/公式转换')
    ap.add_argument('input', help='输入docx文件路径')
    ap.add_argument('output', help='输出docx文件路径')
    ap.add_argument('--no-ocr', action='store_true', help='跳过图片公式OCR')
    ap.add_argument('--heading1', default=None, help='自定义Heading1正则')
    ap.add_argument('--heading2', default=None, help='自定义Heading2正则')
    ap.add_argument('--heading3', default=None, help='自定义Heading3正则')
    ap.add_argument('--fig-pattern', default=None, help='自定义图题注正则')
    ap.add_argument('--tab-pattern', default=None, help='自定义表题注正则')
    ap.add_argument('--work-dir', default=None, help='指定临时工作目录')

    args = ap.parse_args()

    format_docx(
        args.input,
        args.output,
        do_ocr=not args.no_ocr,
        h1_pattern=args.heading1,
        h2_pattern=args.heading2,
        h3_pattern=args.heading3,
        fig_pattern=args.fig_pattern,
        tab_pattern=args.tab_pattern,
        work_dir=args.work_dir,
    )
