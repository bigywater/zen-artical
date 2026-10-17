import sys, os, subprocess, textwrap, json, importlib.metadata as md; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
tee('p47')
d = pdir('p47')
env = {k: v for k, v in os.environ.items() if 'proxy' not in k.lower()}
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--target', str(d / 'site'), 'selectolax'], capture_output=True, env=env)
ROW = '<tr class="r"><td><a href="/item/%d">商品 %d</a></td><td class="p">¥%d.00</td><td><span>库存 %d</span></td></tr>\n'
def make(mb):
    path = d / f'big_{mb}.html'
    target = mb * 1048576
    with open(path, 'w', encoding='utf-8') as f:
        f.write('<html><head><title>big</title></head><body><table>'); n = 0; w = 0
        while w < target:
            s = ROW % (n, n, n % 97, n % 13); f.write(s); w += len(s.encode()); n += 1
        f.write('</table></body></html>')
    return path, n
CHILD = textwrap.dedent(r'''
    import sys, time, resource, json, io
    sys.path.insert(0, sys.argv[3])
    mode, path = sys.argv[1], sys.argv[2]
    import lxml.html, lxml.etree as ET
    base = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576
    t0 = time.perf_counter(); n = 0; total = 0
    if mode == "fromstring":
        data = open(path, "rb").read(); doc = lxml.html.fromstring(data); n = len(doc.xpath("//tr"))
    elif mode == "parse_file":
        doc = lxml.html.parse(path); n = len(doc.xpath("//tr"))
    elif mode == "iterparse_keep":
        for ev, el in ET.iterparse(path, events=("end",), tag="tr", html=True): n += 1
    elif mode == "iterparse_clear":
        for ev, el in ET.iterparse(path, events=("end",), tag="tr", html=True):
            n += 1
            el.clear()
    elif mode == "iterparse_clear_siblings":
        for ev, el in ET.iterparse(path, events=("end",), tag="tr", html=True):
            n += 1
            el.clear()
            while el.getprevious() is not None: del el.getparent()[0]
    elif mode == "lexbor":
        from selectolax.lexbor import LexborHTMLParser
        doc = LexborHTMLParser(open(path, "rb").read()); n = len(doc.css("tr"))
    elif mode == "html_parser":
        from html.parser import HTMLParser
        class P(HTMLParser):
            def __init__(self): super().__init__(); self.n = 0
            def handle_starttag(self, tag, attrs):
                if tag == "tr": self.n += 1
        p = P()
        with open(path, "r", encoding="utf-8") as f:
            while True:
                chunk = f.read(1 << 20)
                if not chunk: break
                p.feed(chunk)
        p.close(); n = p.n
    el = time.perf_counter() - t0
    print(json.dumps(dict(n=n, secs=el, base=base, peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576)))
''')
(d / 'c.py').write_text(CHILD)
def run(mode, path):
    o = subprocess.run([sys.executable, str(d / 'c.py'), mode, str(path), str(d / 'site')], capture_output=True, text=True, env=env, timeout=600)
    try: return json.loads(o.stdout.strip().splitlines()[-1])
    except Exception: return {'err': (o.stderr.strip().splitlines() or ['?'])[-1][:100]}

MODES = [('fromstring', 'lxml.html.fromstring(整个文件读进内存再解析)'), ('parse_file', 'lxml.html.parse(文件路径)'), ('iterparse_keep', 'iterparse(tag="tr"),不清理'), ('iterparse_clear', 'iterparse + el.clear()'),
         ('iterparse_clear_siblings', 'iterparse + el.clear() + 删掉前面的兄弟'), ('lexbor', 'selectolax Lexbor(整个文件读进内存)'), ('html_parser', '标准库 html.parser,按 1 MiB 分块 feed')]
print('== 一:峰值内存与耗时(每个解析方式在独立子进程里跑,峰值内存取 ru_maxrss,"净增"=峰值减去刚导入库之后的内存)')
files = {}
for mb in (5, 25, 100):
    path, n = make(mb); files[mb] = (path, n)
    print(f'  --- 文件 {mb} MiB(磁盘上实际 {os.path.getsize(path) / 1048576:.1f} MiB),{n:,} 行 <tr> ---')
    print(f'  {"方式":<44}{"耗时":>8}{"峰值内存":>10}{"净增":>9}{"净增 / 文件大小":>12}')
    for mode, lab in MODES:
        if mode == 'html_parser' and mb > 25: continue
        r = run(mode, path)
        if 'err' in r: print(f'  {lab:<40}失败:{r["err"]}'); continue
        assert r['n'] >= n - 2, (mode, r, n)
        print(f'  {lab:<40}{r["secs"]:>6.2f} 秒{r["peak"]:>8.0f} MiB{r["peak"] - r["base"]:>7.0f} MiB{(r["peak"] - r["base"]) / mb:>10.1f} 倍')
print('  (html.parser 在 100 MiB 的文件上没有跑,太慢)')
print('== 二:流式解析提取数据的写法:每个 <tr> 到达时就取出需要的字段,再清理(文件没有声明编码,要给 iterparse 传 encoding="utf-8")')
CODE = r'''
import lxml.etree as ET, sys, time
t0 = time.perf_counter(); rows = 0; s = 0
enc = sys.argv[2] if len(sys.argv) > 2 else None
try:
    for ev, tr in ET.iterparse(sys.argv[1], events=("end",), tag="tr", html=True, **({"encoding": enc} if enc else {})):
        price = tr.find(".//td[@class='p']")
        s += int(price.text.strip("¥").split(".")[0]); rows += 1
        tr.clear()
        while tr.getprevious() is not None: del tr.getparent()[0]
    print(rows, s, round(time.perf_counter() - t0, 2))
except Exception as e:
    print("ERR", type(e).__name__, str(e)[:60])
'''
(d / 'ex.py').write_text(CODE, encoding='utf-8')
p25 = files[25][0]
o = subprocess.run([sys.executable, str(d / 'ex.py'), str(p25)], capture_output=True, text=True, env=env).stdout.split()
print(f'  不传 encoding(libxml2 把没声明编码的 HTML 当 Latin-1,"¥" 读成 "Â¥"):{" ".join(o)}')
o = subprocess.run([sys.executable, str(d / 'ex.py'), str(p25), 'utf-8'], capture_output=True, text=True, env=env).stdout.split()
print(f'  传 encoding="utf-8":提取 {o[0]} 行,价格合计 {o[1]},{o[2]} 秒;代码要点:events=("end",)、tag="tr"、html=True,处理完一行就 clear() 并删除前面的兄弟')
print('== 三:流式提取的结果与整棵树提取的结果一致吗(25 MiB 文件)')
CODE2 = r'''
import lxml.html, sys
doc = lxml.html.parse(sys.argv[1], parser=lxml.html.HTMLParser(encoding="utf-8"))
trs = doc.xpath("//tr"); s = sum(int(t.xpath(".//td[@class='p']")[0].text.strip("¥").split(".")[0]) for t in trs)
print(len(trs), s)
'''
(d / 'ex2.py').write_text(CODE2, encoding='utf-8')
full = subprocess.run([sys.executable, str(d / 'ex2.py'), str(p25)], capture_output=True, text=True, env=env).stdout.split()
print(f'  整棵树:{full[0]} 行,价格合计 {full[1]};流式:{o[0]} 行,价格合计 {o[1]};两者一致:{full[:2] == o[:2]}')
purge()
