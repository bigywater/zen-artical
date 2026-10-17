import sys, os, re, time, subprocess, json, tarfile, io, tempfile, gzip; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c8')
img('alpine:3.20')
purge()
SECRET = 'S3cr3t-' + str(int(time.time()))
def find_in_image(tag, needle):
    """docker save,在配置 JSON 和每一层(解压后)的所有文件内容里找 needle,返回命中位置列表"""
    tmp = tempfile.mkdtemp(); p = os.path.join(tmp, 'a.tar'); subprocess.run(['docker', 'save', '-o', p, tag], check=True)
    hits = []
    nb = needle.encode()
    with tarfile.open(p) as t:
        for m in t.getmembers():
            if not m.isfile(): continue
            data = t.extractfile(m).read()
            if nb in data: hits.append(f'{m.name[:30]}(原始 blob/配置)')
            # 尝试把它当成层 tar(gzip 或未压缩)
            try:
                with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as lt:
                    for x in lt.getmembers():
                        if x.isfile() and nb in lt.extractfile(x).read(): hits.append(f'层内文件 {x.name}')
            except Exception:
                pass
    shutil.rmtree(tmp, ignore_errors=True)
    return hits
print('== 一:三种把密钥交给构建的办法,密钥最后在不在镜像里(Docker Engine 29.8.2,BuildKit)')
# A: COPY 再删除
dA = ctx('c8a', {'Dockerfile': 'FROM alpine:3.20\nCOPY secret.txt /tmp/secret.txt\nRUN wc -c /tmp/secret.txt && rm /tmp/secret.txt\n', 'secret.txt': SECRET + '\n'})
rc, o = build(dA, 'bwlab-c8a')
print(f'  [A:COPY 进去用完再 rm] 退出码 {rc};在镜像里找到密钥的位置:{find_in_image("bwlab-c8a", SECRET) or "(没找到)"}')
# B: ARG
dB = ctx('c8b', {'Dockerfile': 'FROM alpine:3.20\nARG TOK\nRUN echo "长度 ${#TOK}"\n'})
rc, o = build(dB, 'bwlab-c8b', '--build-arg', f'TOK={SECRET}')
hist = out('history', '--no-trunc', '--format', '{{.CreatedBy}}', 'bwlab-c8b')
print(f'  [B:--build-arg] 退出码 {rc};在镜像里找到密钥的位置:{find_in_image("bwlab-c8b", SECRET) or "(没找到)"};docker history 里含密钥的行数 {sum(SECRET in l for l in hist.split(chr(10)))}')
# C: secret mount
dC = ctx('c8c', {'Dockerfile': f'FROM alpine:3.20\nRUN echo salt-{time.time()}\nRUN --mount=type=secret,id=tok wc -c /run/secrets/tok && echo "构建期读到了 $(wc -c < /run/secrets/tok) 字节"\n'})
sf = DT / 'c8_secret.txt'; sf.write_text(SECRET + '\n')
rc, o = build(dC, 'bwlab-c8c', '--secret', f'id=tok,src={sf}')
print(f'  [C:RUN --mount=type=secret] 退出码 {rc};构建输出里:' + ' | '.join(re.sub(r'^#\d+ [\d.]+ ', '', l.strip()) for l in o.split('\n') if '字节' in l and 'echo' not in l))
print(f'      在镜像里找到密钥的位置:{find_in_image("bwlab-c8c", SECRET) or "(没找到)"};docker history 里含密钥的行数 {sum(SECRET in l for l in out("history", "--no-trunc", "--format", "{{.CreatedBy}}", "bwlab-c8c").split(chr(10)))}')
rc, o = dk('run', '--rm', *LAB, 'bwlab-c8c', 'sh', '-c', 'ls -la /run/secrets 2>&1 | head -3')
print('      从镜像启动后 ls /run/secrets:' + o.strip().split('\n')[0])
print('== 二:把密钥环境变量交给构建(--secret id=tok,env=TOKVAR)')
dD = ctx('c8d', {'Dockerfile': 'FROM alpine:3.20\nRUN echo salt-' + str(time.time()) + '\nRUN --mount=type=secret,id=tok,env=TOKVAR sh -c \'echo "环境变量 TOKVAR 长度 ${#TOKVAR}"\'\n'})
rc, o = build(dD, 'bwlab-c8d', '--secret', 'id=tok,env=MYTOK', env={'MYTOK': SECRET})
print(f'  退出码 {rc};' + ' | '.join(re.sub(r'^#\d+ [\d.]+ ', '', l.strip()) for l in o.split('\n') if '长度' in l and 'echo' not in l) + f';镜像里的密钥位置:{find_in_image("bwlab-c8d", SECRET) or "(没找到)"}')
print('== 三:密钥的内容不参与缓存键(换一个密钥再构建,这一步还是 CACHED)')
dE = ctx('c8e', {'Dockerfile': f'FROM alpine:3.20\nRUN echo salt-{time.time()}\nRUN --mount=type=secret,id=tok wc -c /run/secrets/tok\n'})
sf.write_text('v1-secret\n'); build(dE, 'bwlab-c8e', '--secret', f'id=tok,src={sf}')
sf.write_text('v2-completely-different-and-longer\n'); rc, o = build(dE, 'bwlab-c8e', '--secret', f'id=tok,src={sf}')
m = re.search(r'#(\d+) \[(?:stage-0 )?3/3\] RUN --mount', o)
print(f'  换了密钥内容(10 字节 → 35 字节)再构建:第 3 步 {"CACHED(命中缓存)" if m and re.search(rf"#{m.group(1)} CACHED", o) else "重新执行"}')
print('== 四:Dockerfile 要求了密钥但构建时没给')
dF = ctx('c8f', {'Dockerfile': 'FROM alpine:3.20\nRUN --mount=type=secret,id=nope,required=true cat /run/secrets/nope\n'})
rc, o = build(dF, 'bwlab-c8f')
print(f'  退出码 {rc};' + ' | '.join(l.strip() for l in o.split('\n') if 'ERROR' in l)[:240])
dG = ctx('c8g', {'Dockerfile': f'FROM alpine:3.20\nRUN echo salt-{time.time()}\nRUN --mount=type=secret,id=nope ls -la /run/secrets/nope 2>&1; echo "退出码 $?"\n'})
rc, o = build(dG, 'bwlab-c8g')
print(f'  没写 required(默认可选):构建退出码 {rc};' + ' | '.join(re.sub(r'^#\d+ [\d.]+ ', '', l.strip()) for l in o.split('\n') if '退出码' in l and 'echo' not in l or 'No such' in l)[:200])
print('== 五:自己犯的错——把密钥写进了镜像里的文件')
dH = ctx('c8h', {'Dockerfile': f'FROM alpine:3.20\nRUN echo salt-{time.time()}\nRUN --mount=type=secret,id=tok cp /run/secrets/tok /app.conf\n'})
sf.write_text(SECRET + '\n'); rc, o = build(dH, 'bwlab-c8h', '--secret', f'id=tok,src={sf}')
print(f'  RUN --mount=type=secret … cp /run/secrets/tok /app.conf:退出码 {rc};镜像里找到密钥的位置:{find_in_image("bwlab-c8h", SECRET)}')
purge()
