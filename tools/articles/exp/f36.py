import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f36'); R = {}
import io, uuid
from flask import Flask, request
from werkzeug.utils import secure_filename
UP = FT / 'f36_uploads'; shutil.rmtree(UP, ignore_errors=True); UP.mkdir(parents=True)
app = Flask('mu'); app.logger.disabled = True
@app.post('/multi')
def multi():
    fs = request.files.getlist('docs'); return {'count': len(fs), 'names': [f.filename for f in fs], 'sizes': [len(f.read()) for f in fs], 'first_via_get': request.files['docs'].filename, 'keys': list(request.files.keys()), 'form': request.form.to_dict(flat=False)}
@app.post('/mixed')
def mixed(): return {k: [f.filename for f in v] for k, v in request.files.lists()}
@app.post('/save-naive')
def save_naive():
    for f in request.files.getlist('docs'): f.save(UP / secure_filename(f.filename))
    return {'files': sorted(p.name for p in UP.iterdir())}
@app.post('/save-unique')
def save_unique():
    out = []
    for f in request.files.getlist('docs'):
        name = f'{uuid.uuid4().hex[:8]}_{secure_filename(f.filename) or "file"}'; f.save(UP / name); out.append(name)
    return {'saved': len(out), 'dir_count': len(list(UP.iterdir()))}
c = app.test_client()
print('== 一:同名字段多个文件:getlist 取全部,files["docs"] 只取第一个')
r = c.post('/multi', data={'docs': [(io.BytesIO(b'AAA'), 'a.txt'), (io.BytesIO(b'BBBBB'), 'b.txt'), (io.BytesIO(b'C'), 'c.txt')], 'note': 'hi'}, content_type='multipart/form-data'); d = r.get_json(); R['multi'] = d; print(' ', d)
print()
print('== 二:不同字段名的文件:files.lists() 按字段名分组')
r = c.post('/mixed', data={'avatar': (io.BytesIO(b'1'), 'me.png'), 'docs': [(io.BytesIO(b'2'), 'd1.pdf'), (io.BytesIO(b'3'), 'd2.pdf')]}, content_type='multipart/form-data'); print(' ', r.get_json()); R['mixed'] = r.get_json()
print()
print('== 三:同名文件互相覆盖:两个用户都上传 report.pdf,后者覆盖前者;用随机前缀避免')
for body, who in ((b'USER-1 data', 'user1'), (b'USER-2 data', 'user2')): c.post('/save-naive', data={'docs': (io.BytesIO(body), 'report.pdf')}, content_type='multipart/form-data')
print('  两次上传同名文件后目录里:', sorted(p.name for p in UP.iterdir()), '| 内容:', (UP / 'report.pdf').read_bytes()); R['overwrite'] = [sorted(p.name for p in UP.iterdir()), (UP / 'report.pdf').read_bytes().decode()]
shutil.rmtree(UP); UP.mkdir()
for body in (b'USER-1 data', b'USER-2 data'): r = c.post('/save-unique', data={'docs': (io.BytesIO(body), 'report.pdf')}, content_type='multipart/form-data')
print('  加随机前缀后目录里:', sorted(p.name[9:] + '(前缀8位)' for p in UP.iterdir()), '| 文件数', len(list(UP.iterdir()))); R['unique'] = len(list(UP.iterdir()))
print()
print('== 四:多文件上传的数量上限:MAX_FORM_PARTS(默认 1000)按「部分」计数——文件与普通字段合计')
app.config['MAX_FORM_PARTS'] = 6
for n in (3, 5, 8): 
    r = c.post('/multi', data={'docs': [(io.BytesIO(b'x'), f'f{i}.txt') for i in range(n)], 'note': 'n'}, content_type='multipart/form-data'); R.setdefault('parts', {})[n] = r.status_code; print(f'  MAX_FORM_PARTS=6:{n} 个文件 + 1 个普通字段 → {r.status_code}')
app.config['MAX_FORM_PARTS'] = 1000
print()
print('== 五:真实 HTTP:curl 一次上传 3 个文件(重复 -F),gunicorn 单 worker')
d = mkapp('f36', {'app.py': 'from flask import Flask, request\napp = Flask(__name__)\n@app.post("/m")\ndef m():\n    fs = request.files.getlist("docs"); return ",".join(f"{f.filename}:{len(f.read())}" for f in fs)\n'}); [(d / n).write_text(t) for n, t in (('1.txt', 'one'), ('2.txt', 'twotwo'), ('3.txt', 'x'))]
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', 'app:app']) as s:
    r = subprocess.run(['curl', '-s', '-F', 'docs=@1.txt', '-F', 'docs=@2.txt', '-F', 'docs=@3.txt', f'http://127.0.0.1:{s.port}/m'], cwd=d, capture_output=True, text=True); print('  →', r.stdout); R['curl'] = r.stdout
save('f36', R)
