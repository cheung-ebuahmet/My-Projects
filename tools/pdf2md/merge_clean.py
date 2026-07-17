#!/usr/bin/env python3
"""
📚 合并《中华穆斯林的现状与展望》4册 → 1本
按真实章节组织，去噪纠错
"""
import re, os
from pathlib import Path

BASE = Path("/Users/admin/Documents/My Projects/books/伊斯兰在中国")
OUT = BASE / "中华穆斯林的现状与展望.md"

FIXES = {
    "中圉": "中国", "申国": "中国", "申圉": "中国", "中圍": "中国", "中囤": "中国",
    "中毕": "中华", "中崋": "中华",
    "程斯林": "穆斯林", "舟斯林": "穆斯林", "各斯林": "穆斯林",
    "伊斯蒯": "伊斯兰", "伊斯籣": "伊斯兰", "伊斯藕": "伊斯兰", "伊斯蘭": "伊斯兰",
    "回纺": "回教", "回救": "回教",
    "牟": "年", "印剛": "印刷",
    "仄": "人", "牠": "它", "箇": "个",
    "雎以": "难以", "重犬": "重大", "阢": "的", "不尤": "不无",
    "姪紫嫣红": "姹紫嫣红",
    "中国伊斯兰史存稿": "", "白寿彝": "", "宁夏人民出版社": "",
}

CHAPTERS = [
    "序", "自序", "第一章 穆斯林的衰落", "第二章 经外传说的泛滥",
    "第三章 功利主义与机会主义", "第四章 民族主义", "第五章 宗派主义",
    "第六章 教条主义与形式主义", "第七章 降示的真相", "第八章 未来的道路",
    "附录",
]

def deep_clean(text):
    text = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.DOTALL)
    text = re.sub(r'^## [^\n]+\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^#[^#][^\n]*\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^> [^\n]*\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'## 第 \d+ 页\n?', '', text)
    text = re.sub(r'\n---+\n', '\n', text)
    for w, c in FIXES.items():
        if w and w in text:
            text = text.replace(w, c)
    text = re.sub(r'([一-鿿])\s+([一-鿿])', r'\1\2', text)
    text = re.sub(r'\s+([，。！？、；：）」」】])', r'\1', text)
    text = re.sub(r'[，,]{2,}', '，', text)
    text = re.sub(r'[。.]{3,}', '。', text)
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        s = line.strip()
        cn = len(re.findall(r'[一-鿿]', s))
        total = len(s.replace(' ', ''))
        if total == 0: continue
        if cn == 0 and len(s) < 6: continue
        if cn == 0 and re.match(r'^[A-Z\s\.\,\;\:\/\\\"\'\(\)\[\]]{6,}$', s): continue
        if cn > 0 and cn / max(total, 1) < 0.08 and total > 20: continue
        cleaned.append(s)
    return '\n'.join(cleaned)

print(f"\n{'='*60}")
print(f"📚 合并精修: 4册 → 1本")
print(f"{'='*60}")

all_text = ""
for i in range(1, 5):
    p = BASE / f"中华穆斯林的现状与展望-{i:02d}.md"
    if p.exists():
        t = open(p, encoding='utf-8').read()
        t = deep_clean(t)
        all_text += t + "\n"
        print(f"   📖 第{i}册: {len(t):,} 字符")

# 分割章节 - 找真正关键词
lines = all_text.split('\n')
sections = {}
current_ch = "序"
current_lines = []

ch_keywords = {
    "序": ["序", "奉至仁至慈", "改革开放"],
    "自序": ["自序"],
    "第一章 穆斯林的衰落": ["第一章", "穆斯林的衰落"],
    "第二章 经外传说的泛滥": ["第二章", "经外传说"],
    "第三章 功利主义与机会主义": ["第三章", "功利主义"],
    "第四章 民族主义": ["第四章", "民族主义"],
    "第五章 宗派主义": ["第五章", "宗派主义"],
    "第六章 教条主义与形式主义": ["第六章", "教条主义"],
    "第七章 降示的真相": ["第七章", "降示的真相"],
    "第八章 未来的道路": ["第八章", "未来的道路"],
    "附录": ["附录", "参考书目", "后记", "读后感"],
}

def detect_chapter(line):
    s = line.strip()
    for ch_name, kws in ch_keywords.items():
        for kw in kws:
            if kw in s:
                return ch_name
    return None

for line in lines:
    detected = detect_chapter(line)
    if detected:
        if current_lines:
            sections.setdefault(current_ch, []).extend(current_lines)
        current_ch = detected
        current_lines = [line]
    else:
        current_lines.append(line)

if current_lines:
    sections.setdefault(current_ch, []).extend(current_lines)

# 输出
out_parts = [f"""---
title: 中华穆斯林的现状与展望
author: 无花果
publisher: 香港天音出版公司
year: 2008
---

# 中华穆斯林的现状与展望

> 无花果 著 | 原名《穆斯林希望之路》

---

## 目录\n"""]

for i, ch in enumerate(CHAPTERS, 1):
    anchor = ch.replace(' ', '-')
    out_parts.append(f"{i}. [{ch}](#{anchor})")

out_parts.append("\n---\n")

for ch in CHAPTERS:
    if ch in sections:
        content = '\n'.join(sections[ch])
        content = re.sub(r'^' + re.escape(ch) + r'\n?', '', content)
        out_parts.append(f"\n## {ch}\n\n{content.strip()}\n\n---\n")
        print(f"   ✅ {ch}: {len(content):,} 字符")

# 未匹配
for ch in sections:
    if ch not in CHAPTERS:
        content = '\n'.join(sections[ch])
        out_parts.append(f"\n## {ch}\n\n{content.strip()}\n\n---\n")

final = '\n'.join(out_parts)
final = re.sub(r'\n{4,}', '\n\n\n', final)

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(final)

cn = len(re.findall(r'[一-鿿]', final))
print(f"\n{'='*60}")
print(f"🎉 完成！文件: {OUT}")
print(f"   大小: {os.path.getsize(OUT)/1024:.0f}KB  中文字符: {cn:,}")
print(f"{'='*60}")
