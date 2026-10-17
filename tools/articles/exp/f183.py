import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
import threading, socket as sk, json as _j
tee('f183'); R = {}
CORE = '''
import os, json, sentry_sdk
from sentry_sdk.transport import Transport
from sentry_sdk.integrations.flask import FlaskIntegration
from flask import Flask, jsonify, request, abort
EV = []
class Cap(Transport):
    def capture_envelope(self, envelope):
        for it in envelope.items:
            if it.type == "event": EV.append(it.payload.json)
def init(**kw):
    del EV[:]; sentry_sdk.init(dsn="http://k@127.0.0.1:1/1", transport=Cap, integrations=[FlaskIntegration()], **kw)
def build(handler=False):
    app = Flask(__name__)
    @app.get("/boom")
    def boom(): return 1 / 0
    @app.get("/notfound")
    def nf(): abort(404)
    @app.post("/login")
    def login(): raise RuntimeError("login failed for " + request.get_json()["user"])
    @app.get("/handled")
    def handled():
        try: {}["k"]
        except KeyError as e: sentry_sdk.capture_exception(e)
        return "recovered"
    if handler:
        @app.errorhandler(Exception)
        def h(e): return jsonify(error=str(e)), 500
    return app
'''
RUN = '''
import json, sys
from core import *
mode = sys.argv[1]; out = {}
def last(): return EV[-1] if EV else None
def summary(ev):
    if not ev: return None
    ex = ev["exception"]["values"][-1]; fr = ex["stacktrace"]["frames"]
    return {"type": ex["type"], "value": ex["value"], "frames": len(fr), "top": f'{fr[-1]["function"]}:{fr[-1]["lineno"]}', "in_app_top": fr[-1].get("in_app"), "method": ev.get("request", {}).get("method"), "url": ev.get("request", {}).get("url"), "transaction": ev.get("transaction"), "mechanism": ex.get("mechanism", {}).get("type")}
if mode == "basic":
    init(); c = build().test_client(); r = c.get("/boom"); out["boom"] = [r.status_code, summary(last())]
    n = len(EV); r = c.get("/notfound"); out["404"] = [r.status_code, len(EV) - n]
    n = len(EV); r = c.get("/handled"); out["handled"] = [r.status_code, len(EV) - n, summary(last()) and last()["exception"]["values"][-1]["mechanism"]["type"]]
    init(); c = build(handler=True).test_client(); r = c.get("/boom"); out["errorhandler"] = [r.status_code, len(EV)]
if mode == "pii":
    for pii in (False, True):
        init(send_default_pii=pii); c = build().test_client(); c.set_cookie("sessionid", "SECRET-COOKIE"); r = c.post("/login?token=QS-TOKEN", json={"user": "ann", "password": "hunter2"}, headers={"Authorization": "Bearer AUTH-SECRET", "X-Trace": "t1"})
        ev = last(); req = ev["request"]; h = req.get("headers", {})
        out[str(pii)] = {"headers": {k: h[k] for k in h if k.lower() in ("authorization", "cookie", "x-trace")}, "cookies": req.get("cookies"), "query": req.get("query_string"), "data": req.get("data"), "user": ev.get("user"), "msg": ev["exception"]["values"][-1]["value"]}
if mode == "send":
    def bs(event, hint):
        t = event["exception"]["values"][-1]["type"]
        return None if t == "ZeroDivisionError" else event
    init(before_send=bs); c = build().test_client(); c.get("/boom"); c.post("/login", json={"user": "u"}); out["before_send"] = [e["exception"]["values"][-1]["type"] for e in EV]
    init(sample_rate=0.5); c = build().test_client()
    for _ in range(400): c.get("/boom")
    out["sample"] = len(EV)
print('JSON:' + json.dumps(out, ensure_ascii=False))
'''
d = mkapp('f183', {'core.py': CORE, 'run.py': RUN})
def go(mode): rc, o = pyfile(d, 'run.py', args=[mode]); return _j.loads([l for l in o.splitlines() if l.startswith('JSON:')][-1][5:]) if rc == 0 and 'JSON:' in o else {'err': o[-600:]}
b = go('basic'); R['basic'] = b
print('== 一:Flask 集成(sentry-sdk 2.71.0,自写 Transport 收下事件,不联网):哪些异常会上报')
bo = b['boom'][1]; print(f'  未处理的 /boom → HTTP {b["boom"][0]},上报 1 个事件:{bo["type"]}: {bo["value"]},栈 {bo["frames"]} 帧,最内层 {bo["top"]}(in_app={bo["in_app_top"]}),request {bo["method"]} {bo["url"]},transaction={bo["transaction"]},mechanism={bo["mechanism"]}')
print(f'  abort(404) → HTTP {b["404"][0]},上报 {b["404"][1]} 个事件')
print(f'  视图里 try/except 后自己 capture_exception → HTTP {b["handled"][0]},上报 {b["handled"][1]} 个事件(mechanism={b["handled"][2]})')
print(f'  注册了 @errorhandler(Exception) 返回 JSON → HTTP {b["errorhandler"][0]},上报 {b["errorhandler"][1]} 个事件')
print()
p = go('pii'); R['pii'] = p
print('== 二:请求里的敏感信息会不会进事件:发一个带 Cookie、Authorization、?token=、JSON 密码的 POST,让视图抛异常(默认 send_default_pii=False vs True)')
for k in ('False', 'True'):
    v = p[k]; print(f'  send_default_pii={k}:'); print(f'    headers {v["headers"]}'); print(f'    cookies {v["cookies"]} | query_string {v["query"]} | body {v["data"]} | user {v["user"]}'); print(f'    异常信息(message)里写进了用户名:{v["msg"]!r}')
print()
s = go('send'); R['send'] = s
print('== 三:before_send 过滤与 sample_rate')
print(f'  before_send 丢掉 ZeroDivisionError:/boom 与 /login 两次请求之后事件类型 = {s["before_send"]}')
print(f'  sample_rate=0.5,400 次 /boom 之后上报的事件数 = {s["sample"]}')
print()
print('== 四:收集端不可达或卡住时,对请求和进程退出的影响(真实 transport,DSN 指向本机端口)')
APP4 = '''
import os, sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from flask import Flask
if os.environ.get("DSN"): sentry_sdk.init(dsn=os.environ["DSN"], integrations=[FlaskIntegration()])
app = Flask(__name__)
@app.get("/boom")
def boom(): return 1 / 0
'''
d4 = mkapp('f183b', {'app.py': APP4})
hang = sk.socket(); hang.bind(('127.0.0.1', 0)); hang.listen(16); hport = hang.getsockname()[1]; conns = []
threading.Thread(target=lambda: [conns.append(hang.accept()) for _ in range(100)], daemon=True).start()
dead = free_port(); R['lat'] = {}; R['exit'] = {}
print(f'{"配置":<34}{"/boom 中位耗时":>16}{"SIGTERM 后进程退出":>20}')
for label, dsn in (('没有初始化 sentry', ''), ('DSN 端口无人监听', f'http://k@127.0.0.1:{dead}/1'), ('DSN 端口接受连接但不回复', f'http://k@127.0.0.1:{hport}/1')):
    s_ = Server(d4, ['gunicorn', '-w', '1', '-b', '127.0.0.1:{port}', 'app:app'], DSN=dsn)
    L = []
    for _ in range(15): L.append(s_.get('/boom')[3])
    time.sleep(0.5); t0 = time.perf_counter(); os.kill(s_.p.pid, signal.SIGTERM); s_.p.wait(15); te = time.perf_counter() - t0; s_.stop()
    print(f'{label:<34}{median(L):>13.1f} ms{te:>17.2f} s'); R['lat'][label] = median(L); R['exit'][label] = te
save('f183', R)
