#!/usr/bin/env python3
"""
📤 批量提取已有文字的 PDF → Markdown
适用于无需 OCR 的文本型 PDF，直接抽取+清噪+纠错
用法: .venv/bin/python projects/pdf2md/batch_extract_text.py
"""
import re, os, json, sys
from pathlib import Path

SRC = Path("/Users/admin/Documents/iSlam/伊起阅读")
OUT = Path("/Users/admin/Documents/My Projects/books/伊斯兰在中国")
FIXES_PATH = Path("/Users/admin/Documents/My Projects/projects/pdf2md/learned_fixes.json")

# 加载纠错表
learned_fixes = {}
if FIXES_PATH.exists():
    with open(FIXES_PATH, encoding='utf-8') as f:
        learned_fixes = json.load(f)

# 通用纠错
COMMON_FIXES = {
    "中圉": "中国", "申国": "中国", "申圉": "中国", "中圍": "中国", "中囤": "中国",
    "中毕": "中华", "中崋": "中华",
    "程斯林": "穆斯林", "舟斯林": "穆斯林", "各斯林": "穆斯林",
    "伊斯蒯": "伊斯兰", "伊斯籣": "伊斯兰", "伊斯藕": "伊斯兰", "伊斯蘭": "伊斯兰",
    "回纺": "回教", "回救": "回教",
    "牟": "年", "印剛": "印刷",
    "仄": "人", "牠": "它", "箇": "个",
    "雎以": "难以", "重犬": "重大", "阢": "的", "不尤": "不无",
    "姪紫嫣红": "姹紫嫣红",
}

def extract_pdf_text(pdf_path):
    """用 PyMuPDF 提取文字"""
    import fitz
    doc = fitz.open(pdf_path)
    pages_text = []
    for i, page in enumerate(doc, 1):
        text = page.get_text()
        pages_text.append((i, text))
    doc.close()
    return pages_text

def clean_text(text, filename=""):
    """清噪+纠错"""
    # 1. 去 frontmatter (markdown 风格的 ---...---)
    text = re.sub(r'^---\s*\n.*?\n---\s*\n', '', text, flags=re.DOTALL)

    # 2. 去页码行: 第 X 页 / Page X / 纯数字行
    text = re.sub(r'^##\s*第\s*\d+\s*页\s*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^第\s*\d+\s*页\s*$', '', text, flags=re.MULTILINE)

    # 3. 去分割线
    text = re.sub(r'\n-{3,}\n', '\n\n', text)

    # 4. 应用纠错表
    all_fixes = {**COMMON_FIXES}
    if learned_fixes:
        for k, v in learned_fixes.items():
            if isinstance(v, str):
                all_fixes[k] = v

    for wrong, right in all_fixes.items():
        if wrong and wrong in text:
            text = text.replace(wrong, right)

    # 5. 中文字符间去空格
    text = re.sub(r'([一-鿿])\s+([一-鿿])', r'\1\2', text)
    text = re.sub(r'([一-鿿])\s+([一-鿿])', r'\1\2', text)  # 两遍

    # 6. 标点前空格去除
    text = re.sub(r'\s+([，。！？、；：」」】）])', r'\1', text)
    text = re.sub(r'([「「【（])\s+', r'\1', text)

    # 7. 重复标点归并
    text = re.sub(r'[，,]{2,}', '，', text)
    text = re.sub(r'[。.]{3,}', '。', text)

    # 8. 去过多空行
    text = re.sub(r'\n{4,}', '\n\n\n', text)

    # 9. 过滤噪声行 (全英文/符号短行)
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        s = line.strip()
        if not s:
            cleaned.append('')
            continue
        cn = len(re.findall(r'[一-鿿]', s))
        total = len(s.replace(' ', ''))
        if total == 0:
            continue
        if cn == 0 and len(s) < 6:
            continue
        if cn == 0 and re.match(r'^[A-Z\s\.\,\;\:\/\\\"\'\(\)\[\]]{6,}$', s):
            continue
        if cn > 0 and cn / max(total, 1) < 0.08 and total > 20:
            continue
        cleaned.append(s)

    return '\n'.join(cleaned)

def save_md(filename, text, pdf_name="", author="", year=""):
    """保存为带 frontmatter 的 Markdown"""
    title = filename.replace('.md', '').replace('_', '')
    front = f"""---
title: {title}
source: {pdf_name}
{('author: ' + author) if author else ''}
{('year: ' + str(year)) if year else ''}
---

# {title}

"""
    path = OUT / filename
    with open(path, 'w', encoding='utf-8') as f:
        f.write(front + text)
    cn = len(re.findall(r'[一-鿿]', text))
    kb = os.path.getsize(path) / 1024
    return f"  ✅ {filename}  ({kb:.0f}KB, {cn:,}中文字符)"

def process_text_pdf(pdf_name, md_name, author="", year=""):
    """处理一个文字型 PDF"""
    pdf_path = SRC / pdf_name
    if not pdf_path.exists():
        return f"  ❌ 文件不存在: {pdf_name}"

    import fitz
    doc = fitz.open(pdf_path)
    total_pages = doc.page_count

    # 先看总体文字量
    all_text = ""
    for page in doc:
        all_text += page.get_text()
    doc.close()

    if len(all_text.strip()) < 50:
        return f"  ⚠️ {pdf_name}: 几乎无文字 ({len(all_text)}字符)，可能需要 OCR"

    cleaned = clean_text(all_text, pdf_name)
    result = save_md(md_name, cleaned, pdf_name, author, year)
    return f"  {result}  ({total_pages}页)"

# ================================================================
# 任务列表: (PDF文件名, 输出的md文件名)
# ================================================================
TASKS = [
    # --- 短文 (2-15页) ---
    ("中国穆斯林第一次大劫难.pdf",            "中国穆斯林第一次大劫难.md"),
    ("中国伊斯兰教的一代宗师——纪念马启西先生逝世90周年.pdf",
                                               "中国伊斯兰教的一代宗师——纪念马启西先生逝世90周年.md"),
    ("西北乡村回族社区功能演变与伊斯兰教.pdf","西北乡村回族社区功能演变与伊斯兰教.md"),
    ("元初伊斯兰教在中国北方和西北的传.pdf",  "元初伊斯兰教在中国北方和西北的传.md"),
    ("伟大的回回民族.pdf",                     "伟大的回回民族.md"),
    ("略述两宋时期伊斯兰教在西北的传播与发展.pdf",
                                               "略述两宋时期伊斯兰教在西北的传播与发展.md"),
    ("伊斯兰教与西部大开发.pdf",               "伊斯兰教与西部大开发.md"),
    ("论伊斯兰教在中国的传播与发展及特征.pdf","论伊斯兰教在中国的传播与发展及特征.md"),
    ("明代穆斯林的法律地位——兼论法律因素对明代伊斯兰教传播与发展的影响.pdf",
                                               "明代穆斯林的法律地位.md"),
    ("伊斯兰教的中国化与”以儒诠经“.pdf",     "伊斯兰教的中国化与以儒诠经.md"),
    ("从文化认同到国家认同——论中华传统文化在回族形成与发展中的重要作用.pdf",
                                               "从文化认同到国家认同.md"),
    ("伊斯兰教与古代新疆文化.pdf",             "伊斯兰教与古代新疆文化.md"),
    ("从回族的文化认同看伊斯兰教与中国社会相适应问题.pdf",
                                               "从回族的文化认同看伊斯兰教与中国社会相适应问题.md"),
    ("中国近代史四大阿訇简介.pdf",             "中国近代史四大阿訇简介.md"),
    ("伊斯兰教之功修及其意义、要素和条件.pdf","伊斯兰教之功修及其意义、要素和条件.md"),

    # --- 短文补充 ---
    ("回族穆斯林的“死亡关怀”及其积极意义.pdf","回族穆斯林的死亡关怀及其积极意义.md"),

    # --- 文字型书籍 ---
    ("白寿彝《中国回教小史》.pdf",             "白寿彝中国回教小史.md"),
    ("中国回教史.pdf",                         "中国回教史.md"),
    ("中国回教史鉴.pdf",                       "中国回教史鉴.md"),
    ("伊斯兰在中国.pdf",                       "伊斯兰在中国.md"),
    ("中国经堂教育与陕学阿訇{全}.pdf",        "中国经堂教育与陕学阿訇.md"),
    ("伊斯兰教史-王怀德 & 郭宝华.txt",        "伊斯兰教史-王怀德郭宝华.md"),  # 已经是txt
]

def main():
    print(f"\n{'='*60}")
    print(f"📤 批量提取文字型 PDF → Markdown")
    print(f"{'='*60}\n")

    results = []
    for pdf_name, md_name in TASKS:
        # .txt 文件特殊处理
        if pdf_name.endswith('.txt'):
            src = SRC / pdf_name
            if src.exists():
                with open(src, encoding='utf-8') as f:
                    text = f.read()
                cleaned = clean_text(text)
                r = save_md(md_name, cleaned, pdf_name)
                results.append(f"  ✅ {r}")
                print(f"  ✅ {md_name}  (已提取 .txt)")
            else:
                results.append(f"  ❌ {pdf_name} 不存在")
                print(f"  ❌ {pdf_name} 不存在")
            continue

        r = process_text_pdf(pdf_name, md_name)
        print(r)
        results.append(r)

    print(f"\n{'='*60}")
    done = sum(1 for r in results if '✅' in r)
    fail = sum(1 for r in results if '❌' in r or '⚠️' in r)
    print(f"📊 总计: {done} 成功, {fail} 需关注")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
