import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f73'); R = {}
import re, time, base64, json, io
from flask import Flask, request, render_template_string, jsonify, session
from flask_wtf import FlaskForm, CSRFProtect
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, PasswordField, IntegerField, BooleanField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Length, Email, EqualTo, NumberRange, Regexp, ValidationError, Optional
from werkzeug.datastructures import MultiDict
class SignupForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(message='必填'), Length(min=3, max=10, message='长度 3-10')])
    email = StringField('邮箱', validators=[DataRequired(), Email(message='邮箱格式不对')])
    age = IntegerField('年龄', validators=[NumberRange(min=18, max=120, message='18-120')])
    password = PasswordField('密码', validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('确认', validators=[EqualTo('password', message='两次密码不一致')])
    agree = BooleanField('同意条款', validators=[DataRequired(message='必须同意')])
    def validate_username(self, field):
        if field.data == 'admin': raise ValidationError('用户名已被占用(自定义校验)')
app = Flask('wtf'); app.logger.disabled = True; app.secret_key = 'lab-secret'
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit(): return jsonify(ok=True, data={k: v for k, v in form.data.items() if k not in ('password', 'confirm', 'csrf_token')})
    return jsonify(ok=False, errors=form.errors, submitted=request.method == 'POST'), 400 if request.method == 'POST' else 200
@app.get('/form')
def form_page(): return render_template_string('{{ form.hidden_tag() }}{{ form.username() }}', form=SignupForm())
@app.route('/upload', methods=['POST'])
def upload():
    class U(FlaskForm): f = FileField('文件', validators=[FileRequired(), FileAllowed(['png', 'jpg'], '只允许 png/jpg')])
    f = U(); return jsonify(ok=f.validate_on_submit(), errors=f.errors)
c = app.test_client()
def token_of(c):
    r = c.get('/form'); m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.get_data(as_text=True)); return m.group(1)
good = {'username': 'annie', 'email': 'a@b.co', 'age': '30', 'password': 'secret1', 'confirm': 'secret1', 'agree': 'y'}
print('== 零:Email() 校验器依赖 email_validator 包——没装时的报错')
try:
    import email_validator; print('  email_validator 已安装')
except ImportError:
    app.testing = True
    try: app.test_client().post('/signup', data={'username': 'annie', 'email': 'a@b.co', 'csrf_token': 'x'})
    except Exception as e: print('  没有安装 email_validator 时提交带 Email() 校验的表单 →', type(e).__name__ + ':', e); R['noev'] = f'{type(e).__name__}: {e}'
    app.testing = False
    env_ = dict(os.environ); env_['HTTPS_PROXY'] = 'http://127.0.0.1:1087'; r_ = subprocess.run([str(BIN / 'pip'), 'install', '-q', 'email_validator'], capture_output=True, text=True, env=env_); print('  pip install email_validator →', 'ok' if r_.returncode == 0 else r_.stderr[-100:])
    import importlib; importlib.invalidate_caches()
print()
print('== 一:GET 渲染表单:hidden_tag() 输出的 csrf_token 隐藏域;token 的结构')
r = c.get('/form'); html = r.get_data(as_text=True); print('  渲染结果:', html[:150] + '…'); tok = token_of(c); print('  csrf_token =', tok); R['token'] = tok
parts = tok.split('.'); print('  结构:', len(parts), '段 | 第 1 段(base64)解码 →', base64.urlsafe_b64decode(parts[0] + '=' * (-len(parts[0]) % 4))[:60], '(签名过的是 session 里的随机串,不是用户信息)')
with c: c.get('/form'); print('  session 里多了键:', [k for k in session if 'csrf' in k]); R['session_key'] = [k for k in session if 'csrf' in k]
print()
print('== 二:提交校验:合法数据;缺 CSRF token;各字段的各种错误信息')
R['posts'] = {}
def post(label, data, c_=None, **kw):
    cc = c_ or app.test_client(); t = token_of(cc) if kw.pop('with_token', True) else None; d_ = dict(data); 
    if t: d_['csrf_token'] = t
    r = cc.post('/signup', data=d_, **kw); j = r.get_json(); R['posts'][label] = [r.status_code, j.get('errors') or j.get('data')]; print(f'  {label:<28} → {r.status_code} {j.get("errors") or j.get("data")}'); return r
post('合法数据 + token', good)
post('合法数据,没有 token', good, with_token=False)
post('用户名太短', dict(good, username='ab')); post('用户名是 admin(自定义校验)', dict(good, username='admin')); post('邮箱格式不对', dict(good, email='nope')); post('年龄 17', dict(good, age='17')); post('年龄不是数字', dict(good, age='abc')); post('两次密码不一致', dict(good, confirm='x')); post('不勾选同意', {k: v for k, v in good.items() if k != 'agree'}); post('什么都不填', {})
print()
print('== 三:validate_on_submit 的含义:是 POST/PUT/PATCH/DELETE 才校验;GET 时返回 False 且 errors 为空')
r = c.get('/signup'); print('  GET /signup →', r.status_code, r.get_json()); R['get'] = r.get_json()
print()
print('== 四:CSRF token 的有效期与绑定:过期、换了 session、篡改')
cc = app.test_client(); t = token_of(cc)
r = cc.post('/signup', data=dict(good, csrf_token=t)); print('  正常:', r.status_code)
c_other = app.test_client(); token_of(c_other); r = c_other.post('/signup', data=dict(good, csrf_token=t)); print('  用别的会话的 token →', r.status_code, r.get_json()['errors']); R['other_session'] = r.get_json()['errors']
r = cc.post('/signup', data=dict(good, csrf_token=t[:-3] + 'xyz')); print('  篡改 token 末尾 →', r.status_code, r.get_json()['errors']); R['tampered'] = r.get_json()['errors']
app.config['WTF_CSRF_TIME_LIMIT'] = 1; cx = app.test_client(); tx = token_of(cx); time.sleep(2.5); r = cx.post('/signup', data=dict(good, csrf_token=tx)); print('  WTF_CSRF_TIME_LIMIT=1 秒,等 2.5 秒再提交(时间戳精度是秒,要等够 2 秒才保证 age > 1) →', r.status_code, r.get_json()['errors']); R['expired'] = r.get_json()['errors']; app.config['WTF_CSRF_TIME_LIMIT'] = 3600
app.config['WTF_CSRF_ENABLED'] = False; r = app.test_client().post('/signup', data=good); print('  WTF_CSRF_ENABLED=False(测试时常用)→', r.status_code); R['disabled'] = r.status_code; app.config['WTF_CSRF_ENABLED'] = True
print()
print('== 五:token 放在请求头里(AJAX)与 JSON 请求体里:FlaskForm 只认表单字段,请求头要由 CSRFProtect 来认')
cj = app.test_client(); tj = token_of(cj)
r = cj.post('/signup', data=good, headers={'X-CSRFToken': tj}); print('  表单数据 + 头 X-CSRFToken →', r.status_code, r.get_json().get('errors') or 'ok'); R['header'] = r.status_code
r = cj.post('/signup', json=dict(good, age=30), headers={'X-CSRFToken': tj}); print('  JSON 请求体 + 头 X-CSRFToken →', r.status_code, r.get_json()['errors']); R['json_body'] = [r.status_code, r.get_json()['errors']]
print()
print('== 六:CSRFProtect 全局保护(不用 FlaskForm 的接口也要 token):POST 没有 token → 400')
a2 = Flask('wtf2'); a2.logger.disabled = True; a2.secret_key = 'k'; CSRFProtect(a2); a2.add_url_rule('/p', 'p', lambda: 'ok', methods=['GET', 'POST']); a2.add_url_rule('/token', 'token', lambda: __import__('flask_wtf.csrf', fromlist=['generate_csrf']).generate_csrf())
cz = a2.test_client(); r = cz.post('/p'); print('  POST /p 没有 token →', r.status_code, re.sub(r'\s+', ' ', r.get_data(as_text=True))[:110]); R['csrfprotect_missing'] = r.status_code
tk = cz.get('/token').get_data(as_text=True); r = cz.post('/p', headers={'X-CSRFToken': tk}); print('  带 token 的 POST →', r.status_code); R['csrfprotect_ok'] = r.status_code
print()
print('== 七:文件上传校验:FileRequired、FileAllowed')
r = c.post('/upload', data={'csrf_token': token_of(c)}, content_type='multipart/form-data'); print('  没有文件 →', r.get_json()['errors']); R['file_missing'] = r.get_json()['errors']
r = c.post('/upload', data={'csrf_token': token_of(c), 'f': (io.BytesIO(b'x'), 'a.exe')}, content_type='multipart/form-data'); print('  a.exe →', r.get_json()['errors']); R['file_exe'] = r.get_json()['errors']
r = c.post('/upload', data={'csrf_token': token_of(c), 'f': (io.BytesIO(b'x'), 'a.png')}, content_type='multipart/form-data'); print('  a.png →', r.get_json()); R['file_png'] = r.get_json()
save('f73', R)
