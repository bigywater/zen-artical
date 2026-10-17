import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d88'); R = {}
files = {
    'assets/site.css': 'body{color:red}', 'assets/shared.txt': 'FROM PROJECT assets', 'assets/proj_only.js': 'console.log(1)',
    'app1/__init__.py': '', 'app1/static/app1/a.css': 'a{}', 'app1/static/shared.txt': 'FROM app1', 'app1/static/admin/override.txt': 'override',
    'app2/__init__.py': '', 'app2/static/shared.txt': 'FROM app2', 'app2/static/app2/b.js': 'var b=1',
}
apps = ['django.contrib.contenttypes', 'django.contrib.staticfiles', 'app1', 'app2']
d = proj('d88', files=files, apps=apps, with_lab=False, settings_extra="\nSTATICFILES_DIRS = [BASE_DIR / 'assets']\nSTATIC_ROOT = BASE_DIR / 'collected'\n")
def tree(root): return sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file())
print('== 一:collectstatic:从哪些地方收集,收集到哪里,同名文件谁赢')
rc, out = manage(d, 'collectstatic', '--noinput'); print('  ' + '\n  '.join(l for l in out.strip().splitlines() if l.strip())); R['first'] = out.strip()
col = d / 'collected'; fl = tree(col); print('  collected/ 下的文件:', fl); R['files'] = fl
print('  shared.txt 的内容:', (col / 'shared.txt').read_text(), '  (STATICFILES_DIRS 里的先于 app 目录;app 之间按 INSTALLED_APPS 顺序)')
print('  findstatic shared.txt -v2(所有候选位置):')
rc, o = manage(d, 'findstatic', 'shared.txt', '-v', '2', '--first' if False else '-v', '2') if False else manage(d, 'findstatic', 'shared.txt', '-v', '2'); print('  ' + '\n  '.join(l.split('djtmp/')[-1] for l in o.strip().splitlines()[:6])); R['find'] = o.strip()
print()
print('== 二:第二次运行:没有变化的文件不再复制;改一个文件只复制它')
rc, out = manage(d, 'collectstatic', '--noinput'); print('  无变化:', out.strip().splitlines()[-1].split("',", 1)[-1].strip()); R['second'] = out.strip().splitlines()[-1].split("',", 1)[-1].strip()
(d / 'assets' / 'site.css').write_text('body{color:blue}'); rc, out = manage(d, 'collectstatic', '--noinput'); print('  刚改完 site.css 立刻运行(与上次复制在同一秒内):', out.strip().splitlines()[-1].split("',", 1)[-1].strip(), '| 目标里的内容:', (col / 'site.css').read_text()); R['third_fast'] = dict(line=out.strip().splitlines()[-1].split("',", 1)[-1].strip(), content=(col / 'site.css').read_text())
time.sleep(1.2); (d / 'assets' / 'site.css').write_text('body{color:green}'); rc, out = manage(d, 'collectstatic', '--noinput'); print('  等 1.2 秒后再改一次并运行:', out.strip().splitlines()[-1].split("',", 1)[-1].strip(), '| 目标里的内容:', (col / 'site.css').read_text()); R['third'] = dict(line=out.strip().splitlines()[-1].split("',", 1)[-1].strip(), content=(col / 'site.css').read_text())
import os as _os
old = (d / 'assets' / 'proj_only.js'); t = old.stat().st_mtime; old.write_text('console.log(2)'); _os.utime(old, (t, t)); rc, out = manage(d, 'collectstatic', '--noinput'); print('  内容变了但 mtime 没变:', out.strip().splitlines()[-1].split("',", 1)[-1].strip(), '|', (col / 'proj_only.js').read_text(), '(collectstatic 用修改时间判断,内容变而 mtime 不变会漏掉)'); R['mtime'] = dict(line=out.strip().splitlines()[-1], content=(col / 'proj_only.js').read_text())
print()
print('== 三:--clear(先清空目标目录)、--dry-run、--link(符号链接)')
rc, out = manage(d, 'collectstatic', '--noinput', '--dry-run'); print('  --dry-run:', out.strip().splitlines()[-1]); R['dry'] = out.strip().splitlines()[-1]
(col / 'stale.txt').write_text('stale'); rc, out = manage(d, 'collectstatic', '--noinput'); print('  目标里多出来的旧文件 stale.txt(源里已不存在),不带 --clear 后:', (col / 'stale.txt').exists(), '(不会自动删除)'); R['stale_kept'] = (col / 'stale.txt').exists()
rc, out = manage(d, 'collectstatic', '--noinput', '--clear'); print('  --clear 之后 stale.txt 还在吗:', (col / 'stale.txt').exists(), '|', out.strip().splitlines()[-1]); R['clear'] = dict(stale=(col / 'stale.txt').exists(), line=out.strip().splitlines()[-1])
rc, out = manage(d, 'collectstatic', '--noinput', '--clear', '--link'); print('  --link:', out.strip().splitlines()[-1], '| site.css 是符号链接:', (col / 'site.css').is_symlink()); R['link'] = dict(line=out.strip().splitlines()[-1], symlink=(col / 'site.css').is_symlink())
print()
print('== 四:忽略模式 --ignore;STATIC_ROOT 未设置时的报错')
rc, out = manage(d, 'collectstatic', '--noinput', '--clear', '-i', '*.js'); print('  -i "*.js":', [f for f in tree(col) if f.endswith('.js')], '(js 文件都被跳过)', '|', out.strip().splitlines()[-1]); R['ignore'] = out.strip().splitlines()[-1]
d2 = proj('d88b', files=files, apps=apps, with_lab=False, settings_extra="\nSTATICFILES_DIRS = [BASE_DIR / 'assets']\n")
rc, out = manage(d2, 'collectstatic', '--noinput'); print('  没有 STATIC_ROOT:', out.strip().splitlines()[-1][:170]); R['noroot'] = out.strip().splitlines()[-1][:170]
save('d88', R)
