#!/usr/bin/env python3
"""
🔄 OCR 文本合并优化工具
=========================
功能：将 OCR 识别结果与在线参考文本合并，取两者之长
策略：
  1. 有参考文本的页面 → 以参考文本为主，保留 OCR 中的额外内容
  2. 无参考文本的页面 → 使用纠错字典修复 OCR 结果
  3. 学习模式 → 从 OCR vs 参考文本的差异中提取新的纠错规则

用法：
  python merge_refine.py <ocr.md> [参考文本.txt] -o <输出.md>
  python merge_refine.py <ocr.md> --learn -o <输出.md>
"""

import re
import sys
import os
from pathlib import Path
from difflib import SequenceMatcher, HtmlDiff
from collections import Counter
import json

# ============================================================
# 1. 页面级别精确替换（已知可靠的参考文本）
# ============================================================

# 从网上搜到的参考文本（按键="章节标题"组织）
REFERENCE_PAGES = {
    "题记": """题记

这本小书收了我十一篇文章。基本上是三四十年前的旧作，不只观点旧，词汇和表述形式也是旧的。现在把这些文章汇集出版，是因为它们也许在历史资料和思想方面多少可以参考参考。这些文章原来散在各处，汇集起来，总可以对愿意阅览的人提供一点方便。原作，除个别文字上的改动和烦文赘词的删削外，基本保持原来的面目。附录里收了几篇别人的作品。其中，陈垣先生的讲稿是一篇很有影响的论述，是从事伊斯兰史研究工作的人应该读一读的。其他几篇，都是现在已经不易见到的在某些方面有代表性的资料。

1944年，我在《中国回教小史》的题记中说到，中国伊斯兰教史的研究，是一门很艰苦的学问。并提出研究这门学问应当具备的几个条件。现在看来，具备这些条件是不容易的，但是应该争取到这些条件，多一个条件就对工作增加不少便利。当时，我是想逐步取得这些条件的，但受到了各种难以克服的限制，在刚起步的时候就无法前进。因此，我在中国伊斯兰史的研究工作上，说不上有什么成就。我愿意在这里重新提出来，如果真正想在这方面的研究取得重大的成果，设法取得这些条件还是很必要的。还应该指出，历史科学理论的指导，是更为重要的。这在三四十年前是不懂得的，而这恰恰是取得工作巨大进展的重要武器。

近年，中国伊斯兰史的研究逐渐开展。关于宗教和民族关系的研究，宗教制度，宗教典籍，宗教派别的研究，宗教史的考古和特定地区的研究等等，都出现了新的课题和论述。相信这些研究都会不断的进展，在这些方面以外还会开拓新的研究领域。我借这本小书出版的机会，祝愿同志们工作顺利。

1982年元月16日，白寿彝于北京。""",

    "目录": """目 录

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
五十年求学自述 (王静斋) (406)""",

    "中国回教小史题记": """中国回教小史

本文写于1943年，发表于《边政公论》。1944年作了一些修改，交商务印书馆出单行本。今据单行本作了字句上的个别修改，内容未加改动。1981年12月30日作者记

题记

中国回教史的研究，是一门很艰苦的学问。研究这门学问的人，须具备几种语言上的工具，须理解回教教义和教法，须熟悉中国史料以及阿拉伯文、波斯文、土耳其文中的有关记载，须明了欧美学者在这方面已有的成绩，更须足迹遍全国，见到过各处的回教社会，见到过各处的碑刻和私家记载。他不只有这些语言文字上的资料，他更要懂得回教的精神，懂得中国回教人的心。一直到现在，我们还没有找到一个能胜任这种工作的人。教外的学者，无论他是如何渊博，究竟觉得隔膜。教内人，虽有的人具备了一两个条件，但还不能具备一些必不可缺的条件。一直到现在，我们见不到一本可看的中国回教史，这实不可怪。这本不是短时期所能产生出来的。

现在我这一个小册子，更谈不到是什么著述，只是介绍中国回教史之一个粗浅的概念而已。在这个册子里，有几处是和一般人的说法不很一样的。也因为限于篇幅，不能详加解说。我希望，以后有机会能写出一本比较详细的东西出来，请大家指正。并希望同道的朋友，以后在这门学问上，能够各出所长，彼此合作，能够写出一部比一部好的东西来。

这本小册子，每章后面都附有参考资料举要，是为初学预备的。这些资料都限于中文方面的。外国文方面的书，一概没有说。

1944年2月作者记""",

    "第一章": """第一章 中国大食间的交通

回教原名叫作伊斯兰（Islam），是一个阿拉伯字，意思是"顺从"。"顺从"，应该是"顺从造物主"的意思。

隋大业六年（公元610年），回教创兴于阿拉伯。不久以后，回教就由阿拉伯传到中国来。但中国和阿拉伯间的交通，是在很早的时候就有了的，并不是回教兴起以后的新鲜事情。

当汉武帝时，张骞凿空，就听说西方有一个条支国。后汉和帝永元九年（公元97年），甘英奉使西域，他亲自到了条支。条支，据有些学者的研究，是Antiochia（Antiochia的讹音）的省译，乃是以一个地方的名字而泛指美索不达米亚（Mesopotamia）全部的。我们知道，美索不达米亚是可以算在阿拉伯半岛以内的。这样，我们很可以说，在回教创兴五百年前，中国阿拉伯间已经有交通了。

在东晋及南北朝时期，南海的航运已经相当地发达。据阿拉伯史家的记载，这时候已有中国和印度的船只，经由波斯湾，航入阿拉伯内河。

隋及唐初，波斯人到中国来的很多。这所谓波斯人，可以解释为波斯国的人，也可以说是从波斯湾来的人。如果后一个解释是对的，当时所谓波斯人中，就一定包含不少的阿拉伯人在内。即使这个解释不对，恐怕事实上也有些阿拉伯人从波斯湾到中国来的。因为波斯湾，在这个时期，已可能成为对印度和中国的重要贸易港口所在了。

这都是回教兴起前，中国与阿拉伯间交通的情形。回教兴起后，中国阿拉伯间的交通已经大大地进步。这时，中国人习惯用"大食"这两个字，称呼阿拉伯。大食是TaZi的译音，原是一个波斯字。中国人大概是从波斯人那里学到了这个名词。大约，至晚从唐永徽二年（公元651年）起，一直到蒙古人入中原止，中国人都使用着这个名字。现在我们也可照着唐宋人的习惯，用这两个字表示唐宋时期的阿拉伯。

唐时，中国大食间的通路，正常的有两条。一条是走海路，一条是走陆路。贞元间（公元785-805年）宰相贾耽著录中国人四夷路程，就详细地说到这两条路。

陆路：安西（库车）西出柘厥关，渡白马河，经俱毗罗碛（赫色勒沙碛）、俱毗罗城、阿悉言城（拜城）、拨换城（阿克苏城），西北渡拨换河、中河，经小石城、胡芦河、大石城（乌什），度拔达岭（Badel岭），经热海（伊塞克湖），至怛逻斯城。

海路：从广州出发，经南中国海，到印度洋，到波斯湾，直到大食的都城缚达城（Baghdad）。沿途经过屯门山、九州石、象石、占不劳山、陵山、门毒国、古笪国、奔陀浪洲、军突弄山（Pulau Kundur）、满剌加海峡、佛逝国（巴林冯）、诃陵国（爪哇）、胜邓洲、婆露国、师子国（锡兰）、没来国、拔䫻国、提䫻国、缚达国、王舍城、提罗卢和（Diera Lari）、乌剌国（Obollah）、末罗国（Basra），直到缚达城。

在这两条路线外，还有两条可能的路线。一条路线是自大食从海道到安南，再由安南从陆路到云南。又一条路线，是自大食从海道到天竺，再自天竺从陆路到云南。

自唐时起，一直到现在，中国大食间的交通路线，除了因受军事影响而需另觅途径者外，似乎都不出这四条路线的范围。""",
}


# ============================================================
# 2. 高频 OCR 错字修正表（在 pdf_to_md_pro.py 基础上扩充）
# ============================================================
OCR_FIXES = {
    # ---- 书名/作者 ----
    "中圉": "中国", "申国": "中国", "申圉": "中国",
    "中図": "中国", "中團": "中国", "中围": "中国",
    "中躅": "中国",
    "伊斯蒯": "伊斯兰", "伊斯籣": "伊斯兰",
    "伊斯藕": "伊斯兰", "伊斯蘭": "伊斯兰",
    "伊斯墩": "伊斯兰",
    "回纺": "回教", "回救": "回教", "国教": "回教",
    "臼": "白", "臭": "白",
    "鼻": "寿", "葬岩": "寿彝", "葬著": "寿彝",
    "白寿鼻": "白寿彝", "白葬岩": "白寿彝",
    "白卉": "白寿",

    # ---- 出版社 ----
    "宁夏": "宁夏",
    "人民出版衽": "人民出版社",
    "人民出版杜": "人民出版社",
    "银川": "银川",
    "解放西街": "解放西街",
    "新华书店": "新华书店",
    "新葺书店": "新华书店",
    "新华印刷": "新华印刷",
    "印剛": "印刷", "印別": "印刷",
    "策王版": "第一版", "第策版": "第一版",
    "策次印刷": "第一次印刷",
    "l吹": "次", "井牛": "开本",
    "申张": "印张", "千数": "字数",
    "芊數": "字数", "芋數": "字数",
    "插瓦": "插页",

    # ---- 常用字 ----
    "仄": "人", "牠": "它", "箇": "个",
    "曆史": "历史",
    "歷史": "历史",
    "歷史": "历史",
    "雎以": "难以",
    "怡恰": "恰恰",
    "重犬": "重大",
    "要武器": "重要武器",
    "阢": "的",
    "几箇": "几个",
    "几亂": "几篇",
    "旧几": "几",
    "台作": "合作",
    "各出所長": "各出所长",
    "長": "长",
    "門": "门",
    "學問": "学问",
    "問": "问",
    "礎": "础",
    "龜": "龟",
    "龍": "龙",

    # ---- 数字/年份 ----
    "1883": "1983", "l": "1",
    "苒": "年", "华B月": "年8月",
    "笨": "第", "邪": "第", "坎": "次",
    "井": "开",
    "牟": "年", "丰": "年",

    # ---- 目录专用 ----
    "但逻斯": "怛逻斯",
    "蟾思丁": "赡思丁",
    "清淨寺": "清净寺",
    "懷聖寺": "怀圣寺",
    "馬譯本": "马译本",
    "壬宽": "王宽",
    "玉静斋": "王静斋",
    "王靜斋": "王静斋",
    "龐士谦": "庞士谦",

    # ---- 英文噪音 ----
    "WWW": "",
    "com": "",
}

# 学习到的动态规则将在运行时添加
LEARNED_FIXES = {}

# 全局累计变量
_total_new_learned = 0

def learn_from_reference(ocr_text: str, ref_text: str) -> dict:
    """
    核心学习函数：
    比较 OCR 文本和参考文本，提取高频错误 → 纠正的映射
    """
    new_fixes = {}
    # 提取 OCR 中的疑似错词（不在参考文本中的词）
    ocr_words = set(re.findall(r'[一-鿿]{2,4}', ocr_text))
    ref_words = set(re.findall(r'[一-鿿]{2,4}', ref_text))

    for ow in ocr_words:
        if ow in ref_words:
            continue  # 正确，跳过
        # 找参考文本中最相似的词
        best = None
        best_ratio = 0
        for rw in ref_words:
            if abs(len(ow) - len(rw)) > 1:
                continue
            ratio = SequenceMatcher(None, ow, rw).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best = rw
        if best and best_ratio > 0.6 and best_ratio < 1.0:
            new_fixes[ow] = best

    return new_fixes


def merge_page(ocr_text: str, ref_text: str = None) -> str:
    """
    合并一页的内容：
    1. 如果有参考文本且质量好 → 使用参考文本
    2. 同时保留 OCR 中参考文本没有的额外内容
    3. 应用纠错表
    """
    if not ref_text:
        # 无参考文本，只做纠错
        return apply_fixes(ocr_text)

    # 清理 OCR 文本
    cleaned_ocr = clean_ocr_noise(ocr_text)
    cleaned_ref = ref_text.strip()

    # 如果参考文本明显更长/更完整，以参考为主
    if len(cleaned_ref) > len(cleaned_ocr) * 0.5:
        # 检查是否有 OCR 独有的内容需要保留
        ocr_extra = extract_extra_content(cleaned_ocr, cleaned_ref)
        if ocr_extra:
            return cleaned_ref + "\n\n<!-- OCR 补充内容 -->\n" + ocr_extra
        return cleaned_ref
    else:
        # OCR 内容更多，做纠错
        return apply_fixes(cleaned_ocr)


def extract_extra_content(ocr: str, ref: str) -> str:
    """提取 OCR 中有但参考文本中没有的额外内容"""
    ocr_sentences = set(re.split(r'[。！？\n]', ocr))
    ref_sentences = set(re.split(r'[。！？\n]', ref))

    extra = []
    for s in ocr_sentences:
        s = s.strip()
        if len(s) < 10:
            continue
        # 检查是否在参考文本中
        found = False
        for rs in ref_sentences:
            if SequenceMatcher(None, s[:20], rs[:20]).ratio() > 0.7:
                found = True
                break
        if not found and len(re.findall(r'[一-鿿]', s)) > 5:
            extra.append(s)

    return "\n".join(extra[:10])  # 最多10句


def apply_fixes(text: str) -> str:
    """应用所有纠错规则"""
    for wrong, correct in OCR_FIXES.items():
        if wrong and wrong in text:
            text = text.replace(wrong, correct)
    for wrong, correct in LEARNED_FIXES.items():
        if wrong and wrong in text:
            text = text.replace(wrong, correct)
    return text


def clean_ocr_noise(text: str) -> str:
    """清理 OCR 噪声"""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        s = line.strip()
        cn = len(re.findall(r'[一-鿿]', s))
        total = len(s.replace(" ", ""))
        if total == 0:
            continue
        # 无中文且短 → 跳过
        if cn == 0 and len(s) < 5:
            continue
        # 纯符号行
        if cn == 0 and not re.search(r'[A-Za-z0-9]', s):
            continue
        # 中文比例过低 → 噪声
        if cn > 0 and cn / max(total, 1) < 0.05:
            continue
        cleaned.append(s)
    return "\n".join(cleaned)


def merge_markdown(input_path: str, output_path: str, learn: bool = False):
    """主合并函数 - 基于页码的精确匹配"""
    print(f"\n{'='*60}")
    print(f"🔄 合并优化: {Path(input_path).name}")
    print(f"{'='*60}")

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

    # 按页分割：找到所有 "## 第 X 页" 标记
    page_pattern = re.compile(r'(## 第 (\d+) 页)')
    splits = list(page_pattern.finditer(body))

    merged_pages = []

    # 提取页眉之前的文字（书名行等）
    prev_end = 0
    if splits:
        pre_header = body[:splits[0].start()].strip()
        if pre_header:
            merged_pages.append(pre_header + "\n")
        prev_end = splits[0].start()

    # 每页内容对应的参考文本映射（基于页码）
    # 元组: (起始页, 结束页, "章节名")
    # 同一章节的多页会分割参考文本
    PAGE_REF_RANGES = [
        (3, 4, "题记"),
        (5, 5, "目录"),
        (6, 6, "中国回教小史题记"),
        (7, 10, "第一章"),
    ]

    # 构建页码 → (起始页码, 结束页码, 参考文本, 章节名) 映射
    page_ref_info = {}
    for start_p, end_p, key in PAGE_REF_RANGES:
        ref_text = REFERENCE_PAGES.get(key, "")
        for p in range(start_p, end_p + 1):
            page_ref_info[p] = (start_p, end_p, ref_text, key)

    for idx, match in enumerate(splits):
        header = match.group(0)
        page_num = int(match.group(2))
        start = match.end()
        end = splits[idx + 1].start() if idx + 1 < len(splits) else len(body)
        page_content = body[start:end].strip()

        # 检查是否有参考文本
        ref_info = page_ref_info.get(page_num)

        if ref_info:
            start_p, end_p, full_ref_text, ref_key = ref_info
            ocr_clean = clean_ocr_noise(page_content)

            # 分割参考文本：如果是多页章节，分割内容
            if end_p > start_p:
                # 将参考文本按行数近似平均分割
                ref_lines = full_ref_text.split("\n")
                total_lines = len(ref_lines)
                pages_in_range = end_p - start_p + 1
                lines_per_page = max(1, total_lines // pages_in_range)

                page_offset = page_num - start_p
                seg_start = page_offset * lines_per_page
                seg_end = (page_offset + 1) * lines_per_page if page_num < end_p else total_lines
                merged = "\n".join(ref_lines[seg_start:seg_end])
            else:
                merged = full_ref_text

            # 学习新规则
            if learn and ocr_clean:
                global _total_new_learned
                new_rules = learn_from_reference(ocr_clean, full_ref_text)
                if new_rules:
                    for k, v in new_rules.items():
                        if k not in OCR_FIXES and k not in LEARNED_FIXES:
                            LEARNED_FIXES[k] = v
                            _total_new_learned += 1
            merged_pages.append(f"\n{header}\n\n{merged}\n")
            print(f"   📄 第{page_num}页 ✅ 参考文本替换（{ref_key}）")
        else:
            # 无参考文本，只做纠错
            fixed = apply_fixes(clean_ocr_noise(page_content))
            merged_pages.append(f"\n{header}\n\n{fixed}\n")

    new_body = "".join(merged_pages)

    # 输出
    output = frontmatter + "\n" + new_body if frontmatter else new_body

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output)

    cn_original = len(re.findall(r'[一-鿿]', body))
    cn_new = len(re.findall(r'[一-鿿]', new_body))

    print(f"\n{'='*60}")
    print(f"✅ 合并完成！")
    print(f"   文件: {output_path}")
    print(f"   中文字符: {cn_original:,} → {cn_new:,}")
    if _total_new_learned > 0:
        print(f"\n📚 本次学习到的新纠错规则 ({len(LEARNED_FIXES)} 条):")
        for k, v in sorted(LEARNED_FIXES.items()):
            print(f"   \"{k}\" → \"{v}\"")
        # 保存学习成果供后续使用
        learned_path = Path(__file__).parent / "learned_fixes.json"
        with open(learned_path, "w", encoding="utf-8") as f:
            json.dump(LEARNED_FIXES, f, ensure_ascii=False, indent=2)
        print(f"   💾 已保存到: {learned_path}")
    print(f"{'='*60}\n")

    return output_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description="🔄 OCR 文本合并优化工具")
    parser.add_argument("input", help="OCR生成的 .md 输入文件")
    parser.add_argument("-o", "--output", help="输出文件路径（默认覆盖输入）")
    parser.add_argument("--learn", action="store_true",
                        help="从参考文本中学习新的纠错规则")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"❌ 文件不存在: {args.input}")
        sys.exit(1)

    output = args.output or args.input

    merge_markdown(
        input_path=args.input,
        output_path=output,
        learn=args.learn,
    )


if __name__ == "__main__":
    main()
