import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f52'); R = {}
from flask import Flask, Blueprint, render_template, render_template_string
d = mkapp('f52', {
 'templates/a.html': '应用 a', 'templates/only_app.html': '只在应用里', 'templates/dir/x.html': '应用的 dir/x', 'templates/.hidden.html': 'hidden',
 'bp1/templates/a.html': 'bp1 的 a', 'bp1/templates/only_bp1.html': '只在 bp1', 'bp1/templates/dir/x.html': 'bp1 的 dir/x',
 'bp2/templates/only_bp2.html': '只在 bp2', 'extra/extra_only.html': '额外目录里的', 'other/x.html': '其它', 'secret.txt': 'OUTSIDE TEMPLATES'})
sys.path.insert(0, str(d)); os.chdir(d)
bp1 = Blueprint('bp1', 'bp1', root_path=str(d / 'bp1'), template_folder='templates'); bp2 = Blueprint('bp2', 'bp2', root_path=str(d / 'bp2'), template_folder='templates')
app = Flask('sp', root_path=str(d)); app.logger.disabled = True; app.register_blueprint(bp1); app.register_blueprint(bp2)
def rt(name):
    with app.test_request_context('/'):
        try: return render_template(name)
        except Exception as e: return f'{type(e).__name__}: {str(e)[:50]!r}'
print('== 一:查找顺序:先应用的 templates,再按注册顺序逐个蓝图;同名时先找到的赢')
R['order'] = {}
for n in ('a.html', 'only_app.html', 'only_bp1.html', 'only_bp2.html', 'dir/x.html', 'nope.html'): R['order'][n] = rt(n); print(f'  render_template({n!r:<18}) → {R["order"][n]}')
print()
print('== 二:render_template 传列表:取第一个存在的(select_template),适合「专用模板 → 通用模板」的回退')
with app.test_request_context('/'):
    R['list'] = [render_template(['nope1.html', 'only_bp2.html', 'a.html']), render_template(['a.html', 'only_bp2.html'])]; print('  [nope1, only_bp2, a] →', R['list'][0], '| [a, only_bp2] →', R['list'][1])
    try: render_template(['x1.html', 'x2.html'])
    except Exception as e: print('  全都不存在 →', type(e).__name__ + ':', e); R['list_none'] = f'{type(e).__name__}: {e}'
print()
print('== 三:模板名的安全:路径穿越、绝对路径、带 .. 的名字、以点开头的文件')
R['safe'] = {}
for n in ('../secret.txt', '../other/x.html', '/etc/passwd', 'dir/../a.html', 'dir//x.html', './a.html', '.hidden.html', 'dir\\x.html', 'a.html\x00'): R['safe'][n] = rt(n); print(f'  render_template({n!r:<22}) → {R["safe"][n]}')
print()
print('== 四:额外的模板目录:用 ChoiceLoader 加进来(应用目录优先)')
from jinja2 import ChoiceLoader, FileSystemLoader
app.jinja_loader = ChoiceLoader([app.jinja_loader, FileSystemLoader(str(d / 'extra'))]); app.jinja_env.cache.clear()
R['extra'] = {n: rt(n) for n in ('extra_only.html', 'a.html')}; [print(f'  render_template({n!r}) →', v) for n, v in R['extra'].items()]
print()
print('== 五:render_template_string 与 render_template 的模板来源不同:前者不经过加载器,直接编译字符串')
with app.test_request_context('/'):
    print('  render_template_string("{{ 1 + 1 }}") →', render_template_string('{{ 1 + 1 }}')); print('  字符串模板里 include 文件模板:', render_template_string('[{% include "only_app.html" %}]')); R['string'] = [render_template_string('{{ 1 + 1 }}'), render_template_string('[{% include "only_app.html" %}]')]
print()
print('== 六:列出全部可用模板名:jinja_env.list_templates()(开发时检查是否有同名冲突很有用)')
app.jinja_loader = app.jinja_loader; names = sorted(app.jinja_env.list_templates()); print('  ', names); R['list_all'] = names
dups = {}
for bpn, bp in app.blueprints.items():
    for t in bp.jinja_loader.list_templates(): dups.setdefault(t, []).append(bpn)
for t in app.jinja_loader.loaders[0].list_templates(): dups.setdefault(t, []).append('应用')
print('  被多处提供的模板名:', {k: v for k, v in dups.items() if len(v) > 1}); R['dups'] = {k: v for k, v in dups.items() if len(v) > 1}
save('f52', R)
