import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c60')
purge()
BASE = '''services:
  web:
    image: alpine:3.20
    command: sleep 100
    environment:
      MODE: base
      KEEP: from-base
    ports:
      - "9901:80"
    volumes:
      - /srv/a:/data/a
      - /srv/b:/data/b
    labels:
      tier: base
      owner: team-a
    depends_on: [db]
  db:
    image: alpine:3.20
    command: sleep 100
'''
OVR = '''services:
  web:
    image: alpine:3.19
    command: sleep 200
    environment:
      MODE: override
      EXTRA: only-in-override
    ports:
      - "9902:80"
    volumes:
      - /srv/c:/data/b
    labels:
      tier: override
'''
def cfg(d, *files, extra=()):
    args = ['docker', 'compose', '-p', 'bwlab-c60']
    for f in files: args += ['-f', str(d / f)]
    r = subprocess.run(args + list(extra) + ['config', '--format', 'json'], capture_output=True, text=True, cwd=str(d))
    if r.returncode: return None, tidy(r.stderr)
    return json.loads(r.stdout), ''
def show(j, svc='web'):
    w = j['services'][svc]
    return (f"image={w.get('image')}  command={w.get('command')}  environment={w.get('environment')}  ports={[ (p.get('published'), p.get('target')) for p in w.get('ports', [])]}  "
            f"volumes={[(v['source'], v['target']) for v in w.get('volumes', [])]}  labels={ {k: v for k, v in w.get('labels', {}).items() if k in ('tier', 'owner')} }  depends_on={list(w.get('depends_on', {}))}")
d = ctx('c60', {'compose.yaml': BASE, 'compose.override.yaml': OVR, 'extra.yaml': OVR.replace('alpine:3.19', 'alpine:3.18')})
print('== 一:compose.yaml 与 compose.override.yaml 自动合并(Docker Compose v5.5.1,docker compose config 的结果)')
j, e = cfg(d, 'compose.yaml'); print('  只有 compose.yaml(-f 显式指定,不自动加 override):' + show(j))
r = subprocess.run(['docker', 'compose', '-p', 'bwlab-c60', 'config', '--format', 'json'], capture_output=True, text=True, cwd=str(d))
j = json.loads(r.stdout); print('  不带 -f(自动读取 compose.yaml + compose.override.yaml):' + show(j))
print('== 二:各类字段的合并规则')
print('  image / command 这类单值:override 覆盖 base(image 从 alpine:3.20 变成 alpine:3.19,command 从 sleep 100 变成 sleep 200)')
print('  environment(映射):按键合并,MODE 被覆盖、KEEP 保留、EXTRA 新增')
print('  ports(列表):' + str([(p.get('published'), p.get('target')) for p in j['services']['web']['ports']]) + '(两个都在,是追加)')
print('  volumes(列表):' + str([(v['source'], v['target']) for v in j['services']['web']['volumes']]) + '(target 相同的 /data/b 被换成 override 的源,/data/a 保留)')
print('  labels(映射):按键合并:' + str({k: v for k, v in j['services']['web']['labels'].items() if k in ('tier', 'owner')}))
print('== 三:-f 的顺序决定谁覆盖谁')
j1, e = cfg(d, 'compose.yaml', 'compose.override.yaml', 'extra.yaml'); print('  -f compose.yaml -f compose.override.yaml -f extra.yaml → image = ' + j1['services']['web']['image'])
j2, e = cfg(d, 'compose.yaml', 'extra.yaml', 'compose.override.yaml'); print('  -f compose.yaml -f extra.yaml -f compose.override.yaml → image = ' + j2['services']['web']['image'])
print('== 四:!reset 和 !override 清除或整体替换')
RST = '''services:
  web:
    ports: !reset []
    volumes: !override
      - /srv/z:/data/z
    labels: !reset null
    depends_on: !reset []
'''
d2 = ctx('c60b', {'compose.yaml': BASE, 'compose.override.yaml': RST})
j3, e = cfg(d2, 'compose.yaml', 'compose.override.yaml')
print('  ' + (show(j3) if j3 else '报错:' + e[:150]))
purge()
