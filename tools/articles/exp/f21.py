import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f21'); R = {}
from flask import Flask, Blueprint, url_for, request
from werkzeug.routing import BuildError
a = Flask('uf'); a.logger.disabled = True
bp = Blueprint('shop', __name__, url_prefix='/shop')
@a.route('/')
def index(): return 'index'
@a.route('/user/<int:uid>')
def user(uid): return 'user'
@a.route('/files/<path:p>')
def files(p): return 'files'
@bp.route('/item/<int:iid>')
def item(iid): return 'item'
@bp.route('/')
def shop_home(): return 'shop home'
a.register_blueprint(bp)
print('== 一:endpoint + 参数 → URL;多出来的参数变成查询字符串;特殊参数 _anchor、_external、_scheme')
with a.test_request_context('/'):
    rows = [("url_for('index')", url_for('index')), ("url_for('user', uid=7)", url_for('user', uid=7)), ("url_for('user', uid=7, tab='info', page=2)", url_for('user', uid=7, tab='info', page=2)), ("url_for('user', uid=7, _anchor='top')", url_for('user', uid=7, _anchor='top')), ("url_for('user', uid=7, _external=True)", url_for('user', uid=7, _external=True)), ("url_for('user', uid=7, _external=True, _scheme='https')", url_for('user', uid=7, _external=True, _scheme='https')), ("url_for('files', p='a b/中文.txt')", url_for('files', p='a b/中文.txt')), ("url_for('user', uid=7, tags=['a', 'b'])", url_for('user', uid=7, tags=['a', 'b'])), ("url_for('user', uid=7, none=None)", url_for('user', uid=7, none=None))]
    R['rows'] = rows
    for k, v in rows: print(f'  {k:<56} → {v}')
print()
print('== 二:蓝图的 endpoint 是「蓝图名.函数名」;在蓝图内部的请求里可以用 .item 的相对写法')
with a.test_request_context('/'):
    print("  url_for('shop.item', iid=3) →", url_for('shop.item', iid=3), "| url_for('shop.shop_home') →", url_for('shop.shop_home')); R['bp'] = [url_for('shop.item', iid=3), url_for('shop.shop_home')]
    try: url_for('.item', iid=3)
    except BuildError as e: print("  在非蓝图请求里写 url_for('.item') → BuildError:", ' '.join(str(e).split())[:140]); R['rel_outside'] = str(e)
with a.test_request_context('/shop/'):
    print("  请求在蓝图里时 request.blueprint =", request.blueprint, "| url_for('.item', iid=3) →", url_for('.item', iid=3)); R['rel_inside'] = [request.blueprint, url_for('.item', iid=3)]
print()
print('== 三:BuildError:endpoint 写错或缺参数')
with a.test_request_context('/'):
    R['err'] = {}
    for label, f in (('endpoint 写错 url_for("usr", uid=1)', lambda: url_for('usr', uid=1)), ('缺少必需参数 url_for("user")', lambda: url_for('user')), ('参数类型不对 url_for("user", uid="x")', lambda: url_for('user', uid='x'))):
        try: print(f'  {label}: {f()}')
        except Exception as e: R['err'][label] = [type(e).__name__, ' '.join(str(e).split())]; print(f'  {label}: {type(e).__name__}: {" ".join(str(e).split())[:230]}')
print()
print('== 四:没有请求上下文时(例如命令行、后台任务):需要应用上下文 + SERVER_NAME;或用 app.test_request_context')
with a.app_context():
    try: url_for('user', uid=1)
    except Exception as e: print('  只有应用上下文,没设 SERVER_NAME →', type(e).__name__ + ':', ' '.join(str(e).split())[:200]); R['no_server_name'] = [type(e).__name__, ' '.join(str(e).split())]
a.config['SERVER_NAME'] = 'example.test:5000'; a.config['PREFERRED_URL_SCHEME'] = 'https'
with a.app_context(): print('  设了 SERVER_NAME=example.test:5000、PREFERRED_URL_SCHEME=https →', url_for('user', uid=1), '|', url_for('user', uid=1, _external=False)); R['server_name'] = [url_for('user', uid=1), url_for('user', uid=1, _external=False)]
a.config['SERVER_NAME'] = None
print()
print('== 五:app.url_for() 方法(Flask 2.2 起);APPLICATION_ROOT 与 SCRIPT_NAME 会加在 URL 前面')
with a.test_request_context('/'): print('  app.url_for("user", uid=2) →', a.url_for('user', uid=2)); R['method'] = a.url_for('user', uid=2)
b = Flask('sub'); b.add_url_rule('/hi', 'hi', lambda: 'hi'); c = b.test_client()
with b.test_request_context('/hi', environ_overrides={'SCRIPT_NAME': '/myapp'}): print('  SCRIPT_NAME=/myapp 时 url_for("hi") →', url_for('hi')); R['script_name'] = url_for('hi')
b.config['APPLICATION_ROOT'] = '/prefix'
with b.test_request_context('/hi'): print('  APPLICATION_ROOT=/prefix 且请求 /hi 时 url_for("hi") →', url_for('hi')); R['app_root'] = url_for('hi')
print()
print('== 六:static 端点与缓存破坏:url_for("static", filename=...)')
with a.test_request_context('/'): print('  url_for("static", filename="css/site.css") →', url_for('static', filename='css/site.css'), '| url_for("static", filename="a b.js", v=3) →', url_for('static', filename='a b.js', v=3)); R['static'] = [url_for('static', filename='css/site.css'), url_for('static', filename='a b.js', v=3)]
save('f21', R)
