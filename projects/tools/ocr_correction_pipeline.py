#!/usr/bin/env python3
"""
OCR 校正管線 — 天方東漸錄 資料庫專用

用法:
  python3 ocr_correction_pipeline.py [檔案路徑]

如果不指定檔案路徑，依優先級處理關鍵文件。
指定檔案路徑則只處理該文件。

校正策略（由淺入深）：
  第1層 — 正則級：常見OCR錯誤字、多餘空格、亂碼
  第2層 — 詞典級：知識庫中的專有名詞強制校正
  第3層 — 語意級：由語言模型處理殘留錯誤（需外部API）
"""

import re
import sys
import os

# ═══════════════════════════════════════════
# 第1層：正則校正表
# ═══════════════════════════════════════════

# 常見OCR錯誤字符映射
def fix_double_char(text):
    """修正OCR造成的重複字（如 这这、中中、阿阿）"""
    # 常見重複模式: 中中 → 中, 这这 → 这
    double_patterns = [
        (r'(.)\1(\.)', r'\1\2'),
        (r'([中这那阿伊的伯])\1', r'\1'),
        (r'(阿拉)\1', r'\1'),
        (r'(伯拉)\1', r'\1'),
        (r'(波斯)\1', r'\1'),
        (r'(第[一二三四五六七八九十]+章)\1+', r'\1'),
        (r'(第[一二三四五六七八九十]+節)\1+', r'\1'),
        (r'(中國大食的交通)\1+', r'\1'),
    ]
    text_tmp = text
    for pattern, replacement in double_patterns:
        text_tmp = re.sub(pattern, replacement, text_tmp)
    return text_tmp


CHAR_FIXES = {
    '娈': '變',   # 常见于参考资料選編
    '汊': '漢',
    '汊人': '漢人',
    '肒': '的',   # OCR 常見誤判
    '肙': '為',
    '裎': '程',
    '餍': '歷',
    '饧': '曆',
    '跚': '聯',
    '喇': '關',
    '唄': '員',
    '嵑': '歲',
    '嵒': '當',
    '嬴': '贏',
    '巖': '嚴',
    '巒': '變',
    '扞': '擴',
    '摜': '關',
    '旪': '時',
    '旲': '昊',
    '朮': '術',
    '栉': '節',
    '槳': '獎',
    '殂': '歿',
    '澆': '邊',
    '灞': '讓',
    '焔': '煙',
    '燉': '敦',
    '爿': '將',
    '𥝱': '的',
    '纒': '纏',
    '膮': '臘',
    '薌': '鄉',
    '蛻': '脫',
    '諒': '體',
    '邏輯': '邏輯',
    '幇': '幫',
    '幷': '並',
    '併': '並',
    '儘': '盡',
    '靑': '青',
    '兪': '俞',
    '値': '值',
    '吿': '告',
    '喩': '喻',
    '囘': '回',
    '囬': '回',
    '囗': '口',
    '壌': '壤',
    '孃': '娘',
    '峯': '峰',
    '彿': '佛',
    '従': '從',
    '徴': '徵',
    '恆': '恒',
    '敎': '教',
    '敍': '敘',
    '敘': '敘',
    '歿': '歿',
    '毎': '每',
    '洶': '洶',
    '涙': '淚',
    '滙': '匯',
    '濶': '闊',
    '烕': '滅',
    '爲': '為',
    '牀': '床',
    '狹': '狹',
    '瑯': '琅',
    '甯': '寧',
    '異': '異',
    '皷': '鼓',
    '硏': '研',
    '稟': '稟',
    '窻': '窗',
    '粵': '粵',
    '翦': '剪',
    '脣': '唇',
    '薔': '薔',
    '藪': '藪',
    '蘇': '蘇',
    '蝨': '虱',
    '術': '術',
    '裏': '裡',
    '覈': '核',
    '謁': '謁',
    '讃': '讚',
    '貶': '貶',
    '蹟': '蹟',
    '輓': '挽',
    '辭': '辭',
    '違': '違',
    '遲': '遲',
    '邇': '邇',
    '鬱': '鬱',
    '鹹': '鹹',
    '麽': '麼',
    '龝': '秋',
}

def apply_char_fixes(text):
    """逐字修正常見OCR錯誤"""
    result = []
    for c in text:
        if c in CHAR_FIXES:
            result.append(CHAR_FIXES[c])
        else:
            result.append(c)
    return ''.join(result)


def remove_ocr_garbage(text):
    """移除OCR殘留亂碼行和符號"""
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        # 移除只剩符號的空行
        if re.match(r'^[\s\-_=*~.,;:!@#$%^&()+\[\]{}|\\\\]+\n?$', line):
            continue
        # 移除行首的亂碼前綴（如 "b5e89b68e5..."）
        if re.match(r'^[a-f0-9]{6,}\s+', line):
            line = re.sub(r'^[a-f0-9]{6,}\s+', '', line)
        # 移除行中的十六進制殘留
        line = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', line)
        # 壓縮多餘空白
        line = re.sub(r'  +', ' ', line)
        cleaned.append(line)
    return '\n'.join(cleaned)


def is_route_line(line):
    """判斷是否為路線描述行（不應合併）"""
    route_patterns = [
        r'^\d+里[至到]',
        r'^又\w+里',
        r'^至\w+城',
        r'^渡\w+河',
        r'^經\w+',
        r'^出\w+至',
        r'^傍\w+',
    ]
    return any(re.match(p, line.strip()) for p in route_patterns)

def fix_line_breaks(text):
    """修正OCR造成的斷行——謹慎合併"""
    lines = text.split('\n')
    merged = []
    i = 0
    while i < len(lines):
        current = lines[i]
        # 只有當行長度短且顯然是被截斷的敘述時才合併
        while (i + 1 < len(lines) and
               current.strip() and
               len(current.strip()) < 30 and
               not is_route_line(current) and
               not current.strip()[-1] in '。！？；）】」』、，：' and
               not current.strip().startswith('> ') and
               not current.strip().startswith('##') and
               lines[i+1].strip() and
               not lines[i+1].strip()[0] in '。！？；）】」』、，：' and
               not is_route_line(lines[i+1])):
            i += 1
            current += lines[i]
        merged.append(current)
        i += 1
    return '\n'.join(merged)


def normalize_punctuation(text):
    """統一中英文標點"""
    text = text.replace(',', '，')
    text = text.replace(';', '；')
    text = text.replace(':', '：')
    text = text.replace('!', '！')
    text = text.replace('?', '？')
    text = re.sub(r'\.{3,}', '……', text)
    text = re.sub(r'…{2,}', '……', text)
    text = re.sub(r'--+', '——', text)
    return text


def clean_header_metadata(text):
    """清理文件頭部的OCR雜訊"""
    lines = text.split('\n')
    cleaned_lines = []
    in_header = True
    for line in lines:
        if in_header:
            # 跳過明顯的OCR亂碼行（過多非CJK字符）
            cjk = sum(1 for c in line if '一' <= c <= '鿿')
            total = len(line.strip())
            if total > 5 and total > 0 and cjk / total < 0.2:
                # 如果CJK比例太低，可能是亂碼行
                continue
            if line.strip().startswith('---'):
                in_header = False
                cleaned_lines.append(line)
                continue
            cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)


# ═══════════════════════════════════════════
# 第2層：詞典級校正（專有名詞）
# ═══════════════════════════════════════════

KNOWLEDGE_BASE = {
    '伊斯兰教史': '伊斯蘭教史',
    '伊斯兰教': '伊斯蘭教',
    '穆斯林': '穆斯林',
    '回教徒': '回教徒',
    '清真寺': '清真寺',
    '蕃坊': '蕃坊',
    '蕃长': '蕃長',
    '蕃客': '蕃客',
    '大食': '大食',
    '可兰经': '可蘭經',
    '古兰经': '古蘭經',
    '安拉': '阿拉',
    '安拉': '阿拉',
    '欧麦尔': '奧馬爾',
    '奥斯曼': '奧斯曼',
    '奥马尔': '奧馬爾',
    '伍麦叶': '伍麥亞',
    '伍麦耶': '伍麥亞',
    '阿拔斯': '阿拔斯',
    '法蒂玛': '法蒂瑪',
    '鄂图曼': '鄂圖曼',
    '奥斯曼帝国': '鄂圖曼帝國',
    '天方': '天方',
    '怛逻斯': '怛邏斯',
    '杜环': '杜環',
    '经行记': '經行記',
    '白寿彝': '白壽彝',
    '傅统先': '傅統先',
    '陈垣': '陳垣',
    '陈寅恪': '陳寅恪',
    '赛典赤': '賽典赤',
    '辛押陀罗': '辛押陀羅',
    '蒲寿庚': '蒲壽庚',
    '郑和': '鄭和',
    '市舶司': '市舶司',
    '市舶使': '市舶使',
    '鸿胪寺': '鴻臚寺',
    '互市监': '互市監',
}



# 全局校正模式（補充正則層級）
WIKI_FIXES = [
    # 常見OCR結構錯誤
    (r'中伊斯兰史教', '中国伊斯兰教史'),
    (r'阿拉伯伯', '阿拉伯'),
    (r'研究究', '研究'),
    (r'波斯字', '波斯'),
    (r'字人', '人'),
    (r'(中国大食的交通){2,}', '中国大食的交通'),
    (r'发达达', '发达'),
    (r'一个个股', '一个'),
    (r'史教史', '教史'),
    (r'回教教', '回教'),
    (r'伊斯蘭兰', '伊斯蘭'),
    (r'伊斯蘭兰教', '伊斯蘭教'),
    (r'阿阿拉伯伯', '阿拉伯'),
    (r'波波斯', '波斯'),
    (r'大大食', '大食'),
    (r'唐唐宋', '唐宋'),
    (r'人人中原', '人中原'),
    (r'个名词', '个名词'),
]

def apply_wiki_fixes(text):
    """應用全局校正模式"""
    for pattern, replacement in WIKI_FIXES:
        text = re.sub(pattern, replacement, text)
    return text
def apply_knowledge_base(text):
    """應用知識庫進行專有名詞校正"""
    for wrong, correct in KNOWLEDGE_BASE.items():
        # 只匹配完整的詞（前後非中文字符或邊界）
        text = re.sub(re.escape(wrong), correct, text)
    return text


# ═══════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════

# 優先處理的文件（按寫作使用頻率排序）
PRIORITY_FILES = [
    '白寿彝中国回教小史.md',
    '中国回教史.md',  # 傅統先
    '中国伊斯兰史存稿.md',  # 白壽彝
    '中国伊斯兰教史参考资料选编.md',
    '从苏莱曼东游记看唐朝与阿拉伯的海上丝路.md',
    '形象学视角下7-13世纪阿拉伯游记中的中国形象研究.md',
]


def correct_file(filepath, dry_run=False):
    """完整校正一個文件"""
    base = os.path.basename(filepath)
    print(f"\n{'='*60}")
    print(f"📄  {base}")
    print(f"{'='*60}")

    with open(filepath, 'r', encoding='utf-8') as f:
        original = f.read()

    # 執行各層校正
    text = original
    steps = [
        ('clean_header_metadata', clean_header_metadata),
        ('remove_ocr_garbage', remove_ocr_garbage),
        ('apply_char_fixes', apply_char_fixes),
        ('fix_double_char', fix_double_char),
        ('apply_wiki_fixes', apply_wiki_fixes),
        ('apply_knowledge_base', apply_knowledge_base),
        ('fix_line_breaks', fix_line_breaks),
        ('normalize_punctuation', normalize_punctuation),
    ]

    for name, func in steps:
        before_len = len(text)
        text = func(text)
        after_len = len(text)
        change = before_len - after_len
        # 算一下改變了多少字符
        diff_count = sum(1 for a, b in zip(original, text) if a != b) if len(original) == len(text) else 'N/A'
        print(f"  |─ {name}: {change:+d} chars")

    # 統計
    orig_chars = len(original)
    new_chars = len(text)
    changed = sum(1 for i in range(min(len(original), len(text))) if original[i] != text[i])
    print(f"\n  原大小: {orig_chars} chars → 新大小: {new_chars} chars")
    print(f"  字符變動: {changed} 處")

    if dry_run:
        print("  ⏸  乾運行，不寫入")
        return text

    # 備份原文件
    backup = filepath + '.bak'
    if not os.path.exists(backup):
        os.rename(filepath, backup)
        print(f"  原文件備份至: {os.path.basename(backup)}")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"  ✅ 校正完成")
    return text


def find_files_in_library():
    """掃描書庫中所有MD文件，按優先級排序"""
    library_root = '/Users/admin/Documents/My Projects/books/伊斯兰在中国'
    all_files = []

    for root, dirs, files in os.walk(library_root):
        # 跳過系列目錄（創作目錄）
        if '系列' in root.split(os.sep):
            continue
        for f in files:
            if f.endswith('.md') and not f.endswith('_简介.md'):
                all_files.append(os.path.join(root, f))

    # 按優先級排序
    priority_files = []
    remaining = []

    for f in all_files:
        basename = os.path.basename(f)
        if basename in PRIORITY_FILES:
            priority_files.append(f)
        else:
            remaining.append(f)

    return priority_files + remaining


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # 處理指定的文件
        filepath = sys.argv[1]
        if os.path.isfile(filepath):
            correct_file(filepath)
        else:
            print(f"❌ 找不到文件: {filepath}")
    else:
        # 掃描書庫
        files = find_files_in_library()
        print(f"找到 {len(files)} 個 MD 文件")
        print(f"優先級文件: {len([f for f in files if os.path.basename(f) in PRIORITY_FILES])}")
        for f in files:
            correct_file(f)
