import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f66'); R = {}
import json
from flask import Flask
d = mkapp('f66', {'defaults_cfg.py': 'ENV_NAME = "from-defaults-file"\nPAGE_SIZE = 10\nFEATURES = ["a"]\nlower_case = "ignored"\n', 'prod.py': 'ENV_NAME = "from-prod-file"\nPAGE_SIZE = 50\n', 'instance/local.py': 'PAGE_SIZE = 99\nSECRET_KEY = "instance-secret"\n', 'cfg.json': json.dumps({'ENV_NAME': 'from-json', 'PAGE_SIZE': 7})})
sys.path.insert(0, str(d)); os.chdir(d)
print('== 一:Flask 自带的默认值(没有任何配置时)')
a = Flask('c', root_path=str(d)); print('  默认键数', len(a.config), '| DEBUG =', a.config['DEBUG'], '| SECRET_KEY =', a.config['SECRET_KEY'], '| 自定义键 PAGE_SIZE 是否存在:', 'PAGE_SIZE' in a.config); R['defaults'] = [len(a.config), a.config['DEBUG'], a.config['SECRET_KEY'], 'PAGE_SIZE' in a.config]
print()
print('== 二:后加载的覆盖先加载的:依次加载并观察 PAGE_SIZE / ENV_NAME(同一个键被多次设置)')
a = Flask('c2', root_path=str(d)); steps_ = []
def snap(label): steps_.append((label, a.config.get('PAGE_SIZE'), a.config.get('ENV_NAME'))); print(f'  {label:<44} PAGE_SIZE={a.config.get("PAGE_SIZE")!s:<5} ENV_NAME={a.config.get("ENV_NAME")}')
snap('(开始)')
a.config.from_object('defaults_cfg'); snap('from_object("defaults_cfg")')
a.config.from_pyfile(str(d / 'prod.py')); snap('from_pyfile("prod.py")')
a.config.from_file(str(d / 'cfg.json'), load=json.load); snap('from_file("cfg.json", load=json.load)')
os.environ['FLASK_PAGE_SIZE'] = '200'; os.environ['FLASK_ENV_NAME'] = '"from-env"'; a.config.from_prefixed_env(); snap('from_prefixed_env()(FLASK_PAGE_SIZE=200)')
a.config.update(PAGE_SIZE=1); snap('config.update(PAGE_SIZE=1)')
a.config['PAGE_SIZE'] = 2; snap('config["PAGE_SIZE"] = 2')
R['steps'] = steps_
print('  结论:没有「优先级表」,就是代码执行的先后顺序;最后一次写入的赢。')
print()
print('== 三:只有大写的键会被加载(from_object / from_pyfile / from_file);小写键被忽略')
a = Flask('c3', root_path=str(d)); a.config.from_object('defaults_cfg'); print('  lower_case 在 config 里吗:', 'lower_case' in a.config, '| 加载进来的自定义键:', sorted(k for k in a.config if k in ('ENV_NAME', 'PAGE_SIZE', 'FEATURES', 'lower_case'))); R['upper'] = ['lower_case' in a.config]
print()
print('== 四:instance 目录:instance_relative_config=True 时 from_pyfile 的相对路径相对于 instance_path(通常放不进版本库的本地配置)')
a = Flask('c4', root_path=str(d), instance_path=str(d / 'instance'), instance_relative_config=True)
print('  instance_path =', a.instance_path.replace(str(d), '<项目>'), '| config.root_path =', a.config.root_path.replace(str(d), '<项目>')); R['paths'] = [a.instance_path.replace(str(d), '<项目>'), a.config.root_path.replace(str(d), '<项目>')]
a.config.from_pyfile('local.py'); print('  from_pyfile("local.py") 之后 PAGE_SIZE =', a.config['PAGE_SIZE'], '| SECRET_KEY =', a.config['SECRET_KEY']); R['instance'] = [a.config['PAGE_SIZE'], a.config['SECRET_KEY']]
a2 = Flask('c4b', root_path=str(d)); print('  不开 instance_relative_config 时 config.root_path =', a2.config.root_path.replace(str(d), '<项目>'), '(相对路径相对应用的 root_path)')
print()
print('== 五:from_prefixed_env 的类型转换:值先按 JSON 解析,失败就保持字符串;双下划线表示嵌套字典')
for k, v in (('FLASK_N', '5'), ('FLASK_F', '1.5'), ('FLASK_B1', 'true'), ('FLASK_B2', 'false'), ('FLASK_NONE', 'null'), ('FLASK_LIST', '[1, 2, 3]'), ('FLASK_TXT', 'hello'), ('FLASK_QUOTED', '"hello"'), ('FLASK_EMPTY', ''), ('FLASK_DB__HOST', 'localhost'), ('FLASK_DB__PORT', '5432'), ('OTHER_X', '1')): os.environ[k] = v
a = Flask('c5', root_path=str(d)); a.config.from_prefixed_env()
R['prefixed'] = {}
for k in ('N', 'F', 'B1', 'B2', 'NONE', 'LIST', 'TXT', 'QUOTED', 'EMPTY', 'DB', 'X'): v = a.config.get(k, '(不存在)'); R['prefixed'][k] = repr(v); print(f'  FLASK_{k:<8} → config["{k}"] = {v!r}  ({type(v).__name__})')
print('  自定义前缀 from_prefixed_env("MYAPP"):', end=' '); os.environ['MYAPP_Z'] = '9'; a.config.from_prefixed_env('MYAPP'); print(a.config.get('Z'))
print()
print('== 六:get_namespace:按前缀取出一组配置')
a.config.update(SMTP_HOST='h', SMTP_PORT=25, SMTP_USE_TLS=True, DB_URL='x'); print('  get_namespace("SMTP_") →', a.config.get_namespace('SMTP_')); print('  get_namespace("SMTP_", lowercase=False) →', a.config.get_namespace('SMTP_', lowercase=False)); R['ns'] = a.config.get_namespace('SMTP_')
save('f66', R)
