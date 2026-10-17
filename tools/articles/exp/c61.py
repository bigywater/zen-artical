import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c61')
img('alpine:3.20')
purge()
def comp(d, *args, env=None, timeout=120):
    e = {k: v for k, v in os.environ.items() if not k.startswith('T_') and k != 'COMPOSE_ENV_FILES'}; e.update(env or {})
    r = subprocess.run(['docker', 'compose', '-p', 'bwlab-c61', *args], capture_output=True, text=True, timeout=timeout, env=e, cwd=str(d))
    return r.returncode, tidy(r.stdout + r.stderr)
def runenv(d, *extra, env=None):
    rc, o = comp(d, 'run', '--rm', '-T', *extra, 'web', 'sh', '-c', 'env | grep ^T_ | sort', env=env)
    return ' '.join(l.strip() for l in o.splitlines() if l.startswith('T_'))
Y = '''services:
  web:
    image: alpine:3.20
    labels: {bwlab: "1"}
    env_file:
      - service.env
    environment:
      T_Y: environment-${T_I}
      T_Z: environment
      T_PASS:
'''
d = ctx('c61', {'compose.yaml': Y, '.env': 'T_I=dotenv\nT_ONLY_DOTENV=yes\n', 'service.env': 'T_X=from-envfile\nT_Y=from-envfile\nT_I=envfile-I\n', 'other.env': 'T_I=other-env-file\n'})
print('== 一:容器里的环境变量来自哪些来源(Docker Compose v5.5.1,docker compose run … env 的结果)')
print('  compose.yaml 里的 environment 有 T_Y(引用 ${T_I})、T_Z、T_PASS(不写值);env_file 有 T_X、T_Y、T_I;.env 有 T_I=dotenv、T_ONLY_DOTENV=yes')
print('  默认:' + runenv(d))
print('== 二:谁的优先级高')
print('  同时在 env_file 和 environment 里的 T_Y:取了 environment 的(上面的 T_Y 值);T_I 在 env_file 和 .env 里,容器里的 T_I 取自 env_file——.env 默认只用于 compose.yaml 里的插值,不进容器')
print('  .env 里独有的 T_ONLY_DOTENV 在容器里吗?' + ('在' if 'T_ONLY_DOTENV' in runenv(d) else '不在'))
print('  shell 里设 T_I=shell 后(插值优先级:shell 高于 .env):' + runenv(d, env={'T_I': 'shell'}))
print('  T_PASS 不写值,shell 里设 T_PASS=from-shell:' + runenv(d, env={'T_PASS': 'from-shell'}))
print('  docker compose run -e T_Z=cli -e T_X=cli:' + runenv(d, '-e', 'T_Z=cli', '-e', 'T_X=cli'))
print('== 三:--env-file 与 .env')
rc, o = comp(d, '--env-file', 'other.env', 'run', '--rm', '-T', 'web', 'sh', '-c', 'env | grep ^T_ | sort'); print('  --env-file other.env(T_I=other-env-file):' + ' '.join(l.strip() for l in o.splitlines() if l.startswith('T_')))
rc, o = comp(d, 'config', '--format', 'json'); j = json.loads(o); print('  docker compose config 展开后的 environment:' + str(j['services']['web']['environment']))
rc, o = comp(d, '--env-file', 'other.env', 'config', '--format', 'json'); j = json.loads(o); print('  --env-file other.env 之后展开的 environment:' + str(j['services']['web']['environment']))
print('== 四:缺失变量的写法')
Y2 = 'services:\n  web:\n    image: alpine:3.20\n    labels: {bwlab: "1"}\n    command: echo ${T_MISSING:-default-value}-${T_EMPTY-unset}\n'
d2 = ctx('c61b', {'compose.yaml': Y2})
rc, o = comp(d2, 'config', '--format', 'json'); print('  ${T_MISSING:-default-value}-${T_EMPTY-unset} 在 T_MISSING 未设、T_EMPTY 未设时展开成:' + str(json.loads(o)['services']['web']['command']))
rc, o = comp(d2, 'config', '--format', 'json', env={'T_EMPTY': ''}); print('  T_EMPTY 设成空串时(${T_EMPTY-unset} 只在未设置时用默认值):' + str(json.loads(o)['services']['web']['command']))
Y3 = 'services:\n  web:\n    image: alpine:3.20\n    command: echo ${T_REQUIRED:?必须设置 T_REQUIRED}\n'
d3 = ctx('c61c', {'compose.yaml': Y3})
rc, o = comp(d3, 'config'); print(f'  ${{T_REQUIRED:?…}} 未设置时:退出码 {rc};{o.strip()[:100]}')
purge()
