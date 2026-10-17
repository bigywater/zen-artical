import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f35'); R = {}
import io, hashlib, tempfile
from flask import Flask, request
UP = FT / 'f35_uploads'; shutil.rmtree(UP, ignore_errors=True); UP.mkdir(parents=True)
app = Flask('up'); app.logger.disabled = True
@app.post('/u')
def u():
    f = request.files['file']
    info = {'filename': f.filename, 'name': f.name, 'content_type': f.content_type, 'mimetype': f.mimetype, 'content_length': f.content_length, 'headers': dict(f.headers), 'stream_type': type(f.stream).__name__, 'bool': bool(f)}
    pos0 = f.stream.tell(); head = f.read(5); pos1 = f.stream.tell(); f.seek(0, 2); size = f.tell(); f.seek(0)
    info.update(head=head.decode('latin-1'), pos_before=pos0, pos_after_read5=pos1, size=size, sha=hashlib.sha256(f.read()).hexdigest()[:12])
    f.seek(0); f.save(UP / 'saved.bin'); info['saved_size'] = (UP / 'saved.bin').stat().st_size
    return info
@app.post('/noname')
def noname():
    f = request.files.get('file'); return {'present': f is not None, 'filename': getattr(f, 'filename', None), 'bool': bool(f), 'len': len(f.read()) if f else None}
@app.post('/missing')
def missing(): return {'files': list(request.files)}
@app.post('/must')
def must(): return request.files['file'].filename
@app.post('/where')
def where():
    f = request.files['file']; s = f.stream; return {'type': type(s).__name__, 'rolled': getattr(s, '_rolled', None), 'max_size': getattr(s, '_max_size', None)}
c = app.test_client()
print('== 一:FileStorage 对象:一次上传的各个属性;stream 的读写位置;save 之后文件落地')
data = b'HELLO' + os.urandom(2000)
r = c.post('/u', data={'file': (io.BytesIO(data), 'report 2024.pdf', 'application/pdf'), 'note': 'x'}, content_type='multipart/form-data'); d = r.get_json(); R['info'] = d
for k in ('filename', 'name', 'content_type', 'mimetype', 'content_length', 'headers', 'stream_type', 'bool', 'head', 'pos_before', 'pos_after_read5', 'size', 'saved_size'): print(f'  {k:<16} = {d[k]!r}')
print('  与原始数据的 sha256 前 12 位相同:', d['sha'] == hashlib.sha256(data).hexdigest()[:12])
print()
print('== 二:没有选择文件时浏览器依然会提交一个空的文件字段(filename 为空串),与「字段不存在」是两回事')
r = c.post('/noname', data={'file': (io.BytesIO(b''), '')}, content_type='multipart/form-data'); print('  空 filename:', r.get_json()); R['empty'] = r.get_json()
r = c.post('/noname', data={'other': 'x'}, content_type='multipart/form-data'); print('  根本没有 file 字段:', r.get_json()); R['absent'] = r.get_json()
r = c.post('/must', data={'other': 'x'}, content_type='multipart/form-data'); print('  视图里 request.files["file"] 缺失 →', r.status_code); R['keyerr'] = r.status_code
print()
print('== 三:内存还是磁盘?小文件留在内存里,大文件会被写进临时文件(Werkzeug 的 SpooledTemporaryFile,阈值 500 KiB)')
for size in (1_000, 400_000, 600_000, 5_000_000):
    r = c.post('/where', data={'file': (io.BytesIO(b'x' * size), 'a.bin')}, content_type='multipart/form-data'); R.setdefault('where', {})[size] = r.get_json(); print(f'  {size:>9} 字节 → {r.get_json()}')
print()
print('== 四:save() 的用法:路径、已打开的文件对象;目标是目录或父目录不存在时报什么')
f_ = c.post('/u', data={'file': (io.BytesIO(b'abc'), 'x.txt')}, content_type='multipart/form-data')
from werkzeug.datastructures import FileStorage
fs = FileStorage(io.BytesIO(b'content'), filename='x.txt'); fs.save(UP / 'a.txt'); print('  save(路径) →', (UP / 'a.txt').read_bytes())
fs = FileStorage(io.BytesIO(b'content2'), filename='x.txt'); buf = io.BytesIO(); fs.save(buf); print('  save(文件对象) →', buf.getvalue())
for label, dst in (('目标是已存在的目录', UP), ('父目录不存在', UP / 'nodir' / 'a.txt')):
    fs = FileStorage(io.BytesIO(b'z'), filename='x.txt')
    try: fs.save(dst); print(f'  {label}: 成功')
    except Exception as e: print(f'  {label}: {type(e).__name__}: {tidy(str(e))[:90]}'); R.setdefault('saveerr', {})[label] = type(e).__name__
fs = FileStorage(io.BytesIO(b'AAA'), filename='x.txt'); fs.save(UP / 'twice.txt'); fs.save(UP / 'twice2.txt'); print('  同一个 FileStorage 连续 save 两次:第二次文件大小 =', (UP / 'twice2.txt').stat().st_size, '(流读到末尾后没有复位,第二次是空文件)'); R['twice'] = (UP / 'twice2.txt').stat().st_size
print()
print('== 五:真实 HTTP 上传:gunicorn + curl -F(浏览器同样的 multipart/form-data)')
d = mkapp('f35', {'app.py': 'import os\nfrom flask import Flask, request\napp = Flask(__name__)\n@app.post("/upload")\ndef up():\n    f = request.files["doc"]; data = f.read()\n    return f"{f.filename}|{f.content_type}|{len(data)}|{request.form.get(\'title\')}"\n'})
(d / 'hello.txt').write_text('你好 hello\n')
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', 'app:app']) as s:
    r = subprocess.run(['curl', '-s', '-F', 'doc=@hello.txt', '-F', 'title=我的文档', f'http://127.0.0.1:{s.port}/upload'], cwd=d, capture_output=True, text=True); print('  curl -F doc=@hello.txt -F title=我的文档 →', r.stdout); R['curl'] = r.stdout
    r = subprocess.run(['curl', '-s', '-F', 'doc=@hello.txt;type=text/markdown;filename=改名.md', f'http://127.0.0.1:{s.port}/upload'], cwd=d, capture_output=True, text=True); print('  curl -F "doc=@hello.txt;type=text/markdown;filename=改名.md" →', r.stdout); R['curl2'] = r.stdout
save('f35', R)
