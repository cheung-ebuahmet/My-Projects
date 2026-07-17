#!/usr/bin/env python3
"""
🔍 OCR 后处理智能纠错工具
===========================
功能：读取 OCR 生成的 .md 文件，使用参考文本和纠错规则修正错字
用法：python repair_ocr.py <输入的.md> [输出的.md]

支持：
1. 基于参考文本的模糊匹配修正
2. 高频错字表替换
3. 正则模式修复
"""

import re
import sys
import os
from pathlib import Path
from difflib import SequenceMatcher
import json

# ============================================================
# 高频 OCR 错字修正表
# ============================================================
OCR_FIXES = {
    # ---- 书名/作者 ----
    "中圉": "中国",
    "申国": "中国",
    "申圉": "中国",
    "中図": "中国",
    "中團": "中国",
    "伊斯蒯": "伊斯兰",
    "伊斯籣": "伊斯兰",
    "伊斯藕": "伊斯兰",
    "伊斯蘭": "伊斯兰",
    "伊斯墩": "伊斯兰",
    "伊靳兰": "伊斯兰",
    "回纺": "回教",
    "回救": "回教",
    "国教": "回教",
    "臼": "白",
    "臭": "白",
    "鼻": "寿",
    "寿鼻": "寿彝",
    "葬岩": "寿彝",
    "葬著": "寿彝",
    "白寿鼻": "白寿彝",
    "白葬岩": "白寿彝",
    "白卉": "白寿",
    "白寿彝": "白寿彝",

    # ---- 出版社/出版信息 ----
    "宁夏": "宁夏",
    "宁夏": "宁夏",
    "人民出版衽": "人民出版社",
    "人民出版杜": "人民出版社",
    "银川": "银川",
    "银j/II": "银川",
    "縵川": "银川",
    "解放西街": "解放西街",
    "新华书店": "新华书店",
    "新葺书店": "新华书店",
    "新华印刷": "新华印刷",
    "印剛": "印刷",
    "印別": "印刷",
    "策王版": "第一版",
    "第策版": "第一版",
    "策次印刷": "第一次印刷",
    "l吹": "次",
    "井牛": "开本",
    "申张": "印张",
    "芋數": "字数",
    "芊數": "字数",
    "芊数": "字数",
    "千数": "字数",
    "插瓦": "插页",
    "书号": "书号",
    "定价": "定价",

    # ---- 题记/序言 ----
    "题记": "题记",
    "題記": "题记",
    "題记": "题记",
    "小书": "小书",
    "旧作": "旧作",
    "汇集": "汇集",
    "匯集": "汇集",
    "散花": "散在各处",
    "烦艾": "烦文",
    "赘词": "赘词",
    "删削": "删削",
    "附录": "附录",
    "附錄": "附录",
    "陈垣": "陈垣",
    "陳垣": "陈垣",
    "讲稿": "讲稿",
    "講稿": "讲稿",
    "论述": "论述",
    "論述": "论述",
    "题记中": "题记中",
    "艰苦": "艰苦",
    "學問": "学问",
    "具备": "具备",
    "幾个": "几个",
    "几箇": "几个",
    "箇条件": "个条件",
    "限制": "限制",
    "雎以": "难以",
    "难以": "难以",
    "起步": "起步",
    "成就": "成就",
    "領域": "领域",
    "巨大": "巨大",
    "重要武器": "重要武器",
    "阢": "的",
    "的": "的",

    # ---- 常见扫描噪声字 ----
    "犒": "",
    "昱": "",
    "皋": "",
    "L": "",
    "|": "",
    "：": "：",

    # ---- 章节标题 ----
    "目^录": "目 录",
    "目錄": "目录",
    "目 录": "目录",
    "中国回教小史": "中国回教小史",
    "中圍国回教小史": "中国回教小史",
    "穆斯林的历史传统": "穆斯林的历史传统",
    "曆史传统": "历史传统",
    "从怛逻斯战役": "从怛逻斯战役",
    "但逻斯": "怛逻斯",
    "华文记录": "华文记录",
    "大食商人": "大食商人",
    "元代": "元代",
    "赛典赤": "赛典赤",
    "赡思丁": "赡思丁",
    "蟾思丁": "赡思丁",
    "柳州": "柳州",
    "马雄": "马雄",
    "清净寺记": "清净寺记",
    "清淨寺记": "清净寺记",
    "怀圣寺记": "怀圣寺记",
    "懷聖寺记": "怀圣寺记",
    "古兰经": "古兰经",
    "馬譯本": "马译本",
    "泉州": "泉州",
    "石刻": "石刻",

    # ---- 附录 ----
    "回回教入中国史略": "回回教入中国史略",
    "寺院教育": "寺院教育",
    "沿革": "沿革",
    "课本": "课本",
    "庞士谦": "庞士谦",
    "龐士谦": "庞士谦",
    "清真教育会": "清真教育会",
    "纪事": "纪事",
    "俱进会": "俱进会",
    "本部通告": "本部通告",
    "王宽": "王宽",
    "三十年": "三十年",
    "文化概况": "文化概况",
    "赵振武": "赵振武",
    "五十年": "五十年",
    "求学自述": "求学自述",
    "王静斋": "王静斋",
    "王靜斋": "王静斋",

    # ---- 常用字修复 ----
    "仄": "人",
    "狎": "人",
    "亻门": "们",
    "們": "们",
    "牠": "它",
    "牠們": "它们",
    "箇": "个",
    "個": "个",
    "並": "并",
    "幷": "并",
    "幹": "干",
    "後": "后",
    "鬱": "郁",
    "蔔": "卜",
    "麼": "么",
    "麽": "么",
    "裏": "里",
    "裡": "里",
    "麵": "面",
    "繫": "系",
    "係": "系",
    "復": "复",
    "複": "复",
    "徵": "征",
    "衝": "冲",
    "儘": "尽",
    "蓋": "盖",
    "曆": "历",
    "歷": "历",
    "歷史": "历史",
    "曆史": "历史",
    "闗": "关",
    "關": "关",
    "對於": "对于",
    "關於": "关于",
    "屬於": "属于",

    # ---- 这本书特有的年份/数字 ----
    "1883": "1983",
    "l": "1",
    "苒": "年",
    "华B月": "年8月",
    "策版": "第一版",
    "笨": "第",
    "邪": "第",
    "坎": "次",
    "给": "宁夏",
    "隼": "印刷",
    "井": "开",

    # ---- 第一章特有修复 ----
    "大食": "大食",
    "回教原名": "回教原名",
    "伊斯兰": "伊斯兰",
    "阿拉伯字": "阿拉伯字",
    "顺从": "顺从",
    "造物主": "造物主",
    "隋大业": "隋大业",
    "创兴": "创兴",
    "汉武帝": "汉武帝",
    "张骞": "张骞",
    "凿空": "凿空",
    "条支": "条支",
    "后汉和帝": "后汉和帝",
    "甘英": "甘英",
    "奉使": "奉使",
    "西域": "西域",
    "唐代": "唐代",
    "宋代": "宋代",
    "元代": "元代",
    "明代": "明代",
    "清代": "清代",

    # ---- 英文/数字修复 ----
    "WWW": "WWW",
    "com": "com",
}


def build_fixes_from_reference(ref_text: str) -> dict:
    """
    从参考文本中提取高频词，构建更好的纠错表
    这个方法会分析参考文本中的双字词，添加到白名单中
    """
    fixes = {}
    # 提取2-4字中文词
    words = re.findall(r'[一-鿿]{2,6}', ref_text)
    from collections import Counter
    word_freq = Counter(words)
    # 高频词（出现2次以上）作为白名单
    for word, count in word_freq.most_common():
        if count >= 2 and len(word) >= 2:
            fixes[word] = word  # 自身映射表示白名单
    return fixes


def clean_noise_lines(text: str) -> str:
    """
    清理噪声行：
    - 纯粹由英文/数字/符号组成的短行（非正文）
    - 装饰性字符行
    - 重复的页眉装饰
    """
    lines = text.split("\n")
    cleaned = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue

        # 计算中文字符比例
        cn_chars = len(re.findall(r'[一-鿿]', stripped))
        total_printable = len(stripped.replace(" ", "").replace("\t", ""))

        # 全空
        if total_printable == 0:
            cleaned.append("")
            continue

        # 无中文字符的行
        if cn_chars == 0:
            # 保留有意义的英文（长度 > 3，包含字母）
            if re.search(r'[A-Za-z]{3,}', stripped) and len(stripped) > 4:
                cleaned.append(stripped)
            elif re.search(r'[0-9]{2,}', stripped) and len(stripped) > 2:
                # 数字行（可能是页码、日期）
                cleaned.append(stripped)
            else:
                # 噪声跳过
                continue
        else:
            # 有中文的行
            # 如果中文比例太低，可能是噪声
            ratio = cn_chars / total_printable
            if ratio < 0.1 and len(stripped) > 15:
                # 尝试保留（可能是带英文的中文行）
                cleaned.append(stripped)
            elif ratio < 0.05 and len(stripped) > 5:
                continue  # 跳过噪声
            else:
                cleaned.append(stripped)

    return "\n".join(cleaned)


def smart_repair(text: str, reference_text: str = "") -> str:
    """
    智能修复管线：
    1. 查表替换高频错字
    2. 基于参考文本的模糊匹配
    3. 正则修复
    4. 噪声过滤
    """
    lines = text.split("\n")
    result = []

    for line in lines:
        fixed = line

        # 1. 查表替换（精确匹配）
        for wrong, correct in OCR_FIXES.items():
            if wrong and wrong in fixed:
                fixed = fixed.replace(wrong, correct)

        # 2. 如果给了参考文本，尝试用参考文本中的词替换相似词
        if reference_text and len(fixed.strip()) > 5:
            fixed = fuzzy_repair_line(fixed, reference_text)

        # 3. 正则修复 - 多余空格
        # 中文之间的空格去掉
        fixed = re.sub(r'([一-鿿])\s+([一-鿿])', r'\1\2', fixed)
        # 中文标点前的空格去掉
        fixed = re.sub(r'\s+([，。！？、；：）」」】])', r'\1', fixed)

        # 4. 合并多处连续标点
        fixed = re.sub(r'[，,]{2,}', '，', fixed)
        fixed = re.sub(r'[。.]{3,}', '。', fixed)
        fixed = re.sub(r'[、]{2,}', '、', fixed)

        result.append(fixed)

    text = "\n".join(result)

    # 5. 全文级噪声清理
    text = clean_noise_lines(text)

    return text


def fuzzy_repair_line(line: str, ref_text: str) -> str:
    """
    用参考文本对单行进行模糊匹配修复
    策略：如果参考文本中有包含该行中某些词汇的上下文，
    尝试用参考文本中的正确版本替换
    """
    # 提取行中的中文字词（2-4字）
    words = re.findall(r'[一-鿿]{2,4}', line)

    for word in words:
        # 检查这个词是否在参考文本中出现过
        if word in ref_text:
            continue  # 已经在白名单中

        # 尝试在参考文本中找相似词（编辑距离 <= 1）
        ref_words = re.findall(r'[一-鿿]{' + str(len(word)) + '}', ref_text)
        best_match = None
        best_ratio = 0

        for ref_word in ref_words:
            ratio = SequenceMatcher(None, word, ref_word).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = ref_word

        # 如果找到高相似度的参考词，替换
        if best_ratio > 0.7 and best_match != word:
            line = line.replace(word, best_match)

    return line


def repair_markdown_file(input_path: str, output_path: str = None,
                         reference_path: str = None):
    """
    主函数：修复一个 .md 文件的 OCR 错字
    """
    print(f="\n{'='*60}")
    print(f"🔍 正在修复: {input_path}")
    print(f"{'='*60}")

    # 读取文件
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 分离 frontmatter 和正文
    frontmatter = ""
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = "---" + parts[1] + "---"
            body = parts[2]

    # 读取参考文本（如果有）
    reference_text = ""
    if reference_path and os.path.exists(reference_path):
        with open(reference_path, "r", encoding="utf-8") as f:
            reference_text = f.read()
        print(f"   📖 已加载参考文本: {len(reference_text)} 字符")

    # 对正文逐页修复
    pages = body.split("## 第")
    fixed_pages = []

    for i, page in enumerate(pages):
        if i == 0:
            # 页眉部分
            fixed_pages.append(page)
            continue

        # 重建 ## 第 X 页 前缀
        page = "## 第" + page

        # 分离标题和内容
        parts = page.split("\n", 1)
        if len(parts) == 2:
            header, content = parts
            fixed_content = smart_repair(content, reference_text)
            fixed_pages.append(f"{header}\n{fixed_content}")
        else:
            fixed_pages.append(page)

        if (i) % 20 == 0:
            print(f"   ✅ 已修复第 {i} 页...")

    body = "\n".join(fixed_pages)

    # 组合输出
    if frontmatter:
        # 更新 frontmatter 增加修复标记
        output = frontmatter + "\n" + body
    else:
        output = body

    # 写入
    if output_path is None:
        output_path = input_path  # 默认覆盖

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output)

    # 统计
    original_chars = len(body)
    fixed_chars = len(output)
    print(f"\n{'='*60}")
    print(f"✅ 修复完成！")
    print(f"   文件: {output_path}")
    print(f"   字符数: {original_chars:,}")
    print(f"{'='*60}\n")

    return output_path


# ============================================================
# 内置参考文本（来自在线搜索）
# ============================================================
BUILTIN_REFERENCE = """中国伊斯兰史存稿
白寿彝
宁夏人民出版社

题记
这本小书收了我十一篇文章。基本上是三四十年前的旧作，不只观点旧，词汇和表述形式也是旧的。现在把这些文章汇集出版，是因为它们也许在历史资料和思想方面多少可以参考参考。这些文章原来散在各处，汇集起来，总可以对愿意阅览的人提供一点方便。原作，除个别文字上的改动和烦文赘词的删削外，基本保持原来的面目。附录里收了几篇别人的作品。其中，陈垣先生的讲稿是一篇很有影响的论述，是从事伊斯兰史研究的人应该读一读的。其他几篇，都是现在已经不易见到的在某些方面有代表性的资料。

1944年，我在《中国回教小史》的题记中说到，中国伊斯兰教史的研究，是一门很艰苦的学问。并提出研究这门学问应当具备的几个条件。现在看来，具备这些条件是不容易的，但是应该争取到这些条件，多一个条件就对工作增加不少便利。当时，我是想逐步取得这些条件的，但受到了各种难以克服的限制，在刚起步的时候就无法前进。因此，我在中国伊斯兰史的研究工作上，说不上有什么成就。我愿意在这里重新提出来，如果真正想在这方面的研究取得重大的成果，设法取得这些条件还是很必要的。还应该指出，历史科学理论的指导，是更为重要的。这在三四十年前是不懂得的，而这恰恰是取得工作巨大进展的重要武器。

近年，中国伊斯兰史的研究逐渐开展。关于宗教和民族关系的研究，宗教制度，宗教典籍，宗教派别的研究，宗教史的考古和特定地区的研究等等，都出现了新的课题和论述。相信这些研究都会不断的进展，在这些方面以外还会开拓新的研究领域。我借这本小书出版的机会，祝愿同志们工作顺利。

1982年元月16日，白寿彝于北京。

目录
题记 (1)
中国回教小史 (1)
中国穆斯林的历史传统 (45)
从怛逻斯战役说到伊斯兰教之最早的华文记录 (56)
宋时大食商人在中国的活动 (104)
元代回教人与回教 (170)
赛典赤赡思丁考 (216)
柳州伊斯兰与马雄 (299)
跋吴鉴《清净寺记》 (314)
跋《重建怀圣寺记》 (325)
《古兰经》马译本序 (340)
《泉州伊斯兰教石刻》序 (344)
附录：回回教入中国史略 (陈垣) (346)
中国回教寺院教育之沿革及课本 (庞士谦) (366)
清真教育会纪事 (375)
《中国回教俱进会本部通告》序 (王宽) (383)
三十年来之中国回教文化概况 (赵振武) (385)
五十年求学自述 (王静斋) (406)

中国回教小史
本文写于1943年，发表于《边政公论》。1944年作了一些修改，交商务印书馆出单行本。今据单行本作了字句上的个别修改，内容未加改动。1981年12月30日作者记

题记
中国回教史的研究，是一门很艰苦的学问。研究这门学问的人，须具备几种语言上的工具，须理解回教教义和教法，须熟悉中国史料以及阿拉伯文、波斯文、土耳其文中的有关记载，须明了欧美学者在这方面已有的成绩，更须足迹遍全国，见到过各处的回教社会，见到过各处的碑刻和私家记载。他不只有这些语言文字上的资料，他更要懂得回教的精神，懂得中国回教人的心。一直到现在，我们还没有找到一个能胜任这种工作的人。教外的学者，无论他是如何渊博，究竟觉得隔膜。教内人，虽有的人具备了一两个条件，但还不能具备一些必不可缺的条件。一直到现在，我们见不到一本可看的中国回教史，这实不可怪。这本不是短时期所能产生出来的。

现在我这一个小册子，更谈不到是什么著述，只是介绍中国回教史之一个粗浅的概念而已。在这个册子里，有几处是和一般人的说法不同的。

第一章 中国大食间的交通
回教原名叫作伊斯兰（Islam），是一个阿拉伯字，意思是顺从。顺从，应该是顺从造物主的意思。
隋大业六年（公元610年），回教创兴于阿拉伯。不久以后，回教就由阿拉伯传到中国来。但中国和阿拉伯间的交通，是在很早的时候就有了的，并不是回教兴起以后的新鲜事情。
当汉武帝时，张骞凿空，就听说西方有一个条支国。后汉和帝永元九年（公元97年），甘英奉使西域，他亲自到了条支。
"""


def main():
    import argparse
    parser = argparse.ArgumentParser(description="🔍 OCR 后处理智能纠错工具")
    parser.add_argument("input", help="输入的 .md 文件路径")
    parser.add_argument("output", nargs="?", help="输出的 .md 文件路径（默认覆盖输入）")
    parser.add_argument("--reference", help="参考文本文件路径")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"❌ 文件不存在: {args.input}")
        sys.exit(1)

    repair_markdown_file(
        input_path=args.input,
        output_path=args.output,
        reference_path=args.reference,
    )


if __name__ == "__main__":
    main()
