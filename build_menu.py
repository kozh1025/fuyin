# -*- coding: utf-8 -*-
"""Build 分隊菜單.html — single-file with base64-embedded images."""
import base64
import json
from pathlib import Path

BASE = Path(r'F:\CLAUDE\分隊菜單')
EAT = BASE / '吃'
DRINK = BASE / '喝'
OUT = BASE / '分隊菜單.html'


def encode(p: Path) -> str:
    return base64.b64encode(p.read_bytes()).decode('ascii')


def collect(d: Path, prefix: str):
    items = []
    for i, f in enumerate(sorted(d.glob('*.jpg'))):
        items.append({
            'id': f'{prefix}-{i+1}',
            'title': f.stem,
            'img': f'data:image/jpeg;base64,{encode(f)}',
        })
    return items


data = {
    'eat': collect(EAT, 'eat'),
    'drink': collect(DRINK, 'drink'),
}

data_json = json.dumps(data, ensure_ascii=False)

HTML = r'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>分隊菜單</title>
<style>
  *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
  html,body{height:100%}
  body{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Microsoft JhengHei","PingFang TC",sans-serif;
    color:#1f2937;background:#fafafa;line-height:1.5;
    -webkit-font-smoothing:antialiased;
  }

  .layout{display:grid;grid-template-columns:240px 1fr;min-height:100vh}

  /* Sidebar */
  .sidebar{
    background:#fff;border-right:1px solid #eee;
    padding:28px 14px;position:sticky;top:0;height:100vh;overflow-y:auto;
  }
  .brand{
    display:flex;align-items:center;gap:8px;
    font-size:16px;font-weight:600;color:#111;
    padding:4px 10px 20px;
  }
  .brand-emoji{font-size:18px}
  .nav-item{
    display:flex;align-items:center;gap:12px;
    padding:11px 12px;margin-bottom:4px;
    border-radius:8px;cursor:pointer;
    font-size:15px;color:#374151;
    transition:background .15s,color .15s;
    user-select:none;
  }
  .nav-item:hover{background:#f5f5f5}
  .nav-item.active{background:#fff4ea;color:#c2410c;font-weight:600}
  .nav-dot{
    width:8px;height:8px;border-radius:50%;
    background:#f59e0b;flex-shrink:0;
  }
  .nav-count{
    margin-left:auto;color:#9ca3af;font-size:13px;
    font-weight:500;
  }
  .nav-item.active .nav-count{color:#c2410c}

  /* Main */
  .main{padding:32px 40px;max-width:1400px}

  .top-bar{
    display:flex;align-items:center;gap:16px;
    margin-bottom:24px;
  }
  .page-title{
    font-size:22px;font-weight:600;color:#111;
    display:flex;align-items:baseline;gap:10px;
  }
  .page-title .count{
    font-size:14px;color:#9ca3af;font-weight:400;
  }

  .search{
    position:relative;flex:1;max-width:420px;
    margin-left:auto;
  }
  .search-icon{
    position:absolute;left:14px;top:50%;
    transform:translateY(-50%);color:#9ca3af;
    font-size:15px;pointer-events:none;
  }
  .search input{
    width:100%;padding:11px 16px 11px 40px;
    border:1px solid #e5e7eb;border-radius:10px;
    font-size:14px;background:#fff;
    transition:border-color .15s,box-shadow .15s;
    font-family:inherit;
  }
  .search input:focus{
    outline:none;border-color:#f59e0b;
    box-shadow:0 0 0 3px rgba(245,158,11,.12);
  }

  /* Gallery */
  .gallery{
    display:grid;
    grid-template-columns:repeat(auto-fill,minmax(240px,1fr));
    gap:20px;
  }
  .card{
    background:#fff;border:1px solid #eee;border-radius:12px;
    overflow:hidden;
    transition:box-shadow .2s,transform .2s;
    display:flex;flex-direction:column;
  }
  .card:hover{
    box-shadow:0 4px 16px rgba(0,0,0,.06);
    transform:translateY(-2px);
  }
  .card-image-wrap{
    aspect-ratio:3/4;background:#f5f5f5;overflow:hidden;
    cursor:zoom-in;position:relative;
  }
  .card-image{
    width:100%;height:100%;object-fit:cover;
    display:block;transition:transform .3s;
  }
  .card:hover .card-image{transform:scale(1.03)}
  .card-body{
    padding:14px 16px 16px;
    display:flex;flex-direction:column;gap:10px;
    flex:1;
  }
  .card-title{
    font-size:15px;font-weight:600;color:#111;
    word-break:break-all;
  }
  .card-actions{display:flex;gap:8px;margin-top:auto}
  .btn{
    display:inline-flex;align-items:center;justify-content:center;gap:6px;
    padding:8px 12px;border-radius:8px;
    font-size:13px;font-weight:500;cursor:pointer;
    border:1px solid transparent;
    transition:background .15s,color .15s,border-color .15s;
    text-decoration:none;font-family:inherit;
    flex:1;
  }
  .btn-line{
    background:#06c755;color:#fff;
  }
  .btn-line:hover{background:#05a648}
  .btn-copy{
    background:#fff;color:#4b5563;border-color:#e5e7eb;
  }
  .btn-copy:hover{background:#f9fafb;border-color:#d1d5db}
  .btn.copied{background:#10b981;color:#fff;border-color:#10b981}

  /* Modal */
  .modal{
    display:none;position:fixed;inset:0;
    background:rgba(0,0,0,.92);z-index:1000;
    justify-content:center;align-items:center;padding:24px;
  }
  .modal.open{display:flex}
  .modal img{
    max-width:100%;max-height:100%;
    border-radius:6px;object-fit:contain;
    box-shadow:0 8px 40px rgba(0,0,0,.5);
  }
  .modal-close{
    position:absolute;top:16px;right:20px;
    color:#fff;font-size:32px;line-height:1;
    background:none;border:none;cursor:pointer;
    width:44px;height:44px;border-radius:50%;
    display:flex;align-items:center;justify-content:center;
    transition:background .15s;
  }
  .modal-close:hover{background:rgba(255,255,255,.12)}

  /* Empty */
  .empty{
    text-align:center;padding:80px 20px;
    color:#9ca3af;font-size:15px;
  }

  /* Toast */
  .toast{
    position:fixed;bottom:32px;left:50%;
    transform:translateX(-50%) translateY(100px);
    background:#111;color:#fff;
    padding:12px 20px;border-radius:8px;
    font-size:14px;z-index:2000;
    opacity:0;transition:opacity .2s,transform .2s;
    pointer-events:none;
  }
  .toast.show{opacity:1;transform:translateX(-50%) translateY(0)}

  /* Mobile */
  @media(max-width:768px){
    .layout{grid-template-columns:1fr}
    .sidebar{
      position:sticky;top:0;height:auto;
      padding:12px;display:flex;gap:8px;
      border-right:none;border-bottom:1px solid #eee;
      overflow-x:auto;z-index:10;
    }
    .brand{display:none}
    .nav-item{flex-shrink:0;margin-bottom:0;padding:8px 14px}
    .nav-count{margin-left:6px}
    .main{padding:20px 16px}
    .top-bar{flex-direction:column;align-items:stretch;gap:12px}
    .search{max-width:none;margin-left:0}
    .gallery{grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:14px}
    .card-body{padding:12px}
    .card-title{font-size:14px}
    .btn{padding:7px 10px;font-size:12px}
  }
</style>
</head>
<body>

<div class="layout">
  <aside class="sidebar">
    <div class="brand"><span class="brand-emoji">🍱</span><span>分隊菜單</span></div>
    <div class="nav-item active" data-cat="eat">
      <span class="nav-dot"></span>
      <span>吃</span>
      <span class="nav-count" id="count-eat"></span>
    </div>
    <div class="nav-item" data-cat="drink">
      <span class="nav-dot"></span>
      <span>喝</span>
      <span class="nav-count" id="count-drink"></span>
    </div>
  </aside>

  <main class="main">
    <div class="top-bar">
      <div class="page-title">
        <span id="pageTitle">吃</span>
        <span class="count" id="pageCount"></span>
      </div>
      <div class="search">
        <span class="search-icon">🔍</span>
        <input type="text" id="searchInput" placeholder="搜尋店家名稱…" autocomplete="off">
      </div>
    </div>
    <div class="gallery" id="gallery"></div>
    <div class="empty" id="empty" style="display:none">找不到符合的店家</div>
  </main>
</div>

<div class="modal" id="modal">
  <button class="modal-close" id="modalClose" aria-label="關閉">×</button>
  <img id="modalImg" src="" alt="">
</div>

<div class="toast" id="toast"></div>

<script>
const DATA = __DATA__;

const CAT_LABEL = { eat: '吃', drink: '喝' };
let currentCat = 'eat';
let currentQuery = '';

const gallery = document.getElementById('gallery');
const empty = document.getElementById('empty');
const searchInput = document.getElementById('searchInput');
const pageTitle = document.getElementById('pageTitle');
const pageCount = document.getElementById('pageCount');
const modal = document.getElementById('modal');
const modalImg = document.getElementById('modalImg');
const toast = document.getElementById('toast');

document.getElementById('count-eat').textContent = DATA.eat.length;
document.getElementById('count-drink').textContent = DATA.drink.length;

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  })[c]);
}

function render() {
  const items = DATA[currentCat].filter(x =>
    !currentQuery || x.title.toLowerCase().includes(currentQuery)
  );
  pageTitle.textContent = CAT_LABEL[currentCat];
  pageCount.textContent = `共 ${items.length} 家`;

  if (items.length === 0) {
    gallery.innerHTML = '';
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';

  gallery.innerHTML = items.map(item => `
    <div class="card" id="${item.id}" data-id="${item.id}">
      <div class="card-image-wrap" data-action="zoom">
        <img class="card-image" src="${item.img}" alt="${escapeHtml(item.title)}" loading="lazy">
      </div>
      <div class="card-body">
        <div class="card-title">${escapeHtml(item.title)}</div>
        <div class="card-actions">
          <button class="btn btn-copy" data-action="copy">📋 複製連結</button>
          <button class="btn btn-line" data-action="line">傳到 LINE</button>
        </div>
      </div>
    </div>
  `).join('');
}

function findItem(id) {
  return DATA.eat.find(x => x.id === id) || DATA.drink.find(x => x.id === id);
}

function openModal(id) {
  const item = findItem(id);
  if (!item) return;
  modalImg.src = item.img;
  modalImg.alt = item.title;
  modal.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  modal.classList.remove('open');
  document.body.style.overflow = '';
}

function buildShareUrl(id) {
  const base = window.location.origin + window.location.pathname;
  return base + '#' + encodeURIComponent(id);
}

function shareLine(id, title) {
  const url = buildShareUrl(id);
  const shareUrl = 'https://social-plugins.line.me/lineit/share'
    + '?url=' + encodeURIComponent(url);
  window.open(shareUrl, '_blank', 'noopener');
}

async function copyLink(id, btn) {
  const url = buildShareUrl(id);
  try {
    await navigator.clipboard.writeText(url);
    btn.classList.add('copied');
    btn.textContent = '✓ 已複製';
    setTimeout(() => {
      btn.classList.remove('copied');
      btn.textContent = '📋 複製連結';
    }, 1500);
  } catch {
    // Fallback
    const ta = document.createElement('textarea');
    ta.value = url;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    showToast('已複製連結');
  }
}

function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 1800);
}

// Nav clicks
document.querySelectorAll('.nav-item').forEach(el => {
  el.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(x => x.classList.remove('active'));
    el.classList.add('active');
    currentCat = el.dataset.cat;
    history.replaceState(null, '', '#' + currentCat);
    render();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
});

// Search
searchInput.addEventListener('input', e => {
  currentQuery = e.target.value.trim().toLowerCase();
  render();
});

// Gallery event delegation
gallery.addEventListener('click', e => {
  const card = e.target.closest('.card');
  if (!card) return;
  const id = card.dataset.id;
  const item = findItem(id);
  if (!item) return;

  const action = e.target.closest('[data-action]')?.dataset.action;
  if (action === 'zoom') {
    openModal(id);
  } else if (action === 'line') {
    shareLine(id, item.title);
  } else if (action === 'copy') {
    copyLink(id, e.target.closest('[data-action]'));
  }
});

// Modal
document.getElementById('modalClose').addEventListener('click', closeModal);
modal.addEventListener('click', e => {
  if (e.target === modal) closeModal();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});

// Deep link
function applyHash() {
  const raw = decodeURIComponent(window.location.hash.slice(1));
  if (!raw) return;
  let cat = null, targetId = null;
  if (raw === 'eat' || raw === 'drink') {
    cat = raw;
  } else if (raw.startsWith('eat-') || raw.startsWith('drink-')) {
    cat = raw.split('-')[0];
    targetId = raw;
  }
  if (cat && cat !== currentCat) {
    document.querySelector(`.nav-item[data-cat="${cat}"]`).click();
  }
  if (targetId) {
    setTimeout(() => {
      const el = document.getElementById(targetId);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.style.transition = 'box-shadow .3s';
        el.style.boxShadow = '0 0 0 3px #f59e0b';
        setTimeout(() => el.style.boxShadow = '', 1500);
      }
    }, 120);
  }
}

render();
applyHash();
window.addEventListener('hashchange', applyHash);
</script>
</body>
</html>
'''

HTML = HTML.replace('__DATA__', data_json)

OUT.write_text(HTML, encoding='utf-8')

size_mb = OUT.stat().st_size / (1024 * 1024)
print(f'OK: {OUT}')
print(f'Size: {size_mb:.2f} MB')
print(f'Eat: {len(data["eat"])} stores')
print(f'Drink: {len(data["drink"])} stores')
