import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u152'); R = {}
print('== 一:Cargo.lock 里有什么:格式版本、每个包的名字/版本/来源/校验和、依赖列表')
d = proj('u152', {'src/main.rs': 'fn main() { let mut b = itoa::Buffer::new(); println!("{}", b.format(1u8)); }'}, deps='itoa = "1"')
rc, o = cargo(['build', '--quiet'], d, timeout=600); lock = (d / 'Cargo.lock').read_text(); print('  Cargo.lock(完整内容):'); print('\n'.join('    ' + l for l in lock.splitlines())); R['lock'] = lock.splitlines()
print()
print('== 二:--locked:锁文件与 Cargo.toml 不一致时拒绝构建;--frozen = --locked + --offline')
(d / 'Cargo.toml').write_text((d / 'Cargo.toml').read_text().replace('itoa = "1"', 'itoa = "1"\nsemver = "1"'))
rc, o = cargo(['build', '--locked'], d, timeout=600); L = [l.strip() for l in o.splitlines() if l.strip()][:4]; print('  Cargo.toml 加了依赖但锁文件没更新,cargo build --locked:'); print('\n'.join('    ' + l for l in L)); R['locked'] = L
rc, o = cargo(['build', '--quiet'], d, timeout=600); print(f'  不加 --locked 时 cargo 自动更新锁文件:退出码 {rc};锁文件里的包数:{(d / "Cargo.lock").read_text().count("[[package]]")}'); R['autoupd'] = (d / 'Cargo.lock').read_text().count('[[package]]')
print()
print('== 三:校验和:篡改 Cargo.lock 里的 checksum,cargo 会拒绝(防止同名同版本的内容被替换)')
t = (d / 'Cargo.lock').read_text(); t2 = re.sub(r'(name = "itoa"\nversion = "[^"]+"\nsource = "[^"]+"\nchecksum = ")([0-9a-f]{8})', lambda m: m.group(1) + 'deadbeef', t, count=1)
(d / 'Cargo.lock').write_text(t2); shutil.rmtree(CH / 'registry' / 'src', ignore_errors=True)
rc, o = cargo(['build', '--locked'], d, timeout=600); L = [l.strip() for l in o.splitlines() if l.strip()][:6]; print('  把 itoa 的 checksum 前 8 位改成 deadbeef 后构建:'); print('\n'.join('    ' + l[:200] for l in L)); R['tamper'] = L
(d / 'Cargo.lock').write_text(t)
print()
print('== 四:同一个锁文件在不同时间构建得到相同版本:模拟「crates.io 上出了新版本」——把锁文件里的 itoa 钉在 1.0.5,不管最新版是什么,build 用的都是 1.0.5')
rc, o = cargo(['update', '-p', 'itoa', '--precise', '1.0.5'], d, timeout=300)
rc, o = cargo(['build', '--locked', '--quiet'], d, timeout=600); print(f'  cargo build --locked 退出码 {rc}'); R['pinned_rc'] = rc
rc, o = cargo(['tree', '--locked'], d, timeout=300); print('  cargo tree --locked:'); print('\n'.join('    ' + l for l in o.splitlines() if l.strip() and 'Compiling' not in l)); R['tree'] = [l for l in o.splitlines() if l.strip()]
print()
print('== 五:cargo new 生成的 .gitignore:库与二进制对 Cargo.lock 的默认处理')
rc, o = sh(['cargo', 'new', '--lib', str(RS / 'proj' / 'u152lib'), '--vcs', 'none'], cwd=RS / 'proj')[0:2] if False else (0, '')
for kind, flag in (('bin', '--bin'), ('lib', '--lib')):
    pdir = RS / 'proj' / f'u152{kind}'; shutil.rmtree(pdir, ignore_errors=True); rc, so, se = sh(['cargo', 'new', flag, str(pdir), '--vcs', 'git'], env=ENVB); gi = (pdir / '.gitignore').read_text().split() if (pdir / '.gitignore').exists() else []
    print(f'  cargo new {flag}:.gitignore 内容 {gi}(是否忽略 Cargo.lock: {"Cargo.lock" in gi})'); R.setdefault('gitignore', {})[kind] = gi
shutil.rmtree(RS / 'proj' / 'u152bin' / '.git', ignore_errors=True)
save('u152', R)
