#!/usr/bin/env python3
"""
OCR Test Script - 中英文 PDF OCR 识别工具
功能：读取当前目录下的任意 PDF 文件，自动识别中英文文本，并保存为同名的 .txt 文件
"""

# ============================================================
# 强制改变 EasyOCR 默认的模型下载和存放路径到当前项目文件夹
# 防止系统权限或网络中断导致的问题
# ⚠️ 必须在 import easyocr 之前设置环境变量，否则不生效
# ============================================================
import os
import sys
import argparse

os.environ["EASYOCR_MODULE_PATH"] = os.path.join(os.getcwd(), ".easyocr")

import fitz  # PyMuPDF
import easyocr

# EasyOCR 模型存放目录（用于提示用户手动放置模型文件）
EASYOCR_MODEL_DIR = os.path.join(os.getcwd(), ".easyocr", "model")


def ocr_pdf_with_pymupdf(pdf_path):
    """
    方法一：使用 PyMuPDF 直接提取文本（适用于数字 PDF，速度快）
    """
    doc = fitz.open(pdf_path)
    full_text = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        if text.strip():
            full_text.append(f"--- Page {page_num + 1} ---\n{text}")
    doc.close()
    return "\n\n".join(full_text)


def check_easyocr_models():
    """
    检查 EasyOCR 模型文件是否已存在，如果不存在则给出手动下载提示。
    EasyOCR 1.7.2 需要以下两个模型文件：
      - detection: craft_mlt_25k.pth   (文字检测模型, ~80MB)
      - recognition: zh_sim_g2.pth     (中文简体识别模型, ~21MB)
    """
    required_models = [
        "craft_mlt_25k.pth",
        "zh_sim_g2.pth",
    ]
    missing_models = []
    for model_name in required_models:
        # 递归搜索模型目录
        found = False
        for root, dirs, files in os.walk(EASYOCR_MODEL_DIR):
            if model_name in files:
                found = True
                break
        if not found:
            missing_models.append(model_name)

    if missing_models:
        print("=" * 60)
        print("⚠️  EasyOCR 模型文件未找到，需要手动下载。")
        print("=" * 60)
        print()
        print(f"模型存放目录: {EASYOCR_MODEL_DIR}")
        print()
        print("请从以下渠道下载模型文件，放入上述目录：")
        print()
        print("📥 方案一：Hugging Face 镜像站（国内可访问，推荐）")
        print("   检测模型:")
        print("   https://hf-mirror.com/JaidedAI/EasyOCR/resolve/main/model/craft_mlt_25k.pth")
        print("   中文识别模型:")
        print("   https://hf-mirror.com/JaidedAI/EasyOCR/resolve/main/model/zh_sim_g2.pth")
        print()
        print("📥 方案二：魔搭社区 (ModelScope)")
        print("   访问 https://modelscope.cn 搜索 'EasyOCR' 找到对应模型文件")
        print()
        print("📥 方案三：使用命令行直接下载（如果网络允许）")
        print(f"   mkdir -p {EASYOCR_MODEL_DIR}")
        print(f"   cd {EASYOCR_MODEL_DIR}")
        print("   # 检测模型 (craft_mlt_25k.pth)")
        print("   curl -L -o craft_mlt_25k.pth \\")
        print("     https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/")
        print("     craft_mlt_25k.zip")
        print("   # 中文识别模型 (zh_sim_g2.pth)")
        print("   curl -L -o zh_sim_g2.pth \\")
        print("     https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/")
        print("     zh_sim_g2.zip")
        print()
        print("需要的模型文件:")
        for m in missing_models:
            print(f"  - {m}")
        print()
        return False
    return True


def init_easyocr_reader(lang_list=None):
    """
    初始化 EasyOCR Reader（延迟初始化，避免模块加载时立即下载模型）
    使用 download_enabled=True 允许自动下载（如果网络通畅）

    参数:
        lang_list: 语言列表，默认 ['ch_sim', 'en']（简体中文+英文）
                   注意：ch_sim 只能与 en 组合使用
                   如需阿拉伯语，请单独运行：lang_list=['ar', 'en']
    """
    if lang_list is None:
        lang_list = ['ch_sim', 'en']

    lang_display = " + ".join(lang_list)
    print(f"   ⏳ 正在初始化 EasyOCR（语言: {lang_display}）...")
    print(f"   📁 模型存放路径: {EASYOCR_MODEL_DIR}")
    try:
        # 创建模型目录（如果不存在）
        os.makedirs(EASYOCR_MODEL_DIR, exist_ok=True)
        # 初始化 Reader，允许自动下载
        reader = easyocr.Reader(
            lang_list,
            gpu=False,
            download_enabled=True,  # 允许自动下载模型
        )
        print(f"   ✅ EasyOCR 初始化成功！（语言: {lang_display}）")
        return reader
    except Exception as e:
        error_msg = str(e)
        if "timeout" in error_msg.lower() or "connection" in error_msg.lower() or "download" in error_msg.lower():
            print(f"   ❌ 网络超时，无法自动下载模型。")
            print(f"   错误信息: {error_msg}")
            print()
            check_easyocr_models()
            print("💡 请按上述提示手动下载模型文件后，重新运行本脚本。")
        else:
            print(f"   ❌ EasyOCR 初始化失败: {error_msg}")
        sys.exit(1)


def ocr_pdf_with_easyocr(pdf_path):
    """
    方法二：使用 EasyOCR 进行图片级 OCR（适用于扫描件/图片型 PDF）
    将 PDF 每页转为图片后识别
    """
    # 延迟初始化 EasyOCR Reader（在函数内部初始化，而非模块加载时）
    reader = init_easyocr_reader()

    doc = fitz.open(pdf_path)
    full_text = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        # 将页面渲染为图片（提高分辨率以获得更好识别效果）
        pix = page.get_pixmap(dpi=300)
        img_bytes = pix.tobytes("png")

        # 使用 EasyOCR 识别
        result = reader.readtext(img_bytes, detail=0)
        page_text = "\n".join(result)
        full_text.append(f"--- Page {page_num + 1} ---\n{page_text}")
        print(f"  [OCR] Page {page_num + 1}/{len(doc)} done.")
    doc.close()
    return "\n\n".join(full_text)


def main():
    parser = argparse.ArgumentParser(
        description="中英文 PDF OCR 识别工具 - 自动提取 PDF 文本并保存为 .txt 文件"
    )
    parser.add_argument(
        "pdf_file",
        nargs="?",
        help="要识别的 PDF 文件路径（默认自动查找当前目录下的第一个 PDF）",
    )
    parser.add_argument(
        "--method",
        choices=["auto", "text", "ocr"],
        default="auto",
        help="识别方式: auto=自动选择, text=仅用PyMuPDF提取文本, ocr=强制使用EasyOCR图片识别",
    )
    parser.add_argument(
        "--force-ocr",
        action="store_true",
        help="强制使用 EasyOCR 进行图片级识别（适用于扫描件）",
    )

    args = parser.parse_args()

    # 确定 PDF 文件路径
    pdf_path = args.pdf_file
    if not pdf_path:
        # 自动查找当前目录下第一个 .pdf 文件
        pdf_files = [f for f in os.listdir(".") if f.lower().endswith(".pdf")]
        if not pdf_files:
            print("❌ 错误：当前目录下未找到任何 PDF 文件！")
            print("   请将 PDF 文件放在当前目录，或通过命令行参数指定文件路径。")
            sys.exit(1)
        pdf_path = pdf_files[0]
        print(f"📄 自动检测到 PDF 文件: {pdf_path}")

    if not os.path.exists(pdf_path):
        print(f"❌ 错误：文件不存在 - {pdf_path}")
        sys.exit(1)

    # 生成输出文件名
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    output_path = f"{base_name}.txt"

    print(f"📖 正在处理: {pdf_path}")
    print(f"💾 输出文件: {output_path}")

    # 决定使用哪种方法
    use_ocr = args.force_ocr or args.method == "ocr"

    if args.method == "text":
        # 强制使用文本提取
        print("🔤 使用 PyMuPDF 文本提取模式...")
        text = ocr_pdf_with_pymupdf(pdf_path)
    elif use_ocr:
        # 强制使用 OCR
        print("🔍 使用 EasyOCR 图片识别模式（适用于扫描件）...")
        print("   ⏳ 首次运行会下载模型，请耐心等待...")
        text = ocr_pdf_with_easyocr(pdf_path)
    else:
        # 自动模式：先尝试提取文本，如果文本太少则使用 OCR
        print("🔄 自动模式：先尝试提取文本...")
        text = ocr_pdf_with_pymupdf(pdf_path)
        if len(text.strip()) < 50:
            print("   ⚠️  提取的文本较少，可能是扫描件，切换到 EasyOCR 识别...")
            print("   ⏳ 首次运行会下载模型，请耐心等待...")
            text = ocr_pdf_with_easyocr(pdf_path)
        else:
            print("   ✅ 文本提取成功！")

    # 保存结果
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    # 输出统计信息
    char_count = len(text)
    line_count = len(text.strip().split("\n"))
    print(f"\n✅ 完成！")
    print(f"   共识别 {char_count} 个字符，{line_count} 行")
    print(f"   结果已保存至: {output_path}")


if __name__ == "__main__":
    main()
