import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c5')
img('alpine:3.20')
purge()
E_SH = '#!/bin/sh\necho "入口脚本收到 $# 个参数:$*"\n'
CASES = [
    ('1', 'ENTRYPOINT ["/e.sh"]\nCMD ["a", "b"]', [], 'exec 形式 ENTRYPOINT + exec 形式 CMD,不加运行参数'),
    ('2', 'ENTRYPOINT ["/e.sh"]\nCMD ["a", "b"]', ['x'], '同上,docker run 后面加参数 x(替换 CMD)'),
    ('3', 'ENTRYPOINT ["/e.sh"]\nCMD ["a", "b"]', ['--entrypoint', 'echo', '@IMG', 'new'], '同上,用 --entrypoint 覆盖入口'),
    ('4', 'ENTRYPOINT /e.sh\nCMD ["a", "b"]', [], 'shell 形式 ENTRYPOINT + exec 形式 CMD(CMD 被忽略)'),
    ('5', 'ENTRYPOINT ["/e.sh"]\nCMD echo hello', [], 'exec 形式 ENTRYPOINT + shell 形式 CMD'),
    ('6', 'CMD ["echo", "from cmd"]', [], '只有 exec 形式 CMD'),
    ('7', 'CMD ["echo", "from cmd"]', ['ls', '/etc/alpine-release'], '同上,docker run 后面给了新命令(整个替换)'),
    ('8', 'CMD echo from shell cmd', [], '只有 shell 形式 CMD'),
    ('9', 'ENTRYPOINT ["/e.sh", "fixed"]\nCMD ["default"]', ['over'], 'ENTRYPOINT 自带参数 + CMD,docker run 再给 over'),
]
print('== 一:ENTRYPOINT 与 CMD 的组合,最终执行的命令(docker create + docker inspect 的 Path 和 Args;Docker Engine 29.8.2)')
rows = []
for k, lines, runargs, label in CASES:
    tag = f'bwlab-c5-{k}'
    d = ctx(f'c5_{k}', {'e.sh': E_SH, 'Dockerfile': 'FROM alpine:3.20\nCOPY --chmod=755 e.sh /e.sh\n' + lines + '\n'})
    rc, o = build(d, tag)
    ra = [tag if a == '@IMG' else a for a in runargs]
    if '--entrypoint' in ra:
        i = ra.index(tag); cid = out('create', *LAB, *ra)
    else:
        cid = out('create', *LAB, tag, *ra)
    path_args = out('inspect', '--format', '{{.Path}}\t{{json .Args}}', cid)
    path, args = path_args.split('\t')
    rc2, o2 = dk('start', '-a', cid)
    cfg = out('inspect', '--format', '{{json .Config.Entrypoint}} {{json .Config.Cmd}}', tag)
    print(f'  [{k}] {label}')
    print(f'      Dockerfile:{lines.replace(chr(10), " ; ")}  运行参数:{" ".join(runargs) or "(无)"}'.replace('@IMG', 'IMG'))
    print(f'      镜像里存的 Entrypoint / Cmd = {cfg}')
    print(f'      容器实际执行:Path={path} Args={args}')
    print(f'      输出:{o2.strip()}')
print('== 二:容器里 PID 1 到底是谁(alpine 的 /bin/sh 是 busybox ash)')
for k, lines in (('a', 'ENTRYPOINT ["sleep", "300"]'), ('b', 'ENTRYPOINT sleep 300'), ('c', 'ENTRYPOINT sleep 300 && echo done')):
    tag = f'bwlab-c5-p{k}'
    d = ctx(f'c5_p{k}', {'Dockerfile': 'FROM alpine:3.20\n' + lines + '\n'})
    build(d, tag)
    cid = out('run', '-d', *LAB, tag)
    time.sleep(0.5)
    rc, o = dk('exec', cid, 'ps', '-o', 'pid,args')
    print(f'  [{lines}] ps 看到:' + ' | '.join(re.sub(r'\s+', ' ', l.strip()) for l in o.split('\n')[1:4]))
    subprocess.run(['docker', 'rm', '-f', cid], capture_output=True)
purge()
