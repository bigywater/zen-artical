import sys, os, re, time, json, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x51'); CP = scp('org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.web.bind.annotation.*; import org.springframework.web.servlet.resource.ResourceUrlProvider;
@SpringBootApplication @RestController
public class Main {
  final ResourceUrlProvider urls; Main(ResourceUrlProvider u) { urls = u; }
  @GetMapping("/url") String url(@RequestParam String path) { return String.valueOf(urls.getForLookupPath(path)); }
  @GetMapping("/over.txt") String over() { return "来自控制器的 over.txt"; }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
FILES = {'src/demo/Main.java': MAIN, 'logback.xml': LOG,
         'static/hello.txt': '0123456789abcdefghij\n', 'static/app.js': 'console.log("app v1");\n', 'static/index.html': '<h1>welcome</h1>\n', 'static/over.txt': '来自静态文件的 over.txt\n', 'static/css/site.css': 'body{color:red}\n', 'public/pub.txt': 'in public/\n'}
b = sbuild('x51', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
SHOW = ['Content-Type', 'Content-Length', 'Cache-Control', 'ETag', 'Last-Modified', 'Accept-Ranges', 'Content-Range', 'Expires', 'Pragma', 'Vary']
def req(app, m, p, hd=None, show=None, label=None):
    c = http.client.HTTPConnection('127.0.0.1', int(app.props['server.port']), timeout=10); c.request(m, p, headers=hd or {}); r = c.getresponse(); d = r.read().decode('utf-8', 'replace'); hs = dict(r.getheaders()); c.close()
    keep = {k: (re.sub(r'(GMT).*', r'\1', v) if k == 'Last-Modified' else v) for k, v in hs.items() if k in (show or SHOW)}
    if 'Last-Modified' in keep: keep['Last-Modified'] = '<日期>'
    h_ = ' '.join(f'{k}: {v}' for k, v in (hd or {}).items())
    d = re.sub(r'\s+', ' ', d.strip())[:40]
    print(f'  {label or ""}{m} {p}{"  [" + h_ + "]" if h_ else ""} → {r.status} {d!r}'); print(f'      响应头:{keep if keep else "(无相关头)"}')
    return r.status, hs, d
def run(props, f, title, head=True):
    app = SApp(b, 'demo.Main', props=props).start(); print(f'== {title}' if head else f'  -- {title}'); f(app); app.stop()
print('Spring Boot 4.0.8 / Spring MVC 7.0.9(Tomcat 11.0.24)。资源文件:classpath:/static/{hello.txt,app.js,index.html,over.txt,css/site.css},classpath:/public/pub.txt')
def one(app):
    req(app, 'GET', '/hello.txt'); req(app, 'GET', '/app.js'); req(app, 'GET', '/css/site.css'); req(app, 'GET', '/'); req(app, 'GET', '/pub.txt'); req(app, 'GET', '/nope.txt'); req(app, 'HEAD', '/hello.txt'); req(app, 'GET', '/over.txt')
run({}, one, '一:默认配置:classpath:/static 下的文件,响应头里有没有缓存头;/ 欢迎页;/public;控制器与同名静态文件')
def two(app):
    s, h, d = req(app, 'GET', '/hello.txt'); lm = h.get('Last-Modified')
    req(app, 'GET', '/hello.txt', {'If-Modified-Since': lm}, label='条件请求:'); req(app, 'GET', '/hello.txt', {'If-Modified-Since': 'Mon, 01 Jan 2001 00:00:00 GMT'}, label='条件请求(旧日期):')
    req(app, 'GET', '/hello.txt', {'Range': 'bytes=0-4'}, label='Range:'); req(app, 'GET', '/hello.txt', {'Range': 'bytes=15-'}, label='Range:'); req(app, 'GET', '/hello.txt', {'Range': 'bytes=999-1000'}, label='Range:')
run({}, two, '二:条件请求(If-Modified-Since)与 Range:304、206、416')
def three(app):
    req(app, 'GET', '/hello.txt'); req(app, 'GET', '/app.js')
print('== 三:三种缓存头配置:cache.period、cachecontrol.*、no-cache')
run({'spring.web.resources.cache.period': '3600'}, three, 'spring.web.resources.cache.period=3600', False)
def four(app):
    req(app, 'GET', '/hello.txt')
run({'spring.web.resources.cache.cachecontrol.max-age': '1d', 'spring.web.resources.cache.cachecontrol.cache-public': 'true', 'spring.web.resources.cache.cachecontrol.must-revalidate': 'true'}, four, 'cachecontrol.max-age=1d、cache-public、must-revalidate', False)
def five(app):
    req(app, 'GET', '/hello.txt')
run({'spring.web.resources.cache.cachecontrol.no-cache': 'true'}, five, 'cachecontrol.no-cache=true', False)
def six(app):
    s, h, d = req(app, 'GET', '/url?path=/app.js'); s, h, d2 = req(app, 'GET', '/url?path=/css/site.css'); s, h, d3 = req(app, 'GET', '/url?path=/hello.txt')
    vp = d if d.startswith('/') else None
    req(app, 'GET', '/app.js', label='未版本化的原路径:')
    if vp: s, h1, _ = req(app, 'GET', vp, label='带内容哈希的路径:'); e = h1.get('ETag'); lm = h1.get('Last-Modified')
    req(app, 'GET', '/app-00000000000000000000000000000000.js', label='错误的哈希:')
    if vp and lm: req(app, 'GET', vp, {'If-Modified-Since': lm}, label='条件请求:')
run({'spring.web.resources.chain.strategy.content.enabled': 'true', 'spring.web.resources.chain.strategy.content.paths': '/**', 'spring.web.resources.cache.cachecontrol.max-age': '365d', 'spring.web.resources.cache.cachecontrol.cache-public': 'true'}, six, '四:内容哈希版本化(chain.strategy.content,max-age=365d):ResourceUrlProvider 生成带哈希的 URL')
def seven(app):
    s, h, d = req(app, 'GET', '/url?path=/app.js'); req(app, 'GET', d, label='版本化路径:'); req(app, 'GET', '/app.js', label='原路径:')
run({'spring.web.resources.chain.strategy.fixed.enabled': 'true', 'spring.web.resources.chain.strategy.fixed.paths': '/**', 'spring.web.resources.chain.strategy.fixed.version': 'v7'}, seven, '五:固定版本前缀(chain.strategy.fixed.version=v7)')
def eight(app):
    req(app, 'GET', '/hello.txt'); req(app, 'GET', '/pub.txt'); req(app, 'GET', '/over.txt'); req(app, 'GET', '/index.html')
run({'spring.web.resources.add-mappings': 'false'}, eight, '六:spring.web.resources.add-mappings=false')
def nine(app):
    for p in ['/%2e%2e/hello.txt', '/css/../hello.txt', '/css/%2e%2e/hello.txt', '/css/..%2fhello.txt', '/..%2f..%2fetc/passwd', '/%2e%2e%2f%2e%2e%2fetc/passwd', '/css/%5c..%5chello.txt']: req(app, 'GET', p)
run({}, nine, '七:路径穿越写法')
