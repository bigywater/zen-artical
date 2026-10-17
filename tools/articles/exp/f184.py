import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
import json as _j
tee('f184'); R = {}
ONE = '''
import os, sys, json
from flask import Flask, session
mode = sys.argv[1]; out = {}
app = Flask("t")
if mode == "types":
    for k, v in (("A", "42"), ("B", "true"), ("C", "false"), ("D", "[1,2]"), ("E", "abc"), ("F", "0"), ("G", "1.5"), ("H", "null"), ("I__J", "x"), ("K", "True"), ("L", "'quoted'"), ("M", "")): os.environ["APP_" + k] = v
    app.config.from_prefixed_env("APP")
    out = {k: [type(app.config[k]).__name__, repr(app.config[k])] for k in "ABCDEFGHKLM"}; out["I"] = repr(app.config["I"])
    out["os_environ_check"] = {v: bool(v) for v in ("0", "false", "False", "no")}
if mode == "secret":
    res = {}
    for val in ("12345", "abcdef", "1e3", "true", "s3cr3t-key"):
        os.environ["APP_SECRET_KEY"] = val; a = Flask("t"); a.config.from_prefixed_env("APP"); sk = a.config["SECRET_KEY"]
        @a.get("/")
        def idx(): session["x"] = 1; return "ok"
        r = a.test_client().get("/"); res[val] = [type(sk).__name__, r.status_code]
    out = res
if mode == "order":
    open("base.py", "w").write("LEVEL = 'file'\\nNAME = 'from-file'\\n")
    app.config.from_mapping(LEVEL="default", NAME="default", ONLY_DEFAULT=1)
    steps = [("from_mapping(默认值)", dict(app.config))]
    app.config.from_pyfile("base.py"); steps.append(("from_pyfile(base.py)", dict(app.config)))
    os.environ["APP_LEVEL"] = "env"; app.config.from_prefixed_env("APP"); steps.append(("from_prefixed_env('APP')", dict(app.config)))
    out = {"steps": [[n, {k: c[k] for k in ("LEVEL", "NAME", "ONLY_DEFAULT")}] for n, c in steps]}
if mode == "envvar":
    try: app.config.from_envvar("NOPE_SETTINGS")
    except Exception as e: out["unset"] = [type(e).__name__, str(e)]
    print(app.config.from_envvar("NOPE_SETTINGS", silent=True), file=sys.stderr)
    out["silent"] = app.config.from_envvar("NOPE_SETTINGS", silent=True)
    open("prod.cfg", "w").write("MODE = 'prod'\\n"); os.environ["NOPE_SETTINGS"] = "prod.cfg"; out["loaded"] = [app.config.from_envvar("NOPE_SETTINGS"), app.config["MODE"]]
    os.environ["NOPE_SETTINGS"] = "missing.cfg"
    try: app.config.from_envvar("NOPE_SETTINGS")
    except Exception as e: out["missingfile"] = [type(e).__name__, __import__("re").sub(r"'/[^']*'", "'<路径>'", str(e))]
print("JSON:" + json.dumps(out, ensure_ascii=False))
'''
DOT = '''
import os, click
from flask import Flask
app = Flask("t")
@app.cli.command("show")
def show(): click.echo("DOT_VAR in environ: " + repr(os.environ.get("DOT_VAR")))
@app.get("/")
def idx(): return repr(os.environ.get("DOT_VAR"))
'''
d = mkapp('f184', {'one.py': ONE, 'dotapp.py': DOT, '.env': 'DOT_VAR=from-dotenv\n'})
def go(mode):
    rc, o = pyfile(d, 'one.py', args=[mode]); ls = [l for l in o.splitlines() if l.startswith('JSON:')]; return _j.loads(ls[-1][5:]) if ls else {'err': o[-400:]}
t = go('types'); R['types'] = t
print('== 一:app.config.from_prefixed_env("APP"):环境变量里的字符串被怎么转换(每个值先按 JSON 解析,失败就保留字符串)')
print(f'{"环境变量 APP_x =":<22}{"config 里的类型":<10}{"值"}')
src = {'A': '42', 'B': 'true', 'C': 'false', 'D': '[1,2]', 'E': 'abc', 'F': '0', 'G': '1.5', 'H': 'null', 'K': 'True', 'L': "'quoted'", 'M': ''}
for k in 'ABCDEFGHKLM': print(f'  {src[k]!r:<18}{t[k][0]:<10}{t[k][1]}')
print(f'  APP_I__J=x(双下划线表示嵌套)→ config["I"] = {t["I"]}')
print(f'  对比:直接 os.environ.get(...) 拿到的字符串再 bool():{t["os_environ_check"]}(任何非空字符串都是 True,包括 "0" 与 "false")')
print()
s = go('secret'); R['secret'] = s
print('== 二:SECRET_KEY 经 from_prefixed_env 读入后,不同取值能不能正常用 session(视图里 session["x"] = 1)')
for v, (ty, st) in s.items(): print(f'  APP_SECRET_KEY={v!r:<14} → config 里是 {ty:<6} → 访问带 session 的视图:HTTP {st}')
print()
o = go('order'); R['order'] = o
print('== 三:加载顺序:后加载的覆盖先加载的')
for n, c in o['steps']: print(f'  {n:<28}→ {c}')
print()
e = go('envvar'); R['envvar'] = e
print('== 四:app.config.from_envvar:变量没设、silent、指向存在的文件、指向不存在的文件')
print(f'  变量没设:{e["unset"][0]}: {e["unset"][1]}'); print(f'  silent=True:返回 {e["silent"]}(没加载,也不报错)'); print(f'  指向 prod.cfg:返回 {e["loaded"][0]},MODE = {e["loaded"][1]!r}'); print(f'  指向不存在的文件:{e["missingfile"][0]}: {e["missingfile"][1]}')
print()
print('== 五:.env 文件(python-dotenv 已安装):flask 命令会自动读,gunicorn 不会')
rc, out = subprocess.run([str(BIN / 'flask'), '--app', 'dotapp', 'show'], cwd=d, env=env(d), capture_output=True, text=True).returncode, subprocess.run([str(BIN / 'flask'), '--app', 'dotapp', 'show'], cwd=d, env=env(d), capture_output=True, text=True).stdout.strip()
print(f'  flask --app dotapp show → {out}'); R['dot_flask'] = out
with Server(d, ['gunicorn', '-w', '1', '-b', '127.0.0.1:{port}', 'dotapp:app']) as sv: body = sv.get('/')[2].decode()
print(f'  gunicorn 下视图里 os.environ.get("DOT_VAR") → {body}'); R['dot_gunicorn'] = body
save('f184', R)
