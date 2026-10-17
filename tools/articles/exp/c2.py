import sys, os, re, time, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c2')
img('alpine:3.20')
purge()
def tree_in_image(tag):
    rc, o = dk('run', '--rm', *LAB, tag, 'sh', '-c', 'cd /app && find . -type f | sort')
    return [l for l in o.split('\n') if l.startswith('./')]
def ctx_size(o):
    m = re.findall(r'\[internal\] load build context\s*\n#\d+ transferring context: ([\d.]+\w+)', o)
    return m[-1] if m else '?'
FILES = {
    'Dockerfile': 'FROM alpine:3.20\nCOPY . /app\n',
    'main.txt': 'main\n',
    'build.log': 'log1\n',
    'notes.md': 'notes\n',
    'README.md': 'readme\n',
    'src/a.txt': 'a\n',
    'src/b.log': 'blog\n',
    'build/out.bin': 'out\n',
    'src/build/inner.txt': 'inner\n',
    'tmp/x/y/temp': 't\n',
    'node_modules/big.bin': os.urandom(30 * 1024 * 1024),
}
print('== 一:没有 .dockerignore:COPY . /app 把什么都带进了镜像(含 30 MiB 的 node_modules)')
d = ctx('c2a', FILES)
t0 = time.time(); rc, o = build(d, 'bwlab-c2a'); t = ms(t0)
print(f'  退出码 {rc},用时 {t:.0f} ms,transferring context(COPY 一步){ctx_size(o)}')
files = tree_in_image('bwlab-c2a')
print(f'  镜像里 /app 有 {len(files)} 个文件:' + ' '.join(files))
print('== 二:写一个 .dockerignore,逐条看效果')
RULES = '''
node_modules
*.log
/build
**/temp
*.md
!README.md
'''
d = ctx('c2b', {**FILES, '.dockerignore': RULES})
t0 = time.time(); rc, o = build(d, 'bwlab-c2b'); t = ms(t0)
print('  .dockerignore 的内容:' + ' | '.join(l for l in RULES.strip().split('\n')))
print(f'  退出码 {rc},用时 {t:.0f} ms,transferring context(COPY 一步){ctx_size(o)}')
files = tree_in_image('bwlab-c2b')
print(f'  镜像里 /app 有 {len(files)} 个文件:' + ' '.join(files))
allf = ['./' + k for k in FILES if k != 'Dockerfile' and not k.startswith('node_modules')] + ['./node_modules/big.bin']
miss = sorted(set(allf) - set(files) - {'./.dockerignore'})
print('  被忽略的文件:' + ' '.join(miss))
print('  说明:`*.log` 只匹配根目录这一层的 build.log,src/b.log 没被忽略;`/build` 只匹配根目录的 build,src/build/inner.txt 没被忽略;`**/temp` 匹配任意深度;`*.md` 之后的 `!README.md` 把 README.md 加回来(后面的规则覆盖前面的)')
print('== 三:`**/*.log` 才匹配任意深度的 log')
d = ctx('c2c', {**FILES, '.dockerignore': '**/*.log\n'})
rc, o = build(d, 'bwlab-c2c')
files = tree_in_image('bwlab-c2c')
print('  忽略规则 **/*.log 之后镜像里还有的 log 文件:' + (' '.join(f for f in files if f.endswith('.log')) or '(没有)'))
print('== 四:忽略一个经常变化的文件,可以让 COPY . 这一层保持缓存')
def copy_cached(o):
    m = re.search(r'#(\d+) \[\d+/\d+\] COPY \. /app', o)
    return bool(m and re.search(r'#%s CACHED' % m.group(1), o))
for label, rules in (('不忽略 build.log', ''), ('忽略 build.log', 'build.log\n')):
    d = ctx('c2d', {'Dockerfile': 'FROM alpine:3.20\nCOPY . /app\n', 'main.txt': 'main\n', 'build.log': 'v1 ' + str(time.time()) + '\n', '.dockerignore': rules})
    build(d, 'bwlab-c2d')
    (d / 'build.log').write_text('v2 changed ' + str(time.time()) + '\n')
    t0 = time.time(); rc, o = build(d, 'bwlab-c2d'); t = ms(t0)
    print(f'  [{label}] 只改了 build.log 后再构建:COPY 层 {"命中缓存(CACHED)" if copy_cached(o) else "重新执行"},用时 {t:.0f} ms')
print('== 五:Dockerfile 与 .dockerignore 即使写进了 .dockerignore,COPY . 仍然会把它们带进镜像吗?')
d = ctx('c2e', {'Dockerfile': 'FROM alpine:3.20\nCOPY . /app\n', 'a.txt': 'a\n', 'b.txt': 'b\n', '.dockerignore': 'Dockerfile\n.dockerignore\nb.txt\n'})
rc, o = build(d, 'bwlab-c2e')
print(f'  只有 .dockerignore(写了 Dockerfile、.dockerignore、b.txt):退出码 {rc};镜像里 /app 有 {tree_in_image("bwlab-c2e")}')
(d / 'Dockerfile.dockerignore').write_text('a.txt\n')
rc, o = build(d, 'bwlab-c2f')
print(f'  再加一个 Dockerfile.dockerignore(只写了 a.txt):退出码 {rc};镜像里 /app 有 {tree_in_image("bwlab-c2f")}(它取代了 .dockerignore,不是叠加)')
purge()
