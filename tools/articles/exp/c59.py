import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c59')
img('alpine:3.20')
purge()
def comp(proj, d, *args, env=None, timeout=180):
    e = dict(os.environ); e.update(env or {}); e.pop('COMPOSE_PROFILES', None) if env is None else None
    r = subprocess.run(['docker', 'compose', '-p', proj, '-f', str(d / 'compose.yaml'), *args], capture_output=True, text=True, timeout=timeout, env=e)
    return r.returncode, tidy(r.stdout + r.stderr)
def running(proj):
    return sorted(n.replace(proj + '-', '').replace('-1', '') for n in out('ps', '--filter', f'name={proj}', '--format', '{{.Names}}').split())
Y = '''services:
  app:
    image: alpine:3.20
    labels: {bwlab: "1"}
    command: sleep 120
  debug:
    image: alpine:3.20
    labels: {bwlab: "1"}
    profiles: [debug]
    command: sleep 120
  tools:
    image: alpine:3.20
    labels: {bwlab: "1"}
    profiles: [tools, debug]
    command: sleep 120
'''
d = ctx('c59', {'compose.yaml': Y})
P = 'bwlab-c59'
print('== 一:没有 profile 的服务总是启动,有 profile 的默认不启动(Docker Compose v5.5.1)')
print('  docker compose config --services:' + comp(P, d, 'config', '--services')[1].replace('\n', ' '))
print('  docker compose --profile debug config --services:' + comp(P, d, '--profile', 'debug', 'config', '--services')[1].replace('\n', ' '))
rc, o = comp(P, d, 'up', '-d'); print(f'  docker compose up -d 之后在运行的服务:{running(P)}')
comp(P, d, '--profile', '*', 'down', '-v', '-t', '1')
rc, o = comp(P, d, '--profile', 'tools', 'up', '-d'); print(f'  --profile tools up -d:{running(P)}')
comp(P, d, '--profile', '*', 'down', '-v', '-t', '1')
rc, o = comp(P, d, '--profile', 'debug', 'up', '-d'); print(f'  --profile debug up -d:{running(P)}(tools 同时属于 tools 和 debug 两个 profile)')
comp(P, d, '--profile', '*', 'down', '-v', '-t', '1')
rc, o = comp(P, d, 'up', '-d', env={'COMPOSE_PROFILES': 'tools'}); print(f'  环境变量 COMPOSE_PROFILES=tools,up -d:{running(P)}')
comp(P, d, '--profile', '*', 'down', '-v', '-t', '1')
print('== 二:直接点名一个带 profile 的服务')
rc, o = comp(P, d, 'up', '-d', 'debug'); print(f'  docker compose up -d debug(没有 --profile):退出码 {rc};在运行的服务:{running(P)}')
comp(P, d, '--profile', '*', 'down', '-v', '-t', '1')
rc, o = comp(P, d, 'run', '--rm', 'tools', 'echo', 'hello-from-tools')
print(f'  run 之后留下的容器:{running(P)}'); print(f'  docker compose run --rm tools echo …(没有 --profile):退出码 {rc};输出:{next((l.strip() for l in o.splitlines() if "hello" in l and "Container" not in l), o.strip()[-60:])}')
print('== 三:没有 profile 的服务依赖一个带 profile 的服务')
Y2 = Y.replace('  app:\n    image: alpine:3.20\n    labels: {bwlab: "1"}\n', '  app:\n    image: alpine:3.20\n    labels: {bwlab: "1"}\n    depends_on: [debug]\n')
d2 = ctx('c59b', {'compose.yaml': Y2})
rc, o = comp(P, d2, 'up', '-d'); print(f'  app depends_on debug,不加 profile:退出码 {rc};输出:{o.strip().splitlines()[-1][:150] if o.strip() else "(无)"};在运行的服务:{running(P)}')
comp(P, d2, '--profile', '*', 'down', '-v', '-t', '1')
rc, o = comp(P, d2, '--profile', 'debug', 'up', '-d'); print(f'  加 --profile debug:退出码 {rc};在运行的服务:{running(P)}')
comp(P, d2, '--profile', '*', 'down', '-v', '-t', '1')
print('== 四:通配所有 profile 与 down 的行为')
rc, o = comp(P, d, '--profile', '*', 'up', '-d'); print(f'  --profile "*" up -d:{running(P)}')
rc, o = comp(P, d, 'down', '-t', '1'); print(f'  不带 profile 的 docker compose down 之后剩下的:{running(P)}')
comp(P, d, '--profile', '*', 'down', '-v', '-t', '1')
print(f'  --profile "*" down 之后:{running(P)}')
purge()
