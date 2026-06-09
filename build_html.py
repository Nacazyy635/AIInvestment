#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自動デイトレシステム_仕様書.md → 自動デイトレシステム_仕様書.html

読みやすい単一HTML（目次サイドバー・スクロール追従・印刷対応・オフライン完結）を生成する。
MDを編集したら、このスクリプトを再実行すればHTMLも更新される:
    python3 build_html.py
"""
from pathlib import Path
from datetime import datetime
import markdown
from markdown.extensions.toc import slugify_unicode

BASE = Path(__file__).resolve().parent
SRC = BASE / "自動デイトレシステム_仕様書.md"
OUT = BASE / "自動デイトレシステム_仕様書.html"

md_text = SRC.read_text(encoding="utf-8")
title = md_text.splitlines()[0].lstrip("# ").strip() or "仕様書"

md = markdown.Markdown(
    extensions=["extra", "toc", "sane_lists"],
    extension_configs={"toc": {"toc_depth": "2-3", "slugify": slugify_unicode}},
    output_format="html5",
)
body = md.convert(md_text)
toc = md.toc  # <div class="toc"><ul>...</ul></div>

# 表は横スクロールできるよう wrapper を付与
body = body.replace("<table>", '<div class="table-wrap"><table>').replace(
    "</table>", "</table></div>"
)

gen = datetime.now().strftime("%Y-%m-%d %H:%M")

CSS = """
:root{
  --bg:#eef1f5; --card:#ffffff; --ink:#1f2933; --muted:#5b6770;
  --accent:#0f766e; --accent-2:#0d9488; --accent-soft:#e6f4f1;
  --border:#dde3ea; --warn-bg:#fff6e6; --warn-bd:#f59e0b; --warn-ink:#92400e;
  --code-bg:#f4f6f8;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font-family:"Hiragino Kaku Gothic ProN","Hiragino Sans","Yu Gothic","Meiryo","Noto Sans JP",system-ui,sans-serif;
  font-size:16px; line-height:1.85; -webkit-font-smoothing:antialiased;
}
.layout{
  max-width:1280px; margin:24px auto; background:var(--card);
  border-radius:16px; box-shadow:0 10px 30px rgba(15,23,42,.08);
  overflow:hidden; display:flex; align-items:flex-start;
}
/* ===== Sidebar ===== */
.sidebar{
  width:300px; flex:0 0 300px; align-self:stretch;
  background:#f7faf9; border-right:1px solid var(--border);
  position:sticky; top:0; max-height:100vh; overflow:auto;
}
.sidebar-inner{padding:18px 12px 48px}
.brand{
  font-weight:800; color:var(--accent); font-size:1.05em;
  padding:.2em .5em .2em; letter-spacing:.02em;
}
.toc-title{font-size:.72em; font-weight:700; color:var(--muted); letter-spacing:.12em;
  text-transform:uppercase; padding:.8em .7em .3em}
.toc-nav .toc{font-size:.9em}
.toc-nav ul{list-style:none; margin:0; padding-left:0}
.toc-nav li{margin:.08em 0}
.toc-nav a{display:block; padding:.34em .6em; border-radius:8px; color:#33454a; line-height:1.35;
  transition:background .12s,color .12s}
.toc-nav a:hover{background:var(--accent-soft); text-decoration:none}
.toc-nav a.active{background:var(--accent); color:#fff}
.toc-nav > .toc > ul > li > a{font-weight:700}
.toc-nav ul ul{padding-left:.55em; margin:.1em 0 .3em .5em; border-left:1px dashed var(--border)}
.toc-nav ul ul a{font-size:.92em; color:#60707a}
/* ===== Content ===== */
.content{flex:1 1 auto; min-width:0; padding:30px clamp(16px,4vw,52px) 90px}
.doc{max-width:900px; margin:0 auto}
.doc > h1{
  background:linear-gradient(135deg,#0f766e,#0e7490); color:#fff;
  padding:30px 30px; border-radius:14px; margin:0 0 1.4em; font-size:1.7em; line-height:1.4;
  box-shadow:0 8px 22px rgba(15,118,110,.25);
}
.doc h2{
  font-size:1.42em; margin:2.4em 0 .8em; color:#0f3d39; line-height:1.4;
  padding:.05em 0 .35em .65em; border-left:5px solid var(--accent);
  border-bottom:1px solid var(--border);
}
.doc h3{font-size:1.17em; margin:1.7em 0 .55em; color:#15524c}
.doc h4{font-size:1.02em; margin:1.3em 0 .5em; color:var(--accent)}
.doc p{margin:.7em 0}
.doc ul,.doc ol{margin:.6em 0; padding-left:1.5em}
.doc li{margin:.28em 0}
a{color:var(--accent-2); text-decoration:none}
a:hover{text-decoration:underline}
hr{border:none; border-top:1px solid var(--border); margin:2.4em 0}
/* tables */
.table-wrap{overflow:auto; margin:1.2em 0; border:1px solid var(--border); border-radius:10px}
table{border-collapse:collapse; width:100%; font-size:.93em}
th,td{padding:.62em .85em; border-bottom:1px solid var(--border); text-align:left; vertical-align:top}
thead th{background:var(--accent-soft); color:#0c4a44; font-weight:700; position:sticky; top:0}
tbody tr:nth-child(even){background:#f8fafc}
tbody tr:hover{background:#eef9f6}
td:first-child,th:first-child{white-space:nowrap}
/* code */
pre{background:var(--code-bg); border:1px solid var(--border); border-radius:10px;
  padding:14px 16px; overflow-x:auto; line-height:1.5; margin:1.1em 0}
pre code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
  font-size:12.5px; white-space:pre; color:#0f172a; background:none; padding:0}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  background:#e9f3f1; color:#0b6b5e; padding:.12em .42em; border-radius:6px; font-size:.86em}
/* blockquote callouts */
blockquote{margin:1.15em 0; padding:.7em 1em .7em 1.05em; background:var(--accent-soft);
  border-left:4px solid var(--accent); border-radius:0 9px 9px 0; color:#22403c}
blockquote.warn{background:var(--warn-bg); border-left-color:var(--warn-bd); color:var(--warn-ink)}
blockquote p{margin:.3em 0}
strong{color:#0b3b37}
blockquote.warn strong{color:#7c2d12}
.pagefoot{max-width:900px; margin:48px auto 0; padding-top:18px; border-top:1px solid var(--border);
  color:var(--muted); font-size:.85em}
/* floating + mobile */
#menuToggle{display:none; position:fixed; top:12px; left:12px; z-index:30;
  background:var(--accent); color:#fff; border:none; border-radius:10px; padding:9px 14px;
  font-size:.95em; box-shadow:0 4px 12px rgba(0,0,0,.18); cursor:pointer}
#toTop{position:fixed; right:18px; bottom:18px; z-index:30; display:none;
  width:44px; height:44px; border-radius:50%; border:none; cursor:pointer;
  background:var(--accent); color:#fff; font-size:1.2em; box-shadow:0 4px 14px rgba(0,0,0,.2);
  align-items:center; justify-content:center}
@media(max-width:880px){
  .layout{flex-direction:column; margin:0; border-radius:0}
  .sidebar{position:static; width:auto; flex:none; max-height:none; align-self:stretch;
    border-right:none; border-bottom:1px solid var(--border); display:none}
  .sidebar.open{display:block}
  #menuToggle{display:inline-flex}
  .content{padding:58px 16px 70px}
  .doc > h1{font-size:1.4em; padding:22px 20px}
}
@media print{
  body{background:#fff}
  .sidebar,#menuToggle,#toTop{display:none !important}
  .layout{box-shadow:none; margin:0; max-width:none; border-radius:0}
  .content{padding:0}
  .doc > h1{color:#000; background:none; box-shadow:none; border:2px solid #000}
  a{color:#000}
  pre,blockquote,.table-wrap,table,tr{break-inside:avoid}
  thead th{position:static}
}
"""

JS = """
(function(){
  var links=[].slice.call(document.querySelectorAll('.toc-nav a'));
  var map={};
  links.forEach(function(a){ map[a.getAttribute('href').slice(1)]=a; });
  var heads=[].slice.call(document.querySelectorAll('.doc h2[id],.doc h3[id]'));
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(es){
      es.forEach(function(e){
        if(e.isIntersecting){
          links.forEach(function(l){l.classList.remove('active');});
          var a=map[e.target.id]; if(a) a.classList.add('active');
        }
      });
    },{rootMargin:'0px 0px -78% 0px',threshold:0});
    heads.forEach(function(h){io.observe(h);});
  }
  document.querySelectorAll('.doc blockquote').forEach(function(b){
    if(b.textContent.indexOf('\\u26a0')>-1) b.classList.add('warn');
  });
  var mt=document.getElementById('menuToggle'), sb=document.getElementById('sidebar');
  if(mt&&sb){
    mt.addEventListener('click',function(){sb.classList.toggle('open');});
    sb.addEventListener('click',function(e){
      if(e.target.tagName==='A'&&window.innerWidth<=880) sb.classList.remove('open');
    });
  }
  var tt=document.getElementById('toTop');
  window.addEventListener('scroll',function(){tt.style.display=window.scrollY>400?'flex':'none';});
  tt.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'});});
})();
"""

html = (
    "<!DOCTYPE html>\n<html lang=\"ja\">\n<head>\n"
    '<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
    "<title>" + title + "</title>\n"
    "<style>" + CSS + "</style>\n</head>\n<body>\n"
    '<button id="menuToggle" aria-label="目次を開閉">☰ 目次</button>\n'
    '<div class="layout">\n'
    '  <aside class="sidebar" id="sidebar"><div class="sidebar-inner">\n'
    '    <div class="brand">📈 仕様書</div>\n'
    '    <div class="toc-title">目次</div>\n'
    '    <nav class="toc-nav">' + toc + "</nav>\n"
    "  </div></aside>\n"
    '  <main class="content"><article class="doc">\n'
    + body +
    "\n  </article>\n"
    '  <footer class="pagefoot">このHTMLは <code>自動デイトレシステム_仕様書.md</code> から自動生成（'
    + gen + "）。MDを編集後 <code>python3 build_html.py</code> で再生成できます。</footer>\n"
    "  </main>\n</div>\n"
    '<button id="toTop" title="トップへ戻る">↑</button>\n'
    "<script>" + JS + "</script>\n</body>\n</html>\n"
)

OUT.write_text(html, encoding="utf-8")
print("OK ->", OUT)
print("bytes:", OUT.stat().st_size)
