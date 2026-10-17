import sys, os, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
from pcdp import Chrome
import requests
tee('p57')
d = pdir('p57')
PROBE = """
(async () => {
  const o = {};
  o.webdriver = navigator.webdriver;
  o.userAgent = navigator.userAgent;
  o.brands = navigator.userAgentData ? navigator.userAgentData.brands.map(b => b.brand + '/' + b.version).join(', ') : null;
  o.platform = navigator.platform;
  o.languages = navigator.languages.join(',');
  o.plugins = navigator.plugins.length;
  o.mimeTypes = navigator.mimeTypes.length;
  o.hardwareConcurrency = navigator.hardwareConcurrency;
  o.maxTouchPoints = navigator.maxTouchPoints;
  o.windowChrome = typeof window.chrome;
  o.screen = screen.width + 'x' + screen.height;
  o.inner = innerWidth + 'x' + innerHeight;
  o.outer = outerWidth + 'x' + outerHeight;
  o.dpr = devicePixelRatio;
  o.notification = (typeof Notification !== 'undefined') ? Notification.permission : null;
  o.hasFocus = document.hasFocus();
  o.visibility = document.visibilityState;
  try { const c = document.createElement('canvas'); const gl = c.getContext('webgl'); const e = gl && gl.getExtension('WEBGL_debug_renderer_info'); o.webglRenderer = e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : (gl ? 'no debug info' : 'no webgl'); } catch (x) { o.webglRenderer = 'error'; }
  o.voices = (window.speechSynthesis ? speechSynthesis.getVoices().length : null);
  return o;
})()
"""
HEADERS = {}
def srv(h):
    HEADERS['last'] = {k: v for k, v in h.hdrs}
    h.reply(200, b'<!doctype html><html><body>probe</body></html>', headers={'Content-Type': 'text/html'})

with Srv(srv) as sv:
    results = {}
    for lab, extra in (('默认(我们的启动参数:headless=new + 远程调试端口)', ()), ('再加 --enable-automation', ('--enable-automation',))):
        with Chrome(free_port(9970), d, extra=extra) as ch:
            pg = ch.new_page(); pg.goto(sv.url('/')); time.sleep(0.3)
            results[lab] = pg.eval(PROBE, await_promise=True); results[lab]['_hdr'] = {k: v for k, v in HEADERS['last'].items() if k.lower().startswith(('sec-ch', 'user-agent'))}; pg.close()
    labs = list(results)
    print('== 一:同一段探测脚本(页面自己的 JavaScript 能读到的值)在两种启动方式下的结果')
    keys = [k for k in results[labs[0]] if k != '_hdr']
    print(f'  {"属性":<22}{"默认启动":<46}{"加 --enable-automation"}')
    for k in keys:
        a, b = results[labs[0]][k], results[labs[1]][k]
        sa = str(a); sb = str(b)
        print(f'  {k:<22}{sa[:44]:<46}{sb[:44]}' + ('   ← 不同' if a != b else ''))
    print(f'  userAgent 完整内容(两种启动方式相同:{results[labs[0]]["userAgent"] == results[labs[1]]["userAgent"]}):{results[labs[0]]["userAgent"]}')
    print(f'  其中是否含 "HeadlessChrome":{"HeadlessChrome" in results[labs[0]]["userAgent"]}')
    print('== 二:服务器这一侧(HTTP 请求头)能看到什么')
    for lab in labs:
        h = results[lab]['_hdr']; print(f'  {lab}:')
        for k, v in h.items(): print(f'      {k}: {v[:160]}')
    print('== 三:对照:requests 发出的请求,服务器能读到的信息(没有 JavaScript,页面脚本根本探测不到它)')
    requests.get(sv.url('/')); h = HEADERS['last']; print('  请求头:' + str({k: v for k, v in h.items()}))
    print('  → 页面上的脚本只能探测"会执行脚本的客户端";不执行脚本的 HTTP 客户端,服务器只能看到上面这几个请求头')
purge()
