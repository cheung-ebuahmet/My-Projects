#!/usr/bin/env python3
"""轻量OCR：fitz渲染 → pytesseract → MD"""
import fitz, pytesseract, os, sys, time, re, json
from PIL import Image

def ocr_pdf(pdf_path, out_path, start=1, end=None, lang='chi_sim', dpi=200):
    d = fitz.open(pdf_path)
    total = len(d)
    if end is None: end = total

    buf = []
    t_start = time.time()
    for i in range(start-1, min(end, total)):
        t0 = time.time()
        pix = d[i].get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(img, lang=lang)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        buf.append(f'## 第{i+1}页\n\n{text}')
        t1 = time.time()
        elapsed = t1 - t0
        done = i - start + 2
        remain = min(end, total) - start + 1 - done
        avg = (t1 - t_start) / done
        eta = avg * remain
        print(f'[{done}/{min(end,total)-start+1}] p{i+1} {elapsed:.1f}s ETA{eta:.0f}s RSS={os.popen("ps -o rss= -p %d" % os.getpid()).read().strip()}KB')
        sys.stdout.flush()
        # 每20页写一次
        if len(buf) >= 20:
            with open(out_path, 'a', encoding='utf-8') as f:
                f.write('\n\n'.join(buf) + '\n\n')
            buf = []
    d.close()
    if buf:
        with open(out_path, 'a', encoding='utf-8') as f:
            f.write('\n\n'.join(buf))
    print(f'✅ 完成 {out_path}')
    return True

if __name__ == '__main__':
    pdf = sys.argv[1]
    out = sys.argv[3]
    start = int(sys.argv[5]) if len(sys.argv) > 5 else 1
    end = int(sys.argv[7]) if len(sys.argv) > 7 else None
    lang = sys.argv[9] if len(sys.argv) > 9 else 'chi_sim'
    ocr_pdf(pdf, out, start, end, lang)
