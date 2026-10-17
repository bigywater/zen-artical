import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f68'); R = {}
APP = '''
import os
from flask import Flask
app = Flask(__name__)
app.config.from_prefixed_env()
@app.get("/cfg")
def cfg():
    return {"DEBUG": app.config["DEBUG"], "GREETING": app.config.get("GREETING"), "MODE": os.environ.get("MODE"), "FLASK_DEBUG": os.environ.get("FLASK_DEBUG"), "SECRET": os.environ.get("SECRET")}
'''
d = mkapp('f68', {'app.py': APP, '.flaskenv': 'FLASK_APP=app\nFLASK_RUN_PORT=0\nMODE=from-flaskenv\n', '.env': 'GREETING=hello-from-dotenv\nMODE=from-dotenv\nSECRET=s3cret\nFLASK_GREETING=prefixed-from-dotenv\n'})
print('== 一:环境变量都是字符串——用 os.environ 读布尔与数字时的陷阱')
os.environ.update(T_FALSE='false', T_ZERO='0', T_EMPTY='', T_NUM='8080')
print('  bool(os.environ["T_FALSE"]) =', bool(os.environ['T_FALSE']), '| bool("0") =', bool(os.environ['T_ZERO']), '| bool("") =', bool(os.environ['T_EMPTY']), '| os.environ["T_NUM"] + 1 →', end=' ')
try: os.environ['T_NUM'] + 1
except TypeError as e: print('TypeError:', e)
R['bool'] = [bool(os.environ['T_FALSE']), bool(os.environ['T_ZERO']), bool(os.environ['T_EMPTY'])]
def env_bool(name, default=False): v = os.environ.get(name); return default if v is None else v.strip().lower() in ('1', 'true', 'yes', 'on')
print('  自己写的 env_bool:', {k: env_bool(k) for k in ('T_FALSE', 'T_ZERO', 'T_EMPTY', 'T_NUM', 'T_MISSING')}); R['env_bool'] = {k: env_bool(k) for k in ('T_FALSE', 'T_ZERO', 'T_EMPTY', 'T_NUM', 'T_MISSING')}
print('  os.environ["不存在"] →', end=' ')
try: os.environ['NOPE_X']
except KeyError as e: print('KeyError', e); R['keyerror'] = str(e)
print('  os.environ.get("不存在") =', os.environ.get('NOPE_X'), '| .get(key, 默认) =', os.environ.get('NOPE_X', '默认'))
print()
print('== 二:flask 命令读 FLASK_* 环境变量:FLASK_APP、FLASK_DEBUG、FLASK_RUN_PORT / FLASK_RUN_HOST')
port = free_port()
with Server(d, ['flask', '--app', 'app', 'run', '--port', str(port)], port=port, FLASK_DEBUG='1', FLASK_GREETING='from-env-var') as s:
    time.sleep(0.4); st, h, b, dt = s.get('/cfg'); print('  FLASK_DEBUG=1 + FLASK_GREETING=from-env-var 下 /cfg:', json.loads(b) if (json := __import__('json')) else b); R['env1'] = json.loads(b)
    print('  启动日志里:', [l.strip() for l in s.logtext().split('\n') if 'Debug mode' in l])
print()
print('== 三:.env 与 .flaskenv:没装 python-dotenv 时 flask 命令的提示;装了之后自动加载')
r = subprocess.run([str(BIN / 'pip'), 'show', 'python-dotenv'], capture_output=True, text=True); has = r.returncode == 0; print('  python-dotenv 已安装:', has); R['has_dotenv'] = has
if has:
    subprocess.run([str(BIN / 'pip'), 'uninstall', '-y', 'python-dotenv'], capture_output=True, text=True)
r = subprocess.run([str(BIN / 'flask'), '--app', 'app', 'routes'], cwd=d, env=env(d), capture_output=True, text=True); print('  卸载 python-dotenv 后运行 flask routes:'); L = [l for l in (r.stdout + r.stderr).split('\n') if 'dotenv' in l.lower() or 'Tip' in l]; print('   ', L); R['tip'] = L
env_ = dict(os.environ); env_['HTTPS_PROXY'] = 'http://127.0.0.1:1087'; r = subprocess.run([str(BIN / 'pip'), 'install', '-q', 'python-dotenv'], capture_output=True, text=True, env=env_); print('  安装 python-dotenv:', 'ok' if r.returncode == 0 else r.stderr[-100:])
print()
print('== 四:装了 python-dotenv 之后:flask 命令自动读取 .flaskenv 与 .env;真实环境变量优先于文件')
port = free_port()
with Server(d, ['flask', 'run', '--port', str(port)], port=port) as s:
    time.sleep(0.4); st, h, b, dt = s.get('/cfg'); R['env2'] = json.loads(b); print('  没有 --app(来自 .flaskenv 的 FLASK_APP=app),没设任何环境变量:', R['env2'])
port = free_port()
with Server(d, ['flask', 'run', '--port', str(port)], port=port, MODE='from-real-env', GREETING='real-greeting', FLASK_GREETING='real-prefixed') as s:
    time.sleep(0.4); st, h, b, dt = s.get('/cfg'); R['env3'] = json.loads(b); print('  同名真实环境变量(MODE、FLASK_GREETING)已设置:', R['env3'])
print('  (.flaskenv 里写的是 MODE=from-flaskenv,.env 里写的是 MODE=from-dotenv;第一次输出里 MODE = ' + R['env2']['MODE'] + ':同名时 .env 的值生效)')
print()
print('== 五:gunicorn 不会自动读 .env(只有 flask 命令会):除非应用自己 load_dotenv()')
port = free_port()
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', 'app:app'], port=port) as s:
    st, h, b, dt = s.get('/cfg'); R['gun'] = json.loads(b); print('  gunicorn app:app 下 /cfg:', R['gun'])
d2 = mkapp('f68b', {'app.py': 'from dotenv import load_dotenv\nload_dotenv()\n' + APP, '.env': '' + (d / '.env').read_text()})
port = free_port()
with Server(d2, ['gunicorn', '-b', '127.0.0.1:{port}', 'app:app'], port=port) as s:
    st, h, b, dt = s.get('/cfg'); R['gun2'] = json.loads(b); print('  应用里 load_dotenv() 之后 gunicorn 下 /cfg:', R['gun2'])
print()
print('== 六:.env 不该提交进版本库;用 .env.example 记录需要哪些变量')
print('  常见做法:.gitignore 里写 .env;仓库里放 .env.example(只有变量名与示例值)——这一节没有实验,只是做法说明')
save('f68', R)
