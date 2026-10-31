#!/usr/bin/env python3
"""Build curated public week/month reviews and their reading indexes."""
from __future__ import annotations

import argparse
from datetime import date
from html import escape
import json
import math
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
FIELDS={'kind','id','start','end','sessions','title','summary','lead','account_return',
        'benchmark_return','sections','note'}
INTERNAL=re.compile(r'审计|门禁|回执|封存|终稿|哈希|指纹|待人判|数据缺口|来源缺口|'
                    r'交易许可|授权|生产数据|机器事实|source_gaps|finalizer|receipt|'
                    r'/Users/|/home/|TICKET-|DISCIPLINE-|\bCAS\b|\bD0\b|\bJSON\b',re.I)
PRIVATE=re.compile(r'\d[\d,.]*\s*(?:元|股)(?!份)|(?<!\d)\d{6}(?!\d)')
PAGE_RE=re.compile(r'(weekly|monthly)-(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2})\.html')


def validate_report(item):
    if not isinstance(item,dict) or set(item)!=FIELDS:
        raise ValueError('public report field mismatch')
    kind=item['kind']
    if kind not in ('weekly','monthly'):raise ValueError('public period invalid')
    start,end=date.fromisoformat(item['start']),date.fromisoformat(item['end'])
    if start>end:raise ValueError('public period range invalid')
    expected=(f'{start.isocalendar().year}-W{start.isocalendar().week:02d}'
              if kind=='weekly' else start.strftime('%Y-%m'))
    if item['id']!=expected:raise ValueError('public period identity mismatch')
    if kind=='weekly' and start.isocalendar()[:2]!=end.isocalendar()[:2]:
        raise ValueError('public week range invalid')
    if kind=='monthly' and start.strftime('%Y-%m')!=end.strftime('%Y-%m'):
        raise ValueError('public month range invalid')
    sessions=item['sessions']
    if not isinstance(sessions,list) or not sessions or sessions!=sorted(set(sessions)):
        raise ValueError('public sessions invalid')
    if sessions[0]!=item['start'] or sessions[-1]!=item['end']:
        raise ValueError('public sessions range invalid')
    for session in sessions:
        day=date.fromisoformat(session)
        if not start<=day<=end or day.weekday()>4:raise ValueError('public session invalid')
    for key in ('account_return','benchmark_return'):
        if type(item[key]) not in (float,int) or not math.isfinite(item[key]):
            raise ValueError('public return invalid')
    for key in ('title','summary','lead','note'):
        if not isinstance(item[key],str) or not item[key].strip():raise ValueError('public text invalid')
    sections=item['sections']
    if not isinstance(sections,list) or not sections:raise ValueError('public sections invalid')
    for section in sections:
        if not isinstance(section,dict) or set(section)!={'title','paragraphs'}:
            raise ValueError('public section field mismatch')
        if not isinstance(section['title'],str) or not section['title'].strip():
            raise ValueError('public section title invalid')
        if not isinstance(section['paragraphs'],list) or not section['paragraphs']:
            raise ValueError('public paragraphs invalid')
        if any(not isinstance(p,str) or not p.strip() for p in section['paragraphs']):
            raise ValueError('public paragraph invalid')
    text=json.dumps(item,ensure_ascii=False)
    if INTERNAL.search(text) or PRIVATE.search(text):raise ValueError('public content contains internal/private detail')


def filename(item):
    return f"{item['kind']}-{item['start']}_{item['end'][5:]}.html"


def render_report(item):
    validate_report(item)
    title=escape(item['title']);summary=escape(item['summary'],quote=True)
    start,end=item['start'],item['end'];kind=item['kind']
    label='本周' if kind=='weekly' else '本月'
    values=[('交易日',f"{len(item['sessions'])}天"),
            (label+'净值变化',f"{item['account_return']:+.2f}%"),
            ('上证同期表现',f"约{item['benchmark_return']:+.2f}%"),
            ('相对表现',f"{item['account_return']-item['benchmark_return']:+.2f}个百分点")]
    kpis=''.join(f'<div class="kpi"><span>{escape(k)}</span><strong>{escape(v)}</strong></div>' for k,v in values)
    nav=''.join(f'<a href="#s{i}">{escape(s["title"])}</a>' for i,s in enumerate(item['sections']))
    sections=''.join(f'<section class="section" id="s{i}"><h2 class="sh">{escape(s["title"])}</h2>'
                     '<div class="sb">'+''.join('<p>'+escape(p)+'</p>' for p in s['paragraphs'])+
                     '</div></section>' for i,s in enumerate(item['sections']))
    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{summary}"><meta name="{kind}-summary" content="{summary}">
<title>{title} · 弈沐资本</title><link rel="stylesheet" href="weekly-review.css"></head>
<body><div class="topbar"><a class="back" href="../index.html">← 平台</a><div class="title">{title}</div>
<div class="meta"><a class="chip" href="../weekly/">周总结</a><a class="chip" href="../monthly/">月总结</a><span class="chip">{start} — {end}</span></div></div>
<div class="layout"><nav class="sidebar" aria-label="总结目录"><div class="label">目录</div>{nav}</nav><main class="content">
<section class="hero"><h1>{title}</h1><p>{escape(item['lead'])}</p><div class="kpis">{kpis}</div></section>{sections}
<section class="section"><h2 class="sh">统计说明</h2><div class="sb"><p>{escape(item['note'])}</p></div></section>
<p><a href="../{kind}/">返回{'周' if kind=='weekly' else '月'}总结目录</a> · <a href="../index.html">返回首页</a></p>
<footer>弈沐资本 · 历史表现与复盘思考。过往表现不代表未来结果。</footer></main></div></body></html>'''


def catalog(kind,names):
    label='周总结' if kind=='weekly' else '月总结';cards=[]
    for name in sorted(names,reverse=True):
        match=PAGE_RE.fullmatch(name)
        if not match or match[1]!=kind:continue
        start=date.fromisoformat(match[2]);end=date.fromisoformat(f'{start.year}-{match[3]}')
        title=(f"W{start.isocalendar().week:02d} · {start:%m/%d}–{end:%m/%d}" if kind=='weekly'
               else f"{start.year}年{start.month}月" if start.month==end.month
               else f"{start.year}年{start.month}–{end.month}月")
        cards.append(f'<section class="section"><div class="sb"><h2><a href="../review-notes/{name}">{title}</a></h2></div></section>')
    other='monthly' if kind=='weekly' else 'weekly';other_label='月总结' if kind=='weekly' else '周总结'
    return f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{label} · 弈沐资本</title><link rel="stylesheet" href="../review-notes/weekly-review.css"></head><body><div class="topbar"><a class="back" href="../index.html">← 平台</a><div class="title">{label}</div><a href="../{other}/">{other_label}</a></div><main class="content" style="max-width:960px;margin:auto"><section class="hero"><h1>{label}</h1><p>回看市场节奏、操作过程与认知变化。</p></section>{''.join(cards)}<p><a href="../review-notes/index.html#{kind}-reviews">复盘归档</a> · <a href="../index.html">返回首页</a></p></main></body></html>'''


def archive_page(text,reports,names):
    for item in sorted(reports,key=lambda x:x['end']):
        name=filename(item);summary=escape(item['summary']);kind=item['kind']
        existing=re.search(r'<a\b[^>]*href="'+re.escape(name)+r'"[^>]*>.*?</a>',text,re.S)
        start,end=date.fromisoformat(item['start']),date.fromisoformat(item['end'])
        if kind=='weekly':
            card=f'  <a href="{name}" class="wk-card"><div class="wr">{start.month}/{start.day} – {end.month}/{end.day}</div><div class="wm">第{start.isocalendar().week}周 · {len(item["sessions"])}天</div><div class="wt">{summary}</div></a>\n'
            marker='<div class="weekly-grid">\n'
            if marker not in text:raise ValueError('weekly archive marker missing')
            if existing:text=text[:existing.start()]+card.strip()+text[existing.end():]
            else:text=text.replace(marker,marker+card,1)
        else:
            card=f'\n<a href="{name}" class="monthly"><div class="mh">{start.year}年{start.month}月 · {len(item["sessions"])}个交易日</div><div class="mv">{summary}</div><div class="ma">阅读月总结 →</div></a>\n'
            marker=re.search(r'<div id="monthly-reviews"[^>]*>.*?</div>',text,re.S)
            if not marker:raise ValueError('monthly archive marker missing')
            if existing:text=text[:existing.start()]+card.strip()+text[existing.end():]
            else:text=text[:marker.end()]+card+text[marker.end():]
    counts={kind:sum(name.startswith(kind+'-') for name in names) for kind in ('weekly','monthly')}
    for phrase,count in [('周覆盖',counts['weekly']),('份周度总结',counts['weekly']),('份月度复盘',counts['monthly'])]:
        text=re.sub(r'(<strong>)\d+(</strong>\s*'+phrase+r')',lambda m:m[1]+str(count)+m[2],text)
    return text


def build(root,payload,check=False):
    root=Path(root)
    if set(payload)!={'schema','reports'} or payload['schema']!='public-period-review.v1':
        raise ValueError('public source schema invalid')
    reports=payload['reports']
    if not isinstance(reports,list) or not reports:raise ValueError('public reports empty')
    pages={}
    for item in reports:
        page=render_report(item);path=Path('review-notes')/filename(item)
        if path in pages:raise ValueError('public duplicate period')
        pages[path]=page
    names={p.name for p in (root/'review-notes').glob('*.html') if PAGE_RE.fullmatch(p.name)}
    names.update(p.name for p in pages)
    pages[Path('review-notes/index.html')]=archive_page((root/'review-notes/index.html').read_text(),reports,names)
    for kind in ('weekly','monthly'):pages[Path(kind)/'index.html']=catalog(kind,names)
    pages={p:text.rstrip('\n')+'\n' for p,text in pages.items()}
    if check:
        stale=[str(p) for p,text in pages.items() if not (root/p).is_file() or (root/p).read_text()!=text]
        if stale:raise ValueError('public pages stale: '+', '.join(stale))
    else:
        for p,text in pages.items():
            (root/p).parent.mkdir(parents=True,exist_ok=True)
            (root/p).write_text(text)
    return list(pages)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'data/period-reviews.json')
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--check',action='store_true');args=parser.parse_args()
    try:
        paths=build(args.root,json.loads(args.source.read_text()),check=args.check)
    except (ValueError,OSError) as exc:print(str(exc));return 1
    print(f"{'checked' if args.check else 'built'} {len(paths)} public review pages/indexes")
    return 0


if __name__=='__main__':raise SystemExit(main())
