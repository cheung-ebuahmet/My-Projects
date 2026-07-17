#!/usr/bin/env python3
"""
📖 扫描版 PDF → Markdown 文字提取工具
=============================================
功能：将扫描版（图片型）PDF 识别为可编辑的 Markdown 文件
引擎：Tesseract（离线轻量） + EasyOCR（深度学习，效果更好）
作者：AI 辅助生成
用法：python pdf_to_md.py [PDF文件路径] [选项]

示例：
  python pdf_to_md.py 一本书.pdf
  python pdf_to_md.py 一本书.pdf --engine tesseract --lang chi_sim
  python pdf_to_md.py 一本书.pdf --engine easyocr
  python pdf_to_md.py 一本书.pdf --page 10-20  # 只识别第10-20页
"""

import os
import sys
import argparse
import time
from pathlib import Path

# ============================================================
# 项目根目录定位：始终以 My Projects 为基准
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # My Projects/
DATA_DIR = PROJECT_ROOT / "data"
EASYOCR_MODEL_DIR = DATA_DIR / "easyocr" / "models"
PIPER_MODEL_DIR = DATA_DIR / "piper"

# 设置 EasyOCR 模型路径（必须在 import easyocr 前设置！）
os.environ["EASYOCR_MODULE_PATH"] = str(EASYOCR_MODEL_DIR)

# 项目内路径
INPUT_DIR = Path(__file__).parent / "input"
OUTPUT_DIR = Path(__file__).parent / "output"

# ============================================================
# 导入
# ============================================================
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import re

# ============================================================
# 工具函数
# ============================================================
def sanitize_filename(filename: str) -> str:
    """去除文件名中的非法字符"""
    return re.sub(r'[\\/:*?"<>|]', '_', filename)

def ensure_dirs():
    """确保输入输出目录存在"""
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"📂 输入目录: {INPUT_DIR}/")
    print(f"📂 输出目录: {OUTPUT_DIR}/")

# ============================================================
# 引擎一：Tesseract OCR（离线、轻量、快速）
# ============================================================
def ocr_tesseract(image: Image.Image, lang: str = "chi_sim+eng") -> str:
    """使用 Tesseract 识别图片中的文字"""
    # 提高对比度以改善识别
    image = image.convert("L")  # 灰度
    # 二值化阈值处理
    threshold = 150
    image = image.point(lambda x: 0 if x < threshold else 255)
    text = pytesseract.image_to_string(image, lang=lang)
    return text.strip()


# ============================================================
# 引擎二：EasyOCR（深度学习，效果更好但更慢）
# ============================================================
# 延迟初始化，避免首次导入时下载
# EasyOCR 限制：ch_tra 只能与 en 组合，不能与 ch_sim 同用
# 所以需要两个 Reader：一个读简中+英文，一个读繁中+英文
_easyocr_readers = {"ch_sim": None, "ch_tra": None}

def get_easyocr_reader(script="ch_sim"):
    """延迟初始化 EasyOCR Reader（按语言分开加载）"""
    global _easyocr_readers

    if _easyocr_readers[script] is None:
        import easyocr
        if script == "ch_sim":
            lang_list = ["ch_sim", "en"]
        else:
            lang_list = ["ch_tra", "en"]

        lang_name = "简体中文" if script == "ch_sim" else "繁体中文"
        print(f"   ⏳ 加载 EasyOCR {lang_name}...")
        start = time.time()
        _easyocr_readers[script] = easyocr.Reader(
            lang_list,
            gpu=True,
            model_storage_directory=str(EASYOCR_MODEL_DIR),
            download_enabled=True
        )
        print(f"   ✅ EasyOCR {lang_name} 加载完毕（{time.time()-start:.1f} 秒）")
    return _easyocr_readers[script]

def ocr_easyocr(image: Image.Image) -> str:
    """
    使用 EasyOCR 识别（合并简繁结果）
    同时用简体+英文和繁体+英文识别，去重合并
    """
    import numpy as np

    reader_sim = get_easyocr_reader("ch_sim")
    reader_tra = get_easyocr_reader("ch_tra")
    img_array = np.array(image)

    # 两个引擎分别识别
    result_sim = reader_sim.readtext(img_array, detail=0, paragraph=True)
    result_tra = reader_tra.readtext(img_array, detail=0, paragraph=True)

    # 合并去重
    seen = set()
    merged = []
    for line in list(result_sim) + list(result_tra):
        stripped = line.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            merged.append(stripped)

    return "\n".join(merged) if merged else ""


# ============================================================
# PDF 处理核心
# ============================================================
def pdf_to_markdown(
    pdf_path: str,
    engine: str = "auto",
    lang: str = "chi_sim+chi_tra+eng",
    page_range: tuple = None,
    dpi: int = 300,
    output_path: str = None,
) -> str:
    """
    将扫描版 PDF 转换为 Markdown 文本

    参数:
        pdf_path: PDF 文件路径
        engine: 识别引擎 - "auto"(自动选择), "tesseract", "easyocr"
        lang: Tesseract 语言参数（用 + 连接）
        page_range: (起始页, 结束页)，从 1 开始
        dpi: 图片渲染分辨率（越高越清晰但越慢）
        output_path: 输出文件路径（None 则自动生成）

    返回:
        输出文件的路径
    """
    pdf_name = Path(pdf_path).stem
    print(f"\n{'='*60}")
    print(f"📖 正在处理: {pdf_name}.pdf")
    print(f"{'='*60}")

    # 打开 PDF
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"📄 总页数: {total_pages}")

    # 确定页码范围
    if page_range:
        start, end = page_range
        if start < 1:
            start = 1
        if end > total_pages:
            end = total_pages
    else:
        start, end = 1, total_pages

    pages_to_process = end - start + 1
    print(f"🔍 处理范围: 第 {start}–{end} 页（共 {pages_to_process} 页）")
    print(f"⚙️  引擎: {engine} | DPI: {dpi}")

    # 确定引擎
    use_engine = engine
    if use_engine == "auto":
        # 如果 EasyOCR 模型存在就用它，否则用 Tesseract
        if (EASYOCR_MODEL_DIR / "craft_mlt_25k.pth").exists():
            use_engine = "easyocr"
        else:
            use_engine = "tesseract"
        print(f"🤖 自动选择引擎: {use_engine}")

    # 解析 Tesseract 语言
    tesseract_lang = lang.replace("chi_tra", "chi_tra").replace("chi_sim", "chi_sim")

    # 逐页处理
    all_text = []
    start_time = time.time()

    for page_num in range(start - 1, end):
        page = doc[page_num]
        page_no = page_num + 1

        # 渲染为图片
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # OCR 识别
        try:
            if use_engine == "tesseract":
                text = ocr_tesseract(img, lang=tesseract_lang)
            elif use_engine == "easyocr":
                text = ocr_easyocr(img)
            else:
                raise ValueError(f"未知引擎: {use_engine}")

            all_text.append(f"## 第 {page_no} 页\n\n{text}\n\n")

            # 进度
            elapsed = time.time() - start_time
            avg = elapsed / (page_no - start + 1)
            remaining = avg * (end - page_no)
            print(f"   ✅ 第 {page_no}/{end} 页 完成 | "
                  f"已用 {elapsed:.0f}s | 预计剩余 {remaining:.0f}s")

        except Exception as e:
            print(f"   ❌ 第 {page_no} 页 失败: {e}")
            all_text.append(f"## 第 {page_no} 页\n\n> [OCR 识别失败: {e}]\n\n")

    doc.close()

    # 合并 Markdown 文本
    markdown_content = f"""---
title: {pdf_name}
source: {Path(pdf_path).name}
date: {time.strftime("%Y-%m-%d")}
pages: {pages_to_process}
engine: {use_engine}
---

# {pdf_name}

> 由扫描版 PDF 自动 OCR 识别生成
> 识别引擎: {use_engine} | 共 {pages_to_process} 页

---

""" + "\n---\n".join(all_text)

    # 写入文件
    if output_path is None:
        safe_name = sanitize_filename(pdf_name)
        output_path = str(OUTPUT_DIR / f"{safe_name}.md")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    # 统计
    total_chars = len(markdown_content)
    total_time = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"🎉 全部完成！")
    print(f"   文件: {output_path}")
    print(f"   字符数: {total_chars:,}")
    print(f"   耗时: {total_time:.0f} 秒（平均 {total_time/pages_to_process:.1f} 秒/页）")
    print(f"{'='*60}\n")

    return output_path


# ============================================================
# 额外功能：TTS 朗读生成的 Markdown
# ============================================================
def speak_markdown(md_path: str, voice: str = "zh-CN-YunjianNeural"):
    """将生成的 Markdown 转为语音（调用 edge-tts）"""
    import subprocess
    md_name = Path(md_path).stem
    audio_dir = PROJECT_ROOT / "audio"
    audio_dir.mkdir(exist_ok=True)
    audio_path = audio_dir / f"{md_name}.mp3"

    print(f"🔊 正在生成语音（{voice}）...")
    subprocess.run([
        str(PROJECT_ROOT / ".venv" / "bin" / "edge-tts"),
        "--voice", voice,
        "-f", md_path,
        "--write-media", str(audio_path),
    ], check=True)
    print(f"✅ 语音文件: {audio_path}")
    return audio_path


# ============================================================
# 命令行入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="📖 扫描版 PDF → Markdown 文字提取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python pdf_to_md.py 一本书.pdf
  python pdf_to_md.py 一本书.pdf --engine tesseract --lang chi_sim
  python pdf_to_md.py 一本书.pdf --engine easyocr
  python pdf_to_md.py input/一本书.pdf -o output/我的书.md
  python pdf_to_md.py 一本书.pdf --page 10-20  # 只识别10-20页
  python pdf_to_md.py 一本书.pdf --speak        # 转文字后直接生成语音
        """
    )
    parser.add_argument("pdf", nargs="?", help="PDF 文件路径（留空则扫描 input/ 目录）")
    parser.add_argument("-o", "--output", help="输出 .md 文件路径（默认自动生成）")
    parser.add_argument("--engine", choices=["auto", "tesseract", "easyocr"],
                        default="auto", help="OCR 引擎（默认自动选择）")
    parser.add_argument("--lang", default="chi_sim+chi_tra+eng",
                        help="Tesseract 语言代码（用 + 连接，默认 chi_sim+chi_tra+eng）")
    parser.add_argument("--page", help="页码范围，如 10-20 或 5")
    parser.add_argument("--dpi", type=int, default=300, help="渲染分辨率（默认 300）")
    parser.add_argument("--speak", action="store_true",
                        help="转换完成后用 edge-tts 生成语音")
    parser.add_argument("--voice", default="zh-CN-YunjianNeural",
                        help="语音角色（配合 --speak 使用）")
    parser.add_argument("--list-models", action="store_true",
                        help="列出已下载的 EasyOCR 模型文件")
    parser.add_argument("--check", action="store_true",
                        help="检查系统环境是否就绪")

    args = parser.parse_args()

    # ---------- 检查环境 ----------
    if args.check:
        check_environment()
        return

    # ---------- 列出模型 ----------
    if args.list_models:
        list_models()
        return

    # ---------- 确保目录 ----------
    ensure_dirs()

    # ---------- 确定 PDF 文件 ----------
    pdf_path = args.pdf
    if not pdf_path:
        # 自动扫描 input/ 目录
        pdf_files = sorted(Path(INPUT_DIR).glob("*.pdf"))
        if not pdf_files:
            print(f"❌ 未指定 PDF 文件，且 {INPUT_DIR}/ 中也没有 PDF 文件")
            print(f"   请将 PDF 放入 {INPUT_DIR}/，或直接传入路径")
            print(f"   用法: python pdf_to_md.py 路径/到/文件.pdf")
            sys.exit(1)
        pdf_path = str(pdf_files[0])
        print(f"📄 自动检测到: {pdf_path}")

    if not os.path.exists(pdf_path):
        print(f"❌ 文件不存在: {pdf_path}")
        sys.exit(1)

    if not pdf_path.lower().endswith(".pdf"):
        print(f"❌ 不是 PDF 文件: {pdf_path}")
        sys.exit(1)

    # ---------- 页码范围 ----------
    page_range = None
    if args.page:
        if "-" in args.page:
            parts = args.page.split("-")
            page_range = (int(parts[0]), int(parts[1]))
        else:
            p = int(args.page)
            page_range = (p, p)

    # ---------- 执行转换 ----------
    output_path = pdf_to_markdown(
        pdf_path=pdf_path,
        engine=args.engine,
        lang=args.lang,
        page_range=page_range,
        dpi=args.dpi,
        output_path=args.output,
    )

    # ---------- 可选：生成语音 ----------
    if args.speak and output_path:
        speak_markdown(output_path, voice=args.voice)


# ============================================================
# 辅助功能
# ============================================================
def check_environment():
    """检查系统环境是否就绪"""
    print("=" * 60)
    print("🔍 系统环境检查")
    print("=" * 60)

    # EasyOCR
    try:
        import easyocr
        print(f"✅ easyocr: {easyocr.__version__}")
    except ImportError:
        print("❌ easyocr: 未安装")

    # PyMuPDF
    try:
        import fitz
        print(f"✅ PyMuPDF: {fitz.version}")
    except ImportError:
        print("❌ PyMuPDF: 未安装")

    # Pillow
    try:
        from PIL import Image
        print(f"✅ Pillow: {Image.__version__}")
    except ImportError:
        print("❌ Pillow: 未安装")

    # pytesseract
    try:
        import pytesseract
        print(f"✅ pytesseract: {pytesseract.__version__}")
    except ImportError:
        print("❌ pytesseract: 未安装")

    # Tesseract 系统引擎
    import subprocess
    try:
        result = subprocess.run(["tesseract", "--version"],
                                capture_output=True, text=True, timeout=5)
        tesseract_ver = result.stdout.split("\n")[0] if result.stdout else "?"
        print(f"✅ Tesseract: {tesseract_ver}")
        # 列出中文语言包
        lang_result = subprocess.run(["tesseract", "--list-langs"],
                                     capture_output=True, text=True, timeout=5)
        langs = [l for l in lang_result.stderr.split("\n") if "chi" in l or "eng" in l]
        if langs:
            for l in langs:
                print(f"   📦 语言包: {l.strip()}")
    except Exception as e:
        print(f"❌ Tesseract: {e}")

    # Torch (GPU)
    try:
        import torch
        print(f"✅ torch: {torch.__version__}")
        print(f"   GPU 可用: {'✅ 是' if torch.cuda.is_available() else '❌ 否（使用 CPU）'}")
    except ImportError:
        print("❌ torch: 未安装")

    # EasyOCR 模型文件
    print(f"\n📁 EasyOCR 模型目录: {EASYOCR_MODEL_DIR}")
    if EASYOCR_MODEL_DIR.exists():
        models = list(EASYOCR_MODEL_DIR.glob("*.pth"))
        if models:
            for m in sorted(models):
                size = m.stat().st_size / 1024 / 1024
                print(f"   📦 {m.name} ({size:.0f} MB)")
        else:
            print("   ⚠️  目录存在但无模型文件")
    else:
        print("   ⚠️  目录不存在")

    print("=" * 60)


def list_models():
    """列出已下载的 EasyOCR 模型"""
    print("📦 EasyOCR 模型文件:")
    if EASYOCR_MODEL_DIR.exists():
        models = sorted(EASYOCR_MODEL_DIR.glob("*.pth"))
        if models:
            for m in models:
                size = m.stat().st_size / 1024 / 1024
                print(f"   {m.name} ({size:.0f} MB)")
        else:
            print("   (暂无模型，首次运行 EasyOCR 时会自动下载)")
    else:
        print("   (模型目录未创建)")


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    main()
