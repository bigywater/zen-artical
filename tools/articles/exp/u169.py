import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
import struct
tee('u169'); R = {}
MAIN = '''
    use std::mem::size_of;
    fn main() {
        println!("os={} arch={} pointer={}bit endian={}", std::env::consts::OS, std::env::consts::ARCH, size_of::<usize>() * 8, if cfg!(target_endian = "little") { "little" } else { "big" });
    }
'''
BUILD = '''
    fn main() {
        println!("cargo:warning=build.rs 在 HOST={} 上运行(它自己的 arch={}),为 TARGET={} 编译", std::env::var("HOST").unwrap(), std::env::consts::ARCH, std::env::var("TARGET").unwrap());
    }
'''
LIB = '''
    #[unsafe(no_mangle)]
    pub extern "C" fn add(a: i32, b: i32) -> i32 { a + b }
    #[unsafe(no_mangle)]
    pub extern "C" fn pointer_bits() -> usize { std::mem::size_of::<usize>() * 8 }
'''
d = proj('u169p', {'src/main.rs': MAIN, 'build.rs': BUILD, 'src/lib.rs': LIB}, toml_extra='[lib]\ncrate-type = ["cdylib", "rlib"]\n')
TGT = RS / 'target_u169'; ZW = RS / 'zigw'
def cm(args, extra=None, env=None, cwd=d, timeout=600):
    e = dict(env or ENVN, CARGO_TARGET_DIR=str(TGT)); e.update(extra or {}); rc, o, er = sh(['cargo', *args], cwd=cwd, env=e, timeout=timeout); return rc, tidy(clean(o + er))
class Res:
    def __init__(s, rc, out, err): s.returncode, s.stdout, s.stderr = rc, out, err
def trun(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30); return Res(r.returncode, r.stdout, r.stderr)
    except OSError as e: return Res(-1, '', f'OSError [Errno {e.errno}] {e.strerror}')
def pr(txt, n=20, ind='    ', w=200):
    L = txt.split('\n'); print('\n'.join(ind + l[:w] for l in L[:n]))
    if len(L) > n: print(f'{ind}…(共 {len(L)} 行)')
def filt(o): return '\n'.join(l for l in o.split('\n') if l.strip() and not l.strip().startswith(('Compiling', 'Finished', 'Locking', 'Downloading')) or 'warning' in l.lower())
def fileinfo(p): rc, o, e = sh(['file', '-b', str(p)], env=ENVN); return o.strip().replace(str(RS), '<实验目录>')
def rs(args): rc, o, e = sh(['rustc', *args], env=ENVN); return rc, tidy(clean(o + e))
print('== 一:目标三元组:本机 rustc 支持的目标数量、本机的 host、两个目标的描述(--print target-spec-json)')
rc, o = rs(['--print', 'target-list']); n = len(o.split('\n')); rc, v = rs(['-vV']); host = re.search(r'host: (\S+)', v).group(1); print(f'  nightly rustc 的 --print target-list:{n} 个目标;host = {host}'); R['ntargets'] = n; R['host'] = host
R['spec'] = {}
for t in ('aarch64-apple-darwin', 'x86_64-unknown-linux-musl', 'wasm32-unknown-unknown'):
    rc, o, e = sh(['rustc', '-Z', 'unstable-options', '--print', 'target-spec-json', '--target', t], env=ENVN); j = json.loads(o)
    keep = {k: j.get(k) for k in ('llvm-target', 'arch', 'os', 'data-layout', 'linker-flavor', 'executables', 'crt-static-default', 'max-atomic-width', 'panic-strategy')}
    print(f'  {t}:'); print('\n'.join(f'    {k:<20} {v}' for k, v in keep.items() if v is not None)); R['spec'][t] = keep
print('  --print cfg(三个目标的 cfg,选 target_arch / target_os / target_pointer_width / target_endian):')
R['cfg'] = {}
for t in ('aarch64-apple-darwin', 'x86_64-unknown-linux-musl', 'wasm32-unknown-unknown', 'aarch64-apple-ios'):
    rc, o = rs(['--print', 'cfg', '--target', t]); c = {k: re.search(rf'^{k}="?([^"\n]*)"?$', o, re.M).group(1) for k in ('target_arch', 'target_os', 'target_pointer_width', 'target_endian')}
    print(f'    {t:<28}', c); R['cfg'][t] = c
print()
print('== 二:没有安装目标的标准库时:用 brew 的 rustc(只带本机 aarch64-apple-darwin)去编译 aarch64-apple-ios')
(RS / 'brewproj').mkdir(exist_ok=True); bp = proj('u169b', {'src/main.rs': MAIN})
rc, o = cargo(['build', '--target', 'aarch64-apple-ios'], bp); print(f'  退出码 {rc}'); pr(o, 14); R['nostd'] = [rc, o.split('\n')[:14]]
print()
print('== 三:同一操作系统、另一种 CPU 架构(x86_64-apple-darwin,本机是 arm64):能编译,但能运行吗')
rc, o = cm(['build', '--target', 'x86_64-apple-darwin']); print(f'  cargo build --target x86_64-apple-darwin:退出码 {rc}'); pr(filt(o), 8)
exe = TGT / 'x86_64-apple-darwin' / 'debug' / 'u169p'; print('  file:', fileinfo(exe)); R['x86'] = dict(rc=rc, file=fileinfo(exe), build=filt(o).split('\n')[:8])
r = trun([str(exe)]); print(f'  直接运行:退出码 {r.returncode}  {r.stderr.strip() or r.stdout.strip()}'); R['x86_run'] = [r.returncode, r.stderr.strip() or r.stdout.strip()]
r = subprocess.run(['arch', '-x86_64', str(exe)], capture_output=True, text=True); print(f'  用 arch -x86_64 运行:退出码 {r.returncode}  {r.stderr.strip() or r.stdout.strip()}  (本机没有 Rosetta)'); R['x86_arch'] = [r.returncode, r.stderr.strip() or r.stdout.strip()]
print()
print('== 四:宿主与目标:build.rs 在宿主机上运行;对比本机、x86_64-apple-darwin 与 wasm32 三次构建里 build.rs 打印的 HOST / TARGET')
R['hostt'] = {}
for t in ([], ['--target', 'x86_64-apple-darwin'], ['--target', 'wasm32-unknown-unknown']):
    shutil.rmtree(TGT, ignore_errors=True); rc, o = cm(['build', *t]); w = [l.strip() for l in o.split('\n') if 'build.rs' in l]; key = t[-1] if t else '(无 --target)'; print(f'  {key:<26} {w[0] if w else o[-200:]}'); R['hostt'][key] = w[:1]
shutil.rmtree(TGT, ignore_errors=True); cm(['build']); d1 = sorted(p.name for p in TGT.iterdir() if not p.name.startswith('.') and p.name != 'CACHEDIR.TAG')
cm(['build', '--target', 'x86_64-apple-darwin']); d2 = sorted(p.name for p in TGT.iterdir() if not p.name.startswith('.') and p.name != 'CACHEDIR.TAG')
print(f'  target/ 下的目录:无 --target 时 {d1};再加 --target x86_64-apple-darwin 后 {d2}(带 --target 的产物放在以三元组命名的子目录里,宿主的产物仍在 debug/)'); R['dirs'] = [d1, d2]
print()
print('== 五:WebAssembly(wasm32-unknown-unknown):编译 cdylib 并在 node 里实际调用 add 与 pointer_bits')
rc, o = cm(['build', '--release', '--lib', '--target', 'wasm32-unknown-unknown']); print(f'  退出码 {rc}'); w = TGT / 'wasm32-unknown-unknown' / 'release' / 'u169p.wasm'; print(f'  {w.name}:{w.stat().st_size} 字节;file: {fileinfo(w)}')
js = RS / 'u169_run.js'; js.write_text(f'const fs=require("fs");const m=new WebAssembly.Module(fs.readFileSync("{w}"));const i=new WebAssembly.Instance(m,{{}});console.log("exports:",Object.keys(i.exports).filter(k=>["add","pointer_bits"].includes(k)).join(","));console.log("add(2,3) =",i.exports.add(2,3));console.log("pointer_bits() =",i.exports.pointer_bits());')
r = subprocess.run(['node', str(js)], capture_output=True, text=True); print('  node 调用:'); print('\n'.join('    ' + l for l in r.stdout.strip().split('\n'))); R['wasm'] = dict(size=w.stat().st_size, out=r.stdout.strip().split('\n'), file=fileinfo(w))
print()
print('== 六:Linux(x86_64-unknown-linux-musl):先不配链接器,再用 zig cc 当链接器')
rc, o = cm(['build', '--target', 'x86_64-unknown-linux-musl', '--bin', 'u169p']); print(f'  默认链接器(本机 cc):退出码 {rc}'); L = [l for l in o.split('\n') if l.strip().startswith(('error', '= note: ld:', 'clang: error')) or 'ld:' in l]; pr('\n'.join(L), 6, w=220); R['nolinker'] = [rc, L[:6]]
ZL = lambda arch: {'CARGO_TARGET_' + f'{arch}-unknown-linux-musl'.upper().replace('-', '_') + '_LINKER': str(ZW / f'zcc-{arch}')}
rc, o = cm(['build', '--release', '--target', 'x86_64-unknown-linux-musl', '--bin', 'u169p'], extra=ZL('x86_64')); L = [l.strip() for l in o.split('\n') if 'duplicate symbol' in l or l.strip().startswith('error')]
print(f'  换成 zig cc 当链接器(只设 linker):退出码 {rc}'); pr('\n'.join(L), 5, w=200); R['zig_dup'] = [rc, L[:5]]
# aarch64:zig 不认识 rustc 传的 --fix-cortex-a53-843419,先看不过滤时的报错
rc, o = cm(['build', '--release', '--target', 'aarch64-unknown-linux-musl', '--bin', 'u169p'], extra=dict(ZL('aarch64'), CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_RUSTFLAGS='-C link-self-contained=no', CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_LINKER=str(ZW / 'zcc-aarch64-raw')))
L = [l.strip() for l in o.split('\n') if 'unsupported linker arg' in l]; print(f'  aarch64 目标,zig 链接器不做任何参数过滤:退出码 {rc}'); pr('\n'.join(L), 3); R['a53'] = [rc, L[:3]]
print('  (给 aarch64 的包装脚本加一行,过滤掉这个参数后再试:)')
R['zig'] = {}
for arch in ('x86_64', 'aarch64'):
    t = f'{arch}-unknown-linux-musl'; ex = ZL(arch); ex['CARGO_TARGET_' + t.upper().replace('-', '_') + '_RUSTFLAGS'] = '-C link-self-contained=no'
    rc, o = cm(['build', '--release', '--target', t, '--bin', 'u169p'], extra=ex); exe = TGT / t / 'release' / 'u169p'
    print(f'  {t}(linker = zig cc -target {arch}-linux-musl,RUSTFLAGS = -C link-self-contained=no):退出码 {rc}')
    data = exe.read_bytes() if rc == 0 else b''; em = struct.unpack_from('<H', data, 18)[0] if data else None
    phoff, phentsize, phnum = struct.unpack_from('<Q', data, 32)[0], struct.unpack_from('<H', data, 54)[0], struct.unpack_from('<H', data, 56)[0]
    ptypes = [struct.unpack_from('<I', data, phoff + i * phentsize)[0] for i in range(phnum)] if data else []
    print(f'    file: {fileinfo(exe)}'); print(f'    大小 {exe.stat().st_size / 1024:.0f} KiB;ELF e_machine = {em}({"x86-64" if em == 62 else "AArch64" if em == 183 else "?"});程序头里是否有 PT_INTERP(动态链接器):{3 in ptypes}')
    r = trun([str(exe)]); print(f'    在 macOS 上直接运行:退出码 {r.returncode},{(r.stderr.strip() or r.stdout.strip())[:100]}')
    R['zig'][t] = dict(rc=rc, file=fileinfo(exe), size=exe.stat().st_size, machine=em, interp=3 in ptypes, run=[r.returncode, (r.stderr.strip() or r.stdout.strip())[:100]])
print()
print('== 七:iOS(aarch64-apple-ios):用 Xcode 的 iPhoneOS SDK 链接;检查平台标记')
rc, o = cm(['build', '--release', '--target', 'aarch64-apple-ios', '--bin', 'u169p']); print(f'  退出码 {rc}'); pr(filt(o), 6); exe = TGT / 'aarch64-apple-ios' / 'release' / 'u169p'; print('  file:', fileinfo(exe))
rc2, o2, e2 = sh(['otool', '-l', str(exe)], env=ENVN); m = re.search(r'cmd (LC_VERSION_MIN_IPHONEOS|LC_BUILD_VERSION).*?version (\S+)\s+sdk (\S+)', o2, re.S); print(f'  otool -l:加载命令 {m.group(1)},version = {m.group(2)},sdk = {m.group(3)}')
host_exe = TGT / 'release' / 'u169p'; cm(['build', '--release']); rc3, o3, e3 = sh(['otool', '-l', str(host_exe)], env=ENVN); m2 = re.search(r'LC_BUILD_VERSION.*?platform (\w+).*?minos (\S+)', o3, re.S); print(f'  对比本机构建:platform = {m2.group(1) if m2 else None},minos = {m2.group(2) if m2 else None}(platform 1 = macOS)')
r = trun([str(exe)]); print(f'  在 macOS 上直接运行:退出码 {r.returncode} {(r.stderr.strip() or r.stdout.strip())[:100]}')
R['ios'] = dict(rc=rc, file=fileinfo(exe), lc=m.group(1) if m else None, minos=m.group(2) if m else None, sdk=m.group(3) if m else None, host_platform=m2.group(1) if m2 else None, run=[r.returncode, (r.stderr.strip() or r.stdout.strip())[:100]])
print()
print('== 八:能运行的目标上的实际输出:本机,以及 wasm32 里调用 pointer_bits 的结果(对照第一节的 cfg)')
r = trun([str(TGT / 'release' / 'u169p')]); print('  本机 aarch64-apple-darwin 运行:', r.stdout.strip()); R['run_host'] = r.stdout.strip()
print('  wasm32-unknown-unknown:pointer_bits() =', R['wasm']['out'][-1].split('=')[1].strip(), '(cfg 里 target_pointer_width =', R['cfg']['wasm32-unknown-unknown']['target_pointer_width'] + ')')
save('u169', R)
