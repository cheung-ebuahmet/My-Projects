import easyocr
import os
import time
from pathlib import Path

# ============================================================
# 配置区
# ============================================================
INPUT_DIR = "input_images"
OUTPUT_DIR = "output_results"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}

# ============================================================
# 初始化文件夹
# ============================================================
def init_folders():
    """创建 input_images 和 output_results 文件夹（如不存在）"""
    for folder in [INPUT_DIR, OUTPUT_DIR]:
        Path(folder).mkdir(parents=True, exist_ok=True)
        print(f"📁 文件夹就绪: {folder}/")

# ============================================================
# 扫描图片
# ============================================================
def scan_images():
    """扫描 input_images 下所有支持的图片文件"""
    images = []
    for f in os.listdir(INPUT_DIR):
        ext = Path(f).suffix.lower()
        if ext in SUPPORTED_EXTENSIONS:
            images.append(f)
    return sorted(images)

# ============================================================
# 单张图片识别 + 导出（三引擎合并）
# ============================================================
def process_image(reader_sim, reader_tra, reader_ar, filename):
    """
    使用三个 Reader 分别识别同一张图片（EasyOCR 限制：ch_tra 只能与 en 组合）：
      - reader_sim: ch_sim + en
      - reader_tra: ch_tra + en
      - reader_ar:  ar + en
    合并结果并去重后写入 output_results 下的同名 .txt 文件
    """
    input_path = os.path.join(INPUT_DIR, filename)
    stem = Path(filename).stem
    output_path = os.path.join(OUTPUT_DIR, f"{stem}.txt")

    # 引擎1：简体中文 + 英文
    result_sim = reader_sim.readtext(input_path, detail=0, paragraph=True)
    # 引擎2：繁体中文 + 英文
    result_tra = reader_tra.readtext(input_path, detail=0, paragraph=True)
    # 引擎3：阿拉伯文 + 英文
    result_ar = reader_ar.readtext(input_path, detail=0, paragraph=True)

    # 合并并去重（保留顺序）
    seen = set()
    merged = []
    for line in result_sim + result_tra + result_ar:
        stripped = line.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            merged.append(stripped)

    # 写入文本文件
    with open(output_path, "w", encoding="utf-8") as f:
        for line in merged:
            f.write(line + "\n")

    return len(merged)

# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 60)
    print("🧠 多语言批量 OCR 智能处理器")
    print("   支持语言: 简体中文 / 繁体中文 / English / العربية")
    print("=" * 60)
    print()

    # 1. 初始化文件夹
    init_folders()

    # 2. 扫描图片
    images = scan_images()
    total = len(images)

    if total == 0:
        print(f"\n⚠️  {INPUT_DIR}/ 文件夹中没有找到图片文件。")
        print(f"   请将 .jpg / .jpeg / .png / .bmp 图片放入 {INPUT_DIR}/ 后重新运行。\n")
        return

    print(f"🔍 共发现 {total} 张待处理图片\n")

    # 3. 初始化三个 Reader（EasyOCR 限制：ch_tra 只能与 en 组合）
    print("⏳ 正在加载 OCR 引擎 1（简体中文 + English）...")
    start_load = time.time()
    reader_sim = easyocr.Reader(["ch_sim", "en"], gpu=True)
    print(f"   ✅ 引擎1 加载完成，耗时: {time.time() - start_load:.2f} 秒")

    print("⏳ 正在加载 OCR 引擎 2（繁体中文 + English）...")
    start_load2 = time.time()
    reader_tra = easyocr.Reader(["ch_tra", "en"], gpu=True)
    print(f"   ✅ 引擎2 加载完成，耗时: {time.time() - start_load2:.2f} 秒")

    print("⏳ 正在加载 OCR 引擎 3（العربية + English）...")
    start_load3 = time.time()
    reader_ar = easyocr.Reader(["ar", "en"], gpu=True)
    print(f"   ✅ 引擎3 加载完成，耗时: {time.time() - start_load3:.2f} 秒\n")

    # 4. 逐张处理
    total_lines = 0
    total_time = 0.0

    for idx, filename in enumerate(images, start=1):
        print(f"📄 正在处理第 {idx}/{total} 张图片: {filename} ...")

        start_proc = time.time()
        lines = process_image(reader_sim, reader_tra, reader_ar, filename)
        elapsed = time.time() - start_proc

        total_lines += lines
        total_time += elapsed

        stem = Path(filename).stem
        print(f"   ✅ 完成 → {OUTPUT_DIR}/{stem}.txt（识别出 {lines} 行文本，耗时: {elapsed:.2f} 秒）\n")

    # 5. 汇总报告
    print("=" * 60)
    print("📊 批量处理报告")
    print(f"   处理图片数: {total} 张")
    print(f"   识别总行数: {total_lines} 行")
    print(f"   总耗时: {total_time:.2f} 秒")
    print(f"   平均每张: {total_time / total:.2f} 秒" if total > 0 else "")
    print(f"   输入目录: {INPUT_DIR}/")
    print(f"   输出目录: {OUTPUT_DIR}/")
    print("=" * 60)
    print("🎉 全部处理完毕！\n")


if __name__ == "__main__":
    main()
