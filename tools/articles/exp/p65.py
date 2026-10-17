import sys, os, socket, subprocess, time, re, collections, urllib.robotparser, asyncio; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests, urllib.request, aiohttp
from curl_cffi import requests as cr
tee('p65')
d = pdir('p65'); port = free_port(9980)
for sub in ('body', 'proxy', 'fcgi', 'uwsgi', 'scgi'): (d / sub).mkdir()
LOG = d / 'access.log'
conf = f"""worker_processes 1; daemon off; pid {d}/nginx.pid; error_log {d}/err.log warn;
events {{ worker_connections 256; }}
http {{
  log_format comb '$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"';
  log_format withfrom '$remote_addr "$request" $status ua="$http_user_agent" from="$http_from"';
  access_log {LOG} comb; access_log {d}/from.log withfrom;
  client_body_temp_path {d}/body; proxy_temp_path {d}/proxy; fastcgi_temp_path {d}/fcgi; uwsgi_temp_path {d}/uwsgi; scgi_temp_path {d}/scgi;
  server {{ listen 127.0.0.1:{port};
    location = /robots.txt {{ return 200 "User-agent: mycrawler\\nDisallow: /private/\\n\\nUser-agent: *\\nDisallow: /\\n"; }}
    location / {{ return 200 "ok\\n"; }} }}
}}
"""
(d / 'nginx.conf').write_text(conf)
nx = subprocess.Popen(['nginx', '-p', str(d), '-c', str(d / 'nginx.conf')], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
for _ in range(100):
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1', port)) == 0: break
    time.sleep(0.05)
B = f'http://127.0.0.1:{port}'
def strip(l): return re.sub(r'^\S+ - - \[[^\]]+\] ', '', l)
def lines(f='access.log'): return (d / f).read_text().splitlines() if (d / f).exists() else []
def mark(): return len(lines())
def new(n0, f='access.log'): return lines(f)[n0:]
def raw(headers_bytes, path='/x'):
    s = socket.create_connection(('127.0.0.1', port)); s.sendall(b'GET ' + path.encode() + b' HTTP/1.1\r\nHost: x\r\n' + headers_bytes + b'Connection: close\r\n\r\n'); buf = b''
    while True:
        try: x = s.recv(65536)
        except OSError: break
        if not x: break
        buf += x
    s.close(); return buf
try:
    print(f'== 一:不改 UA 时,各个库在服务器日志里留下什么(nginx 1.31.6 的 combined 格式访问日志,原样摘录)')
    n0 = mark(); requests.get(B + '/a-requests'); urllib.request.urlopen(B + '/b-urllib').read()
    async def aio():
        async with aiohttp.ClientSession() as s:
            async with s.get(B + '/c-aiohttp') as r: await r.read()
    asyncio.run(aio()); cr.get(B + '/d-curl_cffi'); cr.get(B + '/e-curl_cffi-chrome', impersonate='chrome')
    raw(b'', '/f-no-user-agent-header')
    for l in new(n0): print('  ' + re.sub(r'^\S+ - - \[[^\]]+\] ', '', l))
    print('== 二:自报身份的 User-Agent 和 From 头:日志里的样子(第二个日志格式额外记录 $http_from)')
    UA = 'MyCrawler/1.0 (+https://example.org/bot.html; ops@example.org)'
    n0 = mark(); nf = len(lines('from.log')); requests.get(B + '/with-id', headers={'User-Agent': UA, 'From': 'ops@example.org'}); requests.get(B + '/without-from', headers={'User-Agent': UA})
    for l in new(n0): print('  combined:' + re.sub(r'^\S+ - - \[[^\]]+\] ', '', l))
    for l in new(nf, 'from.log'): print('  withfrom:' + l)
    print('== 三:User-Agent 太长会怎样(nginx 默认 large_client_header_buffers 4 8k,每个请求头和请求行各要放进一个 8 KiB 的缓冲)')
    for n in (1000, 4000, 8000, 8100, 8200, 16000):
        r = raw(b'User-Agent: ' + b'a' * n + b'\r\n'); st = r.split(b'\r\n')[0].decode()
        print(f'  UA 长 {n:5d} 字节:{st}')
    print('== 四:User-Agent 里放中文、换行会怎样')
    for lab, ua in (('中文(str)', '爬虫/1.0 (联系:运维 ops@example.org)'), ('中文(bytes,UTF-8)', '爬虫/1.0'.encode()), ('含换行', 'Bot/1.0\r\nX-Injected: 1')):
        n0 = mark()
        try: r = requests.get(B + '/enc-requests', headers={'User-Agent': ua}); res = f'发出,状态 {r.status_code}'
        except Exception as e: res = f'{type(e).__name__}: {str(e)[:60]}'
        log = [re.sub(r'^\S+ - - \[[^\]]+\] ', '', l) for l in new(n0)]
        print(f'  requests {lab}:{res};日志:{log}')
    n0 = mark()
    try: urllib.request.urlopen(urllib.request.Request(B + '/enc-urllib', headers={'User-Agent': '爬虫/1.0'})).read(); res = '发出'
    except Exception as e: res = f'{type(e).__name__}: {str(e)[:60]}'
    print(f'  urllib 中文(str):{res}')
    async def aio2(ua):
        async with aiohttp.ClientSession(headers={'User-Agent': ua}) as s:
            async with s.get(B + '/enc-aiohttp') as r: return r.status
    n0 = mark()
    try: res = f'发出,状态 {asyncio.run(aio2("爬虫/1.0"))}'
    except Exception as e: res = f'{type(e).__name__}: {str(e)[:60]}'
    print(f'  aiohttp 中文(str):{res};日志:{[strip(l) for l in new(n0)]}')
    print('== 五:robots.txt 按 User-agent 匹配(robots.txt 里 mycrawler 组 Disallow /private/,* 组 Disallow /),标准库 urllib.robotparser')
    rp = urllib.robotparser.RobotFileParser(); rp.parse(requests.get(B + '/robots.txt').text.splitlines())
    for lab, ua in (('只传产品名 MyCrawler', 'MyCrawler'), ('传完整 UA 字符串', UA), ('传 Mozilla 兼容写法', 'Mozilla/5.0 (compatible; MyCrawler/1.0; +https://example.org/bot.html)'), ('传 mycrawler/1.0', 'mycrawler/1.0')):
        print(f'  {lab:22s} can_fetch("/public") = {rp.can_fetch(ua, "/public")}, can_fetch("/private/x") = {rp.can_fetch(ua, "/private/x")}')
    print('== 六:站长从日志里能看到什么:三种客户端各发 300 个请求(同一个 IP 127.0.0.1)')
    n0 = mark()
    def burst(ua, n=300):
        s = requests.Session()
        for i in range(n): s.get(B + f'/burst/{i}', headers=({'User-Agent': ua} if ua else {}))
    burst(None); burst(UA); burst('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36')
    ls = new(n0); byip = collections.Counter(l.split()[0] for l in ls); byua = collections.Counter(re.findall(r'"([^"]*)"$', l)[0] for l in ls)
    print(f'  按来源 IP 统计:{dict(byip)}')
    print('  按 User-Agent 统计:')
    for u, c in byua.most_common(): print(f'    {c:4d}  {u[:130]}')
finally:
    nx.terminate()
    try: nx.wait(5)
    except Exception: nx.kill()
purge()
