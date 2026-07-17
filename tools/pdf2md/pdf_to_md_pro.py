#!/usr/bin/env python3
"""
📖 PDF → Markdown OCR Pro 增强版
===================================
功能：扫描版 PDF → Markdown
增强特性：
  1. 图像预处理：自适应二值化 + 去偏斜 + 去噪 + 锐化
  2. Tesseract PSM 6（适合密集文字排版）
  3. 双引擎合并（Tesseract + EasyOCR）取最优结果
  4. AI 后处理纠错

用法：
  python pdf_to_md_pro.py input/书.pdf
  python pdf_to_md_pro.py input/书.pdf --engine hybrid  # 双引擎合并(推荐)
  python pdf_to_md_pro.py input/书.pdf --engine tesseract --psm 6
"""

import os
import sys
import re
import time
import json
from pathlib import Path
from difflib import SequenceMatcher

# ============================================================
# 项目路径
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
EASYOCR_MODEL_DIR = DATA_DIR / "easyocr" / "models"
os.environ["EASYOCR_MODULE_PATH"] = str(EASYOCR_MODEL_DIR)

INPUT_DIR = Path(__file__).parent / "input"
OUTPUT_DIR = Path(__file__).parent / "output"

import fitz  # PyMuPDF
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
import numpy as np
import pytesseract

# ============================================================
# 1. 图像预处理
# ============================================================

def deskew(image: Image.Image) -> Image.Image:
    """纠正扫描歪斜（deskew）"""
    try:
        img_np = np.array(image.convert("L"))
        # 二值化
        _, binary = cv2_threshold(img_np, 0, 255)
        # 找所有非零点
        coords = np.column_stack(np.where(binary > 0))
        if len(coords) < 10:
            return image
        angle = cv2_minAreaRect(coords)
        if abs(angle) < 0.5:
            return image  # 角度太小，跳过
        # 旋转校正
        h, w = img_np.shape
        center = (w // 2, h // 2)
        M = cv2_getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2_warpAffine(img_np, M, (w, h))
        return Image.fromarray(rotated)
    except Exception:
        return image


def cv2_threshold(img, thresh=0, maxval=255):
    """模拟 cv2.threshold 的 OTSU 二值化"""
    from scipy import ndimage
    # 简单的 OTSU
    hist, bins = np.histogram(img, bins=256, range=(0, 256))
    total = len(img.ravel())
    sum_total = sum(i * hist[i] for i in range(256))
    sum_b = 0
    w_b = 0
    w_f = 0
    var_max = 0
    best_thresh = 0
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        mean_b = sum_b / w_b
        mean_f = (sum_total - sum_b) / w_f
        var_between = w_b * w_f * (mean_b - mean_f) ** 2
        if var_between > var_max:
            var_max = var_between
            best_thresh = t
    binary = (img > best_thresh).astype(np.uint8) * 255
    return img, binary


def cv2_minAreaRect(coords):
    """计算文本倾斜角度"""
    if len(coords) < 100:
        return 0.0
    # 采样
    idx = np.random.choice(len(coords), min(1000, len(coords)), replace=False)
    sample = coords[idx]
    y = sample[:, 0]
    x = sample[:, 1]
    if len(x) < 2:
        return 0.0
    A = np.vstack([x, np.ones(len(x))]).T
    m, _ = np.linalg.lstsq(A, y, rcond=None)[0]
    angle = np.degrees(np.arctan(m))
    # 限制最大角度
    return max(-15, min(15, angle))


def cv2_getRotationMatrix2D(center, angle, scale):
    """简化旋转矩阵"""
    angle_rad = np.radians(angle)
    cos_a = np.cos(angle_rad) * scale
    sin_a = np.sin(angle_rad) * scale
    cx, cy = center
    # 2x3 仿射矩阵
    return np.array([
        [cos_a, sin_a, (1 - cos_a) * cx - sin_a * cy],
        [-sin_a, cos_a, sin_a * cx + (1 - cos_a) * cy]
    ], dtype=np.float32)


def cv2_warpAffine(img, M, dsize):
    """简化仿射变换"""
    h, w = img.shape
    dst = np.zeros_like(img)
    # 反向映射
    inv_M = np.linalg.pinv(np.vstack([M, [0, 0, 1]]))[:2]
    for y_out in range(h):
        for x_out in range(w):
            # 反向变换
            x_in = int(inv_M[0, 0] * x_out + inv_M[0, 1] * y_out + inv_M[0, 2])
            y_in = int(inv_M[1, 0] * x_out + inv_M[1, 1] * y_out + inv_M[1, 2])
            if 0 <= x_in < w and 0 <= y_in < h:
                dst[y_out, x_out] = img[y_in, x_in]
    return dst


def preprocess_image(image: Image.Image, dpi: int = 300) -> Image.Image:
    """
    完整的图像预处理管线：
    1. 转为灰度
    2. 去偏斜
    3. 自适应二值化（处理泛黄纸张）
    4. 去噪（去除斑点）
    5. 锐化
    6. 扩大对比度
    """
    # 1. 灰度
    if image.mode != "L":
        img = image.convert("L")
    else:
        img = image

    # 2. 去偏斜
    try:
        img = deskew(img)
    except Exception:
        pass

    img_np = np.array(img, dtype=np.uint8)

    # 3. 自适应二值化（解决泛黄/明暗不均）
    # 使用局部均值阈值
    kernel_size = max(15, dpi // 20)  # 随 DPI 调整
    if kernel_size % 2 == 0:
        kernel_size += 1
    # 均值模糊作为局部阈值
    from scipy.ndimage import uniform_filter
    local_mean = uniform_filter(img_np.astype(float), size=kernel_size)
    # 偏移量
    offset = 10
    binary = (img_np > local_mean - offset).astype(np.uint8) * 255

    # 4. 去噪 - 中值滤波
    from scipy.ndimage import median_filter
    denoised = median_filter(binary, size=3)

    # 5. 锐化
    result = Image.fromarray(denoised)
    result = result.filter(ImageFilter.SHARPEN)
    result = result.filter(ImageFilter.SHARPEN)

    # 6. 扩大对比度（安全起见）
    enhancer = ImageEnhance.Contrast(result)
    result = enhancer.enhance(1.5)

    return result


# ============================================================
# 2. Tesseract OCR（PSM 6 + 多语言）
# ============================================================

def ocr_tesseract(image: Image.Image, lang: str = "chi_sim+chi_tra+eng",
                  psm: int = 6) -> str:
    """
    使用 Tesseract 识别
    --psm 6: 统一的文本块（适合书籍正文）
    --psm 4: 单列可变大小文本
    """
    custom_config = f"--psm {psm} --oem 3"
    text = pytesseract.image_to_string(image, lang=lang, config=custom_config)
    return text.strip()


# ============================================================
# 3. EasyOCR（深度学习引擎）
# ============================================================

_easyocr_readers = {"ch_sim": None, "ch_tra": None}

def get_easyocr_reader(script="ch_sim"):
    global _easyocr_readers
    if _easyocr_readers[script] is None:
        import easyocr
        lang_list = ["ch_sim", "en"] if script == "ch_sim" else ["ch_tra", "en"]
        lang_name = "简体" if script == "ch_sim" else "繁体"
        print(f"   ⏳ 加载 EasyOCR {lang_name}...")
        start = time.time()
        _easyocr_readers[script] = easyocr.Reader(
            lang_list, gpu=True,
            model_storage_directory=str(EASYOCR_MODEL_DIR),
            download_enabled=True
        )
        print(f"   ✅ EasyOCR {lang_name} 加载完毕（{time.time()-start:.1f} 秒）")
    return _easyocr_readers[script]


def ocr_easyocr(image: Image.Image) -> str:
    """EasyOCR 识别（简繁合并去重）"""
    import numpy as np
    # 保留原始彩色图给 EasyOCR（它对彩色适应性更好）
    if image.mode != "RGB":
        img_rgb = image.convert("RGB")
    else:
        img_rgb = image

    reader_sim = get_easyocr_reader("ch_sim")
    reader_tra = get_easyocr_reader("ch_tra")
    img_array = np.array(img_rgb)

    result_sim = reader_sim.readtext(img_array, detail=0, paragraph=True)
    result_tra = reader_tra.readtext(img_array, detail=0, paragraph=True)

    seen = set()
    merged = []
    for line in list(result_sim) + list(result_tra):
        stripped = line.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            merged.append(stripped)

    return "\n".join(merged) if merged else ""


# ============================================================
# 4. 双引擎合并（取优）
# ============================================================

def ocr_hybrid(image: Image.Image, lang: str = "chi_sim+chi_tra+eng",
               psm: int = 6) -> str:
    """
    双引擎合并策略：
    1. 先用 Tesseract（快）识别
    2. 用 EasyOCR（准）识别
    3. 对每个段落，取字符数多的那个（通常说明识别更完整）
    """
    # 预处理图给 Tesseract
    processed = preprocess_image(image)

    # Tesseract
    text_t = ocr_tesseract(processed, lang=lang, psm=psm)

    # EasyOCR（用原始彩图）
    text_e = ocr_easyocr(image)

    # 如果某个引擎完全没出结果，用另一个
    if not text_t and text_e:
        return text_e
    if not text_e and text_t:
        return text_t
    if not text_t and not text_e:
        return ""

    # 合并：逐行取优
    lines_t = text_t.split("\n")
    lines_e = text_e.split("\n")

    merged = []
    max_len = max(len(lines_t), len(lines_e))
    for i in range(max_len):
        line_t = lines_t[i].strip() if i < len(lines_t) else ""
        line_e = lines_e[i].strip() if i < len(lines_e) else ""

        if not line_t and not line_e:
            continue
        if not line_t:
            merged.append(line_e)
            continue
        if not line_e:
            merged.append(line_t)
            continue

        # 选择包含更多中文字符的行
        cn_t = len(re.findall(r'[一-鿿㐀-䶿]', line_t))
        cn_e = len(re.findall(r'[一-鿿㐀-䶿]', line_e))

        if cn_t >= cn_e:
            merged.append(line_t)
        else:
            merged.append(line_e)

    return "\n".join(merged)


# ============================================================
# 5. AI 后处理纠错
# ============================================================

# 常见 OCR 错字修正表
OCR_FIXES = {
    # 这本书特有的高频错字
    "中圉": "中国",
    "申国": "中国",
    "申圉": "中国",
    "1S兰": "伊斯",
    "伊斯蒯": "伊斯兰",
    "伊斯籣": "伊斯兰",
    "伊斯藕": "伊斯兰",
    "伊斯蘭": "伊斯兰",
    "回教": "回教",
    "回救": "回教",
    "著": "著",
    "蓄": "著",
    "蕃": "著",
    "臼": "白",
    "臭": "白",
    "鼻": "寿",
    "寿鼻": "寿彝",
    "寿彝": "寿彝",
    "葬岩": "寿彝",
    "葬著": "寿彝",
    "白寿鼻": "白寿彝",
    "白葬岩": "白寿彝",
    "白寿彝": "白寿彝",
    "宁夏": "宁夏",
    "宁夏": "宁夏",
    "银川": "银川",
    "银J/II": "银川",
    "解放西街": "解放西街",
    "新葺": "新华",
    "新葺书店": "新华书店",
    "印刷": "印刷",
    "印剛": "印刷",
    "版": "版",
    "策王版": "第一版",
    "第策版": "第一版",
    "策次印刷": "第一次印刷",
    "l吹": "次",
    "井牛": "开本",
    "笮": "等",
    "第": "第",
    "簋": "篇",
    "聿": "书",
    "韦": "书",
    "字": "字",
    "芊": "千",
    "'": "。",
    "。'": "。",
    ">": ">",
    "、": "、",
    '"': "\"",
    '\'': "'",
    '":': "\":",
    '":': "\":",
}

# 正则纠错模式
OCR_PATTERNS = [
    # 修正多余的标点
    (r'\.{4,}', '……'),
    (r',{2,}', '，'),
    (r'。{2,}', '。'),
    # 英文标点转中文
    (r'(一-鿿)', r'\1。'),
    # 修正被拆分的词语
    (r'(\S) +(\S)', r'\1\2'),  # 去掉字间多余空格（慎用）
]


def repair_ocr_text(text: str, book_context: str = "") -> str:
    """
    AI 后处理修复 OCR 错字
    规则：
    1. 查表替换高频错误
    2. 正则修复模式
    3. 去除孤立的英文字母行（扫描边缘噪声）
    """
    lines = text.split("\n")
    cleaned = []

    for line in lines:
        original = line
        fixed = line

        # 1. 表格替换
        for wrong, correct in OCR_FIXES.items():
            if wrong in fixed:
                fixed = fixed.replace(wrong, correct)

        # 2. 过滤噪声行
        stripped = fixed.strip()

        # 去掉全行只有噪音的行（少于2个中文字符且没有意义）
        cn_chars = len(re.findall(r'[一-鿿㐀-䶿]', stripped))
        total_chars = len(stripped.replace(" ", "").replace(".", "").replace(",", ""))

        # 如果是全英文/符号的无意义行，跳过
        if total_chars > 0 and cn_chars == 0:
            # 检查是否有大写单词（可能是正文中的英文）
            if re.search(r'[A-Za-z]{3,}', stripped) and len(stripped) > 5:
                cleaned.append(stripped)  # 保留英文行
            elif len(stripped) < 3:
                continue  # 跳过无意义短行
            else:
                continue  # 跳过噪声行

        # 如果纯中文行少于2个中文字，且行短，可能是边缘噪声
        if cn_chars > 0 and cn_chars < 2 and len(stripped) < 8:
            continue

        # 3. 合并异常换行
        # 如果行末尾没有句号/问号/感叹号，且下一行首是中文字，说明是截断
        if cleaned and not re.search(r'[。！？）」”]', stripped[-1]) if stripped else True:
            prev_line = cleaned[-1]
            if prev_line and stripped and re.match(r'[一-鿿]', stripped[0]):
                cleaned[-1] = prev_line + stripped
                continue

        cleaned.append(stripped)

    return "\n".join(cleaned)


def clean_markdown_output(md_text: str) -> str:
    """修复 Markdown 格式"""
    # 修复页眉
    md_text = re.sub(r'#{2,}\s*第\s*(\d+)\s*页\s*#{0,}', r'## 第 \1 页', md_text)

    # 去除过多的空行（保留合理空行）
    md_text = re.sub(r'\n{4,}', '\n\n\n', md_text)

    # 修复标题周围的噪声
    md_text = re.sub(r'([^\n])\n(#{2,})', r'\1\n\n\2', md_text)

    return md_text


# ============================================================
# 主处理函数
# ============================================================

def pdf_to_markdown_pro(
    pdf_path: str,
    engine: str = "hybrid",
    lang: str = "chi_sim+chi_tra+eng",
    page_range: tuple = None,
    dpi: int = 300,
    psm: int = 6,
    output_path: str = None,
    repair: bool = True,
) -> str:
    """增强版 PDF → Markdown"""
    pdf_name = Path(pdf_path).stem
    print(f"\n{'='*60}")
    print(f"📖 正在处理: {pdf_name}.pdf")
    print(f"{'='*60}")

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"📄 总页数: {total_pages}")

    if page_range:
        start, end = page_range
        if start < 1: start = 1
        if end > total_pages: end = total_pages
    else:
        start, end = 1, total_pages

    pages_to_process = end - start + 1
    engine_name = {"hybrid": "双引擎合并(推荐)", "tesseract": "Tesseract", "easyocr": "EasyOCR"}
    print(f"🔍 第 {start}–{end} 页（共 {pages_to_process} 页）")
    print(f"⚙️  引擎: {engine_name.get(engine, engine)} | DPI: {dpi} | PSM: {psm}")

    # 预加载 EasyOCR（如果用）
    if engine in ("hybrid", "easyocr"):
        print("⏳ 准备 EasyOCR 引擎...")
        get_easyocr_reader("ch_sim")
        get_easyocr_reader("ch_tra")

    all_text = []
    start_time = time.time()

    for page_num in range(start - 1, end):
        page = doc[page_num]
        page_no = page_num + 1

        # 渲染
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # OCR
        try:
            if engine == "tesseract":
                processed = preprocess_image(img, dpi)
                text = ocr_tesseract(processed, lang=lang, psm=psm)
            elif engine == "easyocr":
                text = ocr_easyocr(img)
            else:  # hybrid
                text = ocr_hybrid(img, lang=lang, psm=psm)

            # 后处理纠错
            if repair and text:
                text = repair_ocr_text(text)

            all_text.append(f"## 第 {page_no} 页\n\n{text}\n")

            elapsed = time.time() - start_time
            avg = elapsed / (page_no - start + 1)
            remaining = avg * (end - page_no)
            print(f"   ✅ 第 {page_no}/{end} 页 | "
                  f"用时 {elapsed:.0f}s | 预估剩余 {remaining:.0f}s")

        except Exception as e:
            print(f"   ❌ 第 {page_no} 页 失败: {e}")
            all_text.append(f"## 第 {page_no} 页\n\n> [OCR 失败: {e}]\n")

    doc.close()

    # 合成 Markdown
    body = "\n".join(all_text)
    body = clean_markdown_output(body)

    markdown_content = f"""---
title: {pdf_name}
source: {Path(pdf_path).name}
date: {time.strftime("%Y-%m-%d")}
pages: {pages_to_process}
engine: {engine}
processed: full (thresholding+deskew+denoise+psm6+repair)
---

# {pdf_name}

> 由扫描版 PDF 自动 OCR 识别生成
> 引擎: {engine_name.get(engine, engine)} | DPI: {dpi} | PSM: {psm}
> 共 {pages_to_process} 页

---

{body}
"""

    # 写入
    if output_path is None:
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', pdf_name)
        output_path = str(OUTPUT_DIR / f"{safe_name}.md")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    total_chars = len(markdown_content)
    total_time = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"🎉 全部完成！")
    print(f"   文件: {output_path}")
    print(f"   字符数: {total_chars:,}")
    print(f"   耗时: {total_time:.0f} 秒 ({total_time/pages_to_process:.1f} 秒/页)")
    print(f"{'='*60}\n")

    return output_path


# ============================================================
# 命令行入口
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="📖 PDF → Markdown OCR 增强版")
    parser.add_argument("pdf", nargs="?", help="PDF 文件路径")
    parser.add_argument("-o", "--output", help="输出路径")
    parser.add_argument("--engine", choices=["hybrid", "tesseract", "easyocr"],
                        default="hybrid", help="OCR 引擎（默认 hybrid 双引擎合并）")
    parser.add_argument("--lang", default="chi_sim+chi_tra+eng",
                        help="Tesseract 语言代码")
    parser.add_argument("--page", help="页码范围 (e.g. 1-80, 5)")
    parser.add_argument("--dpi", type=int, default=300, help="DPI (默认 300)")
    parser.add_argument("--psm", type=int, default=6, help="PSM 模式 (默认 6)")
    parser.add_argument("--no-repair", action="store_true", help="关闭文字纠错")
    parser.add_argument("--check", action="store_true", help="环境检查")

    args = parser.parse_args()

    if args.check:
        check_env()
        return

    pdf_path = args.pdf
    if not pdf_path:
        pdf_files = sorted(Path(INPUT_DIR).glob("*.pdf"))
        if not pdf_files:
            print(f"❌ 未指定 PDF，且 {INPUT_DIR}/ 中无 PDF 文件")
            sys.exit(1)
        pdf_path = str(pdf_files[0])
        print(f"📄 自动检测: {pdf_path}")

    if not os.path.exists(pdf_path):
        print(f"❌ 文件不存在: {pdf_path}")
        sys.exit(1)

    page_range = None
    if args.page:
        if "-" in args.page:
            parts = args.page.split("-")
            page_range = (int(parts[0]), int(parts[1]))
        else:
            p = int(args.page)
            page_range = (p, p)

    pdf_to_markdown_pro(
        pdf_path=pdf_path,
        engine=args.engine,
        lang=args.lang,
        page_range=page_range,
        dpi=args.dpi,
        psm=args.psm,
        output_path=args.output,
        repair=not args.no_repair,
    )


def check_env():
    """环境检查"""
    print("=" * 60)
    print("🔍 增强版 OCR 环境检查")
    print("=" * 60)
    for mod, name in [("easyocr", "easyocr"), ("fitz", "PyMuPDF"),
                       ("PIL", "Pillow"), ("pytesseract", "pytesseract"),
                       ("numpy", "NumPy"), ("scipy", "SciPy")]:
        try:
            m = __import__(mod)
            ver = getattr(m, "__version__", "ok")
            print(f"   ✅ {name}: {ver}")
        except ImportError:
            print(f"   ❌ {name}: 未安装")

    import subprocess
    r = subprocess.run(["tesseract", "--version"], capture_output=True, text=True, timeout=5)
    print(f"   ✅ Tesseract: {r.stdout.split(chr(10))[0]}")

    langs = ["chi_sim", "chi_tra", "chi_sim_vert", "chi_tra_vert", "ara"]
    available = pytesseract.get_languages()
    for l in langs:
        print(f"   {'✅' if l in available else '❌'} 语言包: {l}")

    print("=" * 60)


if __name__ == "__main__":
    main()
