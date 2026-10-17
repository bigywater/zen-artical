import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f28'); R = {}
d = mkapp('f28', {
 'main.py': '''
from flask import Flask, render_template, url_for
from admin import bp as admin_bp
from blog import bp as blog_bp
app = Flask(__name__)
app.config["EXPLAIN_TEMPLATE_LOADING"] = False
app.register_blueprint(admin_bp)
app.register_blueprint(blog_bp)
@app.get("/home")
def home(): return render_template("home.html")
''',
 'templates/home.html': '主应用的 home.html',
 'templates/shared.html': '应用的 shared.html',
 'admin/__init__.py': 'from flask import Blueprint, render_template\nbp = Blueprint("admin", __name__, url_prefix="/admin", template_folder="templates", static_folder="static")\n@bp.get("/")\ndef index(): return render_template("index.html")\n@bp.get("/shared")\ndef shared(): return render_template("shared.html")\n@bp.get("/ns")\ndef ns(): return render_template("admin/page.html")\n',
 'admin/templates/index.html': 'admin 蓝图的 index.html',
 'admin/templates/shared.html': 'admin 蓝图的 shared.html',
 'admin/templates/admin/page.html': 'admin/page.html(带子目录的命名)',
 'admin/static/admin.css': 'a{}',
 'blog/__init__.py': 'from flask import Blueprint, render_template\nbp = Blueprint("blog", __name__, url_prefix="/blog", template_folder="templates", static_folder="static", static_url_path="/blog-assets")\n@bp.get("/")\ndef index(): return render_template("index.html")\n',
 'blog/templates/index.html': 'blog 蓝图的 index.html',
 'blog/templates/blog_only.html': 'blog_only.html',
 'blog/static/blog.css': 'p{}',
})
sys.path.insert(0, str(d)); os.chdir(d)
import main
app = main.app; c = app.test_client()
print('== 一:蓝图的目录结构与 root_path / template_folder / static_folder(都相对于蓝图所在模块的目录)')
for n, b in app.blueprints.items(): print(f'  {n:<6} root_path = {b.root_path.replace(str(d), "<项目>")} | template_folder = {b.template_folder} | static_folder = {b.static_folder.replace(str(d), "<项目>") if b.static_folder else None} | static_url_path = {b.static_url_path} | has_static_folder = {b.has_static_folder}'); R.setdefault('bps', {})[n] = [b.template_folder, b.static_url_path]
print()
print('== 二:蓝图的静态文件:endpoint 是「蓝图名.static」,URL 是前缀 + /static(或自定义的 static_url_path)')
with app.test_request_context('/'):
    from flask import url_for
    print("  url_for('admin.static', filename='admin.css') →", url_for('admin.static', filename='admin.css')); print("  url_for('blog.static', filename='blog.css') →", url_for('blog.static', filename='blog.css')); R['static_urls'] = [url_for('admin.static', filename='admin.css'), url_for('blog.static', filename='blog.css')]
print('  请求:', {p: c.get(p).status_code for p in ('/admin/static/admin.css', '/blog/blog-assets/blog.css', '/static/admin.css', '/admin/static/blog.css')}); R['static_req'] = {p: c.get(p).status_code for p in ('/admin/static/admin.css', '/blog/blog-assets/blog.css', '/static/admin.css', '/admin/static/blog.css')}
print('  应用的规则里与静态相关的:', [str(r) for r in app.url_map.iter_rules() if 'static' in r.endpoint]); R['static_rules'] = [str(r) for r in app.url_map.iter_rules() if 'static' in r.endpoint]
print()
print('== 三:模板查找:同名模板时应用的 templates 优先于蓝图的;两个蓝图都有 index.html 时先注册的赢(蓝图模板目录是全局共享的)')
R['tpl'] = {}
for p in ('/home', '/admin/', '/blog/', '/admin/shared', '/admin/ns'):
    R['tpl'][p] = c.get(p).get_data(as_text=True); print(f'  GET {p:<14} → {R["tpl"][p]}')
print('  模板 blog_only.html 只在 blog 蓝图里,应用里任何视图都能用:', end=' ')
with app.test_request_context('/'):
    from flask import render_template; print(render_template('blog_only.html')); R['blog_only'] = render_template('blog_only.html')
print()
print('== 四:用 EXPLAIN_TEMPLATE_LOADING 看查找过程(Flask 内置的调试开关,日志里列出尝试过的每个加载器)')
import logging, io
app.config['EXPLAIN_TEMPLATE_LOADING'] = True; app.logger.setLevel(logging.INFO); buf = io.StringIO(); h = logging.StreamHandler(buf); app.logger.addHandler(h); app.logger.propagate = False
app.jinja_env.cache.clear(); c.get('/admin/shared'); app.logger.removeHandler(h); app.config['EXPLAIN_TEMPLATE_LOADING'] = False
L = [l for l in buf.getvalue().split('\n') if l.strip()]; print('\n'.join('    ' + l.replace(str(d), '<项目>') for l in L[:14])); R['explain'] = [l.replace(str(d), '<项目>') for l in L[:14]]
print()
print('== 五:避免撞名的惯例:蓝图的模板放进「蓝图名」子目录,引用时写 admin/page.html')
print('  /admin/ns →', R['tpl']['/admin/ns'], '| 应用里列出的全部模板名:', sorted(app.jinja_env.list_templates())); R['list'] = sorted(app.jinja_env.list_templates())
save('f28', R)
