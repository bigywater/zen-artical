import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d87'); R = {}
files = {
    'templates/base.html': "[base-top]{% block title %}base-title{% endblock %}|{% block content %}base-content{% endblock %}|{% block footer %}base-footer{% endblock %}[base-bottom]",
    'templates/mid.html': "{% extends 'base.html' %}{% block title %}mid-title/{{ block.super }}{% endblock %}{% block content %}mid-content({% block inner %}mid-inner{% endblock %}){% endblock %}",
    'templates/leaf.html': "{% extends 'mid.html' %}{% block content %}leaf-content/{{ block.super }}{% endblock %}{% block inner %}leaf-inner{% endblock %}{% block nosuch %}IGNORED{% endblock %}",
    'templates/leaf2.html': "{% extends 'base.html' %}{% block content %}c2{% endblock %}",
    'templates/dyn.html': "{% extends parent_tpl %}{% block content %}dyn{% endblock %}",
    'templates/dup.html': "{% extends 'base.html' %}{% block content %}A{% endblock %}{% block content %}B{% endblock %}",
    'templates/text_before.html': "text before {% extends 'base.html' %}",
    'templates/inc.html': "inc({{ x }}|{% block b %}inc-block{% endblock %})",
    'templates/with_inc.html': "{% extends 'base.html' %}{% block content %}{% include 'inc.html' with x=1 %}{% endblock %}",
}
d = proj('d87', files=files, apps=['django.contrib.contenttypes'], with_lab=False, settings_extra="\nTEMPLATES[0]['APP_DIRS'] = False\nTEMPLATES[0]['OPTIONS']['loaders'] = ['django.template.loaders.filesystem.Loader']\n")
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.template.loader import render_to_string\nfrom django.template import engines\nfrom django.template.loaders.filesystem import Loader\nLOADS = []\n_orig = Loader.get_contents\ndef _patched(self, origin): LOADS.append(origin.template_name); return _orig(self, origin)\nLoader.get_contents = _patched\n" + code); return out.rstrip()
print('== 一:三层继承:子模板的 block 覆盖父模板的;{{ block.super }} 取父级内容')
o = run("""
print('base    →', render_to_string('base.html'))
print('mid     →', render_to_string('mid.html'))
print('leaf    →', render_to_string('leaf.html'))
print('leaf2   →', render_to_string('leaf2.html'))
""")
print(o); R['levels'] = o
print()
print('== 二:子模板里 block 之外的内容被忽略;只在子模板里出现的 block(父里没有)也被忽略;重复的 block 名')
o = run("""
from django.template import TemplateSyntaxError
print('leaf.html 里定义了 nosuch block(父模板没有):输出里出现 IGNORED 吗 →', 'IGNORED' in render_to_string('leaf.html'))
print('{% extends %} 前面有文字:', end=' ')
try: print(render_to_string('text_before.html'))
except TemplateSyntaxError as e: print(type(e).__name__ + ':', str(e)[:90])
print('同一个模板里定义两个同名 block:', end=' ')
try: print(render_to_string('dup.html'))
except TemplateSyntaxError as e: print(type(e).__name__ + ':', str(e)[:90])
""")
print(o); R['ignored'] = o
print()
print('== 三:变量作为父模板名;每次渲染要加载几个模板文件(用带日志的加载器,无 cached)')
o = run("""
print('extends 变量:', render_to_string('dyn.html', {'parent_tpl': 'base.html'}))
LOADS.clear(); render_to_string('base.html'); print('渲染 base.html 加载:', LOADS)
LOADS.clear(); render_to_string('mid.html'); print('渲染 mid.html 加载:', LOADS)
LOADS.clear(); render_to_string('leaf.html'); print('渲染 leaf.html 加载:', LOADS, '(三层继承 = 三次读盘;cached 加载器会缓存)')
""")
print(o); R['loads'] = o
print()
print('== 四:include 与 extends 的区别:include 的模板独立渲染,不能覆盖 block;传参用 with / only')
o = run("""
print('with_inc.html →', render_to_string('with_inc.html'))
LOADS.clear(); render_to_string('with_inc.html'); print('加载:', LOADS)
print('inc.html 里的 block b 被外层 extends 覆盖了吗:输出仍是 inc-block →', 'inc-block' in render_to_string('with_inc.html'))
""")
print(o); R['include'] = o
print()
print('== 五:render 时间:extends 层数对渲染耗时的影响(cached 加载器,合成对比,200 次中位)')
d2 = proj('d87b', files=files, apps=['django.contrib.contenttypes'], with_lab=False)
rc, out = pyscript(d2, """
import time, statistics
from django.template.loader import get_template
def t(name):
    tpl = get_template(name); tpl.render({}); xs = []
    for _ in range(300):
        t0 = time.perf_counter(); tpl.render({}); xs.append((time.perf_counter() - t0) * 1e6)
    return statistics.median(xs)
for n in ('base.html', 'leaf2.html', 'leaf.html'): print(f'{n:<12} {t(n):8.1f} µs')
""")
print(out.strip()); R['perf'] = out.strip()
save('d87', R)
