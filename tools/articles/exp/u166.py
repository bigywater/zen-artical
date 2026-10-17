import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
import statistics
tee('u166'); R = {}
d = RS / 'proj' / 'u166'; shutil.rmtree(d, ignore_errors=True); (d / 'src').mkdir(parents=True)
TOML = '''[package]
name = "au"
version = "0.1.0"
edition = "2024"

[dependencies]
smallvec = "=1.6.0"
chrono = { version = "=0.4.19", default-features = false, features = ["clock"] }
atty = "=0.2.14"
'''
(d / 'Cargo.toml').write_text(TOML); (d / 'src' / 'main.rs').write_text('fn main() {\n    println!("hello");\n}\n')
def cm(args, cwd=d, timeout=400):
    t0 = time.perf_counter(); rc, o, e = sh(['cargo', *args], cwd=cwd, env=ENVN, timeout=timeout); return rc, tidy(clean(o + e)), time.perf_counter() - t0
def pr(txt, n=40, ind='    ', w=200):
    L = txt.split('\n'); print('\n'.join(ind + l[:w] for l in L[:n]))
    if len(L) > n: print(f'{ind}…(共 {len(L)} 行)')
def noise(o): return '\n'.join(l for l in o.split('\n') if not l.startswith(('      Loaded', '    Fetching', '    Updating', '    Scanning')) or 'Scanning' in l or 'Loaded' in l)
print('== 一:一个依赖了老版本 smallvec / chrono / atty 的小项目(main 里只打印 hello,根本没有用到它们);cargo tree 与 Cargo.toml')
print('  Cargo.toml:'); print('\n'.join('    ' + l for l in TOML.strip().split('\n')))
rc, o, t = cm(['generate-lockfile']); rc, o, t = cm(['tree']); print('  cargo tree:'); pr(o, 14); R['tree'] = o.split('\n')[:14]
print()
print('== 二:cargo audit:默认会先联网更新 RustSec 漏洞库(日志里的 Fetching 行),再扫描 Cargo.lock')
rc, o, t1 = cm(['audit']); print(f'  退出码 {rc};耗时 {t1:.1f} 秒'); pr(o, 60); R['audit1'] = dict(rc=rc, out=o.split('\n'), secs=round(t1, 1))
adb = ENVN['CARGO_HOME'] + '/advisory-db'; rc_, ci, _ = sh(['git', '-C', adb, 'log', '-1', '--format=%cI %h'], env=ENVN); print('  本地漏洞库最近一次提交:', ci.strip()); R['dbcommit'] = ci.strip()
n_adv = len(list(pathlib.Path(adb).glob('crates/*/RUSTSEC-*.md'))); print(f'  漏洞库里 crates/ 目录下的公告文件数:{n_adv}'); R['n_adv'] = n_adv
print()
print('== 三:加 --no-fetch:不联网,直接用本地漏洞库,与上一节耗时对比')
rc, o, t2 = cm(['audit', '--no-fetch']); print(f'  cargo audit --no-fetch:退出码 {rc};耗时 {t2:.1f} 秒'); R['audit2'] = dict(rc=rc, secs=round(t2, 1))
print()
print('== 四:--json 输出的结构(可供脚本与 CI 消费)')
rc, o, t = cm(['audit', '--no-fetch', '--json']); j = json.loads(o[o.index('{'):])
vl = j['vulnerabilities']; print(f'  退出码 {rc};vulnerabilities.found={vl["found"]},count={vl["count"]}')
for v in vl['list']: print(f'    {v["advisory"]["id"]}  {v["package"]["name"]} {v["package"]["version"]}  patched={v["versions"]["patched"]}  cvss={v["advisory"].get("cvss")}')
print('  warnings 分类:', {k: [(w["package"]["name"], w["advisory"]["id"] if w.get("advisory") else None) for w in ws] for k, ws in j['warnings'].items()})
print('  lockfile 里的依赖数:', j['lockfile']['dependency-count'], ';database.advisory-count:', j['database']['advisory-count'])
R['json'] = dict(rc=rc, found=vl['found'], count=vl['count'], vulns=[[v['advisory']['id'], v['package']['name'], v['package']['version'], v['versions']['patched'], v['advisory'].get('cvss')] for v in vl['list']], warnings={k: [[w['package']['name'], w['kind'], w['advisory']['id'] if w.get('advisory') else None, w['advisory']['title'] if w.get('advisory') else None] for w in ws] for k, ws in j['warnings'].items()}, deps=j['lockfile']['dependency-count'], adv=j['database']['advisory-count'])
print()
print('== 五:--ignore 与 --deny warnings:忽略一条公告;把警告(unmaintained/unsound)也当成失败')
rc, o, t = cm(['audit', '--no-fetch', '--ignore', 'RUSTSEC-2020-0159', '--ignore', 'RUSTSEC-2021-0003']); print(f'  忽略那两个漏洞,退出码 {rc}'); pr(noise(o), 30); R['ignore'] = dict(rc=rc, out=noise(o).split('\n')[:30])
rc, o, t = cm(['audit', '--no-fetch', '--ignore', 'RUSTSEC-2020-0159', '--ignore', 'RUSTSEC-2021-0003', '--deny', 'warnings']); print(f'  再加 --deny warnings,退出码 {rc}'); R['deny_warn'] = rc
print()
print('== 六:修复:把依赖升级到修复版本(smallvec >=1.6.1,chrono >=0.4.20),重新生成锁文件后再审计')
(d / 'Cargo.toml').write_text(TOML.replace('=1.6.0', '1.6.1').replace('=0.4.19', '0.4.20').replace('atty = "=0.2.14"', ''))
rc, o, t = cm(['update']); rc, o, t = cm(['tree']); print('  升级后的 cargo tree:'); pr(o, 12); R['tree2'] = o.split('\n')[:12]
rc, o, t = cm(['audit', '--no-fetch']); print(f'  cargo audit:退出码 {rc}'); pr(noise(o), 20); R['audit3'] = dict(rc=rc, out=noise(o).split('\n')[:20])
print()
print('== 七:cargo audit 不看你有没有调用:main 完全没用到 smallvec 的 insert_many,却照样报告')
print('  上面第二节里 main 只有 println!("hello"),smallvec 与 chrono 都不在 main 里使用;报告仍然出现 —— 审计依据的是 Cargo.lock 里「有没有这个版本」,不是调用图')
(d / 'Cargo.toml').write_text(TOML); rc, o, t = cm(['generate-lockfile']); rc, o, _ = cm(['audit', '--no-fetch']); R['reach'] = rc; print(f'  恢复旧依赖后再审计:退出码 {rc}')
print()
print('== 八:cargo deny:cargo deny init 生成 deny.toml,再 check 四类规则(advisories / bans / licenses / sources)')
rc, o, t = cm(['deny', 'init']); print('  cargo deny init:退出码', rc, o.strip()[:100])
dt_ = (d / 'deny.toml').read_text(); secs = re.findall(r'^\[(\w+)\]', dt_, re.M); print('  deny.toml 的段落:', secs); R['deny_secs'] = secs
rc, o, t = cm(['deny', 'check']); print(f'  cargo deny check(默认模板):退出码 {rc};耗时 {t:.1f} 秒'); lines = [l for l in o.split('\n') if l.startswith(('error', 'warning', 'advisories', 'bans', 'licenses', 'sources'))]; pr('\n'.join(lines), 24); R['deny1'] = dict(rc=rc, lines=lines[:24])
(d / 'deny.toml').write_text('[advisories]\nignore = []\n\n[licenses]\nallow = ["MIT", "Apache-2.0", "Unicode-3.0"]\nconfidence-threshold = 0.8\n\n[bans]\nmultiple-versions = "warn"\n\n[sources]\nunknown-registry = "deny"\nunknown-git = "deny"\n')
rc, o, t = cm(['deny', 'check']); print(f'  自己写的 deny.toml(允许 MIT/Apache-2.0/Unicode-3.0 许可证;禁止未知来源):退出码 {rc}'); lines = [l for l in o.split('\n') if l.startswith(('error', 'warning', 'advisories', 'bans', 'licenses', 'sources'))]; pr('\n'.join(lines), 20); R['deny2'] = dict(rc=rc, lines=lines[:20])
rc, o, t = cm(['deny', 'check', 'licenses']); print(f'  只检查 licenses:退出码 {rc}'); R['deny_lic'] = rc
print()
print('== 九:把审计放进 CI:一个脚本的退出码就是门禁(旧依赖时失败,升级后通过)')
(d / 'Cargo.toml').write_text(TOML); cm(['generate-lockfile']); rc1, _, _ = cm(['audit', '--no-fetch']); (d / 'Cargo.toml').write_text(TOML.replace('=1.6.0', '1.6.1').replace('=0.4.19', '0.4.20').replace('atty = "=0.2.14"', '')); cm(['update']); rc2, _, _ = cm(['audit', '--no-fetch'])
print(f'  旧锁文件:cargo audit 退出码 {rc1}(CI 里这一步失败)  升级后:退出码 {rc2}(通过)'); R['ci'] = [rc1, rc2]
save('u166', R)
