import sys, os, time, json, re, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sec import *
tee('d133'); R = {}
models = "from django.db import models\nclass Doc(models.Model):\n    file = models.FileField(upload_to='docs/')\n"
views = '''
import os
from django.conf import settings
from django.http import HttpResponse, FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from lab.models import Doc
@csrf_exempt
def upload(request):
    f = request.FILES['f']
    d = Doc(); d.file.save(f.name, f); return JsonResponse({'saved_as': d.file.name, 'cls': type(f).__name__, 'size': f.size})
@csrf_exempt
def fields(request): return HttpResponse(str(len(request.POST)))
def download(request, name):
    return FileResponse(open(os.path.join(str(settings.MEDIA_ROOT), name), 'rb'), as_attachment=request.GET.get('att') == '1')
'''
urls = "from django.urls import path\nfrom django.conf import settings\nfrom django.conf.urls.static import static\nfrom lab import views\nurlpatterns = [path('upload/', views.upload), path('fields/', views.fields), path('dl/<path:name>', views.download)] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)\n"
d = proj('d133', files={'lab/models.py': models, 'lab/views.py': views}, urls=urls, apps=['django.contrib.contenttypes', 'lab'], middleware=[], settings_extra=ES + "\nMEDIA_ROOT = BASE_DIR / 'media'\nMEDIA_URL = 'media/'\n")
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
MD = str(d / 'media')
def run(code, **st):
    shutil.rmtree(d / 'media', ignore_errors=True)
    return srun(d, "import io, os\nfrom django.core.files.uploadedfile import SimpleUploadedFile\nc = Client(raise_request_exception=False)\nMEDIA = settings.MEDIA_ROOT\ndef up(name, data=b'x', **kw): return c.post('/upload/', {'f': SimpleUploadedFile(name, data)}, HTTP_HOST='x', **kw)\n" + code, ALLOWED_HOSTS=['*'], **st)
print('== 一:DEBUG=False 时 Django 不提供 /media/;static() 辅助函数只在 DEBUG=True 时返回路由')
o = srun(d, "import os\nfrom django.conf.urls.static import static\nprint('  DEBUG =', settings.DEBUG, '→ static(MEDIA_URL, document_root=…) 返回的路由数:', len(static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)))\nos.makedirs(settings.MEDIA_ROOT, exist_ok=True); open(os.path.join(settings.MEDIA_ROOT, 'a.txt'), 'w').write('hi')\nprint('  GET /media/a.txt →', Client(raise_request_exception=False).get('/media/a.txt', HTTP_HOST='x').status_code)", ALLOWED_HOSTS=['*'], DEBUG=True)
print(o); R['debug_on'] = o
o = srun(d, "import os\nfrom django.conf.urls.static import static\nprint('  DEBUG =', settings.DEBUG, '→ static(MEDIA_URL, document_root=…) 返回的路由数:', len(static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)))\nprint('  GET /media/a.txt →', Client(raise_request_exception=False).get('/media/a.txt', HTTP_HOST='x').status_code)", ALLOWED_HOSTS=['*'], DEBUG=False)
print(o); R['debug_off'] = o
print()
print('== 二:上传的文件名怎么被处理(FileField 保存时):空格、路径穿越写法、重名、中文、超长')
o = run("""
names = ['a b.txt', '../../evil.txt', '/etc/passwd', 'rep.txt', 'rep.txt', '报告.txt', 'x' * 300 + '.txt', 'page.html']
root = os.path.realpath(MEDIA)
for n in names:
    r = up(n)
    if r.status_code != 200: print(f'  上传 {n[:20]!r:<24} → HTTP {r.status_code}'); continue
    saved = r.json()['saved_as']; inside = os.path.realpath(os.path.join(MEDIA, saved)).startswith(root + os.sep)
    print(f'  上传 {(n if len(n) < 24 else n[:10] + "…(" + str(len(n)) + " 字符)")!r:<28} → 保存为 {saved[:46]!r:<50} 在 MEDIA_ROOT 内: {inside}  保存名长度 {len(saved)}')
""", DEBUG=False)
print(o); R['names'] = o
print()
print('== 三:文件上传的内存阈值 FILE_UPLOAD_MAX_MEMORY_SIZE(默认 2.5 MiB):小文件在内存里,大文件落到临时文件')
o = run("""
print('  FILE_UPLOAD_MAX_MEMORY_SIZE =', settings.FILE_UPLOAD_MAX_MEMORY_SIZE, '字节')
for mb in (1, 3):
    j = up('big.bin', os.urandom(mb * 1024 * 1024)).json(); print(f'  上传 {mb} MiB → 请求里的文件对象类型 {j["cls"]},大小 {j["size"]}')
""", DEBUG=False)
print(o); R['mem'] = o
print()
print('== 四:DATA_UPLOAD_MAX_MEMORY_SIZE 不限制文件,只限制非文件的表单数据;文件个数有 DATA_UPLOAD_MAX_NUMBER_FILES')
o = run("""
print('  DATA_UPLOAD_MAX_MEMORY_SIZE 设成 1000 字节:')
r = up('f.bin', os.urandom(500000)); print('    上传 500000 字节的文件 →', r.status_code)
r = c.post('/fields/', {'text': 'a' * 2000}, HTTP_HOST='x'); print('    提交 2000 字节的普通字段 →', r.status_code)
print('  DATA_UPLOAD_MAX_NUMBER_FILES =', settings.DATA_UPLOAD_MAX_NUMBER_FILES)
for n in (100, 101):
    data = {f'f{i}': SimpleUploadedFile(f'f{i}.txt', b'x') for i in range(n)}
    r = c.post('/fields/', data, HTTP_HOST='x'); print(f'    一次上传 {n} 个文件 →', r.status_code)
""", DEBUG=False, DATA_UPLOAD_MAX_MEMORY_SIZE=1000)
print(o); R['limits'] = o
print()
print('== 五:把用户上传的文件原样返回时的 Content-Type / Content-Disposition')
o = run("""
os.makedirs(MEDIA, exist_ok=True)
open(os.path.join(MEDIA, 'page.html'), 'w').write('<script>alert(1)</script>'); open(os.path.join(MEDIA, 'a.txt'), 'w').write('hi')
for name, att in (('page.html', ''), ('page.html', '?att=1'), ('a.txt', '')):
    r = c.get(f'/dl/{name}{att}', HTTP_HOST='x'); print(f'  GET /dl/{name}{att:<7} Content-Type: {r.headers["Content-Type"]:<26} Content-Disposition: {r.headers.get("Content-Disposition", "(没有)")}')
""", DEBUG=False)
print(o); R['serve'] = o
save('d133', R)
