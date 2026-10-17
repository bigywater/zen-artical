import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f146'); R = {}
import threading
from flask import Flask, current_app, request, jsonify, has_app_context
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
app = Flask('bg'); app.logger.disabled = True; app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'; db = SQLAlchemy(app)
with app.app_context(): db.session.execute(sa.text('create table t (id integer)')); db.session.commit()
print('== 一:线程里没有应用上下文:读 current_app 与查数据库')
out = {}
def no_ctx():
    for name, fn in (('current_app.name', lambda: current_app.name), ('db.session.execute', lambda: db.session.execute(sa.text('select 1')).scalar())):
        try: out[name] = fn()
        except RuntimeError as e: out[name] = 'RuntimeError: ' + str(e).splitlines()[0][:70]
t = threading.Thread(target=no_ctx); t.start(); t.join(); [print(f'  {k:<22} → {v}') for k, v in out.items()]; R['noctx'] = dict(out)
print()
print('== 二:在线程里自己推入应用上下文(with app.app_context())')
out = {}
def with_ctx(real_app):
    with real_app.app_context():
        out['current_app.name'] = current_app.name; out['query'] = db.session.execute(sa.text('select 1')).scalar(); out['has_app_context'] = has_app_context()
        out['session_id'] = id(db.session())
    out['after_exit'] = has_app_context()
with app.test_request_context('/'):
    main_session = id(db.session())
    t = threading.Thread(target=with_ctx, args=(current_app._get_current_object(),)); t.start(); t.join()
[print(f'  {k:<22} → {v}') for k, v in out.items()]; print('  线程里的 db.session 与请求线程里的是不是同一个:', out['session_id'] == main_session, '(各有各的 session)'); R['ctx'] = {k: str(v) for k, v in out.items()}; R['same_session'] = out['session_id'] == main_session
print('  (传给线程的是真实的 Flask 对象 current_app._get_current_object(),不是代理)')
print()
print('== 三:线程里的异常:HTTP 响应已经返回,Flask 的错误处理器看不到它')
APP = '''
import threading, time, os, sys
from flask import Flask, jsonify
app = Flask(__name__)
LOG = os.environ["LOGF"]
def job(duration, tag):
    for i in range(int(duration * 10)): time.sleep(0.1)
    with open(LOG, "a") as f: f.write(f"{tag} finished\\n")
def failing():
    time.sleep(0.2); raise ValueError("job failed in background thread")
@app.errorhandler(Exception)
def handler(e): return jsonify(handled=str(e)), 500
@app.post("/fail")
def fail(): threading.Thread(target=failing).start(); return jsonify(ok=True)
@app.post("/job/<mode>")
def start(mode):
    threading.Thread(target=job, args=(3.0, mode), daemon=(mode == "daemon")).start(); return jsonify(started=mode)
'''
d = mkapp('f146', {'app.py': APP}); LOGF = d / 'jobs.log'
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '4', 'app:app'], LOGF=LOGF) as s:
    time.sleep(1.0); r = s.post('/fail') if hasattr(s, 'post') else s.req('POST', '/fail'); print('  POST /fail →', r[0], r[2].decode().strip()); time.sleep(0.6)
    log = s.logtext(); print('  响应是 200;异常出现在服务器日志里:', 'ValueError: job failed in background thread' in log, '| 日志片段:', [l.strip()[:80] for l in log.splitlines() if 'Exception in thread' in l][:1]); R['thread_exc'] = [r[0], 'ValueError: job failed in background thread' in log]
print()
print('== 四:worker 被优雅停止时,还没跑完的后台线程会怎样?(任务要 3 秒,启动 1 秒后给 gunicorn master 发 SIGTERM)')
R['stop'] = {}
for mode in ('daemon', 'nondaemon'):
    LOGF.write_text('')
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '4', '--graceful-timeout', '10', 'app:app'], LOGF=LOGF) as s:
        time.sleep(1.0); r = s.req('POST', f'/job/{mode}'); time.sleep(1.0); t0 = time.time(); os.kill(s.p.pid, signal.SIGTERM)
        try: s.p.wait(15)
        except Exception: pass
        exit_after = time.time() - t0; done = 'finished' in LOGF.read_text(); print(f'  {mode:<10} 线程:master 在 SIGTERM 后 {exit_after:.1f} 秒退出,任务是否做完:{done}'); R['stop'][mode] = [exit_after, done]
save('f146', R)
