#!/usr/bin/env python3
"""
矢量公式提取工具 — 在线 LLM 驱动版
=================================
从 EMF/WMF/PNG 等图片中提取可编辑数学公式。

核心特点:
  - 不依赖 LibreOffice / ImageMagick 等本地重型软件
  - 使用在线转换 API 处理 EMF/WMF (ConvertAPI)
  - 使用 kimi-k2.6 / Moonshot 等多模态大模型进行公式识别
  - 同时输出 Markdown 可用的 LaTeX 和 Word 可用的 OMML

依赖:
  pip install lxml Pillow requests

环境变量:
  CONVERTAPI_SECRET    ConvertAPI 密钥 (用于 EMF/WMF 转 PNG)
  MOONSHOT_API_KEY     Moonshot API 密钥 (公式识别)
  OPENAI_API_KEY       或 OpenAI API 密钥

用法:
  # 单文件 (自动处理 EMF/WMF 转换)
  python3 extract_formula.py 图2-27-漏感产生的反电动势.wmf

  # 批量处理
  python3 extract_formula.py /path/to/assets/ --batch -o ./output/

  # 已有 PNG，直接识别
  python3 extract_formula.py formula.png --no-convert

  # 使用 OpenAI 模型
  python3 extract_formula.py formula.png --provider openai --model gpt-4o
"""

import os
import re
import sys
import json
import gzip
import base64
import shutil
import tempfile
import argparse
import requests
from pathlib import Path
from typing import Optional, Tuple

# ── 导入 latex_to_omml ──
SCRIPT_DIR = Path(__file__).resolve().parent
DOCX_FMT_DIR = SCRIPT_DIR.parent.parent / "docx-format" / "scripts"
if str(DOCX_FMT_DIR) not in sys.path:
    sys.path.insert(0, str(DOCX_FMT_DIR))
try:
    from latex_to_omml import latex_to_omml
except ImportError:
    print("[ERROR] 无法导入 latex_to_omml.py，请确保 docx-format 技能存在")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════
# 配置常量
# ═══════════════════════════════════════════════════════════════════

CONVERTAPI_BASE = "https://v2.convertapi.com"
MOONSHOT_BASE = "https://api.moonshot.cn/v1"
OPENAI_BASE = "https://api.openai.com/v1"

FORMULA_PROMPT = (
    "你是一个专业的数学公式识别专家。请识别图片中的数学公式，"
    "只输出纯 LaTeX 代码（用 $...$ 包裹行内公式，$$...$$ 包裹独立公式），"
    "不要任何解释、不要 markdown 代码块标记。"
    "如果图片中没有公式，请直接回复：无公式。"
)

# ═══════════════════════════════════════════════════════════════════
# 在线转换: EMF/WMF → PNG (ConvertAPI)
# ═══════════════════════════════════════════════════════════════════

class OnlineConverter:
    """使用 ConvertAPI 在线转换 EMF/WMF 到 PNG"""

    def __init__(self, secret: Optional[str] = None):
        self.secret = secret or os.environ.get("CONVERTAPI_SECRET")
        if not self.secret:
            raise RuntimeError(
                "缺少 ConvertAPI 密钥。请设置 CONVERTAPI_SECRET 环境变量，"
                "或访问 https://www.convertapi.com/ 获取免费密钥。"
            )

    def convert(self, input_path: str, output_dir: str) -> str:
        """转换文件，返回 PNG 路径"""
        input_path = Path(input_path).resolve()
        ext = input_path.suffix.lower().lstrip('.')

        # 支持的输入格式映射
        format_map = {'emf': 'emf', 'wmf': 'wmf', 'emz': 'emf', 'wmz': 'wmf'}
        if ext not in format_map:
            raise ValueError(f"不支持的格式: {ext}")

        # EMZ/WMZ 先解压
        actual_input = str(input_path)
        if ext in ('emz', 'wmz'):
            actual_input = self._decompress(input_path, output_dir)
            ext = format_map[ext]

        # 调用 ConvertAPI
        url = f"{CONVERTAPI_BASE}/convert/{ext}/to/png?Secret={self.secret}"
        print(f"  [ConvertAPI] 正在转换 {input_path.name} ...")

        with open(actual_input, 'rb') as f:
            resp = requests.post(url, files={"File": f}, timeout=120)

        if resp.status_code != 200:
            raise RuntimeError(
                f"ConvertAPI 失败: HTTP {resp.status_code}\n{resp.text[:500]}"
            )

        data = resp.json()
        files = data.get("Files", [])
        if not files:
            raise RuntimeError("ConvertAPI 返回空文件列表")

        # 下载转换后的 PNG
        png_url = files[0]["Url"]
        png_name = files[0]["FileName"]
        png_path = Path(output_dir) / png_name

        img_resp = requests.get(png_url, timeout=60)
        img_resp.raise_for_status()
        png_path.write_bytes(img_resp.content)

        print(f"  [ConvertAPI] 完成 → {png_path}")
        return str(png_path)

    @staticmethod
    def _decompress(input_path: Path, output_dir: str) -> str:
        """解压 EMZ/WMZ (gzip 压缩的 EMF/WMF)"""
        out_ext = 'emf' if input_path.suffix.lower() == '.emz' else 'wmf'
        out_path = Path(output_dir) / (input_path.stem + '.' + out_ext)
        with gzip.open(input_path, 'rb') as fin:
            out_path.write_bytes(fin.read())
        print(f"  [解压] {input_path.name} → {out_path.name}")
        return str(out_path)


# ═══════════════════════════════════════════════════════════════════
# LLM 客户端 (Moonshot / OpenAI / 自定义)
# ═══════════════════════════════════════════════════════════════════

class LLMClient:
    """多模态大模型客户端，用于公式识别"""

    def __init__(self, provider: str = "moonshot", api_key: Optional[str] = None,
                 base_url: Optional[str] = None, model: Optional[str] = None):
        self.provider = provider.lower()

        if self.provider == "moonshot":
            self.api_key = api_key or os.environ.get("MOONSHOT_API_KEY")
            self.base_url = base_url or MOONSHOT_BASE
            self.model = model or "kimi-k2-6"
        elif self.provider == "openai":
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
            self.base_url = base_url or OPENAI_BASE
            self.model = model or "gpt-4o"
        else:
            self.api_key = api_key
            self.base_url = base_url or ""
            self.model = model or "default"

        if not self.api_key:
            raise RuntimeError(
                f"缺少 {self.provider} 的 API 密钥。"
                f"请设置环境变量或在命令行指定。"
            )

    def recognize_formula(self, image_path: str) -> str:
        """识别图片中的公式，返回 LaTeX 字符串"""
        image_path = Path(image_path).resolve()

        # 编码为 base64
        image_data = image_path.read_bytes()
        b64 = base64.b64encode(image_data).decode('utf-8')
        mime = "image/png" if image_path.suffix.lower() == '.png' else "image/jpeg"
        data_url = f"data:{mime};base64,{b64}"

        print(f"  [LLM] 使用 {self.provider}/{self.model} 识别公式 ...")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": FORMULA_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}}
                    ]
                }
            ],
            "temperature": 0.1,
            "max_tokens": 2048,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )

        if resp.status_code != 200:
            raise RuntimeError(
                f"LLM API 失败: HTTP {resp.status_code}\n{resp.text[:500]}"
            )

        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        # 清理响应
        latex = self._extract_latex(content)
        return latex

    @staticmethod
    def _extract_latex(text: str) -> str:
        """从 LLM 响应中提取 LaTeX"""
        text = text.strip()

        # 如果回复"无公式"
        if text in ("无公式", "无", "None", "none"):
            return ""

        # 移除 markdown 代码块标记
        text = re.sub(r'^```(?:latex|math)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

        # 如果内容被 $...$ 或 $$...$$ 包裹，保留
        if text.startswith('$') and text.endswith('$'):
            return text

        # 否则用 $$ 包裹作为独立公式
        return f"$${text}$$"


# ═══════════════════════════════════════════════════════════════════
# 输出处理: LaTeX → OMML
# ═══════════════════════════════════════════════════════════════════

def save_outputs(latex: str, basename: str, output_dir: str) -> Tuple[str, str]:
    """保存 LaTeX 和 OMML 输出文件"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 保存 LaTeX (Markdown 可用)
    latex_file = output_dir / f"{basename}.latex.md"
    latex_file.write_text(f"# 公式: {basename}\n\n{latex}\n", encoding='utf-8')

    # 2. 提取裸 LaTeX (去掉 $$) 用于转 OMML
    raw = latex.strip()
    if raw.startswith('$$') and raw.endswith('$$'):
        raw = raw[2:-2].strip()
    elif raw.startswith('$') and raw.endswith('$'):
        raw = raw[1:-1].strip()

    # 3. 转换为 OMML
    omml_file = output_dir / f"{basename}.omml.xml"
    if raw:
        try:
            omml_el = latex_to_omml(raw)
            omml_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                + etree_tostring(omml_el, pretty=True)
            )
            omml_file.write_text(omml_xml, encoding='utf-8')
        except Exception as e:
            print(f"  [WARN] OMML 转换失败: {e}")
            omml_file.write_text(f"<!-- OMML 转换失败: {e} -->\n<!-- LaTeX: {raw} -->", encoding='utf-8')
    else:
        omml_file.write_text("<!-- 无公式 -->", encoding='utf-8')

    print(f"  [输出] LaTeX → {latex_file}")
    print(f"  [输出] OMML  → {omml_file}")
    return str(latex_file), str(omml_file)


def _find_sibling_image(emf_path: Path) -> Optional[Path]:
    """检查同目录下是否存在同名 PNG/JPEG 预览图（Word 常同时保存）"""
    for suffix in ('.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG'):
        candidate = emf_path.with_suffix(suffix)
        if candidate.exists():
            return candidate
    return None


def etree_tostring(element, pretty=False):
    """辅助: lxml 元素转字符串"""
    from lxml import etree
    return etree.tostring(element, encoding='unicode', pretty_print=pretty)


# ═══════════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════════

def process_file(input_path: str, output_dir: str,
                 provider: str, model: Optional[str],
                 no_convert: bool = False,
                 keep_png: bool = False) -> Optional[Tuple[str, str]]:
    """处理单个文件，返回 (latex_path, omml_path)"""
    input_path = Path(input_path).resolve()
    basename = input_path.stem

    print(f"\n{'='*60}")
    print(f"处理: {input_path.name}")
    print(f"{'='*60}")

    # 步骤1: 确定图片路径
    image_path = str(input_path)
    ext = input_path.suffix.lower()

    if ext in ('.emf', '.wmf', '.emz', '.wmz') and not no_convert:
        # 策略A: 先检查同目录是否有同名 PNG/JPEG 预览（Word 常同时保存）
        sibling = _find_sibling_image(input_path)
        if sibling:
            print(f"  [发现] 同目录存在位图预览，直接使用: {sibling.name}")
            return process_image(str(sibling), basename, output_dir, provider, model)

        # 策略B: 使用 ConvertAPI 在线转换
        try:
            converter = OnlineConverter()
            with tempfile.TemporaryDirectory() as tmpdir:
                image_path = converter.convert(str(input_path), tmpdir)
                if keep_png:
                    kept = Path(output_dir) / (basename + '.png')
                    shutil.copy(image_path, kept)
                    print(f"  [保留] 转换后的 PNG → {kept}")
                # 继续用转换后的 PNG 识别
                result = process_image(image_path, basename, output_dir, provider, model)
                return result
        except RuntimeError as e:
            print(f"  [ERROR] 在线转换失败: {e}")
            print("  [提示] 方案1: 手动将 EMF/WMF 转为 PNG，然后用 --no-convert 参数")
            print("  [提示] 方案2: 检查原始 docx 中是否有同名 PNG 预览")
            return None
    elif ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp'):
        return process_image(image_path, basename, output_dir, provider, model)
    else:
        print(f"  [SKIP] 不支持的格式: {ext}")
        return None


def process_image(image_path: str, basename: str, output_dir: str,
                  provider: str, model: Optional[str]) -> Optional[Tuple[str, str]]:
    """处理已转换好的图片"""
    # 步骤2: LLM 识别
    try:
        client = LLMClient(provider=provider, model=model)
        latex = client.recognize_formula(image_path)
    except RuntimeError as e:
        print(f"  [ERROR] LLM 识别失败: {e}")
        return None

    if not latex:
        print("  [结果] 未识别到公式")
        return None

    print(f"  [结果] LaTeX: {latex[:100]}...")

    # 步骤3: 保存输出
    return save_outputs(latex, basename, output_dir)


def main():
    ap = argparse.ArgumentParser(description='矢量公式提取工具 — 在线 LLM 驱动')
    ap.add_argument('input', help='输入文件或目录')
    ap.add_argument('-o', '--output', default='./formula_output',
                    help='输出目录 (默认: ./formula_output)')
    ap.add_argument('--provider', default='moonshot',
                    choices=['moonshot', 'openai', 'custom'],
                    help='LLM 提供商 (默认: moonshot)')
    ap.add_argument('--model', default=None,
                    help='模型名称 (默认: kimi-k2-6 / gpt-4o)')
    ap.add_argument('--api-key', default=None,
                    help='API 密钥 (默认从环境变量读取)')
    ap.add_argument('--base-url', default=None,
                    help='自定义 API Base URL (仅 provider=custom 时使用)')
    ap.add_argument('--convertapi-secret', default=None,
                    help='ConvertAPI 密钥 (默认从 CONVERTAPI_SECRET 读取)')
    ap.add_argument('--no-convert', action='store_true',
                    help='跳过 EMF/WMF 转换（输入已是 PNG/JPG）')
    ap.add_argument('--batch', action='store_true',
                    help='批量处理目录中的所有支持文件')
    ap.add_argument('--keep-png', action='store_true',
                    help='保留在线转换后的 PNG 文件')

    args = ap.parse_args()

    # 设置环境变量（如果命令行指定）
    if args.api_key:
        if args.provider == 'moonshot':
            os.environ['MOONSHOT_API_KEY'] = args.api_key
        else:
            os.environ['OPENAI_API_KEY'] = args.api_key
    if args.convertapi_secret:
        os.environ['CONVERTAPI_SECRET'] = args.convertapi_secret

    input_path = Path(args.input).resolve()

    if args.batch or input_path.is_dir():
        # 批量模式
        files = []
        for ext in ('*.emf', '*.wmf', '*.emz', '*.wmz', '*.png', '*.jpg', '*.jpeg'):
            files.extend(input_path.glob(ext))
            files.extend(input_path.glob(ext.upper()))
        files = sorted(set(files))

        if not files:
            print(f"未找到支持格式的文件: {input_path}")
            sys.exit(1)

        print(f"\n批量处理: 发现 {len(files)} 个文件")
        success = 0
        for f in files:
            if process_file(str(f), args.output, args.provider, args.model,
                           args.no_convert, args.keep_png):
                success += 1
        print(f"\n完成: {success}/{len(files)} 个文件成功")
    else:
        # 单文件模式
        process_file(str(input_path), args.output, args.provider, args.model,
                    args.no_convert, args.keep_png)


if __name__ == '__main__':
    main()
