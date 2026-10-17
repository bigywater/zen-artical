import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f63'); R = {}
import timeit, time
from jinja2 import Environment, FileSystemLoader, DictLoader
from flask import Flask, render_template
d = mkapp('f63', {f'templates/t{i}.html': 'Hello {{ name }} ' + '{% if x %}a{% endif %}' * 5 + f' #{i}' for i in range(6)})
tpath = str(d / 'templates')
class Counting(FileSystemLoader):
    n = 0
    def get_source(self, env, name): Counting.n += 1; return super().get_source(env, name)
print('== 一:编译结果缓存在 environment.cache(LRUCache);第二次 get_template 命中缓存,不再读文件')
env = Environment(loader=Counting(tpath)); Counting.n = 0
for i in range(3): env.get_template('t0.html')
print('  get_template("t0.html") 3 次:加载器的 get_source 调用了', Counting.n, '次;缓存里有', len(env.cache), '项;缓存键示例:', [str(k)[:60].replace(str(d), '<项目>') for k in env.cache.keys()][:1]); R['hit'] = [Counting.n, len(env.cache)]
print('  默认 auto_reload =', env.auto_reload, '→ 每次 get_template 都会检查文件是否被修改(uptodate)')
print()
print('== 二:auto_reload 开着时每次 get_template 都要 stat 一次文件;关掉后纯缓存命中')
R['auto'] = {}
for ar in (True, False):
    e = Environment(loader=FileSystemLoader(tpath), auto_reload=ar); e.get_template('t0.html')
    t = min(timeit.timeit(lambda: e.get_template('t0.html'), number=20000) / 20000 * 1e6 for _ in range(3)); R['auto'][str(ar)] = t; print(f'  auto_reload={ar!s:<5} 缓存命中的 get_template:{t:.2f} µs/次')
print()
print('== 三:修改文件后:auto_reload=True 能看到,auto_reload=False 看不到(要重启或清缓存)')
(d / 'templates' / 'live.html').write_text('版本 1')
for ar in (True, False):
    e = Environment(loader=FileSystemLoader(tpath), auto_reload=ar); a = e.get_template('live.html').render(); (d / 'templates' / 'live.html').write_text('版本 2'); time.sleep(0.01); os.utime(d / 'templates' / 'live.html', (time.time() + 5, time.time() + 5)); b = e.get_template('live.html').render(); (d / 'templates' / 'live.html').write_text('版本 1'); os.utime(d / 'templates' / 'live.html', (time.time() - 5, time.time() - 5))
    R.setdefault('reload', {})[str(ar)] = [a, b]; print(f'  auto_reload={ar!s:<5} 改前 {a!r} → 改后 {b!r}')
print()
print('== 四:缓存容量:默认 400;设成 2 并轮流用 3 个模板,每次都未命中(LRU 淘汰了最久没用的)')
for cap in (400, 2):
    e = Environment(loader=Counting(tpath), cache_size=cap, auto_reload=False); Counting.n = 0
    for _ in range(10):
        for i in range(3): e.get_template(f't{i}.html')
    R.setdefault('cap', {})[cap] = Counting.n; print(f'  cache_size={cap:<4} 10 轮 × 3 个模板 = 30 次 get_template,加载器读文件 {Counting.n} 次')
t = {}
for cap in (400, 2):
    e = Environment(loader=FileSystemLoader(tpath), cache_size=cap, auto_reload=False)
    def cycle():
        for i in range(3): e.get_template(f't{i}.html')
    cycle(); t[cap] = min(timeit.timeit(cycle, number=300) / 300 * 1e3 for _ in range(3)); R.setdefault('cap_t', {})[cap] = t[cap]; print(f'  cache_size={cap:<4} 轮流取 3 个模板:{t[cap]:.3f} ms/轮')
print()
print('== 五:关闭缓存(cache_size=0)与手动清缓存')
e = Environment(loader=Counting(tpath), cache_size=0, auto_reload=False); Counting.n = 0
for _ in range(5): e.get_template('t0.html')
print('  cache_size=0:get_template 5 次,读文件', Counting.n, '次'); R['zero'] = Counting.n
e = Environment(loader=Counting(tpath)); Counting.n = 0; e.get_template('t0.html'); e.cache.clear(); e.get_template('t0.html'); print('  cache.clear() 之后再取:读文件', Counting.n, '次(共 2 次:清之前 1 次 + 清之后 1 次)'); R['clear'] = Counting.n
print()
print('== 六:Flask 里的开关:TEMPLATES_AUTO_RELOAD(None 时跟随 debug)')
for dbg, cfg in ((False, None), (True, None), (False, True), (True, False)):
    a = Flask('x', root_path=str(d)); a.config['DEBUG'] = dbg; a.config['TEMPLATES_AUTO_RELOAD'] = cfg; print(f'  DEBUG={dbg!s:<5} TEMPLATES_AUTO_RELOAD={cfg!s:<5} → jinja_env.auto_reload = {a.jinja_env.auto_reload}'); R.setdefault('flask_cfg', {})[f'{dbg}/{cfg}'] = a.jinja_env.auto_reload
a = Flask('x2', root_path=str(d)); a.debug = False; a.config['TEMPLATES_AUTO_RELOAD'] = True; print('  先设 app.debug = False(这会创建 jinja_env),再设 TEMPLATES_AUTO_RELOAD = True → jinja_env.auto_reload =', a.jinja_env.auto_reload, '(配置必须在 jinja_env 创建之前设好)'); R['late_cfg'] = a.jinja_env.auto_reload
print()
print('== 七:Flask 请求里 render_template 的整体耗时:缓存命中时(第一次 vs 之后)')
a = Flask('y', root_path=str(d)); a.logger.disabled = True; a.add_url_rule('/p', 'p', lambda: render_template('t0.html', name='x', x=1)); cc = a.test_client()
t0 = time.perf_counter(); cc.get('/p'); first = (time.perf_counter() - t0) * 1e6; rest = min(timeit.timeit(lambda: cc.get('/p'), number=2000) / 2000 * 1e6 for _ in range(3)); print(f'  第一次请求(含编译){first:.0f} µs;之后每次 {rest:.0f} µs;第一次是之后的 {first / rest:.0f} 倍'); R['flask'] = [first, rest]
save('f63', R)
