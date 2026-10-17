import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f162'); R = {}
import io, json, pstats, timeit, glob, statistics
from flask import Flask, jsonify, render_template_string
from werkzeug.middleware.profiler import ProfilerMiddleware
def build(wrap=None, **kw):
    app = Flask('pf'); app.logger.disabled = True
    def slow_helper(n): return sum(i * i for i in range(n))
    def json_work(): return len(json.dumps([{'id': i, 'name': f'user{i}', 'tags': ['a', 'b']} for i in range(3000)]))
    def render_work(): return len(render_template_string('{% for i in range(800) %}<li>{{ i }} {{ "x" | upper }}</li>{% endfor %}'))
    @app.get('/mixed')
    def mixed():
        a = slow_helper(60000); b = json_work(); c = render_template_string('{% for i in range(800) %}<li>{{ i }}</li>{% endfor %}'); time.sleep(0.02); return jsonify(a=a, b=b, c=len(c))
    @app.get('/fast')
    def fast(): return 'ok'
    if wrap == 'cprofile': app.wsgi_app = ProfilerMiddleware(app.wsgi_app, stream=kw['stream'], restrictions=kw.get('restrictions', (8,)), profile_dir=kw.get('profile_dir'))
    return app
print('== 一:Werkzeug 自带的 ProfilerMiddleware(基于 cProfile):对一个混合了计算、JSON、模板、等待的视图做剖析')
buf = io.StringIO(); app = build('cprofile', stream=buf, restrictions=(8,)); c = app.test_client(); r = c.get('/mixed'); out = tidy(buf.getvalue()).splitlines()
print('  响应:', r.status_code); [print('  ' + l[:150]) for l in out if l.strip()][:22]; R['cprofile_out'] = [l for l in out if l.strip()][:22]
print()
print('== 二:剖析的开销:同一个视图有无 ProfilerMiddleware(各 30 次取中位数)')
plain = build(); cp = build('cprofile', stream=io.StringIO(), restrictions=(1,)); R['cost'] = {}
for label, a in (('没有剖析', plain), ('ProfilerMiddleware(cProfile)', cp)):
    cl = a.test_client(); cl.get('/mixed'); L = []
    for _ in range(30): t0 = time.perf_counter(); cl.get('/mixed'); L.append(ms(t0))
    f = []; 
    for _ in range(300): t0 = time.perf_counter(); cl.get('/fast'); f.append(ms(t0))
    print(f'  {label:<30} /mixed 中位数 {statistics.median(L):7.2f} ms | /fast 中位数 {statistics.median(f) * 1000:7.0f} µs'); R['cost'][label] = [statistics.median(L), statistics.median(f) * 1000]
print()
print('== 三:profile_dir:每个请求一个 .prof 文件,可以事后用 pstats 排序、看调用者')
pdir = FT / 'f162prof'; shutil.rmtree(pdir, ignore_errors=True); pdir.mkdir()
a = build('cprofile', stream=None, profile_dir=str(pdir)); cl = a.test_client(); cl.get('/mixed'); files = sorted(glob.glob(str(pdir / '*.prof'))); print('  生成的文件:', [os.path.basename(f)[:40] for f in files])
st = pstats.Stats(files[0]); sio = io.StringIO(); st.stream = sio; st.sort_stats('tottime').print_stats(6); lines = [l for l in tidy(sio.getvalue()).splitlines() if l.strip()][:14]; print('  按 tottime(函数自身耗时,不含子调用)排序的前几行:'); [print('    ' + l[:150]) for l in lines]; R['tottime'] = lines
print()
print('== 四:采样式剖析 pyinstrument:同一个视图,看调用树;开销')
from pyinstrument import Profiler
a = build(); cl = a.test_client(); cl.get('/mixed')
pr = Profiler(interval=0.001); pr.start(); cl.get('/mixed'); pr.stop(); txt = tidy(pr.output_text(unicode=False, color=False)); lines = [l for l in txt.splitlines() if l.strip()][:16]; [print('  ' + l[:150]) for l in lines]; R['pyinstrument'] = lines
L = []
for _ in range(30):
    pr = Profiler(interval=0.001); pr.start(); t0 = time.perf_counter(); cl.get('/mixed'); L.append(ms(t0)); pr.stop()
print(f'  pyinstrument(1 ms 采样间隔)下 /mixed 中位数 {statistics.median(L):.2f} ms'); R['pyinstr_cost'] = statistics.median(L)
save('f162', R)
