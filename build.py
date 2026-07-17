# -*- coding: utf-8 -*-
"""
分隊入口網 建置腳本

掃描 content/ 目錄結構，產出 docs/（GitHub Pages 根目錄）。

目錄約定
--------
content/<區塊>/<類別>/
  區塊、類別的資料夾名可加數字前綴控制排序，顯示時會去掉：
    10-生活/  →  顯示「生活」，排在 20-公務 前面

類別型態（由該類別資料夾內的 _index.md 的 type: 決定，預設 gallery）
  gallery  圖片卡片牆。掃描 *.jpg/*.png，同名 .md 為選配的補充資料。
  doc      業務說明頁。_index.md 為內文，files/ 內的檔案成為附件下載區。
  files    純檔案清單。files/ 內的檔案（沒有的話就掃類別資料夾本身）。

新增一個業務 = 開一個資料夾，不需要改這支腳本。
"""
import html
import json
import re
import shutil
from pathlib import Path
from urllib.parse import quote

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

BASE = Path(__file__).parent
CONTENT = BASE / 'content'
DOCS = BASE / 'docs'
ASSETS = DOCS / 'assets'

IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
THUMB_WIDTH = 480
THUMB_QUALITY = 78

ORDER_RE = re.compile(r'^(\d+)[-_](.+)$')


# --------------------------------------------------------------------------
# 目錄名稱：數字前綴 → 排序權重
# --------------------------------------------------------------------------

def parse_name(name: str):
    """'10-生活' → (10, '生活')；沒有前綴的排到最後，依名稱排。"""
    m = ORDER_RE.match(name)
    if m:
        return int(m.group(1)), m.group(2)
    return 9999, name


def sorted_dirs(d: Path):
    subs = [p for p in d.iterdir() if p.is_dir() and not p.name.startswith(('_', '.'))]
    return sorted(subs, key=lambda p: (parse_name(p.name), p.name))


# --------------------------------------------------------------------------
# Frontmatter：不依賴 PyYAML，只支援 key: value 與逗號分隔的 tags
# --------------------------------------------------------------------------

LIST_KEYS = {'tags'}


def parse_frontmatter(text: str):
    """回傳 (meta_dict, body_markdown)。沒有 frontmatter 就回 ({}, 全文)。"""
    if not text.startswith('---'):
        return {}, text
    parts = text.split('---', 2)
    if len(parts) < 3:
        return {}, text
    meta = {}
    for line in parts[1].strip().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or ':' not in line:
            continue
        key, _, val = line.partition(':')
        key, val = key.strip(), val.strip()
        if key in LIST_KEYS:
            meta[key] = [t.strip() for t in val.split(',') if t.strip()]
        else:
            meta[key] = val
    return meta, parts[2].strip()


def read_md(p: Path):
    if not p.exists():
        return {}, ''
    return parse_frontmatter(p.read_text(encoding='utf-8').strip())


# --------------------------------------------------------------------------
# Mini markdown → HTML（夠用於業務說明：標題、清單、粗體、連結、引言、程式碼）
# --------------------------------------------------------------------------

def inline_md(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', s)
    s = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        lambda m: f'<a href="{html.escape(m.group(2), quote=True)}" '
                  f'target="_blank" rel="noopener">{m.group(1)}</a>',
        s,
    )
    return s


def render_md(text: str) -> str:
    """有序清單會被渲染成帶編號的步驟卡片，這是業務說明的主要用途。"""
    if not text.strip():
        return ''
    out, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # 圍欄程式碼區塊：整段原樣輸出，不做任何 inline 解析
        if stripped.startswith('```'):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith('```'):
                buf.append(lines[i])
                i += 1
            i += 1  # 跳過收尾的 ```
            out.append(f'<pre><code>{html.escape(chr(10).join(buf))}</code></pre>')
            continue

        m = re.match(r'^(#{1,4})\s+(.*)', stripped)
        if m:
            lv = len(m.group(1))
            out.append(f'<h{lv}>{inline_md(m.group(2))}</h{lv}>')
            i += 1
            continue

        # 有序清單 → 步驟
        if re.match(r'^\d+[.)]\s+', stripped):
            steps = []
            while i < len(lines) and re.match(r'^\d+[.)]\s+', lines[i].strip()):
                steps.append(re.sub(r'^\d+[.)]\s+', '', lines[i].strip()))
                i += 1
            items = ''.join(
                f'<li><span class="step-num">{n}</span>'
                f'<div class="step-text">{inline_md(s)}</div></li>'
                for n, s in enumerate(steps, 1)
            )
            out.append(f'<ol class="steps">{items}</ol>')
            continue

        # 無序清單
        if re.match(r'^[-*+]\s+', stripped):
            items = []
            while i < len(lines) and re.match(r'^[-*+]\s+', lines[i].strip()):
                items.append(re.sub(r'^[-*+]\s+', '', lines[i].strip()))
                i += 1
            body = ''.join(f'<li>{inline_md(x)}</li>' for x in items)
            out.append(f'<ul class="bullets">{body}</ul>')
            continue

        # 引言 → 注意事項
        if stripped.startswith('>'):
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith('>'):
                quote_lines.append(lines[i].strip().lstrip('>').strip())
                i += 1
            out.append(f'<blockquote>{inline_md(" ".join(quote_lines))}</blockquote>')
            continue

        # 段落
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(
            r'^(#{1,4}\s|[-*+]\s|\d+[.)]\s|>|```)', lines[i].strip()
        ):
            para.append(lines[i].strip())
            i += 1
        if para:
            out.append(f'<p>{inline_md(" ".join(para))}</p>')

    return '\n'.join(out)


# --------------------------------------------------------------------------
# 資產：複製原檔 + 產生縮圖
# --------------------------------------------------------------------------

_stats = {'copied': 0, 'thumbed': 0, 'skipped': 0}
_written = set()  # 這次建置實際產出的資產（用來清掉孤兒檔）


def copy_asset(src: Path, rel_dir: str) -> str:
    """複製到 docs/assets/<rel_dir>/，回傳給 HTML 用的 URL。"""
    dest_dir = ASSETS / rel_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime:
        shutil.copy2(src, dest)
        _stats['copied'] += 1
    else:
        _stats['skipped'] += 1
    _written.add(dest.resolve())
    return 'assets/' + quote(f'{rel_dir}/{src.name}')


def make_thumb(src: Path, rel_dir: str) -> str:
    """產生縮圖；沒有 Pillow 就退回原圖（只是比較吃流量，不會壞）。"""
    if not HAS_PIL:
        return copy_asset(src, rel_dir)
    dest_dir = ASSETS / rel_dir / 'thumbs'
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / (src.stem + '.jpg')
    if not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime:
        with Image.open(src) as im:
            im = im.convert('RGB')
            w, h = im.size
            if w > THUMB_WIDTH:
                im = im.resize(
                    (THUMB_WIDTH, round(h * THUMB_WIDTH / w)), Image.LANCZOS
                )
            im.save(dest, 'JPEG', quality=THUMB_QUALITY, optimize=True)
        _stats['thumbed'] += 1
    _written.add(dest.resolve())
    return 'assets/' + quote(f'{rel_dir}/thumbs/{dest.name}')


def human_size(n: int) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return f'{n:.0f} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1024
    return f'{n:.1f} TB'


def collect_files(d: Path, rel_dir: str):
    if not d.exists():
        return []
    out = []
    for f in sorted(d.iterdir()):
        if not f.is_file() or f.name.startswith(('_', '.')):
            continue
        out.append({
            'name': f.name,
            'stem': f.stem,
            'ext': f.suffix.lstrip('.').upper(),
            'size': human_size(f.stat().st_size),
            'url': copy_asset(f, rel_dir),
        })
    return out


# --------------------------------------------------------------------------
# 掃描 content/
# --------------------------------------------------------------------------

def build_gallery(cat_dir: Path, rel_dir: str, path_id: str):
    items = []
    for f in sorted(cat_dir.iterdir()):
        if not f.is_file() or f.suffix.lower() not in IMAGE_EXT:
            continue
        if f.name.startswith(('_', '.')):
            continue
        meta, body = read_md(f.with_suffix('.md'))
        title = meta.get('title', f.stem)
        # 圖旁邊的同名資料夾 = 這張圖的附件（懶人包的可下載檔案）
        attach = cat_dir / f.stem
        files = collect_files(attach, f'{rel_dir}/{f.stem}') if attach.is_dir() else []
        items.append({
            'id': f'{path_id}/{f.stem}',
            'title': title,
            'img': copy_asset(f, rel_dir),
            'thumb': make_thumb(f, rel_dir),
            'phone': meta.get('phone', ''),
            'address': meta.get('address', ''),
            'tags': meta.get('tags', []),
            'note': render_md(body),
            'files': files,
            'search': ' '.join([
                title, meta.get('address', ''),
                ' '.join(meta.get('tags', [])), body,
                ' '.join(x['name'] for x in files),
            ]).lower(),
        })
    return items


def build_category(sec_slug: str, cat_dir: Path):
    order, cat_name = parse_name(cat_dir.name)
    meta, body = read_md(cat_dir / '_index.md')
    cat_slug = meta.get('title', cat_name)
    path_id = f'{sec_slug}/{cat_slug}'
    rel_dir = f'{sec_slug}/{cat_slug}'
    ctype = meta.get('type', 'gallery')

    cat = {
        'id': path_id,
        'name': cat_slug,
        'icon': meta.get('icon', ''),
        'type': ctype,
        'desc': meta.get('desc', ''),
        'body': render_md(body),
        'items': [],
        'files': [],
        'images': [],
    }

    if ctype == 'gallery':
        cat['items'] = build_gallery(cat_dir, rel_dir, path_id)
        cat['count'] = len(cat['items'])
    else:
        files_dir = cat_dir / 'files'
        if files_dir.exists():
            cat['files'] = collect_files(files_dir, f'{rel_dir}/files')
        elif ctype == 'files':
            cat['files'] = collect_files(cat_dir, f'{rel_dir}/files')
        # doc 頁可把資料夾內的圖片依序直接內嵌顯示（例如公文掃描頁）
        if ctype == 'doc':
            for f in sorted(cat_dir.iterdir()):
                if (f.is_file() and f.suffix.lower() in IMAGE_EXT
                        and not f.name.startswith(('_', '.'))):
                    cat['images'].append({
                        'full': copy_asset(f, rel_dir),
                        'alt': parse_name(f.stem)[1],
                    })
        cat['count'] = len(cat['files'])

    cat['search'] = ' '.join(
        [cat_slug, meta.get('desc', ''), body]
        + [f['name'] for f in cat['files']]
        + [im['alt'] for im in cat['images']]
    ).lower()
    return cat


def scan():
    if not CONTENT.exists():
        raise SystemExit(f'找不到 content/ 目錄：{CONTENT}')
    sections = []
    for sec_dir in sorted_dirs(CONTENT):
        _, sec_name = parse_name(sec_dir.name)
        smeta, _ = read_md(sec_dir / '_index.md')
        sec_slug = smeta.get('title', sec_name)
        cats = [build_category(sec_slug, c) for c in sorted_dirs(sec_dir)]
        cats = [c for c in cats if c['count'] or c['body'] or c['images']]
        if cats:
            sections.append({
                'id': sec_slug,
                'name': sec_slug,
                'icon': smeta.get('icon', ''),
                'categories': cats,
            })
    return sections


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>分隊資訊站</title>
<style>
  *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
  body{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Microsoft JhengHei","PingFang TC",sans-serif;
    color:#1f2937;background:#fafafa;line-height:1.6;
    -webkit-font-smoothing:antialiased;
  }
  .layout{display:grid;grid-template-columns:250px 1fr;min-height:100vh}

  /* ---------- Sidebar ---------- */
  .sidebar{
    background:#fff;border-right:1px solid #eee;
    padding:24px 12px;position:sticky;top:0;height:100vh;overflow-y:auto;
  }
  .brand{
    display:flex;align-items:center;gap:8px;
    font-size:16px;font-weight:600;color:#111;padding:4px 10px 18px;
  }
  .sec-label{
    font-size:11px;font-weight:700;color:#9ca3af;
    letter-spacing:.08em;padding:14px 12px 6px;text-transform:uppercase;
  }
  .nav-item{
    display:flex;align-items:center;gap:10px;
    padding:10px 12px;margin-bottom:2px;border-radius:8px;cursor:pointer;
    font-size:14.5px;color:#374151;user-select:none;
    transition:background .15s,color .15s;
  }
  .nav-item:hover{background:#f5f5f5}
  .nav-item.active{background:#fff4ea;color:#c2410c;font-weight:600}
  .nav-icon{width:18px;text-align:center;flex-shrink:0;font-size:15px}
  .nav-count{margin-left:auto;color:#9ca3af;font-size:12.5px}
  .nav-item.active .nav-count{color:#c2410c}

  /* ---------- Main ---------- */
  .main{padding:30px 40px 60px;max-width:1400px}
  .top-bar{display:flex;align-items:center;gap:16px;margin-bottom:8px}
  .page-title{font-size:22px;font-weight:600;color:#111;display:flex;align-items:baseline;gap:10px}
  .page-title .count{font-size:14px;color:#9ca3af;font-weight:400}
  .page-desc{color:#6b7280;font-size:14px;margin-bottom:22px}
  .search{position:relative;flex:1;max-width:400px;margin-left:auto}
  .search-icon{position:absolute;left:14px;top:50%;transform:translateY(-50%);color:#9ca3af;font-size:15px;pointer-events:none}
  .search input{
    width:100%;padding:10px 16px 10px 40px;
    border:1px solid #e5e7eb;border-radius:10px;font-size:14px;
    background:#fff;font-family:inherit;transition:border-color .15s,box-shadow .15s;
  }
  .search input:focus{outline:none;border-color:#f59e0b;box-shadow:0 0 0 3px rgba(245,158,11,.12)}

  /* ---------- Gallery ---------- */
  .gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:20px}
  .card{
    background:#fff;border:1px solid #eee;border-radius:12px;overflow:hidden;
    display:flex;flex-direction:column;transition:box-shadow .2s,transform .2s;
  }
  .card:hover{box-shadow:0 4px 16px rgba(0,0,0,.06);transform:translateY(-2px)}
  .card-image-wrap{aspect-ratio:3/4;background:#f5f5f5;overflow:hidden;cursor:zoom-in;position:relative}
  .card-image{width:100%;height:100%;object-fit:cover;display:block;transition:transform .3s}
  .card:hover .card-image{transform:scale(1.03)}
  .dl-badge{
    position:absolute;top:8px;right:8px;
    background:rgba(17,24,39,.82);color:#fff;font-size:12px;font-weight:600;
    padding:3px 9px;border-radius:99px;
  }
  .card-body{padding:14px 16px 16px;display:flex;flex-direction:column;gap:8px;flex:1}
  .card-title{font-size:15px;font-weight:600;color:#111}
  .card-meta{font-size:12.5px;color:#6b7280;display:flex;flex-direction:column;gap:3px}
  .card-meta a{color:#c2410c;text-decoration:none}
  .card-meta a:hover{text-decoration:underline}
  .tags{display:flex;flex-wrap:wrap;gap:5px}
  .tag{background:#fff4ea;color:#c2410c;font-size:11px;padding:2px 8px;border-radius:99px;font-weight:500}
  .card-note{font-size:12.5px;color:#6b7280;border-top:1px solid #f3f4f6;padding-top:8px}
  .card-note p{margin:0}
  .card-files{display:flex;flex-direction:column;gap:6px;margin-top:auto}
  .chip{
    display:flex;align-items:center;gap:9px;padding:8px 10px;width:100%;
    border:1px solid #e5e7eb;border-radius:8px;background:#fff;cursor:pointer;
    font-family:inherit;text-align:left;
    transition:border-color .15s,background .15s;
  }
  .chip:hover{border-color:#06c755;background:#f0fdf4}
  .chip-ext{
    flex-shrink:0;font-size:10px;font-weight:700;color:#c2410c;background:#fff4ea;
    padding:3px 6px;border-radius:5px;min-width:36px;text-align:center;
  }
  .chip-name{font-size:13px;color:#374151;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .chip-line{
    margin-left:auto;flex-shrink:0;white-space:nowrap;
    font-size:12px;font-weight:700;color:#fff;background:#06c755;
    padding:5px 10px;border-radius:6px;
  }
  .card-actions{display:flex;gap:8px;margin-top:auto;padding-top:4px}
  .btn{
    display:inline-flex;align-items:center;justify-content:center;gap:5px;
    padding:8px 12px;border-radius:8px;font-size:13px;font-weight:500;
    cursor:pointer;border:1px solid transparent;text-decoration:none;
    font-family:inherit;flex:1;transition:background .15s,border-color .15s;
  }
  .btn-line{background:#06c755;color:#fff}
  .btn-line:hover{background:#05a648}
  .btn-copy{background:#fff;color:#4b5563;border-color:#e5e7eb}
  .btn-copy:hover{background:#f9fafb;border-color:#d1d5db}
  .btn.copied{background:#10b981;color:#fff;border-color:#10b981}

  /* ---------- Doc ---------- */
  .doc{background:#fff;border:1px solid #eee;border-radius:12px;padding:32px 36px;max-width:820px}
  .doc h1{font-size:20px;margin:26px 0 12px;color:#111;font-weight:600}
  .doc h2{font-size:18px;margin:28px 0 12px;color:#111;font-weight:600}
  .doc h1:first-child,.doc h2:first-child{margin-top:0}
  .doc h3{font-size:15.5px;margin:20px 0 8px;color:#374151;font-weight:600}
  .doc h4{font-size:14.5px;margin:16px 0 6px;color:#4b5563;font-weight:600}
  .doc p{margin:10px 0;color:#374151;font-size:14.5px}
  .doc code{background:#f3f4f6;padding:2px 6px;border-radius:4px;font-size:13px;font-family:ui-monospace,Menlo,Consolas,monospace}
  .doc pre{
    background:#1f2937;padding:14px 16px;border-radius:8px;
    overflow-x:auto;margin:14px 0;
  }
  .doc pre code{
    background:none;padding:0;color:#e5e7eb;font-size:12.5px;line-height:1.7;
    white-space:pre;
  }
  .doc a{color:#c2410c}
  .doc blockquote{
    border-left:3px solid #f59e0b;background:#fffbeb;
    padding:12px 16px;margin:16px 0;border-radius:0 8px 8px 0;
    color:#92400e;font-size:14px;
  }
  .bullets{margin:10px 0 10px 20px;color:#374151;font-size:14.5px}
  .bullets li{margin:5px 0}
  .steps{list-style:none;margin:16px 0;display:flex;flex-direction:column;gap:2px}
  .steps li{display:flex;gap:14px;padding:12px 0;border-bottom:1px solid #f3f4f6}
  .steps li:last-child{border-bottom:none}
  .step-num{
    flex-shrink:0;width:26px;height:26px;border-radius:50%;
    background:#fff4ea;color:#c2410c;font-size:13px;font-weight:700;
    display:flex;align-items:center;justify-content:center;margin-top:1px;
  }
  .step-text{font-size:14.5px;color:#374151;padding-top:2px}

  /* ---------- Doc inline images ---------- */
  .doc-images{display:flex;flex-direction:column;gap:16px;max-width:820px;margin-top:20px}
  .doc-image{
    width:100%;height:auto;display:block;background:#f5f5f5;
    border:1px solid #eee;border-radius:10px;cursor:zoom-in;
  }

  /* ---------- Files ---------- */
  .files{margin-top:28px;max-width:820px}
  .files-head{font-size:13px;font-weight:700;color:#9ca3af;letter-spacing:.06em;margin-bottom:10px}
  .file-row{
    display:flex;align-items:center;gap:14px;background:#fff;
    border:1px solid #eee;border-radius:10px;padding:13px 16px;margin-bottom:8px;
    color:inherit;
  }
  .file-ext{
    flex-shrink:0;width:44px;height:44px;border-radius:8px;background:#fff4ea;
    color:#c2410c;font-size:10.5px;font-weight:700;
    display:flex;align-items:center;justify-content:center;
  }
  .file-info{flex:1;min-width:0}
  .file-name{font-size:14.5px;color:#111;font-weight:500}
  .file-size{font-size:12.5px;color:#9ca3af;margin-top:1px}
  .btn-fileline{
    flex-shrink:0;font-size:13px;font-weight:700;color:#fff;background:#06c755;
    border:none;border-radius:8px;padding:9px 16px;cursor:pointer;font-family:inherit;
  }
  .btn-fileline:hover{background:#05a648}

  /* ---------- Search results ---------- */
  .result-group{margin-bottom:28px}
  .result-label{
    font-size:12px;font-weight:700;color:#9ca3af;letter-spacing:.06em;
    margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid #eee;
  }

  /* ---------- Modal ---------- */
  .modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.92);z-index:1000;justify-content:center;align-items:center;padding:24px}
  .modal.open{display:flex}
  .modal-inner{display:flex;flex-direction:column;gap:14px;align-items:center;max-width:100%;max-height:100%}
  .modal-inner img{max-width:100%;max-height:calc(100vh - 150px);border-radius:6px;object-fit:contain}
  .modal-files{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;max-width:680px}
  .chip-dark{background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.18)}
  .chip-dark:hover{background:rgba(255,255,255,.16);border-color:#06c755}
  .chip-dark .chip-name{color:#f3f4f6}
  .chip-dark .chip-ext{background:rgba(245,158,11,.2);color:#fcd34d}
  .modal-close{
    position:absolute;top:16px;right:20px;color:#fff;font-size:32px;line-height:1;
    background:none;border:none;cursor:pointer;width:44px;height:44px;border-radius:50%;
    display:flex;align-items:center;justify-content:center;transition:background .15s;
  }
  .modal-close:hover{background:rgba(255,255,255,.12)}

  .empty{text-align:center;padding:80px 20px;color:#9ca3af;font-size:15px}
  .toast{
    position:fixed;bottom:32px;left:50%;transform:translateX(-50%) translateY(100px);
    background:#111;color:#fff;padding:12px 20px;border-radius:8px;font-size:14px;
    z-index:2000;opacity:0;transition:opacity .2s,transform .2s;pointer-events:none;
  }
  .toast.show{opacity:1;transform:translateX(-50%) translateY(0)}

  /* ---------- Mobile ---------- */
  @media(max-width:768px){
    .layout{grid-template-columns:1fr}
    .sidebar{
      position:sticky;top:0;height:auto;padding:10px;display:flex;gap:6px;
      border-right:none;border-bottom:1px solid #eee;overflow-x:auto;z-index:10;
    }
    .brand,.sec-label{display:none}
    .nav-item{flex-shrink:0;margin-bottom:0;padding:8px 14px;white-space:nowrap}
    .nav-count{margin-left:6px}
    .main{padding:18px 14px 40px}
    .top-bar{flex-direction:column;align-items:stretch;gap:10px}
    .search{max-width:none;margin-left:0}
    .gallery{grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}
    .card-body{padding:12px}
    .doc{padding:22px 18px}
    .btn{padding:7px 8px;font-size:12px}
  }
</style>
</head>
<body>

<div class="layout">
  <aside class="sidebar">
    <div class="brand"><span>🚒</span><span>分隊資訊站</span></div>
    <nav id="nav"></nav>
  </aside>

  <main class="main">
    <div class="top-bar">
      <div class="page-title">
        <span id="pageTitle"></span>
        <span class="count" id="pageCount"></span>
      </div>
      <div class="search">
        <span class="search-icon">🔍</span>
        <input type="text" id="searchInput" placeholder="搜尋全站（店家、業務、表單…）" autocomplete="off">
      </div>
    </div>
    <div class="page-desc" id="pageDesc"></div>
    <div id="content"></div>
    <div class="empty" id="empty" style="display:none">找不到符合的項目</div>
  </main>
</div>

<div class="modal" id="modal">
  <button class="modal-close" id="modalClose" aria-label="關閉">×</button>
  <div class="modal-inner">
    <img id="modalImg" src="" alt="">
    <div class="modal-files" id="modalFiles"></div>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
const DATA = __DATA__;

const $ = id => document.getElementById(id);
const nav = $('nav'), content = $('content'), empty = $('empty');
const pageTitle = $('pageTitle'), pageCount = $('pageCount'), pageDesc = $('pageDesc');
const modal = $('modal'), modalImg = $('modalImg'), modalFiles = $('modalFiles'), toast = $('toast');

// 攤平成 id → category，id 是「區塊/類別」這種語意路徑，跟排序脫鉤。
const CATS = {};
DATA.forEach(sec => sec.categories.forEach(c => { CATS[c.id] = { ...c, section: sec.name }; }));

let currentCat = DATA[0]?.categories[0]?.id || '';
let currentQuery = '';

const esc = s => String(s).replace(/[&<>"']/g, c =>
  ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' })[c]);

/* ---------- Sidebar ---------- */
nav.innerHTML = DATA.map(sec => `
  <div class="sec-label">${esc(sec.name)}</div>
  ${sec.categories.map(c => `
    <div class="nav-item" data-cat="${esc(c.id)}">
      <span class="nav-icon">${c.icon || '•'}</span>
      <span>${esc(c.name)}</span>
      <span class="nav-count">${c.type === 'gallery' && c.count ? c.count : ''}</span>
    </div>`).join('')}
`).join('');

function setActiveNav() {
  document.querySelectorAll('.nav-item').forEach(el =>
    el.classList.toggle('active', !currentQuery && el.dataset.cat === currentCat));
}

/* ---------- Renderers ---------- */
function cardHtml(item, i) {
  const meta = [];
  if (item.phone) meta.push(`<span>📞 <a href="tel:${esc(item.phone)}">${esc(item.phone)}</a></span>`);
  if (item.address) meta.push(`<span>📍 ${esc(item.address)}</span>`);
  // 首屏的圖一定會被看到，lazy 只會延後它們；第一排之後才交給 lazy。
  const lazy = i >= 6 ? ' loading="lazy"' : '';
  const files = item.files || [];
  return `
    <div class="card" data-id="${esc(item.id)}">
      <div class="card-image-wrap" data-action="zoom">
        <img class="card-image" src="${item.thumb}" alt="${esc(item.title)}"${lazy}>
        ${files.length ? `<span class="dl-badge">📎 ${files.length}</span>` : ''}
      </div>
      <div class="card-body">
        <div class="card-title">${esc(item.title)}</div>
        ${meta.length ? `<div class="card-meta">${meta.join('')}</div>` : ''}
        ${item.tags.length ? `<div class="tags">${item.tags.map(t => `<span class="tag">${esc(t)}</span>`).join('')}</div>` : ''}
        ${item.note ? `<div class="card-note">${item.note}</div>` : ''}
        ${files.length
          ? `<div class="card-files">${files.map(f => fileChip(f)).join('')}</div>`
          : `<div class="card-actions">
          <button class="btn btn-copy" data-action="copy">📋 複製連結</button>
          <button class="btn btn-line" data-action="line">傳到 LINE</button>
        </div>`}
      </div>
    </div>`;
}

function fileChip(f, dark) {
  return `<button class="chip${dark ? ' chip-dark' : ''}" data-action="fileline" data-url="${esc(f.url)}">
    <span class="chip-ext">${esc(f.ext)}</span>
    <span class="chip-name">${esc(f.stem)}</span>
    <span class="chip-line">傳到 LINE</span></button>`;
}

function filesHtml(files, heading) {
  if (!files.length) return '';
  return `
    <div class="files">
      ${heading ? `<div class="files-head">${esc(heading)}</div>` : ''}
      ${files.map(f => `
        <div class="file-row">
          <div class="file-ext">${esc(f.ext)}</div>
          <div class="file-info">
            <div class="file-name">${esc(f.stem)}</div>
            <div class="file-size">${esc(f.ext)} · ${esc(f.size)}</div>
          </div>
          <button class="btn-fileline" data-action="fileline" data-url="${esc(f.url)}">傳到 LINE</button>
        </div>`).join('')}
    </div>`;
}

function renderCategory(cat) {
  pageTitle.textContent = cat.name;
  pageCount.textContent = cat.type === 'gallery' ? `共 ${cat.count} 家` :
    cat.count ? `${cat.count} 份文件` : '';
  pageDesc.textContent = cat.desc || '';

  if (cat.type === 'gallery') {
    content.innerHTML = `<div class="gallery">${cat.items.map(cardHtml).join('')}</div>`;
  } else {
    const imgs = (cat.images || []).map(im =>
      `<img class="doc-image" data-action="docimg" data-full="${im.full}" src="${im.full}" alt="${esc(im.alt)}" loading="lazy">`
    ).join('');
    content.innerHTML =
      (cat.body ? `<div class="doc">${cat.body}</div>` : '') +
      (imgs ? `<div class="doc-images">${imgs}</div>` : '') +
      filesHtml(cat.files, '傳到 LINE');
  }
  empty.style.display = (cat.count || cat.body || (cat.images && cat.images.length)) ? 'none' : 'block';
}

function renderSearch(q) {
  pageTitle.textContent = '搜尋結果';
  pageDesc.textContent = `關鍵字：${q}`;
  let total = 0;
  const groups = Object.values(CATS).map(cat => {
    const items = (cat.items || []).filter(x => x.search.includes(q));
    const files = (cat.files || []).filter(f => f.name.toLowerCase().includes(q));
    const catHit = cat.search.includes(q);
    if (!items.length && !files.length && !catHit) return '';
    total += items.length + files.length + (catHit && !items.length && !files.length ? 1 : 0);
    const label = `${cat.section} / ${cat.name}`;
    let body = '';
    if (items.length) body += `<div class="gallery">${items.map(cardHtml).join('')}</div>`;
    if (files.length) body += filesHtml(files, '');
    if (!body && catHit) {
      body = `<div class="file-row" data-action="goto" data-goto="${esc(cat.id)}" style="cursor:pointer">
        <div class="file-ext">${cat.icon || '📄'}</div>
        <div><div class="file-name">${esc(cat.name)}</div>
        <div class="file-size">${esc(cat.desc || '符合此業務說明')}</div></div>
        <div class="file-dl">前往 →</div></div>`;
    }
    return `<div class="result-group"><div class="result-label">${esc(label)}</div>${body}</div>`;
  }).filter(Boolean);

  pageCount.textContent = `${total} 筆`;
  content.innerHTML = groups.join('');
  empty.style.display = total ? 'none' : 'block';
}

function render() {
  if (currentQuery) renderSearch(currentQuery);
  else if (CATS[currentCat]) renderCategory(CATS[currentCat]);
  setActiveNav();
}

/* ---------- Share ---------- */
function findItem(id) {
  for (const c of Object.values(CATS)) {
    const hit = (c.items || []).find(x => x.id === id);
    if (hit) return hit;
  }
  return null;
}

// 語意路徑當 hash：新增資料不會讓舊連結指到別家店。
const shareUrl = id =>
  location.origin + location.pathname + '#' + encodeURIComponent(id);

function shareLine(id) {
  window.open(
    'https://social-plugins.line.me/lineit/share?url=' + encodeURIComponent(shareUrl(id)),
    '_blank', 'noopener');
}

// 把某個檔案的公開網址傳到 LINE（相對路徑要先解析成絕對網址）
function shareFileLine(relUrl) {
  const abs = new URL(relUrl, location.href).href;
  window.open(
    'https://social-plugins.line.me/lineit/share?url=' + encodeURIComponent(abs),
    '_blank', 'noopener');
}

async function copyLink(id, btn) {
  const url = shareUrl(id);
  try {
    await navigator.clipboard.writeText(url);
  } catch {
    const ta = document.createElement('textarea');
    ta.value = url;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
  }
  btn.classList.add('copied');
  btn.textContent = '✓ 已複製';
  setTimeout(() => { btn.classList.remove('copied'); btn.textContent = '📋 複製連結'; }, 1500);
}

function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 1800);
}

/* ---------- Modal ---------- */
function openModal(id) {
  const item = findItem(id);
  if (!item) return;
  modalImg.src = item.img;          // 點開才載原圖，卡片牆只吃縮圖
  modalImg.alt = item.title;
  const files = item.files || [];
  modalFiles.innerHTML = files.map(f => fileChip(f, true)).join('');
  modalFiles.style.display = files.length ? 'flex' : 'none';
  modal.classList.add('open');
  document.body.style.overflow = 'hidden';
}
// 內嵌圖片放大（doc 頁的公文/速查表），純看圖、無附件列
function openImage(full, alt) {
  modalImg.src = full;
  modalImg.alt = alt || '';
  modalFiles.innerHTML = '';
  modalFiles.style.display = 'none';
  modal.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  modal.classList.remove('open');
  document.body.style.overflow = '';
}

/* ---------- Events ---------- */
nav.addEventListener('click', e => {
  const el = e.target.closest('.nav-item');
  if (!el) return;
  currentQuery = '';
  $('searchInput').value = '';
  currentCat = el.dataset.cat;
  location.hash = encodeURIComponent(currentCat);
  render();
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

let searchTimer;
$('searchInput').addEventListener('input', e => {
  clearTimeout(searchTimer);
  const v = e.target.value.trim().toLowerCase();
  searchTimer = setTimeout(() => { currentQuery = v; render(); }, 120);
});

content.addEventListener('click', e => {
  const trigger = e.target.closest('[data-action]');
  if (!trigger) return;
  const action = trigger.dataset.action;

  if (action === 'goto') {
    currentQuery = '';
    $('searchInput').value = '';
    currentCat = trigger.dataset.goto;
    location.hash = encodeURIComponent(currentCat);
    render();
    return;
  }
  // doc 頁的檔案/圖片不在 .card 內，要在 card 判斷前處理
  if (action === 'fileline') { shareFileLine(trigger.dataset.url); return; }
  if (action === 'docimg') { openImage(trigger.dataset.full, trigger.getAttribute('alt')); return; }

  const card = e.target.closest('.card');
  if (!card) return;
  const id = card.dataset.id;
  if (action === 'zoom') openModal(id);
  else if (action === 'line') shareLine(id);
  else if (action === 'copy') copyLink(id, trigger);
});

$('modalClose').addEventListener('click', closeModal);
modal.addEventListener('click', e => {
  const fl = e.target.closest('[data-action="fileline"]');
  if (fl) { shareFileLine(fl.dataset.url); return; }
  if (e.target === modal) closeModal();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
  if (e.key === '/' && document.activeElement !== $('searchInput')) {
    e.preventDefault();
    $('searchInput').focus();
  }
});

/* ---------- Deep link ---------- */
function applyHash() {
  const raw = decodeURIComponent(location.hash.slice(1));
  if (!raw) { render(); return; }

  if (CATS[raw]) { currentCat = raw; render(); return; }

  // 「區塊/類別/項目」→ 切到該類別並高亮該項目
  const catId = raw.split('/').slice(0, 2).join('/');
  if (CATS[catId]) {
    currentCat = catId;
    currentQuery = '';
    render();
    const card = content.querySelector(`.card[data-id="${CSS.escape(raw)}"]`);
    if (card) {
      card.scrollIntoView({ behavior: 'smooth', block: 'center' });
      card.style.transition = 'box-shadow .3s';
      card.style.boxShadow = '0 0 0 3px #f59e0b';
      setTimeout(() => { card.style.boxShadow = ''; }, 1600);
    }
    return;
  }
  render();
}

applyHash();
window.addEventListener('hashchange', applyHash);
</script>
</body>
</html>
'''


def prune_orphans() -> int:
    """刪掉 docs/assets 內這次沒產出的檔案（來源被刪除/改名留下的孤兒），再清空資料夾。"""
    if not ASSETS.exists():
        return 0
    removed = 0
    for f in ASSETS.rglob('*'):
        if f.is_file() and f.resolve() not in _written:
            f.unlink()
            removed += 1
    for d in sorted((p for p in ASSETS.rglob('*') if p.is_dir()), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()
    return removed


def main():
    sections = scan()
    DOCS.mkdir(exist_ok=True)
    orphans = prune_orphans()
    # GitHub Pages 預設跑 Jekyll，會吃掉 _ / . 開頭的路徑；關掉它。
    (DOCS / '.nojekyll').write_text('', encoding='utf-8')

    out_html = TEMPLATE.replace(
        '__DATA__', json.dumps(sections, ensure_ascii=False, separators=(',', ':'))
    )
    (DOCS / 'index.html').write_text(out_html, encoding='utf-8')

    size_kb = (DOCS / 'index.html').stat().st_size / 1024
    total = sum(f.stat().st_size for f in ASSETS.rglob('*') if f.is_file()) / (1024 * 1024)

    print(f'OK  → {DOCS / "index.html"}  ({size_kb:.1f} KB)')
    print(f'資產 → {ASSETS}  ({total:.1f} MB)')
    print(f'     複製 {_stats["copied"]} 個、縮圖 {_stats["thumbed"]} 張、'
          f'略過 {_stats["skipped"]} 個未變更、清除孤兒 {orphans} 個')
    if not HAS_PIL:
        print('警告：未安裝 Pillow，跳過縮圖（卡片會直接載原圖，較吃流量）')
    for sec in sections:
        print(f'\n[{sec["name"]}]')
        for c in sec['categories']:
            print(f'  {c["name"]:<12} {c["type"]:<8} {c["count"]} 筆')


if __name__ == '__main__':
    main()
