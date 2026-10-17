import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f138'); R = {}
import asyncio, threading, contextvars
from flask import Flask, request, jsonify, g, session, current_app, copy_current_request_context, has_request_context
app = Flask('b'); app.logger.disabled = True; app.config['SECRET_KEY'] = 'k' * 32; app.config['PROPAGATE_EXCEPTIONS'] = False
CV = contextvars.ContextVar('cv', default='unset')
FLAGS = {}
@app.before_request
def before(): g.from_before = 'set in before_request'; CV.set('set in before_request')
@app.get('/threads')
def sync_threads(): return jsonify(thread=threading.current_thread().name, main=threading.current_thread() is threading.main_thread())
@app.get('/athreads')
async def async_threads(): return jsonify(thread=threading.current_thread().name, main=threading.current_thread() is threading.main_thread())
@app.get('/ctx')
async def ctx():
    session['x'] = 1
    return jsonify(request_path=request.path, has_request_context=has_request_context(), g_value=g.get('from_before'), app_name=current_app.name, contextvar=CV.get(), session_x=session.get('x'))
@app.get('/task')
async def task_view():
    FLAGS['task'] = 'not run'
    async def later(): await asyncio.sleep(0.5); FLAGS['task'] = 'finished'
    asyncio.create_task(later()); return 'responded'
@app.get('/task-await')
async def task_await():
    FLAGS['t2'] = 'not run'
    async def later(): await asyncio.sleep(0.3); FLAGS['t2'] = 'finished'
    t = asyncio.create_task(later()); await t; return 'responded after task'
EV = asyncio.Event()
@app.get('/global-event')
async def global_event():
    try: await asyncio.wait_for(EV.wait(), timeout=0.2)
    except asyncio.TimeoutError: return 'timed out waiting (event not set)'
    return 'event was set'
LOCK = asyncio.Lock()
async def critical(): 
    async with LOCK: await asyncio.sleep(0.1)
@app.get('/global-lock')
async def global_lock():
    await asyncio.gather(critical(), critical()); return 'lock ok'
@app.get('/thread-in-async')
async def thread_in_async():
    def blocking(): time.sleep(0.3); return threading.current_thread().name
    name = await asyncio.to_thread(blocking); return jsonify(worker_thread=name)
@app.get('/copy-ctx')
async def copy_ctx():
    @copy_current_request_context
    def work(): return request.path
    return jsonify(path=await asyncio.to_thread(work))
@app.get('/plain-thread')
async def plain_thread():
    out = {}
    def work(): out['has'] = has_request_context()
    t = threading.Thread(target=work); t.start(); t.join(); return jsonify(has_request_context=out['has'])
@app.get('/no-copy')
async def no_copy():
    def work(): return has_request_context()
    return jsonify(has_request_context=await asyncio.to_thread(work))
c = app.test_client()
print('== 一:视图代码在哪个线程运行')
a, b = c.get('/threads').get_json(), c.get('/athreads').get_json(); print('  sync 视图:', a); print('  async 视图:', b); R['threads'] = [a, b]
print()
print('== 二:async 视图里还能用哪些上下文')
r = c.get('/ctx').get_json(); [print(f'  {k:<18} {v}') for k, v in r.items()]; R['ctx'] = r
print()
print('== 三:响应返回之后,视图里用 create_task 启动的任务还会继续吗?')
c.get('/task'); time.sleep(1.0); print('  create_task 之后立刻返回响应,1 秒后任务状态:', FLAGS['task']); R['task'] = FLAGS['task']
r = c.get('/task-await'); print('  await 了任务再返回:', r.get_data(as_text=True), '| 任务状态:', FLAGS['t2']); R['task_await'] = FLAGS['t2']
print()
print('== 四:模块级的 asyncio 对象(Event、Lock)是绑定到事件循环的:每个请求一个新循环,第二个请求会遇到什么')
app.config['PROPAGATE_EXCEPTIONS'] = False
for path in ('/global-event', '/global-event', '/global-lock', '/global-lock'):
    r = c.get(path); print(f'  GET {path:<14} → {r.status_code} {r.get_data(as_text=True)[:70]!r}'); R.setdefault('global', []).append([path, r.status_code, r.get_data(as_text=True)[:70]])
app.config['PROPAGATE_EXCEPTIONS'] = True
for path in ('/global-event', '/global-lock'):
    try: c.get(path); out = '没有异常'
    except Exception as e: out = f'{type(e).__name__}: {str(e)[:100]}'
    print(f'  再请求一次 {path}(让异常传播出来)→', out); R.setdefault('global_err', {})[path] = out
app.config['PROPAGATE_EXCEPTIONS'] = False
print()
print('== 五:从 async 视图里启动的线程:asyncio.to_thread 会带上上下文,自己 new 的 threading.Thread 不会')
r1, r2 = c.get('/no-copy').get_json(), c.get('/copy-ctx').get_json(); print('  asyncio.to_thread 里直接 has_request_context():', r1['has_request_context']); print('  再用 copy_current_request_context 包装后读 request.path:', r2['path']); r3 = c.get('/plain-thread').get_json(); print('  自己 new 的 threading.Thread 里 has_request_context():', r3['has_request_context']); R['copy'] = [r1['has_request_context'], r2['path'], r3['has_request_context']]
r = c.get('/thread-in-async').get_json(); print('  to_thread 的工作线程名:', r['worker_thread'])
save('f138', R)
