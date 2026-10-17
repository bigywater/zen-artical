import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d89'); R = {}
files = {
    'assets/css/site.css': "@import url('base.css'); .logo{background:url('../img/logo.png')} .bg{background:url(\"../img/bg.png?v=1#x\")} .ext{background:url('https://cdn.example.com/x.png')} .data{background:url(data:image/png;base64,AAAA)}",
    'assets/css/base.css': 'body{margin:0}',
    'assets/img/logo.png': 'LOGO-BYTES', 'assets/img/bg.png': 'BG-BYTES',
    'assets/js/app.js': 'console.log("app")',
    'templates/page.html': '{% load static %}<link href="{% static "css/site.css" %}"><img src="{% static "img/logo.png" %}"><script src="{% static "js/app.js" %}"></script><img src="{% static "img/missing.png" %}">',
}
apps = ['django.contrib.contenttypes', 'django.contrib.staticfiles']
extra = "\nSTATICFILES_DIRS = [BASE_DIR / 'assets']\nSTATIC_ROOT = BASE_DIR / 'collected'\nSTORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'}}\nDEBUG = False\n"
d = proj('d89', files=files, apps=apps, with_lab=False, settings_extra=extra)
print('== 一:collectstatic 之后:文件名带上内容哈希;staticfiles.json 是映射表')
rc, out = manage(d, 'collectstatic', '--noinput'); print('  ' + out.strip().splitlines()[-1]); R['collect'] = out.strip().splitlines()[-1]
col = d / 'collected'; fl = sorted(str(p.relative_to(col)) for p in col.rglob('*') if p.is_file()); print('  收集到的文件(原名 + 带哈希的副本):'); [print('   ', f) for f in fl]; R['files'] = fl
mfull = json.loads((col / 'staticfiles.json').read_text()); m = mfull['paths']; print('  staticfiles.json 的键:', list(mfull), '  paths 映射:'); [print('   ', k, '→', v) for k, v in m.items()]; R['manifest'] = m
print()
print('== 二:CSS 里的 url() 与 @import 被改写成带哈希的文件名;外部 URL 与 data: 保持原样')
css = [f for f in fl if f.startswith('css/site.') and f != 'css/site.css'][0]; print('  ' + css + ' 的内容:'); txt = (col / css).read_text(); print('   ', txt); R['css'] = txt
print()
print('== 三:哈希是内容的 MD5 前 12 位:内容不变文件名不变;内容变了文件名变(缓存失效)')
import hashlib
h = hashlib.md5(b'console.log("app")').hexdigest()[:12]; print('  app.js 内容的 md5[:12] =', h, ' 与 manifest 里的文件名一致:', h in m['js/app.js']); R['md5_match'] = h in m['js/app.js']
rc, out = manage(d, 'collectstatic', '--noinput'); m2 = json.loads((col / 'staticfiles.json').read_text())['paths']; print('  再运行一次(内容没变),映射不变:', m2 == m)
(d / 'assets' / 'js' / 'app.js').write_text('console.log("app v2")'); rc, out = manage(d, 'collectstatic', '--noinput'); m3 = json.loads((col / 'staticfiles.json').read_text())['paths']; print('  改了 app.js:', m['js/app.js'], '→', m3['js/app.js']); R['change'] = [m['js/app.js'], m3['js/app.js']]
print('  旧的哈希文件还留在目录里:', (col / m['js/app.js']).exists(), '(不会自动删除,需要 --clear 或者定期清理)'); R['old_kept'] = (col / m['js/app.js']).exists()
print()
print('== 四:{% static %} 在 DEBUG=False 下输出哈希名;清单里没有的文件会怎样')
rc, o = pyscript(d, """
import logging; logging.disable(logging.CRITICAL)
from django.template.loader import render_to_string
try: print(render_to_string('page.html'))
except Exception as e: print(type(e).__name__ + ':', str(e)[:130])
from django.template import engines
src = '{% load static %}<a href="{% static "css/site.css" %}">'
print(engines['django'].from_string(src).render({}))
""")
print('  ' + o.strip().replace('\n', '\n  ')); R['tag'] = o.strip()
print()
print('== 五:manifest_strict = False:文件在磁盘上但不在清单里时现算哈希;文件根本不存在仍然报错')
d2 = proj('d89b', files=dict(files, **{'proj/storage.py': 'from django.contrib.staticfiles.storage import ManifestStaticFilesStorage\nclass NonStrict(ManifestStaticFilesStorage):\n    manifest_strict = False\n'}), apps=apps, with_lab=False, settings_extra=extra.replace('django.contrib.staticfiles.storage.ManifestStaticFilesStorage', 'proj.storage.NonStrict'))
manage(d2, 'collectstatic', '--noinput')
(d2 / 'collected' / 'img').mkdir(exist_ok=True, parents=True); (d2 / 'collected' / 'img' / 'late.png').write_bytes(b'LATE')
rc, o = pyscript(d2, """
from django.templatetags.static import static
for n in ('img/late.png', 'img/missing.png'):
    try: print('非严格:', n, '→', static(n))
    except Exception as e: print('非严格:', n, '→', type(e).__name__ + ':', str(e)[:80])
""")
print('  ' + o.strip().replace('\n', '\n  ')); R['nonstrict'] = o.strip()
rc, o = pyscript(d, """
from django.templatetags.static import static
import shutil, pathlib
p = pathlib.Path(__import__('django.conf', fromlist=['settings']).settings.STATIC_ROOT) / 'img' / 'late.png'; p.write_bytes(b'LATE')
try: print('严格:', 'img/late.png(文件在磁盘上,但不在 manifest)→', static('img/late.png'))
except Exception as e: print('严格:', 'img/late.png →', type(e).__name__ + ':', str(e)[:80])
""")
print('  ' + o.strip().replace('\n', '\n  ')); R['strict_late'] = o.strip()
save('d89', R)
