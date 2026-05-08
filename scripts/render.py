#!/usr/bin/env python3
"""
Scholar Radar v3 · 渲染脚本
读取 scholar_radar_archive.json → 生成单页 HTML 仪表板
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

PROJECT_DIR = Path(__file__).resolve().parent.parent
ARCHIVE_PATH = PROJECT_DIR / "output" / "scholar_radar_archive.json"
OUTPUT_PATH = PROJECT_DIR / "output" / "index.html"

CSS = """
:root {
  --bg: #0d1117; --card: #161b22; --border: #30363d;
  --text: #c9d1d9; --muted: #8b949e; --accent: #58a6ff;
  --green: #3fb950; --orange: #d29922; --red: #f85149;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  background:var(--bg); color:var(--text); line-height:1.6; }
.header { padding:2rem; text-align:center; border-bottom:1px solid var(--border); }
.header h1 { font-size:2rem; color:var(--accent); }
.header .meta { color:var(--muted); font-size:0.9rem; margin-top:0.5rem; }
.filters { display:flex; gap:0.5rem; padding:1rem 2rem; flex-wrap:wrap;
  justify-content:center; border-bottom:1px solid var(--border); }
.filter-btn { padding:0.4rem 1rem; border:1px solid var(--border); border-radius:20px;
  background:transparent; color:var(--text); cursor:pointer; font-size:0.85rem; transition:.2s; }
.filter-btn:hover { border-color:var(--accent); color:var(--accent); }
.filter-btn.active { background:var(--accent); color:#fff; border-color:var(--accent); }
.stats { display:flex; gap:1.5rem; justify-content:center; padding:1rem;
  color:var(--muted); font-size:0.85rem; }
.timeline { max-width:900px; margin:0 auto; padding:1rem 2rem 3rem; }
.entry { border:1px solid var(--border); border-radius:8px; padding:1rem;
  margin-bottom:0.8rem; background:var(--card); transition:border-color .2s; }
.entry:hover { border-color:var(--accent); }
.entry-header { display:flex; justify-content:space-between; align-items:flex-start;
  gap:1rem; margin-bottom:0.3rem; }
.entry-title { font-weight:600; font-size:1rem; }
.entry-title a { color:var(--accent); text-decoration:none; }
.entry-title a:hover { text-decoration:underline; }
.entry-meta { display:flex; gap:0.6rem; flex-wrap:wrap; align-items:center;
  font-size:0.8rem; color:var(--muted); margin:0.3rem 0; }
.badge { padding:0.15rem 0.5rem; border-radius:10px; font-size:0.75rem; font-weight:500; }
.badge-academic { background:rgba(88,166,255,0.15); color:var(--accent); }
.badge-source { background:rgba(210,153,34,0.15); color:var(--orange); }
.entry-abstract { font-size:0.85rem; color:var(--muted); margin-top:0.4rem;
  display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
.hidden { display:none; }
.no-results { text-align:center; padding:3rem; color:var(--muted); }
.footer { text-align:center; padding:1rem; color:var(--muted); font-size:0.75rem;
  border-top:1px solid var(--border); }
"""

JS = """
const entries = document.querySelectorAll('.entry');
function filter(cat, val) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  let visible = 0;
  entries.forEach(e => {
    const match = !val || e.dataset[cat] === val;
    e.classList.toggle('hidden', !match);
    if (match) visible++;
  });
  document.getElementById('result-count').textContent = visible;
}
document.getElementById('result-count').textContent = entries.length;
"""


def render():
    if not ARCHIVE_PATH.exists():
        print(f"❌ 归档文件不存在: {ARCHIVE_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(ARCHIVE_PATH) as f:
        archive = json.load(f)

    items = archive["items"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 统计
    scholars = set()
    sources = set()
    for i in items:
        if "matched_scholar" in i:
            scholars.add(i["matched_scholar"])
        sources.add(i["source"])

    # 生成过滤按钮
    filter_btns = '<button class="filter-btn active" onclick="filter(\'all\',\'\')">全部</button>'
    for s in sorted(scholars):
        filter_btns += f'<button class="filter-btn" onclick="filter(\'scholar\',\'{s}\')">👤 {s}</button>'

    # 生成条目
    entries_html = []
    for item in items:
        title = item.get("title", "Untitled")[:120]
        url = item.get("url", "#")
        source = item.get("source", "Unknown")
        stype = item.get("source_type", "academic")
        pub_date = item.get("published_date", "")[:10]
        abstract = item.get("abstract", "")
        authors = item.get("authors", [])
        author_str = ", ".join(authors[:5])
        if len(authors) > 5:
            author_str += f" +{len(authors)-5}"
        doi = item.get("doi", "")
        cited = item.get("cited_by_count", 0)

        data_attrs = f'data-source-type="{stype}"'
        if "matched_scholar" in item:
            data_attrs += f' data-scholar="{item["matched_scholar"]}"'

        type_badge = (
            '<span class="badge badge-academic">预印本</span>'
            if stype == "preprint"
            else '<span class="badge badge-academic">论文</span>'
        )
        source_badge = f'<span class="badge badge-source">{source}</span>'

        meta_parts = [type_badge, source_badge]
        if pub_date:
            meta_parts.insert(0, f'<span>{pub_date}</span>')
        if author_str:
            meta_parts.append(f'<span>{author_str}</span>')
        if cited:
            meta_parts.append(f'<span>被引 {cited}</span>')

        abstract_html = ""
        if abstract:
            abstract_html = f'<div class="entry-abstract">{abstract[:300]}</div>'
        elif doi:
            abstract_html = f'<div class="entry-abstract" style="color:var(--muted);font-style:italic;">DOI: {doi}</div>'

        entries_html.append(
            f"""<div class="entry" {data_attrs}>
<div class="entry-header">
  <div class="entry-title"><a href="{url}" target="_blank" rel="noopener">{title}</a></div>
</div>
<div class="entry-meta">{' · '.join(meta_parts)}</div>
{abstract_html}
</div>"""
        )

    # 组装 HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>🔭 Scholar Radar · 学者追踪</title>
<style>{CSS}</style>
</head>
<body>
<div class="header">
  <h1>🔭 Scholar Radar</h1>
  <div class="meta">
    追踪学者：{', '.join(sorted(scholars))} &nbsp;|&nbsp;
    共 {len(items)} 条 · 更新于 {now}
  </div>
</div>
<div class="filters">{filter_btns}</div>
<div class="stats">显示 <strong id="result-count">{len(items)}</strong> 条</div>
<div class="timeline">{"".join(entries_html)}</div>
<div class="footer">Scholar Radar v3 · 数据源: arXiv / OpenAlex / Semantic Scholar · 学术论文追踪</div>
<script>{JS}</script>
</body>
</html>"""

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"✅ 渲染完成: {OUTPUT_PATH}")
    print(f"   共 {len(items)} 条 · 文件大小 {OUTPUT_PATH.stat().st_size:,} bytes")


if __name__ == "__main__":
    render()
