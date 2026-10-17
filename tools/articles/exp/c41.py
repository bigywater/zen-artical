import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c41')
img('python:3.12-alpine')
purge()
d = ctx('c41', {'Dockerfile': 'FROM python:3.12-alpine\nRUN cp "$(readlink -f /usr/local/bin/python3)" /pysuid && chmod 4755 /pysuid && ls -l /pysuid | cut -c1-40 && cp "$(readlink -f /usr/local/bin/python3)" /pynormal\n'})
rc, o = build(d, 'bwlab-c41', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
CODE = 'import os; print("uid=%d euid=%d gid=%d" % (os.getuid(), os.geteuid(), os.getgid()), [l.strip() for l in open("/proc/self/status") if l.startswith(("NoNewPrivs", "CapEff"))])'
print('== 一:setuid root 的程序,普通用户(uid 1000)运行(Docker Engine 29.8.2)')
print('  /pysuid 的权限:' + dk('run', '--rm', *LAB, 'bwlab-c41', 'ls', '-l', '/pysuid')[1].strip()[:60])
for label, opts in (('默认', []), ('--security-opt no-new-privileges', ['--security-opt', 'no-new-privileges']), ('--security-opt no-new-privileges=false', ['--security-opt', 'no-new-privileges=false'])):
    rc, o = dk('run', '--rm', *LAB, '--user', '1000', *opts, 'bwlab-c41', '/pysuid', '-c', CODE)
    rc2, o2 = dk('run', '--rm', *LAB, '--user', '1000', *opts, 'bwlab-c41', '/pynormal', '-c', CODE)
    print(f'  {label}:\n    setuid 的 /pysuid → {o.strip()[:140]}\n    普通的 /pynormal → {o2.strip()[:140]}')
print('== 二:no-new-privileges 对已经是 root 的进程、对 docker exec 进来的进程')
rc, o = dk('run', '--rm', *LAB, '--security-opt', 'no-new-privileges', 'bwlab-c41', 'python', '-c', CODE); print(f'  root 用户 + no-new-privileges:{o.strip()[:150]}')
n = 'bwlab-c41-ex'
dk('run', '-d', '--name', n, *LAB, '--security-opt', 'no-new-privileges', '--user', '1000', 'bwlab-c41', 'sleep', '60')
rc, o = dk('exec', n, '/pysuid', '-c', CODE); print(f'  docker exec 进入 no-new-privileges 的容器,运行 /pysuid:{o.strip()[:150]}')
rc, o = dk('exec', '--user', '0', n, 'python', '-c', CODE); print(f'  docker exec --user 0 进去:{o.strip()[:150]}')
print(f'  HostConfig.SecurityOpt = {out("inspect", "--format", "{{.HostConfig.SecurityOpt}}", n)}')
dk('rm', '-f', n)
purge()
