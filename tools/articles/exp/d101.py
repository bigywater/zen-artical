import sys, os, time, json, re, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d101'); R = {}
models = "from django.db import models\nclass Author(models.Model):\n    name = models.CharField(max_length=20)\nclass Post(models.Model):\n    title = models.CharField(max_length=20)\n    author = models.ForeignKey(Author, on_delete=models.CASCADE)\n"
views = "from django.http import HttpResponse\nfrom lab.models import *\ndef page(request):\n    out = []\n    for p in Post.objects.all(): out.append(p.author.name)\n    return HttpResponse('<html><body>' + ','.join(out) + '</body></html>')\ndef page_ok(request):\n    return HttpResponse('<html><body>' + ','.join(p.author.name for p in Post.objects.select_related('author')) + '</body></html>')\ndef dup(request):\n    for _ in range(3): list(Author.objects.filter(name='a1'))\n    return HttpResponse('<html><body>dup</body></html>')\n"
urls = "from django.urls import path, include\nfrom lab import views\nurlpatterns = [path('page/', views.page), path('ok/', views.page_ok), path('dup/', views.dup), path('__debug__/', include('debug_toolbar.urls'))]\n"
apps = ['django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.staticfiles', 'debug_toolbar', 'lab']
def build(toolbar):
    mw = (['debug_toolbar.middleware.DebugToolbarMiddleware'] if toolbar else [])
    d = proj('d101', files={'lab/models.py': models, 'lab/views.py': views}, urls=urls, apps=apps, middleware=mw, settings_extra="\nINTERNAL_IPS = ['127.0.0.1']\nDEBUG = True\n"); manage(d, 'makemigrations', 'lab'); manage(d, 'migrate'); return d
def run(d, code): rc, out = pyscript(d, "import logging, re, time, statistics; logging.disable(logging.CRITICAL)\nfrom django.test import Client\nfrom lab.models import *\nif not Post.objects.exists():\n    A = Author.objects.bulk_create([Author(name=f'a{i}') for i in range(10)]); Post.objects.bulk_create([Post(title=f't{i}', author=A[i % 10]) for i in range(100)])\nc = Client(REMOTE_ADDR='127.0.0.1')\n" + code); return out.rstrip()
d = build(True)
HELP = "import html as H\ndef panel(path):\n    r = c.get(path); rid = re.search(r'data-request-id=\"([0-9a-f]+)\"', r.content.decode()).group(1)\n    body = c.get('/__debug__/render_panel/?request_id=%s&panel_id=SQLPanel' % rid, HTTP_X_REQUESTED_WITH='XMLHttpRequest').json()['content']\n    txt = re.sub(r'\\s+', ' ', H.unescape(re.sub(r'<[^>]+>', ' ', body)))\n    return r, rid, body, txt\ndef summary(txt): return re.search(r'default ([\\d.]+) ms \\((.*?)\\)', txt).groups()\n"
print('== 一:请求一个 N+1 页面(100 篇文章、每篇访问 author),响应里被注入了工具栏;从里面取出 request_id,再请求 SQL 面板')
o = run(d, HELP + """
r, rid, body, txt = panel('/page/')
print('响应状态', r.status_code, ' 响应里有工具栏(djDebug)吗:', 'djDebug' in r.content.decode())
print('request_id 形如:', rid[:8] + '…', '(每个请求一个,面板内容存在服务端,前端按它取)')
t, s = summary(txt); print('SQL 面板摘要:', f'default {t} ms ({s})')
print('提示行:', re.findall(r'\\d+ similar queries\\. Duplicated \\d+ times\\.|\\d+ similar queries', txt)[:2])
print('面板里带调用栈(能看到是哪一行代码发的查询)——出现 views.py 行:', 'views.py' in txt, ' 出现 site-packages 行:', 'site-packages' in txt)
""")
print(o); R['panel'] = o
print()
print('== 二:同样的页面用 select_related 修复后,面板里的查询数')
o = run(d, HELP + """
r, rid, body, txt = panel('/ok/'); t, s = summary(txt); print('修复后 SQL 面板摘要:', f'default {t} ms ({s})')
""")
print(o); R['fixed'] = o
print()
print('== 三:重复查询(同一条 SQL 被执行 3 次)')
o = run(d, HELP + """
r, rid, body, txt = panel('/dup/'); t, s = summary(txt); print('SQL 面板摘要:', f'default {t} ms ({s})'); print('提示:', re.findall(r'\\d+ similar queries\\. Duplicated \\d+ times\\.', txt))
""")
print(o); R['dup'] = o
print()
print('== 四:工具栏的开销:同一个页面(101 次查询),有无工具栏的请求耗时(30 次中位)')
R['overhead'] = {}
for label, tb in (('没有工具栏', False), ('有工具栏', True)):
    dd = build(tb)
    o = run(dd, """
c.get('/page/'); xs = []
for _ in range(30):
    t0 = time.perf_counter(); c.get('/page/'); xs.append((time.perf_counter() - t0) * 1000)
print('%.2f' % statistics.median(xs))
""")
    R['overhead'][label] = float(o.strip().splitlines()[-1]); print(f'  {label:<8} {R["overhead"][label]:.2f} ms')
save('d101', R)
