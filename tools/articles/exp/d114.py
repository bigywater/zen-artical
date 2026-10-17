import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
import asrv
tee('d114'); R = {}
models = "from django.db import models\nclass Item(models.Model):\n    name = models.CharField(max_length=20)\n"
urls = '''
from django.urls import path
from django.http import HttpResponse
from lab.models import Item
def ping(request): return HttpResponse('ok')
async def bad(request):
    n = Item.objects.count()
    return HttpResponse(str(n))
async def good(request):
    return HttpResponse(str(await Item.objects.acount()))
urlpatterns = [path('ping/', ping), path('bad/', bad), path('good/', good)]
'''
d = proj('d114', files={'lab/models.py': models}, urls=urls, apps=['django.contrib.contenttypes', 'lab'], middleware=[])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
def run(code, **e): rc, out = pyscript(d, "import asyncio, logging; logging.disable(logging.CRITICAL)\nfrom lab.models import Item\nfrom django.db import connection\nfrom asgiref.sync import sync_to_async\n" + code, **e); return out.rstrip()
print('== 一:在 async 代码里直接调用同步 ORM(asyncio.run 里)')
o = run("""
async def main():
    for label, fn in (('Item.objects.count()', lambda: Item.objects.count()), ('list(Item.objects.all())', lambda: list(Item.objects.all())), ('Item.objects.create(name="x")', lambda: Item.objects.create(name='x')), ('connection.cursor()', lambda: connection.cursor())):
        try: fn(); print(f'  {label:<32} → 没有报错')
        except Exception as e: print(f'  {label:<32} → {type(e).__name__}: {str(e)[:78]}')
asyncio.run(main())
""")
print(o); R['direct'] = o
print()
print('== 二:三种正确写法')
o = run("""
async def main():
    print('  await Item.objects.acount() →', await Item.objects.acount())
    print('  await sync_to_async(Item.objects.count)() →', await sync_to_async(Item.objects.count)())
    print('  [i async for i in Item.objects.all()] →', len([i async for i in Item.objects.all()]), '行')
asyncio.run(main())
""")
print(o); R['ok'] = o
print()
print('== 三:环境变量 DJANGO_ALLOW_ASYNC_UNSAFE=true 会关掉这个检查(不解决问题,只是不再报错)')
o = run("""
async def main():
    try: print('  在 async 里直接 count() →', Item.objects.count())
    except Exception as e: print('  ', type(e).__name__)
asyncio.run(main())
""", DJANGO_ALLOW_ASYNC_UNSAFE='true')
print(o); R['unsafe'] = o
print()
print('== 四:真实的 uvicorn 服务:async 视图里直接 count() 得到什么响应')
p = asrv.serve(d, 'uvicorn', 9508)
try:
    st, b, _ = asrv.get(9508, '/bad/'); m = re.search(r'<title>(.*?)</title>', b, re.S)
    print('  /bad/  状态码', st, ' 页面标题:', re.sub(r'\s+', ' ', m.group(1)).strip()[:110] if m else b[:100])
    st, b, _ = asrv.get(9508, '/good/'); print('  /good/ 状态码', st, ' 内容:', b)
    R['server'] = dict(bad=st)
finally: asrv.stop(p)
import subprocess
print('  检查用的装饰器(读源码):', subprocess.run(['grep', '-n', 'def async_unsafe', str(HERE.parent / 'djlab/lib/python3.14/site-packages/django/utils/asyncio.py')], capture_output=True, text=True).stdout.strip().replace(':', ' 行:', 1).join(['django/utils/asyncio.py 第 ', '']))
save('d114', R)
