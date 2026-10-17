import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
import json
tee('u151'); R = {}
def lock_versions(d, names):
    t = (d / 'Cargo.lock').read_text(); out = {}
    for blk in t.split('[[package]]'):
        m = re.search(r'name = "([^"]+)"\nversion = "([^"]+)"', blk)
        if m and m.group(1) in names: out.setdefault(m.group(1), []).append(m.group(2))
    return out
print('== 一:版本要求的写法与解析结果:同一个 crate(itoa)用不同写法,Cargo 选出的版本(看 Cargo.lock)')
reqs = [('"1"', '1 的最新版本'), ('"1.0"', '^1.0'), ('"~1.0.5"', '~1.0.5 = >=1.0.5, <1.1.0'), ('"=1.0.9"', '精确版本'), ('"0.4"', '^0.4(0.x 里次版本号是不兼容边界)'), ('">=1.0.2, <1.0.8"', '范围')]
R['reqs'] = []
for req, note in reqs:
    d = proj('u151a', {'src/main.rs': 'fn main() {}'}, deps=f'itoa = {req}'); rc, o = cargo(['generate-lockfile'], d, timeout=300)
    v = lock_versions(d, ['itoa']).get('itoa', ['(失败)']); print(f'  itoa = {req:<22} {note:<30} → 解析为 {v}'); R['reqs'].append([req, note, v])
print()
print('== 二:同一个 crate 的两个不兼容版本可以同时存在(用 package 重命名依赖):cargo tree 显示两个版本,cargo tree -d 列出重复')
d = proj('u151b', {'src/main.rs': 'fn main() { let mut b = itoa::Buffer::new(); println!("{}", b.format(12345u32)); let mut c = itoa_old::Buffer::new(); println!("{}", c.format(67890u32)); }'}, deps='itoa = "1"\nitoa_old = { package = "itoa", version = "0.4" }')
rc, o = cargo(['tree'], d, timeout=300); print('  cargo tree:'); print('\n'.join('    ' + l for l in o.splitlines() if l.strip())); R['tree'] = [l for l in o.splitlines() if l.strip()]
rc, o = cargo(['tree', '-d'], d, timeout=300); print('  cargo tree -d(重复的 crate):'); print('\n'.join('    ' + l for l in o.splitlines() if l.strip())); R['tree_d'] = [l for l in o.splitlines() if l.strip()]
rc, o = cargo(['run', '--quiet'], d, timeout=600); print('  运行(两个版本在同一个程序里都可用):', o.strip().replace('\n', ' | ')); R['run'] = o.strip()
print()
print('== 三:解析失败:两个依赖对同一个 crate 提出互相冲突的版本要求(用两个本地 path crate 构造)')
base = RS / 'proj' / 'u151c'; shutil.rmtree(base, ignore_errors=True)
for n, req in (('left', '=1.0.5'), ('right', '>=1.0.10')):
    (base / n / 'src').mkdir(parents=True); (base / n / 'Cargo.toml').write_text(f'[package]\nname = "{n}"\nversion = "0.1.0"\nedition = "2024"\n[dependencies]\nitoa = "{req}"\n'); (base / n / 'src' / 'lib.rs').write_text('')
(base / 'app' / 'src').mkdir(parents=True); (base / 'app' / 'Cargo.toml').write_text('[package]\nname = "app"\nversion = "0.1.0"\nedition = "2024"\n[dependencies]\nleft = { path = "../left" }\nright = { path = "../right" }\n'); (base / 'app' / 'src' / 'main.rs').write_text('fn main() {}')
rc, o = cargo(['generate-lockfile'], base / 'app', timeout=300); L = [l.replace(str(RS), '<实验目录>') for l in o.splitlines() if l.strip()][:8]; print('\n'.join('  ' + l for l in L)); R['conflict'] = L
print()
print('== 四:cargo update:Cargo.lock 钉住的版本不会自动升级;cargo update -p 只升级指定的包;--precise 回退到指定版本')
d = proj('u151d', {'src/main.rs': 'fn main() {}'}, deps='itoa = "1"'); cargo(['generate-lockfile'], d, timeout=300)
v0 = lock_versions(d, ['itoa'])['itoa'][0]; t = (d / 'Cargo.lock').read_text(); t2 = re.sub(r'(name = "itoa"\nversion = ")[^"]+("\nsource = "[^"]+"\nchecksum = ")[^"]+', lambda m: m.group(1) + '1.0.5' + m.group(2) + '', t)
rc, o = cargo(['update', '-p', 'itoa', '--precise', '1.0.5'], d, timeout=300); v1 = lock_versions(d, ['itoa'])['itoa'][0]
print(f'  generate-lockfile 得到 itoa {v0};cargo update -p itoa --precise 1.0.5 之后 Cargo.lock 里是 {v1}(满足 "1" 的要求,可以回退)')
rc, o = cargo(['build', '--quiet'], d, timeout=600); vb = lock_versions(d, ['itoa'])['itoa'][0]; print(f'  之后正常 cargo build:Cargo.lock 里仍是 {vb}(即使 crates.io 上有更新的 1.0.18,锁文件钉住的版本不会被自动升级)'); R['pinned'] = vb
rc, o = cargo(['update', '-p', 'itoa'], d, timeout=300); v2 = lock_versions(d, ['itoa'])['itoa'][0]; print(f'  cargo update -p itoa 之后回到 {v2};Cargo.toml 没有改动:{(d / "Cargo.toml").read_text().count("itoa")} 处 itoa 声明'); R['update'] = [v0, v1, v2]
rc, o = cargo(['update', '-p', 'itoa', '--precise', '0.4.8'], d, timeout=300); print('  --precise 到不满足 "1" 的 0.4.8:', [l.strip() for l in o.splitlines() if 'error' in l.lower() or 'failed' in l.lower()][:2]); R['update_bad'] = [l.strip() for l in o.splitlines() if 'error' in l.lower() or 'failed' in l.lower()][:2]
save('u151', R)
