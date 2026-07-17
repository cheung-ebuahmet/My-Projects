#!/usr/bin/env python3
"""
📚 PDF → 资料库 Markdown 一体化管线
=========================================
功能：扫描版 PDF → 按章节组织的 Markdown 资料库文件
流程：增强 OCR → 纠错修复 → 参考文本合并 → 章节重组

用法（一步到位）：
  python pdf_to_library.py /path/to/书.pdf                              # 整本书
  python pdf_to_library.py /path/to/书.pdf --pages 81-160 --seq 02     # 分册
  python pdf_to_library.py /path/to/书.pdf --pages 1-80 -o 书名-01.md  # 指定输出

示例：
  python pdf_to_library.py ~/Downloads/中国伊斯兰史存稿.pdf --pages 1-80 --seq 01
  python pdf_to_library.py input/书.pdf --pages 81-160 --seq 02 --engine easyocr
  python pdf_to_library.py input/书.pdf --no-reorganize  # 仅OCR，不做章节重组
"""

import os
import sys
import re
import time
import json
import subprocess
import argparse
from pathlib import Path

# ============================================================
# 项目路径
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
EASYOCR_MODEL_DIR = DATA_DIR / "easyocr" / "models"
os.environ["EASYOCR_MODULE_PATH"] = str(EASYOCR_MODEL_DIR)

SCRIPT_DIR = Path(__file__).parent
INPUT_DIR = SCRIPT_DIR / "input"
OUTPUT_DIR = SCRIPT_DIR / "output"


def run_pipeline(
    pdf_path: str,
    pages: str = None,
    seq: str = None,
    engine: str = "hybrid",
    dpi: int = 200,
    psm: int = 6,
    output_path: str = None,
    book_title: str = None,
    reorganize: bool = True,
    repair: bool = True,
    books_dir: str = None,
):
    """
    全线执行：
    Step 1: OCR 识别（pdf_to_md_pro.py）
    Step 2: 章节重组 + 参考文本替换（reorganize_by_chapter.py）
    """

    pdf_name = Path(pdf_path).stem
    print(f"\n{'='*60}")
    print(f"📚 PDF → 资料库 一体化管线")
    print(f"{'='*60}")
    print(f"📖 源文件: {pdf_path}")
    print(f"🔧 引擎: {engine} | DPI: {dpi} | PSM: {psm}")
    if pages:
        print(f"📄 页码范围: {pages}")
    print(f"{'='*60}\n")

    # ────────────────────────────
    # Step 1: OCR → 临时文件
    # ────────────────────────────
    temp_dir = PROJECT_ROOT / "books" / "_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_ocr = temp_dir / f"{pdf_name}_ocr_temp.md"

    print(f"🔍 Step 1/2: 增强 OCR 识别...")

    page_args = []
    if pages:
        page_args = ["--page", pages]

    result = subprocess.run([
        sys.executable, str(SCRIPT_DIR / "pdf_to_md_pro.py"),
        pdf_path,
        "--engine", engine,
        "--dpi", str(dpi),
        "--psm", str(psm),
        "-o", str(temp_ocr),
        *(["--no-repair"] if not repair else []),
        *page_args,
    ], cwd=str(PROJECT_ROOT))

    if result.returncode != 0:
        print(f"❌ Step 1 OCR 失败 (exit {result.returncode})")
        return None

    if not temp_ocr.exists():
        print(f"❌ OCR 输出文件未生成")
        return None

    ocr_size = temp_ocr.stat().st_size
    print(f"   ✅ OCR 完成: {temp_ocr.name} ({ocr_size/1024:.0f}KB)\n")

    # ────────────────────────────
    # Step 2: 章节重组 → 最终输出
    # ────────────────────────────
    if reorganize:
        print(f"🔍 Step 2/2: 按章节重组...")

        # 确定输出路径
        if not output_path:
            if seq:
                safe_name = re.sub(r'[\\/:*?"<>|]', '_', pdf_name)
                if books_dir:
                    output_dir = Path(books_dir)
                else:
                    output_dir = PROJECT_ROOT / "books" / safe_name
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = str(output_dir / f"{safe_name}-{seq}.md")
            else:
                output_path = str(OUTPUT_DIR / f"{pdf_name}.md")

        result = subprocess.run([
            sys.executable, str(SCRIPT_DIR / "reorganize_by_chapter.py"),
            str(temp_ocr),
            "-o", str(output_path),
        ], cwd=str(PROJECT_ROOT))

        if result.returncode != 0:
            print(f"⚠️  Step 2 章节重组未完成，临时文件保留: {temp_ocr}")
            return str(temp_ocr)

        # 清理临时文件
        temp_ocr.unlink(missing_ok=True)

        if Path(output_path).exists():
            final_size = Path(output_path).stat().st_size
            chapter_count = len(re.findall(r'^##\s', open(output_path, encoding='utf-8').read()))
            cn_chars = len(re.findall(r'[一-鿿]', open(output_path, encoding='utf-8').read()))
            print(f"\n{'='*60}")
            print(f"🎉 管线全部完成！")
            print(f"   文件: {output_path}")
            print(f"   大小: {final_size/1024:.0f}KB")
            print(f"   章节: {chapter_count} 章")
            print(f"   中文字符: {cn_chars:,}")
            print(f"{'='*60}\n")
            return str(output_path)
        else:
            print(f"❌ 输出文件未生成")
            return None
    else:
        # 不重组，直接把 OCR 结果移到输出
        if not output_path:
            output_path = str(OUTPUT_DIR / f"{pdf_name}.md")
        temp_ocr.rename(output_path)
        print(f"\n✅ OCR 完成（未重组）: {output_path}")
        return str(output_path)


def list_commands():
    """输出快速参考"""
    print("""
📚 PDF → 资料库 管线 — 常用命令

### 整本书 → 资料库
  python pdf_to_library.py ~/Downloads/书.pdf

### 分册处理（推荐）
  python pdf_to_library.py ~/Downloads/书.pdf --pages 1-80 --seq 01
  python pdf_to_library.py ~/Downloads/书.pdf --pages 81-160 --seq 02
  python pdf_to_library.py ~/Downloads/书.pdf --pages 161-240 --seq 03

### 指定输出目录（存入现有分类）
  python pdf_to_library.py ~/Downloads/书.pdf \\
    --pages 1-80 --seq 01 \\
    --books-dir "books/伊斯兰在中国"

### 仅 OCR（不做章节重组）
  python pdf_to_library.py ~/Downloads/书.pdf --no-reorganize

### 切换引擎
  python pdf_to_library.py ~/Downloads/书.pdf --engine easyocr   # 深度学习（慢但准）
  python pdf_to_library.py ~/Downloads/书.pdf --engine tesseract  # 轻量（快）
""")


def main():
    parser = argparse.ArgumentParser(
        description="📚 PDF → 资料库 Markdown 一体化管线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
一步到位：
  python pdf_to_library.py ~/Downloads/书.pdf --pages 1-80 --seq 01

分册处理：
  python pdf_to_library.py ~/Downloads/书.pdf --pages 81-160 --seq 02
        """,
    )
    parser.add_argument("pdf", nargs="?", help="PDF 文件路径")
    parser.add_argument("--pages", help="页码范围，如 1-80 或 5")
    parser.add_argument("--seq", help="分册序号，如 01、02，输出为 书名-01.md")
    parser.add_argument("-o", "--output", help="输出文件路径（优先级高于 --seq）")
    parser.add_argument("--engine", choices=["hybrid", "tesseract", "easyocr"],
                        default="hybrid", help="OCR 引擎（默认 hybrid 最佳）")
    parser.add_argument("--dpi", type=int, default=200, help="DPI（默认 200）")
    parser.add_argument("--psm", type=int, default=6, help="Tesseract PSM 模式")
    parser.add_argument("--books-dir", help="资料库存放目录，如 'books/伊斯兰在中国'")
    parser.add_argument("--no-reorganize", action="store_true", help="跳过章节重组，仅 OCR")
    parser.add_argument("--commands", action="store_true", help="显示常用命令参考")

    args = parser.parse_args()

    if args.commands:
        list_commands()
        return

    if not args.pdf:
        print("❌ 请指定 PDF 文件路径")
        print("   用法: python pdf_to_library.py /path/to/书.pdf --pages 1-80 --seq 01")
        print("   参考: python pdf_to_library.py --commands")
        sys.exit(1)

    if not os.path.exists(args.pdf):
        print(f"❌ 文件不存在: {args.pdf}")
        sys.exit(1)

    run_pipeline(
        pdf_path=args.pdf,
        pages=args.pages,
        seq=args.seq,
        engine=args.engine,
        dpi=args.dpi,
        psm=args.psm,
        output_path=args.output,
        reorganize=not args.no_reorganize,
        books_dir=args.books_dir,
    )


if __name__ == "__main__":
    main()
