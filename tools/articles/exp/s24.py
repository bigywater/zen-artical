import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s24'); reset_s()
class Raw:
    """原始套接字服务器:记录收到的请求头块(字节),回一个最小的 200。"""
    def __init__(self):
        self.reqs = []
        def fn(conn, addr):
            while True:
                data = read_request(conn)
                if not data: break
                self.reqs.append(data)
                conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 15\r\n\r\n<html>ok</html>')
        self.srv = RawSrv(fn)
    def __enter__(self): self.srv.__enter__(); return self
    def __exit__(self, *a): self.srv.__exit__()
    @property
    def port(self): return self.srv.port
def go(spider_body, settings=None, tag='s24', runs=1):
    d = sdir(tag)
    with Raw() as r:
        code = f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
{spider_body.replace('@P@', str(r.port))}
"""
        rc, out, t = runspider(d, code, dict({'LOG_LEVEL': 'WARNING'}, **(settings or {})))
    return r, out
def show(raw, port):
    for line in raw.decode('latin-1').replace(f'127.0.0.1:{port}', '127.0.0.1:端口').strip().split('\r\n'): print('    ' + line)

print('== 一:默认发出的原始请求(用原始套接字服务器看字节:请求行与每个头的顺序、大小写)')
r, out = go("""
    async def start(self): yield scrapy.Request('http://127.0.0.1:@P@/a')
    def parse(self, response): pass
""")
print('  GET 请求:'); show(r.reqs[0], r.port)

print('== 二:内置默认值')
x = subprocess.run([SPY, '-c', 'from scrapy.settings import default_settings as d; print(d.USER_AGENT); print(d.DEFAULT_REQUEST_HEADERS)'], capture_output=True, text=True).stdout.strip().split('\n')
print('  USER_AGENT = ' + x[0]); print('  DEFAULT_REQUEST_HEADERS = ' + x[1])

print('== 三:谁覆盖谁:三个请求头来源(Request.headers、DEFAULT_REQUEST_HEADERS、USER_AGENT 设置)')
CASES = [
 ('只改 USER_AGENT 设置', "yield scrapy.Request('http://127.0.0.1:@P@/a')", {'USER_AGENT': 'MyBot/1.0'}),
 ('Request 的 headers 里写 User-Agent', "yield scrapy.Request('http://127.0.0.1:@P@/a', headers={'User-Agent': 'PerRequest/9'})", {'USER_AGENT': 'MyBot/1.0'}),
 ('DEFAULT_REQUEST_HEADERS 改 Accept-Language,新增 X-Token', "yield scrapy.Request('http://127.0.0.1:@P@/a')", {'DEFAULT_REQUEST_HEADERS': '{"Accept": "application/json", "Accept-Language": "zh-CN", "X-Token": "t"}'}),
 ('Request 的 headers 覆盖 Accept-Language', "yield scrapy.Request('http://127.0.0.1:@P@/a', headers={'Accept-Language': 'fr'})", {}),
 ('USER_AGENT 设成空串', "yield scrapy.Request('http://127.0.0.1:@P@/a')", {'USER_AGENT': ''}),
 ('COMPRESSION_ENABLED=0', "yield scrapy.Request('http://127.0.0.1:@P@/a')", {'COMPRESSION_ENABLED': 0}),
]
for tag, req, st in CASES:
    r, out = go(f"""
    async def start(self): {req}
    def parse(self, response): pass
""", st)
    hs = r.reqs[0].decode('latin-1').split('\r\n')[1:]
    keep = [h for h in hs if h.split(':')[0] in ('User-Agent', 'Accept', 'Accept-Language', 'Accept-Encoding', 'X-Token')]
    print(f'  {tag}:')
    for h in keep: print('      ' + h)
    if not any(h.startswith('User-Agent') for h in keep): print('      (没有 User-Agent 头)')

print('== 四:头名规范化与多值:headers={"user-agent": …, "ACCEPT": …, "x-custom-header": …, "X-Multi": ["a", "b"]} 实际发出的写法')
r, out = go("""
    async def start(self): yield scrapy.Request('http://127.0.0.1:@P@/a', headers={'user-agent': 'lower', 'ACCEPT': 'UPPER', 'x-custom-header': 'v', 'X-Multi': ['a', 'b']})
    def parse(self, response): pass
""")
show(r.reqs[0], r.port)

print('== 五:POST 请求的头:Content-Type、Content-Length 由谁加')
r, out = go("""
    async def start(self): yield scrapy.Request('http://127.0.0.1:@P@/p', method='POST', body='a=1&b=2')
    def parse(self, response): pass
""")
show(r.reqs[0], r.port)
r, out = go("""
    async def start(self): yield scrapy.FormRequest('http://127.0.0.1:@P@/p', formdata={'a': '1', 'b': '2'})
    def parse(self, response): pass
""")
print('  FormRequest(formdata=…):'); show(r.reqs[0], r.port)
