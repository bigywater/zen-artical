import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests
tee('p7')
BLOCK = b'x' * 65536
written = {}

def server(h):
    p = h.path.split('?')[0]
    if p == '/chunked':
        h.send_chunks([b'A' * 1000, b'B' * 1000, b'C' * 1000, b'D' * 1000, b'E' * 1000], delay=0.3)
    elif p == '/lines':
        h.send_chunks([b'line1\nli', b'ne2\nline3\n', b'lin', b'e4'], delay=0.1)
    elif p == '/big':
        n = int(h.path.split('n=')[1]) if 'n=' in h.path else 3200
        h.send_response(200); h.send_header('Content-Length', str(n * 65536)); h.end_headers()
        sent = 0
        try:
            for _ in range(n): h.wfile.write(BLOCK); sent += len(BLOCK)
            h.wfile.flush()
        except Exception: h.close_connection = True
    elif p == '/short':
        h.send_response(200); h.send_header('Content-Length', '1000'); h.end_headers()
        h.wfile.write(b'y' * 600); h.wfile.flush(); h.close_connection = True
    elif p == '/short-chunked':
        h.send_response(200); h.send_header('Transfer-Encoding', 'chunked'); h.end_headers()
        h.wfile.write(b'3e8\r\n' + b'z' * 1000 + b'\r\n'); h.wfile.write(b'3e8\r\n' + b'z' * 300); h.wfile.flush(); h.close_connection = True
    elif p == '/bighead': h.reply(200, b'', headers={'Content-Length': str(3200 * 65536)})
    elif p == '/small': h.reply(200, b'ok')
    else: h.reply(404)

with Srv(server) as sv:
    print('== 一:chunked 响应没有 Content-Length;服务器每 0.3 秒发一块(5 块,每块 1000 字节)')
    r = requests.get(sv.url('/chunked'), stream=True)
    print(f'  响应头:Transfer-Encoding={r.headers.get("Transfer-Encoding")},Content-Length={r.headers.get("Content-Length")}')
    t0 = time.perf_counter(); arr = []
    for ch in r.iter_content(chunk_size=None): arr.append((ms(t0), len(ch)))
    print('  iter_content(chunk_size=None):每块到达的时刻与大小 ' + ', '.join(f'{t:.0f}ms/{n}B' for t, n in arr))
    r = requests.get(sv.url('/chunked'), stream=True); t0 = time.perf_counter(); arr = []
    for ch in r.iter_content(chunk_size=4096): arr.append((ms(t0), len(ch)))
    print('  iter_content(chunk_size=4096):' + ', '.join(f'{t:.0f}ms/{n}B' for t, n in arr))
    r = requests.get(sv.url('/chunked'), stream=True); t0 = time.perf_counter(); arr = []
    for ch in r.iter_content(chunk_size=300): arr.append((ms(t0), len(ch)))
    print('  iter_content(chunk_size=300):' + f'共 {len(arr)} 次,前 6 次 ' + ', '.join(f'{t:.0f}ms/{n}B' for t, n in arr[:6]))
    t0 = time.perf_counter(); r = requests.get(sv.url('/chunked')); print(f'  不用 stream:requests.get 返回时已经过了 {ms(t0):.0f} ms,r.content 共 {len(r.content)} 字节')
    t0 = time.perf_counter(); r = requests.get(sv.url('/chunked'), stream=True); print(f'  stream=True:requests.get 返回(只拿到响应头)用了 {ms(t0):.0f} ms')

    print('== 二:iter_lines 按行切分,行可以跨块')
    r = requests.get(sv.url('/lines'), stream=True)
    print('  服务器发的块:[b"line1\\nli", b"ne2\\nline3\\n", b"lin", b"e4"]')
    print('  iter_lines() 得到:' + repr(list(r.iter_lines())))

    print('== 三:只想看响应头:服务器要发 200 MiB。stream 看一眼就 close、HEAD、读完,各花多久,之后同一个 Session 的下一个请求要不要新建连接')
    for label in ('stream=True 看一眼就 close()', 'HEAD', '普通 get 读完'):
        sv.reset(); s = requests.Session()
        t0 = time.perf_counter()
        if label.startswith('stream'):
            r = s.get(sv.url('/big'), stream=True); info = f'状态码 {r.status_code} Content-Length={r.headers["Content-Length"]}'; r.close()
        elif label == 'HEAD':
            r = s.head(sv.url('/bighead')); info = f'状态码 {r.status_code} Content-Length={r.headers["Content-Length"]}'
        else:
            r = s.get(sv.url('/big')); info = f'r.content {len(r.content) / 1048576:.0f} MiB'
        t = ms(t0)
        s.get(sv.url('/small')); 
        print(f'  {label}:{t:.1f} ms({info});随后同一个 Session 再发一个小请求,服务器累计连接数 {sv.n_conn}')
    print('  (本机回环速度;真实网络上差距按带宽放大)')

    print('== 四:响应被截断时 requests 的表现:Content-Length 声称 1000 字节但只发了 600 就断开')
    for path, label in (('/short', 'Content-Length: 1000,实发 600 字节'), ('/short-chunked', 'chunked,第二块声明 1000 字节只发了 300')):
        try:
            r = requests.get(sv.url(path)); res = f'没有异常,r.content {len(r.content)} 字节'
        except Exception as e: res = f'{type(e).__name__}:{str(e)[:100]}'
        print(f'  {label} → {res}')
        try:
            r = requests.get(sv.url(path), stream=True); n = 0
            for ch in r.iter_content(256): n += len(ch)
            res = f'没有异常,读到 {n} 字节'
        except Exception as e: res = f'读到 {n} 字节后 {type(e).__name__}'
        print(f'    stream 逐块读 → {res}')
purge()
