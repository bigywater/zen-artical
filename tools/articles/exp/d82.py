import sys, os, time, json, re, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d82'); R = {}
files = {
    'app1/__init__.py': '', 'app1/templates/shared.html': 'shared FROM app1', 'app1/templates/only1.html': 'only in app1',
    'app2/__init__.py': '', 'app2/templates/shared.html': 'shared FROM app2', 'app2/templates/only2.html': 'only in app2',
    'templates/shared.html': 'shared FROM project templates dir', 'templates/proj_only.html': 'proj only',
}
apps = ['django.contrib.contenttypes', 'app1', 'app2']
d = proj('d82', files=files, apps=apps, with_lab=False)
def run(code, proj_dir=None): rc, out = pyscript(proj_dir or d, "import logging, time; logging.disable(logging.CRITICAL)\nfrom django.template.loader import get_template, select_template, render_to_string\nfrom django.template import engines\n" + code); return out.rstrip()
print('== 一:同名模板出现在多个位置时谁赢:DIRS 优先,其次按 INSTALLED_APPS 顺序')
o = run("""
print('shared.html →', render_to_string('shared.html'))
e = engines['django']; print('loaders:', [l.__class__.__name__ for l in e.engine.template_loaders], ' 内部:', [type(x).__name__ for x in e.engine.template_loaders[0].loaders] if hasattr(e.engine.template_loaders[0], 'loaders') else '')
print('only1.html →', render_to_string('only1.html'), '|', 'only2.html →', render_to_string('only2.html'))
print('列出 shared.html 的所有候选(按尝试顺序):')
for l in e.engine.template_loaders[0].loaders:
    print('   ', type(l).__name__, [str(o.name) for o in l.get_template_sources('shared.html')])
""")
print(o); R['order'] = o
print()
print('== 二:把 app 的顺序反过来,同名模板换了赢家')
d2 = proj('d82b', files=files, apps=['django.contrib.contenttypes', 'app2', 'app1'], with_lab=False, settings_extra="\nTEMPLATES[0]['DIRS'] = []\n")
o = run("print('DIRS 为空,INSTALLED_APPS = [app2, app1] →', render_to_string('shared.html'))", d2)
print(o); R['reverse'] = o
d3 = proj('d82c', files=files, apps=apps, with_lab=False, settings_extra="\nTEMPLATES[0]['DIRS'] = []\n")
o = run("print('DIRS 为空,INSTALLED_APPS = [app1, app2] →', render_to_string('shared.html'))", d3)
print(o); R['forward'] = o
print()
print('== 三:找不到模板:TemplateDoesNotExist 会列出所有尝试过的位置')
o = run("""
from django.template import TemplateDoesNotExist
try: get_template('missing.html')
except TemplateDoesNotExist as e:
    print('异常:', e); ch = getattr(e, 'chain', []); print('chain 里的引擎异常数:', len(ch)); tr = [t for x in ch for t in x.tried]; print('尝试过的位置共', len(tr), '条:'); [print('   ', str(o.name).split('djtmp/')[-1], '→', st) for o, st in tr]
try: select_template(['nope1.html', 'only1.html']); print('select_template 选到了第一个存在的:', select_template(['nope1.html', 'only1.html']).origin.template_name)
except TemplateDoesNotExist as e: print(e)
""")
print(o); R['missing'] = o
print()
print('== 四:cached 模板加载器:编译结果缓存在进程里(第一次慢,之后快);关闭 cached 后每次都重新读盘编译')
big = "{% for i in items %}<li>{{ i }} {% if i > 5 %}big{% else %}small{% endif %}</li>{% endfor %}" * 40
def bench(cached):
    dd = proj('d82d', files={'templates/big.html': big}, apps=['django.contrib.contenttypes'], with_lab=False, settings_extra=("\nTEMPLATES[0]['APP_DIRS'] = False\nTEMPLATES[0]['OPTIONS']['loaders'] = " + ("[('django.template.loaders.cached.Loader', ['django.template.loaders.filesystem.Loader'])]" if cached else "['django.template.loaders.filesystem.Loader']") + "\n"))
    rc, out = pyscript(dd, """
import time, statistics
from django.template.loader import get_template
t0 = time.perf_counter(); get_template('big.html'); first = (time.perf_counter() - t0) * 1000
xs = []
for _ in range(300):
    t0 = time.perf_counter(); get_template('big.html'); xs.append((time.perf_counter() - t0) * 1000)
print('%.3f %.4f' % (first, statistics.median(xs)))
""")
    a, b = map(float, out.strip().split()); return a, b
R['cache'] = {}
for label, cached in (('cached loader', True), ('没有 cached', False)):
    a, b = bench(cached); R['cache'][label] = dict(first=a, median=b); print(f'  {label:<14} 第一次 get_template {a:8.3f} ms   之后每次(300 次中位){b:9.4f} ms')
d4 = proj('d82e', files={'templates/x.html': 'x'}, apps=['django.contrib.contenttypes'], with_lab=False, settings_extra="\nDEBUG = %s\n")
for dbg in (True, False):
    dd = proj('d82f', files={'templates/x.html': 'x'}, apps=['django.contrib.contenttypes'], with_lab=False, settings_extra=f"\nDEBUG = {dbg}\n")
    rc, out = pyscript(dd, "from django.template import engines\nprint([type(l).__module__ + '.' + type(l).__name__ for l in engines['django'].engine.template_loaders])"); print(f'  DEBUG={dbg}(未显式设置 loaders)时的加载器:', out.strip()); R.setdefault('debug_loaders', {})[str(dbg)] = out.strip()
save('d82', R)
