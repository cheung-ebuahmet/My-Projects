import os
import sys
import re
import json
from pathlib import Path
from PyPDF2 import PdfReader
from spellchecker import SpellChecker
from textblob import TextBlob
import jieba

# ============================================================
# 配置区
# ============================================================
INPUT_DIR = "input_pdfs"
OUTPUT_DIR = "output_reports"
DESKTOP_DIR = os.path.expanduser("~/Desktop")

# ============================================================
# 初始化
# ============================================================
spell = SpellChecker()
CHINESE_ERRORS = {}

def load_chinese_errors():
    """从 JSON 文件加载中文错别字库"""
    global CHINESE_ERRORS
    errors_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chinese_errors.json")
    if os.path.exists(errors_file):
        try:
            with open(errors_file, "r", encoding="utf-8") as f:
                CHINESE_ERRORS = json.load(f)
            print(f"   ✅ 已加载中文错别字库: {len(CHINESE_ERRORS)} 条规则")
        except Exception as e:
            print(f"   ⚠️  加载中文错别字库失败: {e}")
            CHINESE_ERRORS = {}
    else:
        print(f"   ⚠️  未找到中文错别字库文件: {errors_file}")
        CHINESE_ERRORS = {}

def init_folders():
    """确保输入输出文件夹存在"""
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"📁 文件夹就绪: {INPUT_DIR}/")
    print(f"📁 文件夹就绪: {OUTPUT_DIR}/")

def extract_text_from_pdf(pdf_path):
    """从 PDF 提取文字，返回 [(页码, 文字), ...]"""
    pages = []
    try:
        reader = PdfReader(pdf_path)
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                pages.append((i, text.strip()))
    except Exception as e:
        print(f"   ❌ 读取 PDF 失败: {e}")
    return pages

def is_chinese_text(text):
    """判断文本是否主要是中文"""
    if not text:
        return False
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = len(text.strip())
    if total_chars == 0:
        return False
    return chinese_chars / total_chars > 0.3

def check_chinese_spelling(text):
    """检查中文拼写（错别字）"""
    errors = []
    # 按标点符号和空格分割成短句
    sentences = re.split(r'[，。！？、；：""''（）\n\r\s]+', text)
    
    for sent in sentences:
        if not sent.strip():
            continue
        # 对每个错误词进行匹配
        for wrong, correct in CHINESE_ERRORS.items():
            if wrong in sent:
                # 找到具体位置
                idx = sent.find(wrong)
                start = max(0, idx - 10)
                end = min(len(sent), idx + len(wrong) + 10)
                context = sent[start:end]
                errors.append({
                    "wrong": wrong,
                    "correct": correct,
                    "context": context,
                    "position": idx
                })
    return errors

def check_chinese_grammar(text):
    """检查中文语法问题"""
    issues = []
    # 常见中文语法模式检查
    patterns = [
        (r'被[^被]{0,10}被', '重复使用"被"字'),
        (r'把[^把]{0,10}把', '重复使用"把"字'),
        (r'[。！？][^。！？]{0,5}[。！？]', '句号/感叹号/问号使用可能不当'),
    ]
    
    for pattern, desc in patterns:
        matches = re.finditer(pattern, text)
        for m in matches:
            context_start = max(0, m.start() - 10)
            context_end = min(len(text), m.end() + 10)
            context = text[context_start:context_end]
            issues.append({
                "text": m.group(),
                "description": desc,
                "context": context
            })
    
    return issues

def check_english_spelling(text):
    """检查英文拼写"""
    errors = []
    # 提取英文单词
    words = re.findall(r'\b[a-zA-Z]+\b', text)
    # 过滤掉明显是缩写或专有名词的大写词
    for word in words:
        if len(word) <= 1:
            continue
        # 跳过全大写的词（可能是缩写）
        if word.isupper() and len(word) <= 5:
            continue
        # 跳过包含数字的词
        if re.search(r'\d', word):
            continue
        # 拼写检查
        corrected = spell.correction(word)
        if corrected and corrected.lower() != word.lower():
            candidates = list(spell.candidates(word)) if spell.candidates(word) else []
            errors.append({
                "word": word,
                "suggestion": corrected,
                "candidates": candidates[:5]
            })
    return errors

def check_english_grammar(text):
    """检查英文语法"""
    issues = []
    # 提取英文句子
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for sent in sentences:
        sent = sent.strip()
        if not sent or len(sent) < 5:
            continue
        # 只检查包含英文单词的句子
        if not re.search(r'[a-zA-Z]{2,}', sent):
            continue
        try:
            blob = TextBlob(sent)
            corrected = str(blob.correct())
            if corrected.lower() != sent.lower():
                issues.append({
                    "original": sent[:100],
                    "suggestion": corrected[:100]
                })
        except:
            pass
    return issues

def generate_report(filename, pages_text, cn_spell_errors, cn_grammar_issues, 
                    en_spell_errors, en_grammar_issues, focus_hints=None):
    """生成检查报告"""
    base_name = os.path.splitext(filename)[0]
    report_path = os.path.join(OUTPUT_DIR, f"{base_name}_检查报告.txt")
    
    lines = []
    lines.append("=" * 60)
    lines.append("📝 PDF 拼写与语法检查报告")
    lines.append("=" * 60)
    lines.append(f"📄 文件: {filename}")
    lines.append(f"📊 总页数: {len(pages_text)}")
    lines.append("")
    
    if focus_hints:
        lines.append("🔍 重点检查区域（你指定的）：")
        for hint in focus_hints:
            lines.append(f"   • {hint}")
        lines.append("")
    
    # 中文拼写错误
    lines.append("-" * 60)
    lines.append(f"🔴 中文错别字检查（共 {len(cn_spell_errors)} 处）")
    lines.append("-" * 60)
    if cn_spell_errors:
        for i, err in enumerate(cn_spell_errors, 1):
            lines.append(f"  {i}. \"{err['wrong']}\" → 建议改为: \"{err['correct']}\"")
            lines.append(f"     原文片段: ...{err['context']}...")
            lines.append("")
    else:
        lines.append("  ✅ 未发现中文错别字\n")
    
    # 中文语法问题
    lines.append("-" * 60)
    lines.append(f"🟡 中文语法检查（共 {len(cn_grammar_issues)} 处）")
    lines.append("-" * 60)
    if cn_grammar_issues:
        for i, issue in enumerate(cn_grammar_issues, 1):
            lines.append(f"  {i}. 问题: {issue['description']}")
            lines.append(f"     原文: ...{issue['context']}...")
            lines.append("")
    else:
        lines.append("  ✅ 未发现明显中文语法问题\n")
    
    # 英文拼写错误
    lines.append("-" * 60)
    lines.append(f"🔴 英文拼写检查（共 {len(en_spell_errors)} 处）")
    lines.append("-" * 60)
    if en_spell_errors:
        for i, err in enumerate(en_spell_errors, 1):
            lines.append(f"  {i}. \"{err['word']}\" → 建议: {err['suggestion']}")
            if err['candidates']:
                lines.append(f"     其他建议: {', '.join(err['candidates'])}")
            lines.append("")
    else:
        lines.append("  ✅ 未发现英文拼写错误\n")
    
    # 英文语法问题
    lines.append("-" * 60)
    lines.append(f"🟡 英文语法检查（共 {len(en_grammar_issues)} 处）")
    lines.append("-" * 60)
    if en_grammar_issues:
        for i, issue in enumerate(en_grammar_issues, 1):
            lines.append(f"  {i}. 原文: \"{issue['original']}\"")
            lines.append(f"     建议: \"{issue['suggestion']}\"")
            lines.append("")
    else:
        lines.append("  ✅ 未发现英文语法问题\n")
    
    # 全文预览（前2000字）
    lines.append("-" * 60)
    lines.append("📖 全文预览（前 2000 字符）")
    lines.append("-" * 60)
    full_text = "\n".join([t for _, t in pages_text])
    preview = full_text[:2000]
    lines.append(preview)
    lines.append("\n...（以下省略）\n")
    
    lines.append("=" * 60)
    lines.append("📊 检查汇总")
    lines.append(f"   中文错别字: {len(cn_spell_errors)} 处")
    lines.append(f"   中文语法问题: {len(cn_grammar_issues)} 处")
    lines.append(f"   英文拼写错误: {len(en_spell_errors)} 处")
    lines.append(f"   英文语法问题: {len(en_grammar_issues)} 处")
    lines.append("=" * 60)
    
    report_content = "\n".join(lines)
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    
    return report_path, report_content

def process_single_pdf(pdf_path, focus_hints=None, output_to_desktop=False):
    """处理单个 PDF 文件"""
    filename = os.path.basename(pdf_path)
    print(f"📄 正在处理文件: {filename} ...")
    
    # 提取文字
    pages_text = extract_text_from_pdf(pdf_path)
    if not pages_text:
        print(f"   ⚠️  无法从 {filename} 中提取文字（可能是扫描件，建议先用 OCR 处理）\n")
        return None
    
    full_text = "\n".join([t for _, t in pages_text])
    print(f"   📖 成功提取 {len(pages_text)} 页，共 {len(full_text)} 字符")
    
    # 判断文本类型
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', full_text))
    has_english = bool(re.search(r'[a-zA-Z]', full_text))
    
    cn_spell_errors = []
    cn_grammar_issues = []
    en_spell_errors = []
    en_grammar_issues = []
    
    # 中文检查
    if has_chinese:
        print(f"   🔍 正在检查中文错别字...")
        cn_spell_errors = check_chinese_spelling(full_text)
        print(f"   🔍 正在检查中文语法...")
        cn_grammar_issues = check_chinese_grammar(full_text)
    
    # 英文检查
    if has_english:
        print(f"   🔍 正在检查英文拼写...")
        en_spell_errors = check_english_spelling(full_text)
        print(f"   🔍 正在检查英文语法...")
        en_grammar_issues = check_english_grammar(full_text)
    
    # 生成报告
    report_path, report_content = generate_report(
        filename, pages_text, cn_spell_errors, cn_grammar_issues,
        en_spell_errors, en_grammar_issues, focus_hints
    )
    
    # 如果要求输出到桌面，复制一份到桌面
    if output_to_desktop:
        desktop_path = os.path.join(DESKTOP_DIR, os.path.basename(report_path))
        with open(desktop_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(f"   ✅ 报告已复制到桌面: {desktop_path}")
    
    print(f"   ✅ 完成 → {report_path}")
    print(f"      📊 中文错别字: {len(cn_spell_errors)} 处 | 中文语法: {len(cn_grammar_issues)} 处")
    print(f"      📊 英文拼写: {len(en_spell_errors)} 处 | 英文语法: {len(en_grammar_issues)} 处\n")
    
    return {
        "filename": filename,
        "pages": len(pages_text),
        "cn_spell": len(cn_spell_errors),
        "cn_grammar": len(cn_grammar_issues),
        "en_spell": len(en_spell_errors),
        "en_grammar": len(en_grammar_issues),
        "report_path": report_path
    }

def main():
    print("=" * 60)
    print("📝 PDF 拼写与语法检查工具")
    print("   功能：提取 PDF 文字 → 中文错别字检查 → 英文拼写检查 → 语法检查 → 生成报告")
    print("=" * 60)
    print()
    
    # 1. 初始化文件夹
    init_folders()
    
    # 2. 加载中文错别字库
    load_chinese_errors()
    
    # 3. 检查是否通过命令行参数传入了文件路径
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        if not os.path.exists(pdf_path):
            print(f"❌ 文件不存在: {pdf_path}")
            return
        if not pdf_path.lower().endswith(".pdf"):
            print(f"❌ 不是 PDF 文件: {pdf_path}")
            return
        
        # 询问重点检查区域
        print("\n💡 提示：你可以告诉我重点检查哪些内容（例如：'重点检查人名翻译一致性'）")
        print("   如果不需要，直接按回车跳过。")
        focus_input = input("👉 请输入重点检查提示（可选）: ").strip()
        focus_hints = [h.strip() for h in focus_input.split("、") if h.strip()] if focus_input else None
        if focus_hints:
            print(f"   ✅ 已记录 {len(focus_hints)} 条重点提示\n")
        
        # 处理单个文件，输出到桌面
        result = process_single_pdf(pdf_path, focus_hints, output_to_desktop=True)
        
        if result:
            print("=" * 60)
            print("🎉 检查完毕！报告已保存至:")
            print(f"   📁 项目目录: {result['report_path']}")
            print(f"   🖥️  桌面: {DESKTOP_DIR}/{os.path.basename(result['report_path'])}")
            print("=" * 60)
        return
    
    # 4. 如果没有传入参数，扫描 input_pdfs 文件夹
    pdf_files = sorted([f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".pdf")])
    total = len(pdf_files)
    
    if total == 0:
        print(f"\n⚠️  {INPUT_DIR}/ 文件夹中没有找到 PDF 文件。")
        print(f"   请将 .pdf 文件放入 {INPUT_DIR}/ 后重新运行。\n")
        print(f"   或者直接传入文件路径: python pdf_spell_check.py /路径/到/文件.pdf\n")
        return
    
    print(f"🔍 共发现 {total} 个 PDF 文件\n")
    
    # 5. 询问重点检查区域
    print("💡 提示：你可以告诉我重点检查哪些内容（例如：'重点检查人名翻译一致性'）")
    print("   如果不需要，直接按回车跳过。")
    focus_input = input("👉 请输入重点检查提示（可选）: ").strip()
    focus_hints = [h.strip() for h in focus_input.split("、") if h.strip()] if focus_input else None
    if focus_hints:
        print(f"   ✅ 已记录 {len(focus_hints)} 条重点提示\n")
    
    # 6. 逐文件处理
    all_results = []
    for idx, filename in enumerate(pdf_files, start=1):
        print(f"📄 正在处理第 {idx}/{total} 个文件: {filename} ...")
        pdf_path = os.path.join(INPUT_DIR, filename)
        result = process_single_pdf(pdf_path, focus_hints)
        if result:
            all_results.append(result)
    
    # 7. 汇总
    if all_results:
        print("=" * 60)
        print("🎉 全部检查完毕！报告已保存至 output_reports/ 文件夹")
        print("=" * 60)

if __name__ == "__main__":
    main()
