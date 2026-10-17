import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c62')
img('alpine:3.20')
purge()
P = 'bwlab-c62'
def comp(d, *args, timeout=180):
    r = subprocess.run(['docker', 'compose', '-p', P, '-f', str(d / 'compose.yaml'), *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, tidy(r.stdout + r.stderr)
def ex(svc, *cmd): return dk('exec', f'{P}-{svc}-1', *cmd)
def can(frm, target):
    rc, o = ex(frm, 'ping', '-c', '1', '-W', '2', target); return '通' if rc == 0 else f'不通({o.strip().splitlines()[0][:50] if o.strip() else "超时"})'
print('== 一:不写 networks 时(Docker Compose v5.5.1)')
Y1 = '''services:
  web:
    image: alpine:3.20
    labels: {bwlab: "1"}
    command: sleep 300
  api:
    image: alpine:3.20
    labels: {bwlab: "1"}
    command: sleep 300
'''
d = ctx('c62a', {'compose.yaml': Y1})
comp(d, 'up', '-d')
print('  项目的网络:' + out('network', 'ls', '--filter', f'name={P}', '--format', '{{.Name}}/{{.Driver}}'))
print('  web 的 Networks / 别名:' + out('inspect', '--format', '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} aliases={{$v.Aliases}}{{end}}', f'{P}-web-1'))
print(f'  web ping api(服务名):{can("web", "api")};ping bwlab-c62-api-1(容器名):{can("web", f"{P}-api-1")}')
comp(d, 'down', '-v', '-t', '1')
print('  down 之后网络还在吗?' + (out('network', 'ls', '--filter', f'name={P}', '--format', '{{.Name}}') or '已删除'))
print('== 二:前后端分网:proxy → app → db')
Y2 = '''services:
  proxy:
    image: alpine:3.20
    labels: {bwlab: "1"}
    command: sleep 300
    networks: [front]
  app:
    image: alpine:3.20
    labels: {bwlab: "1"}
    command: sleep 300
    networks: [front, back]
  db:
    image: alpine:3.20
    labels: {bwlab: "1"}
    command: sleep 300
    networks: [back]
networks:
  front:
  back:
'''
d = ctx('c62b', {'compose.yaml': Y2})
comp(d, 'up', '-d')
print('  proxy ping app:' + can('proxy', 'app') + ';proxy ping db:' + can('proxy', 'db') + ';app ping db:' + can('app', 'db') + ';db ping proxy:' + can('db', 'proxy'))
print('  项目的网络名:' + out('network', 'ls', '--filter', f'name={P}', '--format', '{{.Name}}').replace('\n', ' '))
comp(d, 'down', '-v', '-t', '1')
print('== 三:internal 网络不能出网')
Y3 = '''services:
  inside:
    image: alpine:3.20
    labels: {bwlab: "1"}
    command: sleep 300
    networks: [priv]
  outside:
    image: alpine:3.20
    labels: {bwlab: "1"}
    command: sleep 300
    networks: [pub]
networks:
  priv:
    internal: true
  pub:
'''
d = ctx('c62c', {'compose.yaml': Y3})
comp(d, 'up', '-d')
print('  网络 priv 的 Internal = ' + out('network', 'inspect', f'{P}_priv', '--format', '{{.Internal}}') + ';网络 pub 的 Internal = ' + out('network', 'inspect', f'{P}_pub', '--format', '{{.Internal}}'))
for svc in ('inside', 'outside'):
    t0 = time.time(); rc, o = ex(svc, 'ping', '-c', '1', '-W', '3', '1.1.1.1'); dt = time.time() - t0
    rc2, o2 = ex(svc, 'nslookup', 'github.com')
    print(f'  {svc} ping 1.1.1.1:{"通" if rc == 0 else "不通"}({dt:.1f} 秒);{o.strip().splitlines()[0][:60] if rc else ""};nslookup github.com:' + ('成功' if rc2 == 0 else '失败'))
print('  路由:inside → ' + ex('inside', 'ip', 'route')[1].strip().replace('\n', ' ; ') + ' | outside → ' + ex('outside', 'ip', 'route')[1].strip().replace('\n', ' ; ')[:80])
comp(d, 'down', '-v', '-t', '1')
print('== 四:别名与固定 IP')
Y4 = '''services:
  a:
    image: alpine:3.20
    labels: {bwlab: "1"}
    command: sleep 300
    networks:
      n:
        aliases: [alpha, first]
        ipv4_address: 10.62.0.10
  b:
    image: alpine:3.20
    labels: {bwlab: "1"}
    command: sleep 300
    networks: [n]
networks:
  n:
    ipam:
      config:
        - subnet: 10.62.0.0/24
'''
d = ctx('c62d', {'compose.yaml': Y4})
rc, o = comp(d, 'up', '-d'); print(f'  docker compose up -d:退出码 {rc}')
print('  a 的地址:' + out('inspect', '--format', '{{range $k,$v := .NetworkSettings.Networks}}{{$v.IPAddress}} aliases={{$v.Aliases}}{{end}}', f'{P}-a-1'))
print('  b 解析 alpha / first / a:' + ' ; '.join(f'{n}→' + (' '.join(l.split()[-1] for l in ex('b', 'nslookup', n)[1].splitlines() if l.startswith('Address') and '#' not in l)) for n in ('alpha', 'first', 'a')))
print('  网络子网:' + out('network', 'inspect', f'{P}_n', '--format', '{{range .IPAM.Config}}{{.Subnet}}{{end}}'))
comp(d, 'down', '-v', '-t', '1')
purge()
