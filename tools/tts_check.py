#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tts_check.py — edge-tts 朗讀前的多音字檢查與矯正

用法:
    python tts_check.py 文字.txt            # 掃描並逐一詢問
    python tts_check.py 文字.txt -o 輸出.txt # 確認後輸出矯正文本
    python tts_check.py --text "直接傳字串"

流程:
    1. 掃出文中所有多音字（含在句中的上下文）
    2. 對每個多音字，列出 g2pW 詞典中的可能讀音（注音符號）
    3. 逐個問你確認：保留 / 換成指定讀法 / 跳過
    4. 依你的決定輸出矯正後的文字，供 edge-tts 使用

多音字矯正技巧:
    - 保留: 該字讀音無疑義，直接用
    - 強制: 若 TTS 會讀錯，改寫成同音字或加語境詞
      (例: 「地」讀錯→「的」；「了」→「了解」改成「理解」)
"""

import sys
import os
import re
import argparse
from collections import OrderedDict

# ── 多音字詞典（g2pW 格式，注音符號）──
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
G2PW_DIR = os.path.join(TOOLS_DIR, "g2pW")
POLY_FILE = os.path.join(G2PW_DIR, "POLYPHONIC_CHARS.txt")

# 讀入多音字詞典
poly_map = {}  # char -> {zhuyin: count}
def load_poly():
    with open(POLY_FILE, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                ch = parts[0]
                zhuyin = parts[1] if len(parts) > 1 else ""
                if ch not in poly_map:
                    poly_map[ch] = OrderedDict()
                poly_map[ch][zhuyin] = poly_map[ch].get(zhuyin, 0) + 1

load_poly()

# ── 高危多音字（TTS 真正容易讀錯的）──
# 只有這些字會逐一詢問；其餘多音字視為低風險直接跳過
HIGH_RISK = set("地了行樂重參長校中朝為和數還應發得看覺教傳當降觀間差藏場系說和乾曲處省折著泥量供強落稱相盛空便角難分便解更幾曾劃盡擔單當調倒都彈種好")

# ── 專有名詞讀音表（edge-tts 易讀錯）──
# 從 proper_nouns.txt 載入: 詞 → 擬定讀音
PROPER_NOUNS = {}
def load_proper_nouns():
    path = os.path.join(TOOLS_DIR, "proper_nouns.txt")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                PROPER_NOUNS[parts[0]] = parts[1]
load_proper_nouns()

# 注音符號 → 說明（部分常用字）
ZHUYIN_NOTE = {
    "ㄉㄧ": "dī/dí/dǐ/dì（第/地/的）",
    "ㄉㄜ": "de（的/得）",
    "ㄌㄜ": "le（了）",
    "ㄌㄧㄠˇ": "liǎo（了解）",
    "ㄏㄤˊ": "háng（銀行/行走）",
    "ㄒㄧㄥˊ": "xíng（行走/行為）",
    "ㄩㄝˋ": "yuè（音樂）",
    "ㄌㄜˋ": "lè（快樂）",
    "ㄔㄨㄥˊ": "chóng（重新）",
    "ㄓㄨㄥˋ": "zhòng（重量）",
    "ㄘㄢ": "cān（參加）",
    "ㄕㄣ": "shēn（人參）",
}

def extract_text(args):
    """從參數或檔案取得待檢查文字"""
    if args.text:
        return args.text
    with open(args.file, encoding="utf-8") as f:
        return f.read()

def find_poly_contexts(text):
    """找出文中高危多音字及上下文"""
    found = OrderedDict()  # 出現位置 -> (char, context)
    for m in re.finditer(r'[一-鿿]', text):
        ch = m.group()
        # 只檢查高危字；其餘多音字視為低風險
        if ch in HIGH_RISK and ch in poly_map and len(poly_map[ch]) > 1:
            pos = m.start()
            start = max(0, pos - 6)
            end = min(len(text), pos + 7)
            context = text[start:end].replace("\n", " ")
            if ch not in found:
                found[ch] = []
            found[ch].append((pos, context))
    return found

def find_proper_nouns(text):
    """找出文中出現的專有名詞（已建讀音表的），依出現順序去重"""
    found = OrderedDict()  # name -> (reading, [contexts])
    for name in PROPER_NOUNS:
        for m in re.finditer(re.escape(name), text):
            pos = m.start()
            start = max(0, pos - 6)
            end = min(len(text), pos + len(name) + 6)
            context = text[start:end].replace("\n", " ")
            if name not in found:
                found[name] = [PROPER_NOUNS[name], []]
            found[name][1].append(context)
    return found

def ask_user(char, contexts, kind="多音字"):
    """詢問使用者該字/詞的處理方式"""
    print(f"\n┌─ {kind}「{char}」 ─────────────────────────")
    print(f"│ 出現 {len(contexts)} 次")
    if kind == "多音字":
        readings = list(poly_map[char].keys())
        print(f"│ 可能讀音: {', '.join(readings[:5])}")
        if char in ZHUYIN_NOTE:
            print(f"│ 常見: {ZHUYIN_NOTE[char]}")
    print(f"│ 上下文:")
    for ctx in contexts[:4]:
        if isinstance(ctx, tuple):
            ctx = ctx[1]  # 多音字是 (pos, ctx)
        idx = ctx.find(char)
        if idx >= 0:
            marked = ctx[:idx] + f"[{char}]" + ctx[idx+len(char):]
        else:
            marked = ctx
        print(f"│   …{marked}…")
    print("└──────────────────────────────────────────")
    while True:
        choice = input(f"  「{char}」處理? [r=保留/f=改寫/s=跳過] ").strip().lower()
        if choice in ("r", "f", "s"):
            return choice
        print("  請輸入 r / f / s")

def main():
    parser = argparse.ArgumentParser(description="edge-tts 朗讀前多音字檢查")
    parser.add_argument("file", nargs="?", help="待檢查文字檔")
    parser.add_argument("--text", help="直接傳入文字")
    parser.add_argument("-o", "--output", help="輸出矯正後文字檔")
    args = parser.parse_args()

    if not args.file and not args.text:
        parser.error("需要指定文字檔或 --text")

    text = extract_text(args)

    # ── 第一層：專有名詞檢查 ──
    pn_found = find_proper_nouns(text)
    pn_decisions = {}
    if pn_found:
        print(f"\n⚠️  發現 {len(pn_found)} 個專有名詞（edge-tts 可能讀錯），逐一確認:")
        for name, (reading, contexts) in pn_found.items():
            print(f"  「{name}」→ 讀作「{reading}」")
            pn_decisions[name] = ask_user(name, contexts, kind="專名")
    else:
        print("✅ 未發現建表專有名詞")

    # ── 第二層：高危多音字 ──
    found = find_poly_contexts(text)
    decisions = {}

    if found:
        print(f"\n⚠️  發現 {sum(len(v) for v in found.values())} 個高危多音字，逐一確認:")
        for char, contexts in found.items():
            decisions[char] = ask_user(char, contexts)
    else:
        print("✅ 未發現高危多音字")

    # ── 輸出確認結果 ──
    if decisions:
        print("\n── 多音字確認結果 ──")
        for char, d in decisions.items():
            label = {"r": "保留", "f": "改寫", "s": "跳過"}[d]
            print(f"  「{char}」→ {label}")
    if pn_decisions:
        print("\n── 專名確認結果 ──")
        for name, d in pn_decisions.items():
            label = {"r": "保留", "f": "改寫", "s": "跳過"}[d]
            print(f"  「{name}」→ {label}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"\n→ 文字已寫入 {args.output}")
        print("  （若選擇改寫，請在輸出檔中手動替換該字）")

    print("\n確認完成，可進行 edge-tts 轉錄。")

if __name__ == "__main__":
    main()
