import sys, os, time, json, re, threading, queue; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d119'); R = {}
pg = PG(9474).start()
models = "from django.db import models\nclass Order(models.Model):\n    name = models.CharField(max_length=20)\n    status = models.CharField(max_length=10, default='new')\n"
urls = '''
from django.urls import path
from django.http import HttpResponse
from django.db import transaction
from lab.models import Order
import lab.worker as W
def create_early(request):
    o = Order.objects.create(name='v'); W.Q.put(o.pk); return HttpResponse('ok')
def create_oncommit(request):
    o = Order.objects.create(name='v'); transaction.on_commit(lambda: W.Q.put(o.pk)); return HttpResponse('ok')
urlpatterns = [path('early/', create_early), path('oncommit/', create_oncommit)]
'''
worker = '''
import queue, threading
from django.db import connections
from lab.models import Order
Q = queue.Queue(); RES = queue.Queue()
def loop():
    while True:
        pk = Q.get()
        if pk is None: break
        try: RES.put(('found' if Order.objects.filter(pk=pk).exists() else 'missing'))
        finally: connections.close_all()
threading.Thread(target=loop, daemon=True).start()
'''
d = proj('d119', files={'lab/models.py': models, 'lab/worker.py': worker}, urls=urls, databases=pg.databases(", 'ATOMIC_REQUESTS': True"), apps=['django.contrib.contenttypes', 'lab'], middleware=[])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
def run(code, timeout=300): rc, out = pyscript(d, "import logging, time, collections; logging.disable(logging.CRITICAL)\nfrom django.db import connection, connections, transaction\nfrom django.test import Client\nfrom lab.models import Order\nimport lab.worker as W\ndef drain(n): return collections.Counter(W.RES.get(timeout=5) for _ in range(n))\n" + code, timeout); return out.rstrip()
print('== 一:worker 线程(另一个数据库连接)收到任务 id 后立刻查订单。三种入队方式')
o = run("""
N = 200
for _ in range(N):
    with transaction.atomic():
        o = Order.objects.create(name='x'); W.Q.put(o.pk)
print('  atomic 里入队,入队后立刻退出 atomic(提交)      共 %d 次:' % N, dict(drain(N)))
N2 = 40
for _ in range(N2):
    with transaction.atomic():
        o = Order.objects.create(name='x'); W.Q.put(o.pk); time.sleep(0.05)
print('  atomic 里入队,入队后再做 50 ms 别的事才提交     共 %d 次:' % N2, dict(drain(N2)))
for _ in range(N):
    with transaction.atomic():
        o = Order.objects.create(name='x'); pk = o.pk
        transaction.on_commit(lambda pk=pk: W.Q.put(pk))
print('  on_commit 里入队                                共 %d 次:' % N, dict(drain(N)))
""")
print(o); R['race'] = o
print()
print('== 二:ATOMIC_REQUESTS = True 时,视图里入队(视图返回后才提交):通过 Client 请求 200 次')
o = run("""
c = Client(); N = 200
for _ in range(N): c.get('/early/')
print('  视图里直接入队:', dict(drain(N)))
for _ in range(N): c.get('/oncommit/')
print('  视图里 on_commit 入队:', dict(drain(N)))
""")
print(o); R['atomic_req'] = o
print()
print('== 三:worker 端加重试(每次隔 20 ms,最多 5 次)能补救吗?')
o = run("""
import threading, queue
Q2, RES2 = queue.Queue(), queue.Queue()
def loop():
    while True:
        pk = Q2.get()
        for i in range(1, 6):
            try: ok = Order.objects.filter(pk=pk).exists()
            finally: connections.close_all()
            if ok: RES2.put(i); break
            time.sleep(0.02)
        else: RES2.put(0)
threading.Thread(target=loop, daemon=True).start()
N2 = 40
for _ in range(N2):
    with transaction.atomic():
        o = Order.objects.create(name='x'); Q2.put(o.pk); time.sleep(0.05)
import collections
print('  atomic 里入队 + 50 ms 后才提交,worker 第几次尝试查到(0 = 5 次都没查到):', dict(sorted(collections.Counter(RES2.get(timeout=5) for _ in range(N2)).items())))
""")
print(o); R['retry'] = o
pg.stop(); save('d119', R)
