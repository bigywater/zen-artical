import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f64'); R = {}
import time, textwrap
from jinja2 import Environment, FileSystemLoader, FileSystemBytecodeCache, MemcachedBytecodeCache
N = 300
files = {}
for i in range(N):
    body = '\n'.join(f'<li>{{{{ item{j}|upper }}}} {{% if flag{j} %}}yes{{% else %}}no{{% endif %}} {{% for r in rows %}}<b>{{{{ r.a }}}}</b>{{% endfor %}}</li>' for j in range(15))
    files[f'templates/page{i}.html'] = body
d = mkapp('f64', files); tpath = str(d / 'templates'); cdir = d / 'bccache'
SCRIPT = '''
import sys, time, os
from jinja2 import Environment, FileSystemLoader, FileSystemBytecodeCache
use_cache = sys.argv[1] == "cache"; cdir = sys.argv[2]; n = int(sys.argv[3]); tpath = sys.argv[4]
kw = dict(bytecode_cache=FileSystemBytecodeCache(cdir)) if use_cache else {}
env = Environment(loader=FileSystemLoader(tpath), auto_reload=False, **kw)
ctx = {f"item{j}": "x" for j in range(15)}; ctx.update({f"flag{j}": 1 for j in range(15)}); ctx["rows"] = [{"a": 1}, {"a": 2}]
t0 = time.perf_counter(); first = None
for i in range(n):
    env.get_template(f"page{i}.html").render(**ctx)
    if i == 0: first = time.perf_counter() - t0
print(f"{first * 1000:.2f} {(time.perf_counter() - t0) * 1000:.1f}")
'''
(d / 'run.py').write_text(SCRIPT)
def run(mode):
    r = subprocess.run([PY, 'run.py', mode, str(cdir), str(N), tpath], cwd=d, capture_output=True, text=True, env=env(d)); a, b = r.stdout.split(); return float(a), float(b)
print(f'== 一:一个新进程里首次渲染 {N} 个模板(每个 15 行、含循环/过滤器/条件)的耗时:没有字节码缓存')
R['nocache'] = [run('none') for _ in range(3)]
for a, b in R['nocache']: print(f'  第一个模板 {a:.2f} ms;{N} 个模板共 {b:.1f} ms')
print()
print('== 二:FileSystemBytecodeCache:第一次(写缓存)与之后(读缓存)')
shutil.rmtree(cdir, ignore_errors=True); cdir.mkdir()
R['write'] = run('cache'); print(f'  第一次(缓存目录是空的,编译并写入):第一个 {R["write"][0]:.2f} ms;{N} 个共 {R["write"][1]:.1f} ms')
files_ = sorted(cdir.iterdir()); print(f'  缓存目录里生成了 {len(files_)} 个文件;示例文件名:{files_[0].name};单个大小约 {files_[0].stat().st_size} 字节;总计 {sum(f.stat().st_size for f in files_) / 1024:.0f} KiB'); R['files'] = [len(files_), files_[0].name, files_[0].stat().st_size, sum(f.stat().st_size for f in files_)]
R['read'] = [run('cache') for _ in range(3)]
for a, b in R['read']: print(f'  之后的新进程(读缓存):第一个 {a:.2f} ms;{N} 个共 {b:.1f} ms')
import statistics
nc = statistics.median(b for a, b in R['nocache']); rd = statistics.median(b for a, b in R['read']); print(f'  {N} 个模板:无缓存中位数 {nc:.1f} ms → 读缓存中位数 {rd:.1f} ms,快 {nc / rd:.1f} 倍'); R['ratio'] = [nc, rd]
print()
print('== 三:模板源码变了之后:缓存按源码校验和失效,只重新编译变了的那一个')
(d / 'templates' / 'page0.html').write_text((d / 'templates' / 'page0.html').read_text() + '\n<!-- changed -->')
from jinja2 import Environment
e = Environment(loader=FileSystemLoader(tpath), auto_reload=False, bytecode_cache=FileSystemBytecodeCache(str(cdir))); before = {f.name: f.stat().st_mtime_ns for f in cdir.iterdir()}
time.sleep(0.01); e.get_template('page0.html'); e.get_template('page1.html'); after = {f.name: f.stat().st_mtime_ns for f in cdir.iterdir()}
changed = [n for n in after if after[n] != before.get(n)]; print(f'  修改 page0.html 后加载 page0 与 page1:缓存目录里被重写的文件数 = {len(changed)}(只有被修改的 page0)'); R['invalidate'] = len(changed)
print()
print('== 四:在 Flask 里启用:app.jinja_env.bytecode_cache = FileSystemBytecodeCache(目录)(要在第一次渲染之前设)')
from flask import Flask, render_template
a = Flask('bc', root_path=str(d)); a.jinja_env.bytecode_cache = FileSystemBytecodeCache(str(d / 'bccache2')); (d / 'bccache2').mkdir(exist_ok=True)
ctx = {f'item{j}': 'x' for j in range(15)}; ctx.update({f'flag{j}': 1 for j in range(15)}); ctx['rows'] = [{'a': 1}]
with a.test_request_context('/'): render_template('page5.html', **ctx)
print('  Flask 渲染一个模板后缓存目录里的文件:', [f.name[:30] for f in (d / 'bccache2').iterdir()]); R['flask'] = len(list((d / 'bccache2').iterdir()))
print()
print('== 五:多个 gunicorn worker 与缓存:每个 worker 是独立进程,各自编译;共享的磁盘缓存能让后启动的 worker 跳过编译(这里量「重启后第一个请求」)')
d3 = mkapp('f64g', {'app.py': 'import os\nfrom flask import Flask, render_template\nfrom jinja2 import FileSystemBytecodeCache\napp = Flask(__name__, template_folder=os.environ["TPATH"])\nif os.environ.get("BC"): app.jinja_env.bytecode_cache = FileSystemBytecodeCache(os.environ["BC"])\n@app.get("/p/<int:i>")\ndef p(i):\n    ctx = {f"item{j}": "x" for j in range(15)}; ctx.update({f"flag{j}": 1 for j in range(15)}); ctx["rows"] = [{"a": 1}]\n    return render_template(f"page{i}.html", **ctx)\n'})
R['gun'] = {}
for label, bc in (('无缓存', ''), ('有磁盘缓存(首次启动,写入)', str(d / 'bcg')), ('有磁盘缓存(再次启动,读取)', str(d / 'bcg'))):
    if label.startswith('有磁盘缓存(首次'): shutil.rmtree(d / 'bcg', ignore_errors=True); (d / 'bcg').mkdir()
    with Server(d3, ['gunicorn', '-b', '127.0.0.1:{port}', '--workers', '1', 'app:app'], TPATH=tpath, BC=bc) as s:
        t0 = time.perf_counter(); [s.get(f'/p/{i}') for i in range(60)]; tt = (time.perf_counter() - t0) * 1000
    R['gun'][label] = tt; print(f'  {label:<30} 新启动的服务器上,头 60 个不同页面的请求共 {tt:.0f} ms')
save('f64', R)
