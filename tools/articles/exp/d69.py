import sys, os, time, json, re, signal, http.client, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d69'); R = {}
urls = '''
from django.urls import path
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django import forms
class UF(forms.Form):
    f = forms.FileField()
    def clean_f(self):
        f = self.cleaned_data['f']
        if f.size > 1024 * 1024: raise forms.ValidationError('文件不能超过 1 MiB(实际 %(s)d 字节)', code='too_big', params={'s': f.size})
        return f
@csrf_exempt
def plain(request):
    try:
        fs = request.FILES.getlist('f'); return JsonResponse({'files': len(fs), 'total': sum(x.size for x in fs)})
    except Exception as e: return JsonResponse({'error': type(e).__name__}, status=400)
@csrf_exempt
def checked(request):
    form = UF(request.POST, request.FILES); ok = form.is_valid()
    return JsonResponse({'valid': ok, 'errors': {k: [e.code for e in v.as_data()] for k, v in form.errors.items()}})
urlpatterns = [path('plain/', plain), path('checked/', checked)]
'''
d = proj('d69', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False)
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.test import Client\nfrom django.core.files.uploadedfile import SimpleUploadedFile\nc = Client(raise_request_exception=False)\n" + code); return out.rstrip()
print('== 一:Django 本身没有「单个文件最大多少」的设置:大文件默认都被接受')
o = run("""
for mb in (1, 5, 30):
    r = c.post('/plain/', {'f': SimpleUploadedFile('a.bin', b'x' * (mb * 1048576))}); print(f'上传 {mb:>2} MiB → status {r.status_code} {r.json()}')
""")
print(o); R['nolimit'] = o
print()
print('== 二:自己在表单里限制大小:文件已经被完整接收之后才能检查')
o = run("""
for kb in (500, 1024, 1025, 5000):
    r = c.post('/checked/', {'f': SimpleUploadedFile('a.bin', b'x' * (kb * 1024))}); print(f'{kb:>5} KiB → {r.json()}')
""")
print(o); R['form'] = o
print()
print('== 三:DATA_UPLOAD_MAX_MEMORY_SIZE 不计文件字段;但访问 request.body 时整个请求体都算')
o = run("""
from django.conf import settings
print('DATA_UPLOAD_MAX_MEMORY_SIZE =', settings.DATA_UPLOAD_MAX_MEMORY_SIZE, ' 上传 10 MiB 文件的 multipart:', end=' ')
r = c.post('/plain/', {'f': SimpleUploadedFile('a.bin', b'x' * (10 * 1048576))}); print('status', r.status_code, r.json())
r = c.post('/plain/', {'a': 'y' * (3 * 1048576)}); print('3 MiB 的普通表单字段(非文件):status', r.status_code, r.content[:60])
""")
print(o); R['datalimit'] = o
print()
print('== 四:DATA_UPLOAD_MAX_NUMBER_FILES(默认值);超过一个就被拒')
o = run("""
from django.conf import settings
print('DATA_UPLOAD_MAX_NUMBER_FILES 默认 =', settings.DATA_UPLOAD_MAX_NUMBER_FILES)
for n in (100, 101):
    r = c.post('/plain/', {'f': [SimpleUploadedFile(f'{i}.txt', b'x') for i in range(n)]}); print(f'上传 {n} 个文件 → status {r.status_code} {r.json()}')
""")
print(o); R['nfiles'] = o
save('d69', R)
