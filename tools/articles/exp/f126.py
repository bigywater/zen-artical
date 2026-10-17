import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f126'); R = {}
import io, uuid, pathlib
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from PIL import Image, UnidentifiedImageError
UP = FT / 'f126up'; shutil.rmtree(UP, ignore_errors=True); UP.mkdir()
app = Flask('u'); app.logger.disabled = True; app.config['MAX_CONTENT_LENGTH'] = 200 * 1024
ALLOWED = {'png', 'jpg', 'jpeg', 'gif'}
MAGIC = [(b'\x89PNG\r\n\x1a\n', 'png'), (b'\xff\xd8\xff', 'jpg'), (b'GIF87a', 'gif'), (b'GIF89a', 'gif')]
def ext_of(name): return name.rsplit('.', 1)[1].lower() if '.' in name else ''
def sniff(head):
    for sig, kind in MAGIC:
        if head.startswith(sig): return kind
@app.post('/naive')
def naive():
    f = request.files['f']
    if ext_of(f.filename) in ALLOWED and f.mimetype.startswith('image/'): return jsonify(accepted=True, name=f.filename, client_mimetype=f.mimetype)
    return jsonify(accepted=False), 400
@app.post('/checked')
def checked():
    f = request.files.get('f')
    if f is None or not f.filename: return jsonify(error='没有文件'), 400
    ext = ext_of(secure_filename(f.filename))
    if ext not in ALLOWED: return jsonify(error='扩展名不允许', ext=ext), 400
    head = f.stream.read(16); f.stream.seek(0); kind = sniff(head)
    if kind is None: return jsonify(error='文件内容不是允许的图片类型'), 400
    if {'jpeg': 'jpg'}.get(ext, ext) != kind: return jsonify(error='扩展名与内容不一致', ext=ext, content=kind), 400
    data = f.stream.read()
    try: img = Image.open(io.BytesIO(data)); img.verify()
    except (UnidentifiedImageError, Exception) as e: return jsonify(error='图片无法解析', detail=type(e).__name__), 400
    name = f'{uuid.uuid4().hex}.{kind}'; (UP / name).write_bytes(data); return jsonify(saved_as=name, original=secure_filename(f.filename), size=len(data))
def png_bytes(): b = io.BytesIO(); Image.new('RGB', (4, 4), (255, 0, 0)).save(b, 'PNG'); return b.getvalue()
def jpg_bytes(): b = io.BytesIO(); Image.new('RGB', (4, 4), (0, 255, 0)).save(b, 'JPEG'); return b.getvalue()
c = app.test_client()
def up(path, name, data, ctype=None):
    r = c.post(path, data={'f': (io.BytesIO(data), name, ctype)} if ctype else {'f': (io.BytesIO(data), name)}, content_type='multipart/form-data'); return r
def line(label, r): print(f'  {label:<44} → {r.status_code} {json.dumps(r.get_json(), ensure_ascii=False) if r.is_json else r.get_data(as_text=True)[:40]}'); return [r.status_code, r.get_json() if r.is_json else None]
png = png_bytes(); fake = b'this is just text, not an image'
print('== 一:只看扩展名和客户端声明的 Content-Type(naive)能被轻易骗过——客户端想写什么就写什么')
R['naive'] = {}
R['naive']['真 PNG'] = line('真正的 PNG,x.png,image/png', up('/naive', 'x.png', png, 'image/png'))
R['naive']['文本冒充'] = line('纯文本,x.png,声明 image/png', up('/naive', 'x.png', fake, 'image/png'))
R['naive']['大写扩展名'] = line('纯文本,X.PNG,声明 image/png', up('/naive', 'X.PNG', fake, 'image/png'))
R['naive']['真 PNG 错扩展'] = line('真正的 PNG,x.txt,image/png', up('/naive', 'x.txt', png, 'image/png'))
print()
print('== 二:校验内容(检查文件头签名 + 扩展名与内容一致 + 用 Pillow 解析)后保存')
R['checked'] = {}
for label, name, data, ct in (('真正的 PNG', 'photo.png', png, 'image/png'), ('真正的 JPEG,扩展名 jpeg', 'p.jpeg', jpg_bytes(), 'image/jpeg'), ('纯文本冒充 PNG', 'x.png', fake, 'image/png'), ('PNG 内容,扩展名写成 jpg', 'x.jpg', png, 'image/jpeg'), ('PNG 签名 + 后面是垃圾', 'x.png', b'\x89PNG\r\n\x1a\n' + b'garbage' * 10, 'image/png'), ('扩展名不在白名单', 'x.svg', png, 'image/svg+xml'), ('没有扩展名', 'noext', png, 'image/png'), ('文件名含路径与空格', '../my pic.png', png, 'image/png'), ('中文文件名', '照片.png', png, 'image/png')):
    R['checked'][label] = line(label, up('/checked', name, data, ct))
print('  磁盘上保存的文件:', sorted(p.name[:8] + '….' + p.suffix[1:] for p in UP.iterdir()), '(名字是随机的 uuid,不是用户给的)'); R['saved'] = len(list(UP.iterdir()))
r = c.post('/checked', data={}, content_type='multipart/form-data'); R['nofile'] = line('没有 f 字段', r)
print()
print('== 三:大小限制 MAX_CONTENT_LENGTH(这里 200 KB)')
R['size'] = {}
for kb in (100, 199, 201, 1000):
    r = up('/checked', 'big.png', png + b'\x00' * (kb * 1024), 'image/png'); print(f'  上传约 {kb} KB → {r.status_code}'); R['size'][kb] = r.status_code
print()
print('== 四:文件头签名只证明「开头像」:Pillow 的 verify 能识别多少')
trunc = png[:30]; r = line('被截断的 PNG(签名与头部完整,数据缺失)', up('/checked', 'cut.png', trunc, 'image/png')); R['trunc'] = r
save('f126', R)
