"""Python 系列文章渲染库:骨架复用 sample.html(线上 python-signal 页面的原样),
额外补 flow / bars / term / chips 四种演示面板。实验输出统一从 out/ 目录读,保证正文里的输出就是真跑出来的。"""
import html, json, re, sqlite3, pathlib

HERE = pathlib.Path(__file__).parent
SAMPLE = (HERE / 'sample.html').read_text()
TOPICS = {int(k): v for k, v in json.load(open(HERE / 'topics.json')).items()}
RTOPICS = {int(k): v for k, v in json.load(open(HERE / 'redis_topics.json')).items()}
DTOPICS = {int(k): v for k, v in json.load(open(HERE / 'django_topics.json')).items()}
ZTOPICS = {int(k): v for k, v in json.load(open(HERE / 'zookeeper_topics.json')).items()}
UTOPICS = {int(k): v for k, v in json.load(open(HERE / 'rust_topics.json')).items()}
FTOPICS = {int(k): v for k, v in json.load(open(HERE / 'flask_topics.json')).items()}
JTOPICS = {int(k): v for k, v in json.load(open(HERE / 'java_topics.json')).items()}
JOFF = 140  # DB 里 java 系列原有 140 篇,新批次的显示编号接在后面
GTOPICS = {int(k): v for k, v in json.load(open(HERE / 'go_topics.json')).items()}
CTOPICS = {int(k): v for k, v in json.load(open(HERE / 'docker_topics.json')).items()}
KTOPICS = {int(k): v for k, v in json.load(open(HERE / 'k8s_topics.json')).items()}
NTOPICS = {int(k): v for k, v in json.load(open(HERE / 'gin_topics.json')).items()}
ITOPICS = {int(k): v for k, v in json.load(open(HERE / 'git_topics.json')).items()}
MTOPICS = {int(k): v for k, v in json.load(open(HERE / 'mongo_topics.json')).items()}
PTOPICS = {int(k): v for k, v in json.load(open(HERE / 'crawler_topics.json')).items()}
ETOPICS = {int(k): v for k, v in json.load(open(HERE / 'codec_topics.json')).items()}
HTOPICS = {int(k): v for k, v in json.load(open(HERE / 'grpc_topics.json')).items()}
QTOPICS = {int(k): v for k, v in json.load(open(HERE / 'rabbitmq_topics.json')).items()}
WTOPICS = {int(k): v for k, v in json.load(open(HERE / 'network_topics.json')).items()}
TTOPICS = {int(k): v for k, v in json.load(open(HERE / 'transaction_topics.json')).items()}
VTOPICS = {int(k): v for k, v in json.load(open(HERE / 'microservice_topics.json')).items()}
XTOPICS = {int(k): v for k, v in json.load(open(HERE / 'spring_topics.json')).items()}
YTOPICS = {int(k): v for k, v in json.load(open(HERE / 'scrapy_topics.json')).items()}
# 新批次系列在 DB 里原有的篇数(显示编号接在后面)
OFF = {'java': 140, 'go': 11, 'docker': 5, 'k8s': 6, 'gin': 4, 'git': 4, 'mongo': 8, 'crawler': 1, 'codec': 0, 'scrapy': 0, 'grpc': 0, 'rabbitmq': 0, 'network': 0, 'transaction': 0, 'microservice': 0, 'spring': 0}
SERIES_COLORS = {  # key: (light c, light soft, dark c, dark soft)
    'go': ('#00799A', '#D9F1F8', '#4FC3E8', '#0B2A33'),
    'docker': ('#1769B8', '#DCEBFA', '#5AAEF2', '#10263D'),
    'k8s': ('#5D4A9C', '#E7E2F3', '#A596DB', '#231D3A'),
    'gin': ('#C23B6B', '#F9E1EA', '#E8789D', '#3A1522'),
    'git': ('#8B3FA0', '#F1E3F6', '#C48AD6', '#2E1838'),
    'mongo': ('#1C7C74', '#D9F0ED', '#4DB8AE', '#10302D'),
    'crawler': ('#5F7F1E', '#E6EFD2', '#A3C45A', '#222C0E'),
    'codec': ('#A8561A', '#F6E3D2', '#E39A5E', '#33200F'),
    'grpc': ('#2B7A78', '#D6EEEC', '#6CC5C1', '#0F2E2D'),
    'scrapy': ('#2F8F4E', '#DAF0E1', '#6FCB8A', '#12301D'),
    'rabbitmq': ('#D9531E', '#FBE3D8', '#F58A5B', '#3A1A0F'),
    'network': ('#40678F', '#DDE7F2', '#86B1DC', '#16263A'),
    'transaction': ('#B0485B', '#F6DEE2', '#E58A9A', '#3A1820'),
    'microservice': ('#8A6D12', '#F3EBCB', '#D9B94A', '#332B0B'),
    'spring': ('#3E8E2C', '#DDEFD6', '#7FD068', '#12290C'),
    'grpc': ('#2B7A78', '#D6EEEC', '#6CC5C1', '#0F2E2D'),
}
PREV71 = ('python-signal.html', 'signal：进程收到信号后到底发生什么')
import datetime as _dt
DATE = _dt.date.today().isoformat()   # dates.json 里没有登记的文章按“今天写的”处理;一批写完后跑 python3 mkdates.py 把日期冻结进 dates.json
try: DATES = json.load(open(pathlib.Path(__file__).parent / 'dates.json'))   # url -> 写作日期,由 mkdates.py 生成
except Exception: DATES = {}

_style = re.search(r'<style>\n(.*?)</style>', SAMPLE, re.S).group(1)
EXTRA_CSS = r"""
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:.88em; background:var(--series-c-soft); padding:1px 6px; border-radius:5px;}
.flow{display:flex; flex-wrap:wrap; align-items:stretch; gap:6px;}
.fnode{min-width:84px; padding:8px 12px; border:1.5px solid var(--line); border-radius:10px; background:var(--paper); text-align:center; font-family:ui-monospace,Menlo,monospace; font-size:.85rem; transition:background .15s,border-color .15s;}
.fnode .sub{display:block; margin-top:3px; font-size:.68rem; color:var(--ink-dim); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}
.fnode.cur{background:var(--mem-c-soft); border-color:var(--mem-c);}
.fnode.done{background:var(--ok-c-soft); border-color:var(--ok-c);}
.fnode.mark{background:var(--mark-soft); border-color:var(--mark-c); font-weight:700;}
.fnode.dim{opacity:.4;}
.flow .far{align-self:center; color:var(--ink-dim);}
.bars{display:flex; flex-direction:column; gap:7px;}
.brow{display:flex; align-items:center; gap:10px; font-family:ui-monospace,Menlo,monospace; font-size:.82rem;}
.brow .bl{width:150px; flex:none; color:var(--ink-dim); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
.brow .bt{flex:1; height:16px; background:var(--bg); border-radius:5px; overflow:hidden; border:1px solid var(--line);}
.brow .bf{height:100%; background:var(--series-c); transition:width .25s;}
.brow.cur .bf{background:var(--mem-c);} .brow.mark .bf{background:var(--mark-c);} .brow.done .bf{background:var(--ok-c);}
.brow .bv{width:92px; flex:none; text-align:right; font-variant-numeric:tabular-nums;}
.tlines{background:var(--code-bg); color:var(--code-ink); border-radius:8px; padding:10px 14px; font-family:ui-monospace,Menlo,monospace; font-size:.8rem; line-height:1.6; white-space:pre-wrap; word-break:break-word;}
.tlines .tl.cur{background:rgba(111,168,224,.28); border-radius:4px; display:block; margin:0 -6px; padding:0 6px;}
.tlines .tl.mark{background:rgba(229,168,46,.30); border-radius:4px; display:block; margin:0 -6px; padding:0 6px;}
.tlines .tl{display:block; margin:0 -6px; padding:0 6px;}
.tlines .tl.dim{opacity:.45;}
.chips{display:flex; flex-wrap:wrap; gap:6px;}
.chipx{padding:5px 10px; border:1.5px solid var(--line); border-radius:8px; background:var(--paper); font-family:ui-monospace,Menlo,monospace; font-size:.85rem; text-align:center;}
.chipx .sub{display:block; font-size:.66rem; color:var(--ink-dim);}
.chipx.cur{background:var(--mem-c-soft); border-color:var(--mem-c);} .chipx.done{background:var(--ok-c-soft); border-color:var(--ok-c);} .chipx.mark{background:var(--mark-soft); border-color:var(--mark-c);} .chipx.dim{opacity:.4;}
"""

_NAV = re.search(r'<body>\n(.*?)</nav>\n', SAMPLE, re.S).group(0)
if 'series=zookeeper' not in _NAV:
    _ZK = '<a class="md3-drawer-item" href="/?series=zookeeper" style="--item-c:#7A5B2E">\n      <span class="md3-drawer-dot" style="--dot:#7A5B2E"></span>\n      <span class="md3-drawer-label">ZooKeeper 内部原理</span>\n      <span class="md3-drawer-count">0</span>\n    </a>\n    '
    _i = _NAV.index('<a class="md3-drawer-item" href="/?series=redis"'); _NAV = _NAV[:_i] + _ZK + _NAV[_i:]

if 'series=rust' not in _NAV:
    _RU = '<a class="md3-drawer-item" href="/?series=rust" style="--item-c:#B7410E">\n      <span class="md3-drawer-dot" style="--dot:#B7410E"></span>\n      <span class="md3-drawer-label">Rust 内部机制</span>\n      <span class="md3-drawer-count">0</span>\n    </a>\n    '
    _i = _NAV.index('<a class="md3-drawer-item" href="/?series=redis"'); _NAV = _NAV[:_i] + _RU + _NAV[_i:]

if 'series=flask' not in _NAV:
    _FL = '<a class="md3-drawer-item" href="/?series=flask" style="--item-c:#4A5568">\n      <span class="md3-drawer-dot" style="--dot:#4A5568"></span>\n      <span class="md3-drawer-label">Flask 内部机制</span>\n      <span class="md3-drawer-count">0</span>\n    </a>\n    '
    _i = _NAV.index('<a class="md3-drawer-item" href="/?series=redis"'); _NAV = _NAV[:_i] + _FL + _NAV[_i:]

# ---------- demo runtime(取自 sample.html 的渲染器,补充 4 个新面板) ----------
_js = re.search(r'<script>\(function\(\)\{\n(.*?)\}\)\(\);</script>', SAMPLE, re.S).group(1)
_js_body = _js.split('\n', 1)[1]  # 去掉 const D = ... 那一行
_js_body = _js_body.replace(
    "const R = {cells:rCells, kv:rKV, matrix:rMatrix, chain:rChain, stack:rStack, text:rText, tree:rTree};",
    r"""function kc(s, i){ return (s.cur||[]).includes(i) ? ' cur' : (s.mark||[]).includes(i) ? ' mark' : (s.done||[]).includes(i) ? ' done' : (s.dim||[]).includes(i) ? ' dim' : ''; }
function rFlow(s){ const w = h('div','flow'); s.nodes.forEach((n,i)=>{ const b = h('div','fnode'+kc(s,i), n[0]); if(n[1]) b.appendChild(h('span','sub',n[1])); w.appendChild(b); if(i < s.nodes.length-1 && !s.noarrow) w.appendChild(h('span','far','→')); }); return w; }
function rBars(s){ const w = h('div','bars'); const mx = s.max || Math.max.apply(null, s.items.map(x=>x[1]).concat([1])); s.items.forEach((it,i)=>{ const r = h('div','brow'+kc(s,i)); r.appendChild(h('span','bl',it[0])); const t = h('div','bt'); const f = h('div','bf'); f.style.width = Math.max(0.5, it[1]/mx*100)+'%'; t.appendChild(f); r.appendChild(t); r.appendChild(h('span','bv', it[2]!=null ? it[2] : String(it[1]))); w.appendChild(r); }); return w; }
function rTerm(s){ const w = h('div','tlines'); s.lines.forEach((l,i)=>{ w.appendChild(h('span','tl'+kc(s,i), l)); }); return w; }
function rChips(s){ const w = h('div','chips'); s.values.forEach((v,i)=>{ const c = h('div','chipx'+kc(s,i), Array.isArray(v)?v[0]:v); if(Array.isArray(v)&&v[1]) c.appendChild(h('span','sub',v[1])); w.appendChild(c); }); return w; }
const R = {cells:rCells, kv:rKV, matrix:rMatrix, chain:rChain, stack:rStack, text:rText, tree:rTree, flow:rFlow, bars:rBars, term:rTerm, chips:rChips};""")
_js_body = _js_body.replace("}, 1000); };", "}, 1600); };")
_js_body = _js_body.replace("body.innerHTML = ''; if(st.s[p.id])", "body.innerHTML = ''; body.parentNode.style.display = st.s[p.id] ? '' : 'none'; if(st.s[p.id])")
assert "parentNode.style.display" in _js_body
assert 'rFlow' in _js_body and '1600' in _js_body


def esc(s):
    return html.escape(s, quote=False)


_PATH_RE = re.compile(r"/private/tmp/claude-501/[^\s\\\"'|,;)]*")
_IP_RE = re.compile(r'(?<![\d.])192\.168\.\d+\.\d+(?![\d])')
def san(t): return _IP_RE.sub('<本机局域网IP>', _PATH_RE.sub('<实验目录>', t.replace('/opt/homebrew/Cellar/rust/1.98.1/lib/rustlib/src/rust/', '<rust 标准库源码>/')))


def out(name):
    return san((HERE / 'out' / f'{name}.txt').read_text().rstrip('\n'))


def src(path, code):
    return f'<blockquote class="src"><span class="path">{esc(path)}</span>\n{esc(code.strip(chr(10)))}</blockquote>'


def term(cmd, output, tag='实测 · 本机执行输出'):
    """cmd 是命令行/说明;output 是真实输出(原样,不改格式)。"""
    body = (esc(cmd) + '\n' if cmd else '') + esc(output)
    return f'<div class="term"><span class="real-tag">{esc(tag)}</span>\n<pre class="code">{body}</pre></div>'


def callout(text, b=False):
    return f'<div class="callout{" b" if b else ""}">{text}</div>'


def table(head, rows, mono=True):
    h = ''.join(f'<th>{c}</th>' for c in head)
    r = ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>' for row in rows)
    return f'<table{" class=mono" if mono else ""}><thead><tr>{h}</tr></thead><tbody>{r}</tbody></table>'


def sec(h2, sub, *parts):
    subh = f'<div class="h2-sub">{sub}</div>' if sub else ''
    return f'<section>\n  <h2>{h2}</h2>\n  {subh}\n  ' + '\n  '.join(parts) + '\n</section>'


def demo(title, panels, steps, legend='这一步新出现/被高亮的对象'):
    D = {'panels': [{'id': p[0], 'kind': p[1], 'label': p[2]} for p in panels], 'steps': steps}
    data = json.dumps(D, ensure_ascii=False).replace('</', '<\\/')
    return (f'<div class="demo" id="demo"><div class="demo-head">{esc(title)}</div><div class="demo-panels"></div>'
            f'<div class="demo-note"></div><div class="demo-legend"><span><i class="cur"></i>{esc(legend)}</span></div>'
            '<div class="demo-ctl"><button type="button" data-a="reset">重置</button><button type="button" data-a="prev">上一步</button>'
            '<button type="button" data-a="play">播放</button><button type="button" data-a="next">下一步</button><span class="demo-count"></span></div>'
            f'<ol class="demo-log"></ol></div><script>(function(){{\nconst D = {data};\n{_js_body}}})();</script>')


def step(note, **panels):
    # 终端面板只认 tl(...) 自己带的 cur/mark/done;写在 step() 这一层的 mark=/done= 以前被悄悄丢掉了,这里并进去
    if isinstance(panels.get('t'), dict):
        t = dict(panels['t'])
        for k in ('cur', 'mark', 'done'):
            if k in panels and not isinstance(panels[k], dict) and panels[k]:
                t[k] = sorted(set(t.get(k, [])) | set(panels[k]))
        panels['t'] = t
    for k in ('mark', 'done'):
        if isinstance(panels.get(k), list): panels.pop(k)
    return {'note': note, 's': panels}


def nav_html(counts):
    n = _NAV
    total = sum(counts.values())
    n = re.sub(r'(全部文章</span>\s*<span class="md3-drawer-count">)\d+', lambda m: m.group(1) + str(total), n)
    for key, c in counts.items():
        n = re.sub(rf'(href="/\?series={key}".*?md3-drawer-count">)\d+', lambda m: m.group(1) + str(c), n, flags=re.S)
    return n


def render(a, counts):
    """a: dict(n, title, desc, lead, facts[(num,lbl)], body[html...], refs[str], )"""
    n = a['n']; ser = a.get('series', 'python'); T = {'redis': RTOPICS, 'django': DTOPICS, 'zookeeper': ZTOPICS, 'rust': UTOPICS, 'flask': FTOPICS, 'java': JTOPICS, 'go': GTOPICS, 'docker': CTOPICS, 'k8s': KTOPICS, 'gin': NTOPICS, 'git': ITOPICS, 'mongo': MTOPICS, 'crawler': PTOPICS, 'codec': ETOPICS, 'scrapy': YTOPICS, 'grpc': HTOPICS, 'rabbitmq': QTOPICS, 'network': WTOPICS, 'transaction': TTOPICS, 'microservice': VTOPICS, 'spring': XTOPICS}.get(ser, TOPICS); pre = ser
    slug = T[n]['slug']; url = f'{pre}-{slug}.html'
    title = a['title'] if 'title' in a else T[n]['title']
    desc = a['desc']
    prev = PREV71 if (ser == 'python' and n == 71) else ('queryset-sql.html', 'QuerySet 怎么编译成 SQL:filter() 链式调用为什么不查库,select_related 又是怎么把 N+1 变成 1 次的') if (ser == 'django' and n == 11) else None if (ser in ('zookeeper', 'rust', 'flask', 'java', 'go', 'docker', 'k8s', 'gin', 'git', 'mongo', 'crawler', 'codec', 'scrapy', 'grpc', 'rabbitmq', 'network', 'transaction', 'microservice', 'spring') and n == 1) else (f"{pre}-{T[n-1]['slug']}.html", T[n-1]['title'])
    nxt = (f"{pre}-{T[n+1]['slug']}.html", T[n+1]['title'], n + 1) if n + 1 in T else None
    SER = {'redis': 'Redis', 'django': 'Django', 'zookeeper': 'ZooKeeper', 'rust': 'Rust', 'flask': 'Flask', 'java': 'Java', 'go': 'Go', 'docker': 'Docker', 'k8s': 'Kubernetes', 'gin': 'Gin', 'git': 'Git', 'mongo': 'MongoDB', 'crawler': '爬虫工程', 'codec': '数据编码与压缩', 'scrapy': 'Scrapy', 'grpc': 'gRPC', 'rabbitmq': 'RabbitMQ', 'network': '网络协议', 'transaction': '分布式事务', 'microservice': '微服务', 'spring': 'Spring'}.get(ser, 'Python')
    NO = n + OFF.get(ser, 0)
    style = _style + EXTRA_CSS
    if ser == 'k8s': style += '.term pre.code{white-space:pre-wrap; word-break:break-word; overflow-x:visible;}\n'  # kubectl 输出里的长行自动换行,不横向滚动
    if ser == 'redis':
        style = (style.replace('--series-c:#306998; --series-c-soft:#E3EBF5;', '--series-c:#C6302B; --series-c-soft:#FBE1DF;')
                 .replace('--series-c:#5B9BD5; --series-c-soft:#1B2F4D;', '--series-c:#E0554D; --series-c-soft:#3D1613;'))
        assert '#C6302B' in style and '#306998' not in style
    if ser == 'django':
        style = (style.replace('--series-c:#306998; --series-c-soft:#E3EBF5;', '--series-c:#0C4B33; --series-c-soft:#DDEFE7;')
                 .replace('--series-c:#5B9BD5; --series-c-soft:#1B2F4D;', '--series-c:#3FAF7F; --series-c-soft:#12281F;'))
        assert '#0C4B33' in style and '#306998' not in style
    if ser == 'zookeeper':
        style = (style.replace('--series-c:#306998; --series-c-soft:#E3EBF5;', '--series-c:#7A5B2E; --series-c-soft:#F2E9D8;')
                 .replace('--series-c:#5B9BD5; --series-c-soft:#1B2F4D;', '--series-c:#D1A65C; --series-c-soft:#2E2312;'))
        assert '#7A5B2E' in style and '#306998' not in style
    if ser == 'rust':
        style = (style.replace('--series-c:#306998; --series-c-soft:#E3EBF5;', '--series-c:#B7410E; --series-c-soft:#F7E0D3;')
                 .replace('--series-c:#5B9BD5; --series-c-soft:#1B2F4D;', '--series-c:#E8805A; --series-c-soft:#3A1D12;'))
        assert '#B7410E' in style and '#306998' not in style
    if ser == 'flask':
        style = (style.replace('--series-c:#306998; --series-c-soft:#E3EBF5;', '--series-c:#4A5568; --series-c-soft:#E6E9EE;')
                 .replace('--series-c:#5B9BD5; --series-c-soft:#1B2F4D;', '--series-c:#9AA8BC; --series-c-soft:#232A35;'))
        assert '#4A5568' in style and '#306998' not in style
    if ser == 'java':
        style = (style.replace('--series-c:#306998; --series-c-soft:#E3EBF5;', '--series-c:#B85C00; --series-c-soft:#FBE7D1;')
                 .replace('--series-c:#5B9BD5; --series-c-soft:#1B2F4D;', '--series-c:#F29A4A; --series-c-soft:#3B2208;'))
        assert '#B85C00' in style and '#306998' not in style
    if ser in SERIES_COLORS:
        lc, ls, dc, ds = SERIES_COLORS[ser]
        style = (style.replace('--series-c:#306998; --series-c-soft:#E3EBF5;', f'--series-c:{lc}; --series-c-soft:{ls};')
                 .replace('--series-c:#5B9BD5; --series-c-soft:#1B2F4D;', f'--series-c:{dc}; --series-c-soft:{ds};'))
        assert lc in style and dc in style and '#306998' not in style
    facts = ''.join(f'<div><div class="num">{f[0]}</div><div class="lbl">{f[1]}</div></div>' for f in a['facts'])
    refs = ''.join(f'<li>{r}</li>' for r in a['refs'])
    nextsec = ''
    if nxt:
        nextsec = (f'<section>\n  <a class="next-post" href="{nxt[0]}">\n    <div>\n      <div class="t1">下一篇 · {SER.upper()} {nxt[2] + OFF.get(ser, 0)}</div>\n'
                   f'      <div class="t2">{esc(nxt[1])}</div>\n    </div>\n    <span aria-hidden="true">→</span>\n  </a>\n</section>\n')
    d = esc(desc).replace('"', '&quot;')
    t = esc(title)
    head = f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/assets/icons/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/assets/icons/favicon-192.png" sizes="192x192" type="image/png">
<link rel="apple-touch-icon" href="/assets/icons/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<title>{t}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="https://bigywater.tech/{url}">
<meta property="og:type" content="article">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="https://bigywater.tech/{url}">
<meta property="og:locale" content="zh_CN">
<meta property="og:site_name" content="bigywater.tech">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{t}">
<meta name="twitter:description" content="{d}">
<link rel="stylesheet" href="/assets/css/md3-shell.css">
<link rel="stylesheet" href="/assets/css/md3-article.css">
</head>
'''
    page = (head + nav_html(counts) + '<style>\n' + style + '</style>\n'
            f'<div class="hero"><div class="hero-inner">\n  <div class="eyebrow"><span class="dot"></span>{SER} · {NO}</div>\n  <h1>{t}</h1>\n'
            f'  <p>{a["lead"]}</p>\n  <div class="hero-fact">\n{facts}\n</div>\n</div></div>\n<div class="wrap">\n'
            + (f'<div class="prev-post">← 上一篇 <a href="{prev[0]}">{esc(prev[1])}</a></div>\n' if prev else '')
            + '\n'.join(a['body']) +
            f'\n<section>\n  <div class="refs">\n    <h3>本文用到的工具与边界</h3>\n    <ul>{refs}</ul>\n  </div>\n</section>\n'
            + nextsec + f'</div>\n<footer>{SER} · {t} · 实验记录 · {DATES.get(url, DATE)}</footer>\n</body>\n</html>\n')
    return url, title, page


# ---------- redis 系列辅助 ----------
def blk(name, k):
    """取 out/NAME.txt 里第 k 个 '== ' 小节(不含标题行)。"""
    L = out(name).splitlines(); starts = [i for i, l in enumerate(L) if l.startswith('== ')]
    i = starts[k - 1]; j = starts[k] if k < len(starts) else len(L)
    return '\n'.join(l for l in L[i + 1:j]).strip('\n')


def head(name, k):
    L = out(name).splitlines(); starts = [l for l in L if l.startswith('== ')]
    return starts[k - 1][3:]


def J(name):
    return json.loads(san((HERE / 'out' / f'{name}.json').read_text()))


RVER = json.loads((HERE / 'out' / 'rver.json').read_text())['ver'] if (HERE / 'out' / 'rver.json').exists() else '8.10.2'
ENV_D = '本机 macOS 27 / Python 3.14.7 / Django 6.1.1(默认用 SQLite,其它数据库会在文中注明),用 django.test.Client 或真实的本机服务器进程实测;计时用 time.perf_counter,数字每次运行会有小幅抖动'
ENV_Z = '本机 macOS 27 / ZooKeeper 3.9.6(brew 安装的 jar,用 java -cp 直接启动自己的实例,OpenJDK 17 Temurin,JVM 堆 128 MiB)/ 本机回环端口 7300+,数据在临时目录;默认 tickTime=2000;计时用 time.perf_counter,数字每次运行会有小幅抖动'
ENV_R = f'本机 macOS 27 / Redis {RVER} 独立实例(本机回环端口,save 关闭),redis-cli 风格输出由自写的 RESP 客户端打印;计时用 time.perf_counter,数字每次运行会有小幅抖动'


# ---------- 演示面板的小构造函数(art 里直接用) ----------
def KV(items, hl=()): return {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def tl(lines, cur=(), mark=(), done=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}

ENV_U = '本机 macOS 27 arm64 / rustc 1.98.1(brew)/ cargo 1.98.1;单个文件用 rustc 直接编译,需要依赖时用 cargo(经代理从 crates.io 下载);计时用 std::time::Instant,数字每次运行会有小幅抖动'

ENV_N = ENV_U + '。nightly 工具链用 rustup 装在隔离目录(不影响 brew 的 rustc):rustc 1.101.0-nightly (21b707e3f 2026-09-30)、miri 0.1.0 (21b707e3f9 2026-09-30)'

def lidx(lines, *subs, last=False):
    """返回含有任一子串的行号(用来给终端面板的 mark / done 定位)。"""
    r = [i for i, l in enumerate(lines) if any(s in l for s in subs)]
    import sys as _sys
    for s in subs:
        if not any(s in l for l in lines): print('[lidx 警告] 未匹配:', repr(s[:50]), file=_sys.stderr)
    return r[-1:] if (last and r) else r

def mkart(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels=None, series='rust'):
    """items: [(h2, note_html)] 依次对应实验输出的第 1..k 节;steps 由调用者用 S(k) 构造。"""
    _L = out(name).splitlines(); _n = len([l for l in _L if l.startswith('== ')])
    if _n != len(items) or _n != len(steps):
        raise SystemExit(f'[段数不一致] {name}: out 里有 {_n} 个 "== " 小节,但 items={len(items)}、steps={len(steps)};三者必须相等,否则最后的小节会被悄悄丢掉')
    body = [sec(h, '', term('', blk(name, k + 1)), *([note] if note else [])) for k, (h, note) in enumerate(items)]
    if panels is None and series in ('go', 'docker', 'k8s', 'gin', 'git', 'mongo', 'crawler', 'codec', 'scrapy', 'grpc', 'rabbitmq', 'network', 'transaction', 'microservice', 'spring'):  # 新批次系列:步骤里用了 b= 就真的渲染柱状图面板
        panels = [('t', 'term', '编译与运行输出')] + ([('b', 'bars', '数字对比')] if any('b' in st['s'] for st in steps) else []) + [('kv', 'kv', '要点')]
    body.append(sec('分步演示', '', demo(demo_title, panels or [('t', 'term', '编译与运行输出'), ('kv', 'kv', '要点')], steps, '本步的对象')))
    return dict(n=n, series=series, tags=tags, desc=desc, lead=lead, facts=facts, body=body, refs=refs)
def SS(name):
    return lambda k: [x for x in blk(name, k).splitlines() if x.strip()]

ENV_F = '本机 macOS 27 arm64 / Python 3.14.7 / Flask 3.1.3 / Werkzeug 3.1.9 / Jinja2 3.1.6 / SQLAlchemy 2.1.1 / gunicorn 26.2.0(都装在自己的虚拟环境里);大多数实验用 Flask 的 test_client(直接调用 WSGI 应用,不经过网络),需要真实 HTTP 时另起 gunicorn 或开发服务器(端口 9600 以上,本机 127.0.0.1);计时用 time.perf_counter,数字每次运行会有小幅抖动'
def mkartf(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels=None):
    return mkart(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels, series='flask')

ENV_X = '本机 macOS 27 arm64 / OpenJDK 21.0.12(Homebrew) / Spring Boot 4.0.8(Spring Framework 7.0.9、Tomcat 11.0.24) / Spring Cloud 2025.1.3;用 javac 编译、java 直接运行,依赖由 Maven 从 Maven Central 解析;数字每次运行会有小幅抖动'
ENV_J = '本机 macOS 27 arm64 / OpenJDK(Temurin 17.0.20、Homebrew 21.0.12 与 27,每篇注明实际用的版本);用 javac 编译、java 直接运行,需要第三方库时用 Maven 解析依赖;计时用 System.nanoTime,数字每次运行会有小幅抖动'
def mkartj(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels=None):
    return mkart(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels, series='java')

ENV_G = '本机 macOS 27 arm64 / Go 1.27.1(brew);用 go run / go build / go test 直接编译运行,需要第三方库时经代理从 proxy.golang.org 下载;计时用 time.Now / testing.B,数字每次运行会有小幅抖动'
def mkartg(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels=None):
    return mkart(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels, series='go')

ENV_C = '本机 macOS 27 arm64 / Docker Desktop(Engine 29.8.2,容器跑在 Docker Desktop 自带的 Linux 虚拟机里,内核与宿主机的 macOS 不同);镜像为 linux/arm64;需要看虚拟机内部时用特权容器 + nsenter;计时用 time / date +%s%N,数字每次运行会有小幅抖动'
def mkartc(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels=None):
    return mkart(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels, series='docker')

ENV_K = '本机 macOS 27 arm64 / kind(Docker 里的单节点或多节点真实集群,节点是 Docker Desktop 虚拟机里的容器)/ kubectl;用空的 kubeconfig 之外的独立 kubeconfig,不碰用户自己的集群;计时用 date +%s%N / kubectl 事件时间戳,数字每次运行会有小幅抖动'
def mkartk(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels=None):
    return mkart(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels, series='k8s')

ENV_N_GIN = '本机 macOS 27 arm64 / Go 1.27.1(brew)/ Gin v1.12.0(go.mod 里 require,源码在模块缓存里);用 go run / go test 直接编译运行,需要库时经代理从 proxy.golang.org 下载;HTTP 实验用 httptest 或本机回环端口(9700 以上);计时用 time.Now / testing.B,数字每次运行会有小幅抖动'
def mkartn(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels=None):
    return mkart(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels, series='gin')

ENV_I_GIT = '本机 macOS 27 arm64 / git 2.54.0(Apple Git-157);每个实验在临时目录里新建仓库,HOME 和全局配置指向实验专用的空目录(不读用户自己的 git 配置),提交的作者与时间固定以便复现;需要网络协议的实验用本机的 file:// 或 git daemon 回环端口(9800 以上),不碰任何远程仓库;计时用 time.perf_counter,数字每次运行会有小幅抖动'
def mkarti(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels=None):
    return mkart(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels, series='git')

ENV_M = '本机 macOS 27 arm64 / MongoDB 9.0.2(Homebrew 的 mongod、mongos)/ mongosh 2.12.0 / pymongo 4.18.3;每个实验在临时目录里起全新的 mongod(独立 dbpath,端口 9900 以上,只监听 127.0.0.1,WiredTiger 缓存 0.25 GB),需要副本集或分片集群时在本机起多个进程;命令输出来自真实的 mongosh,批量写入、计时与多线程用 pymongo;计时用 time.perf_counter,数字每次运行会有小幅抖动,ObjectId、时间戳等每次运行都不同'
def mkartm(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels=None):
    return mkart(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels, series='mongo')

ENV_P = '本机 macOS 27 arm64 / Python 3.14.8 / requests 2.34.2 / aiohttp 3.14.3 / lxml 6.1.1(系统 Python);所有请求只发给本机自己起的测试服务器(127.0.0.1,端口 9960 以上,不访问任何真实网站);服务器可以按实验需要制造延迟、断连、压缩、重定向等行为,并记录收到的原始请求;计时用 time.perf_counter,数字每次运行会有小幅抖动'
def mkartp(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels=None):
    return mkart(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels, series='crawler')

ENV_E = '本机 macOS 27 arm64 / Python 3.14.8(系统 Python,自带 compression.zstd)/ zstandard 0.25.0 / lz4 4.4.5 / zstd、lz4、brotli、protoc 命令行(Homebrew);msgpack、protobuf、snappy 等第三方库临时装在临时目录里,用完删除;所有数据都是本机脚本生成的合成数据(固定随机种子),没有使用任何真实网站或用户的数据;计时用 time.perf_counter,取多次中位数,数字每次运行会有小幅抖动'
def mkarte(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels=None):
    return mkart(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels, series='codec')

ENV_Y = '本机 macOS 27 arm64 / Python 3.14.8 / Scrapy 2.19.0 / Twisted 26.4.0 / lxml 6.1.3 / parsel 1.12.1(临时虚拟环境);所有请求只发给本机自己起的测试服务器(127.0.0.1,端口 9960 以上,不访问任何真实网站);服务器可以按实验需要制造延迟、重定向、压缩、断连等行为,并记录收到的原始请求;每个实验在临时目录里新建 Scrapy 项目或单文件 spider,命令输出来自真实的 scrapy 进程;计时用 time.perf_counter,数字每次运行会有小幅抖动'
def mkarts(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels=None):
    return mkart(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels, series='scrapy')

ENV_H = '本机 macOS 27 arm64 / Go 1.27.1 / grpc-go v1.84.0 / protobuf-go v1.36.12 / golang.org/x/net v0.57.0 / protoc 36.2(Homebrew);服务端和客户端都是本机起的 Go 进程(127.0.0.1,端口 9800 以上,不访问任何外部服务);需要看线上字节时用我自己写的 TCP 抓包代理加 golang.org/x/net/http2 的 Framer 解析 HTTP/2 帧;计时用 time.Now 或 perf_counter,数字每次运行会有小幅抖动'
def mkarth(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels=None):
    return mkart(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels, series='grpc')

ENV_Q = '本机 macOS 27 arm64 / RabbitMQ 4.3.6 / Erlang/OTP 28.5 / pika 1.4.4(Homebrew 与临时虚拟环境);所有节点都是本机自己起的 RabbitMQ 进程(127.0.0.1,端口 9500 以上,每个实验独立的数据目录与节点名,不连任何外部服务);命令输出来自真实的 rabbitmqctl 与管理 API,发布与消费用 pika 的真实连接;计时用 time.perf_counter,数字每次运行会有小幅抖动'
def mkartq(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels=None):
    return mkart(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels, series='rabbitmq')

ENV_W = '本机 macOS 27 arm64(Apple 芯片)/ Python 3.14.8 / tcpdump(libpcap)/ scapy 2.8 / dpkt / dnspython / h2 / aioquic / OpenSSL / curl 8.7.1;抓包在 lo0(环回)上做,少数实验用真实网卡 en0(这台机器上 en0 是 Wi-Fi,tcpdump 看到的是系统转成以太网格式的帧,所以文中的“以太网头”都指这个 14 字节的头)或访问公网(会在文章里注明);需要丢包 / 延迟 / 限速时,用一个只作用于 lo0 端口 9400-9499 的 dummynet 辅助脚本(netlab);所有服务端都是本机自己起的进程;时间戳取自 tcpdump 的 -tt,数字每次运行会有小幅抖动'
def mkartw(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels=None):
    return mkart(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels, series='network')

ENV_T = '本机 macOS 27 arm64 / MySQL 26.7.0 与 PostgreSQL 16.15(Homebrew,每个实验自己 initdb、自己起实例,端口 9150 以上,只监听 127.0.0.1)/ Python 3.14.8 + PyMySQL 1.2.3 + psycopg 3.3.6 / Redis 8.10.2 / Kafka 4.3.1 / RabbitMQ 4.3.6 / etcd 3.7.2(按各篇注明用到哪些);不连任何外部服务,不碰本机已有的数据库实例;故障用 kill -9 进程、让连接断开或在代码里的指定位置抛异常来制造;计时用 time.perf_counter,数字每次运行会有小幅抖动'
def mkartt(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels=None):
    return mkart(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels, series='transaction')

ENV_V = '本机 macOS 27 arm64 / Python 3.14.8 / Go / nginx / Envoy / etcd / Consul / Nacos / OpenTelemetry / Prometheus(按各篇注明用到哪些及版本);所有服务都是本机自己起的进程,端口 9150 以上,只监听 127.0.0.1,不连任何外部服务,不碰本机已有的实例;故障用 kill -9 进程、让连接断开或在代码里注入延迟与错误来制造;计时用 time.perf_counter,数字每次运行会有小幅抖动'
def mkartv(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels=None):
    return mkart(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels, series='microservice')

def mkartx(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels=None):
    return mkart(name, n, tags, desc, lead, facts, items, steps, refs, demo_title, panels, series='spring')
