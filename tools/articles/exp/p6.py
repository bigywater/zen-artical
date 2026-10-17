import sys, os, subprocess, hashlib, zlib, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
tee('p6')
d = pdir('p6'); SITE = d / 'site'
r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--target', str(SITE), 'brotli'], capture_output=True, text=True,
                   env={k: v for k, v in os.environ.items() if 'proxy' not in k.lower()})
assert (SITE / 'brotli.py').exists() or list(SITE.glob('_brotli*')) or list(SITE.glob('brotli*')), r.stderr[-300:]
sys.path.insert(0, str(SITE)); import brotli
from compression import zstd

HTML = ('<div class="item"><a href="/product/%d">商品 %d</a><span class="price">¥%d.00</span></div>\n' * 1)
PAGE = ''.join(HTML % (i, i, i % 97) for i in range(3000)).encode()
RAND = os.urandom(len(PAGE))
ENC = {'identity': lambda b: b, 'gzip': lambda b: gz(b), 'deflate': lambda b: zlib.compress(b, 6), 'zstd': lambda b: zstd.compress(b), 'br': lambda b: brotli.compress(b, quality=5)}

_c = zlib.compressobj(9, zlib.DEFLATED, 31); BOMB_DATA = _c.compress(b'\0' * (64 << 20)) + _c.flush()  # 预先压好,避免把服务器压缩的时间算进客户端
def server(h):
    p = h.path.split('?')[0]
    if p == '/ae': return h.reply(200, b'ok')
    if p.startswith('/enc/'):
        _, _, name, kind = p.split('/')
        body = PAGE if kind == 'html' else RAND
        data = ENC[name](body)
        hd = {} if name == 'identity' else {'Content-Encoding': name}
        return h.reply(200, data, headers=hd)
    if p == '/bomb':
        return h.reply(200, BOMB_DATA, headers={'Content-Encoding': 'gzip'})
    h.reply(404, b'')

CLIENT = r'''
import sys, json, hashlib, requests, time
url, kind, name, orig = sys.argv[1:5]
r = requests.get(url, stream=True)
wire = r.raw.read(decode_content=False)
r2 = requests.get(url)
want = open(orig, 'rb').read()
print(json.dumps(dict(wire=len(wire), decoded=len(r2.content), same=r2.content == want, ce=r2.headers.get('Content-Encoding'), sent=r2.request.headers['Accept-Encoding'])))
'''
(d / 'client.py').write_text(CLIENT); (d / 'html.bin').write_bytes(PAGE); (d / 'rand.bin').write_bytes(RAND)
def client(args, with_br, extra_env=None):
    e = {k: v for k, v in os.environ.items()}
    e['PYTHONPATH'] = str(SITE) if with_br else ''
    r = subprocess.run([sys.executable, str(d / 'client.py'), *args], capture_output=True, text=True, env=e, timeout=120)
    return json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {'err': r.stderr.strip().splitlines()[-1][:160]}

with Srv(server) as sv:
    print('== 一:requests 默认发的 Accept-Encoding,取决于本机装了哪些解压库')
    for with_br in (False, True):
        sv.reset()
        subprocess.run([sys.executable, '-c', f'import requests; requests.get("{sv.url("/ae")}")'], capture_output=True, env={**os.environ, 'PYTHONPATH': str(SITE) if with_br else ''})
        ae = next(v for k, v in sv.log[-1]['hdrs'] if k == 'Accept-Encoding')
        print(f'  {"装了 brotli" if with_br else "没装 brotli"}:Accept-Encoding: {ae}')
    import urllib3.util.request as ur
    print(f'  (zstd 不需要另外装:Python 3.14 标准库自带 compression.zstd;这里装的 brotli 版本 {brotli.__version__})')

    print(f'== 二:同一个页面({len(PAGE)} 字节的重复 HTML)用不同压缩方式传输,线上字节数与解压结果(客户端装了 brotli)')
    print(f'  {"编码":<9}{"线上字节":>9}{"占原始比例":>10}  解压后字节  解压结果与原文一致')
    for name in ENC:
        o = client([sv.url(f'/enc/{name}/html'), 'html', name, str(d / 'html.bin')], True)
        print(f'  {name:<9}{o["wire"]:>9}{o["wire"] / len(PAGE) * 100:>9.1f}%  {o["decoded"]:>9}  {o["same"]}')
    print(f'== 三:不可压缩的数据({len(RAND)} 字节随机字节,像已经压缩过的图片/视频)压缩没有收益')
    print(f'  {"编码":<9}{"线上字节":>9}{"占原始比例":>10}')
    for name in ENC:
        o = client([sv.url(f'/enc/{name}/rand'), 'rand', name, str(d / 'rand.bin')], True)
        print(f'  {name:<9}{o["wire"]:>9}{o["wire"] / len(RAND) * 100:>9.1f}%  一致={o["same"]}')

    print('== 四:服务器无视 Accept-Encoding,硬发 br;客户端没装 brotli 会怎样')
    for with_br in (False, True):
        o = client([sv.url('/enc/br/html'), 'html', 'br', str(d / 'html.bin')], with_br)
        print(f'  {"装了 brotli" if with_br else "没装 brotli"}:Content-Encoding={o.get("ce")} 线上 {o.get("wire")} 字节,r.content 长度 {o.get("decoded")},与原文一致={o.get("same")}' + (f' 错误:{o["err"]}' if 'err' in o else ''))

    print('== 五:压缩炸弹:几十 KB 的响应解压成 64 MiB')
    BOMB = r'''
import requests, time, resource, sys
url = sys.argv[1]
t0 = time.perf_counter(); r = requests.get(url)
dt = (time.perf_counter() - t0) * 1000
print(f"普通 get:r.content {len(r.content)} 字节,耗时 {dt:.0f} ms,进程峰值内存 {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576:.0f} MiB")
'''
    BOMB2 = r'''
import requests, time, resource, sys
url = sys.argv[1]
t0 = time.perf_counter(); got = 0
with requests.get(url, stream=True) as r:
    for ch in r.iter_content(65536):
        got += len(ch)
        if got >= (1 << 20): break
dt = (time.perf_counter() - t0) * 1000
print(f"stream + 读满 1 MiB 就停:读到 {got} 字节,耗时 {dt:.0f} ms,进程峰值内存 {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576:.0f} MiB")
'''
    (d / 'b1.py').write_text(BOMB); (d / 'b2.py').write_text(BOMB2)
    import urllib.request
    o = subprocess.run([sys.executable, '-c', f'import requests;r=requests.get("{sv.url("/bomb")}",stream=True);print(len(r.raw.read(decode_content=False)))'], capture_output=True, text=True)
    print(f'  线上传输的字节数(压缩后)= {o.stdout.strip()}')
    for f in ('b1.py', 'b2.py'):
        o = subprocess.run([sys.executable, str(d / f), sv.url('/bomb')], capture_output=True, text=True, env={**os.environ, 'PYTHONPATH': ''})
        print('  ' + (o.stdout.strip() or o.stderr.strip()[-200:]))
purge()
