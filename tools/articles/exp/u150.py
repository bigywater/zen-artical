import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u150'); R = {}
WD = RS / 'wasm'; LDW = WD / 'bin' / 'wasm-ld'
(WD / 'bin').mkdir(parents=True, exist_ok=True)
LDW.write_text(f'#!/bin/sh\nif [ "$1" = "-flavor" ]; then shift 2; fi\nexec {HERE.parent / "djlab" / "bin" / "python"} -m ziglang wasm-ld "$@"\n'); LDW.chmod(0o755)
def build(name, lib_rs, opt='s'):
    d = WD / name; shutil.rmtree(d, ignore_errors=True); (d / 'src').mkdir(parents=True); (d / '.cargo').mkdir()
    (d / 'Cargo.toml').write_text(f'[package]\nname = "{name}"\nversion = "0.1.0"\nedition = "2024"\n[lib]\ncrate-type = ["cdylib"]\n[profile.release]\nopt-level = "{opt}"\npanic = "abort"\nlto = true\n')
    (d / '.cargo' / 'config.toml').write_text(f'[target.wasm32-unknown-unknown]\nlinker = "{LDW}"\n')
    (d / 'src' / 'lib.rs').write_text(textwrap.dedent(lib_rs))
    env = dict(ENVB, RUSTC_BOOTSTRAP='1', CARGO_TARGET_DIR=str(WD / 'target'))
    rc, o, e = sh(['cargo', 'build', '--release', '--target', 'wasm32-unknown-unknown', '-Z', 'build-std=core,panic_abort', '--quiet'], cwd=d, env=env, timeout=900)
    w = WD / 'target' / 'wasm32-unknown-unknown' / 'release' / f'{name}.wasm'
    return (w if w.exists() else None), (o + e)[-500:]
def node(js, *args):
    r = subprocess.run(['node', '-e', js, *args], capture_output=True, text=True); return (r.stdout + r.stderr).strip()
print('== 一:把 no_std 的 Rust 编译成 WebAssembly 模块(wasm32-unknown-unknown),看大小、导出和导入,在 node 里调用')
w1, err = build('w1', '''
    #![no_std]
    #[panic_handler] fn panic(_: &core::panic::PanicInfo) -> ! { core::arch::wasm32::unreachable() }
    #[unsafe(no_mangle)] pub extern "C" fn add(a: i32, b: i32) -> i32 { a + b }
    #[unsafe(no_mangle)] pub extern "C" fn fib(n: u32) -> u64 { let (mut a, mut b) = (0u64, 1u64); for _ in 0..n { let t = a + b; a = b; b = t; } a }
    #[unsafe(no_mangle)] pub extern "C" fn checked_div(a: i32, b: i32) -> i32 { if b == 0 { panic!() } a / b }
''')
assert w1, err
print(f'  w1.wasm 大小 {w1.stat().st_size} 字节(包含 3 个函数)'); R['size'] = w1.stat().st_size
out = node('''
const b = require("fs").readFileSync(process.argv[1]); const m = new WebAssembly.Module(b);
console.log("导出:", JSON.stringify(WebAssembly.Module.exports(m).map(e => e.name + ":" + e.kind)));
console.log("导入:", JSON.stringify(WebAssembly.Module.imports(m)));
const i = new WebAssembly.Instance(m, {});
console.log("add(2, 3) =", i.exports.add(2, 3), " 返回类型", typeof i.exports.add(2, 3));
const f = i.exports.fib(50); console.log("fib(50) =", f, " 返回类型", typeof f, "(i64 在 JS 里是 BigInt)");
console.log("add(2147483647, 1) =", i.exports.add(2147483647, 1), "(i32 回绕:wasm 整数加法不检查溢出)");
try { i.exports.checked_div(1, 0); } catch (e) { console.log("checked_div(1, 0) →", e.constructor.name + ":", e.message); }
console.log("陷入 trap 之后实例还能用:add(1, 1) =", i.exports.add(1, 1));
''', str(w1)); print('\n'.join('  ' + l for l in out.splitlines())); R['node1'] = out.splitlines()
print()
print('== 二:线性内存:JS 往 wasm 的内存里写字节,Rust 读;指针就是内存里的偏移(整数),没有地址空间的其它部分')
w2, err = build('w2', '''
    #![no_std]
    #[panic_handler] fn panic(_: &core::panic::PanicInfo) -> ! { core::arch::wasm32::unreachable() }
    static mut BUF: [u8; 64] = [0; 64];
    #[unsafe(no_mangle)] pub extern "C" fn buf_ptr() -> *mut u8 { &raw mut BUF as *mut u8 }
    #[unsafe(no_mangle)] pub extern "C" fn sum(len: usize) -> u32 { let p = &raw const BUF as *const u8; let mut s = 0u32; let mut i = 0; while i < len && i < 64 { s += unsafe { *p.add(i) } as u32; i += 1; } s }
    #[unsafe(no_mangle)] pub extern "C" fn upper(len: usize) { let p = &raw mut BUF as *mut u8; let mut i = 0; while i < len && i < 64 { unsafe { let c = *p.add(i); if c >= b'a' && c <= b'z' { *p.add(i) = c - 32; } } i += 1; } }
''')
assert w2, err
out = node('''
const i = new WebAssembly.Instance(new WebAssembly.Module(require("fs").readFileSync(process.argv[1])), {});
const mem = new Uint8Array(i.exports.memory.buffer); const p = i.exports.buf_ptr();
console.log("buf_ptr() =", p, "(线性内存里的偏移);内存大小", i.exports.memory.buffer.byteLength, "字节 =", i.exports.memory.buffer.byteLength / 65536, "页(每页 64 KiB)");
const msg = Buffer.from("hello wasm"); mem.set(msg, p); console.log("JS 写入 10 字节后 sum(10) =", i.exports.sum(10), " JS 里算 =", [...msg].reduce((a, b) => a + b, 0));
i.exports.upper(10); console.log("upper(10) 在 Rust 里就地改写后,JS 读到:", Buffer.from(mem.slice(p, p + 10)).toString());
''', str(w2)); print('\n'.join('  ' + l for l in out.splitlines())); R['node2'] = out.splitlines()
print()
print('== 三:WASI:模块通过导入 wasi_snapshot_preview1.fd_write 才能输出;由宿主(这里是 node 的 WASI)决定 fd 1 接到哪里;没有导入就没有任何系统能力')
w3, err = build('w3', '''
    #![no_std]
    #[panic_handler] fn panic(_: &core::panic::PanicInfo) -> ! { core::arch::wasm32::unreachable() }
    #[repr(C)] struct Iovec { buf: *const u8, len: usize }
    #[link(wasm_import_module = "wasi_snapshot_preview1")]
    unsafe extern "C" { fn fd_write(fd: i32, iovs: *const Iovec, n: usize, nwritten: *mut usize) -> i32; fn proc_exit(code: i32) -> !; }
    #[unsafe(no_mangle)] pub extern "C" fn _start() {
        let msg = b"hello from Rust compiled to WASI\\n"; let iov = Iovec { buf: msg.as_ptr(), len: msg.len() }; let mut n = 0usize;
        let rc = unsafe { fd_write(1, &iov, 1, &mut n) };
        unsafe { proc_exit(if rc == 0 && n == msg.len() { 0 } else { 1 }) }
    }
''')
assert w3, err
out = node('''
const { WASI } = require("node:wasi"); const fs = require("fs");
const m = new WebAssembly.Module(fs.readFileSync(process.argv[1]));
console.log("导入:", JSON.stringify(WebAssembly.Module.imports(m).map(i => i.module + "." + i.name)), " 导出:", JSON.stringify(WebAssembly.Module.exports(m).map(e => e.name)));
const wasi = new WASI({ version: "preview1" });
const inst = new WebAssembly.Instance(m, wasi.getImportObject());
const code = wasi.start(inst); console.log("wasi.start 返回(退出码)", code);
try { new WebAssembly.Instance(m, {}); } catch (e) { console.log("宿主不提供 WASI 导入时实例化:", e.constructor.name + ":", e.message.slice(0, 110)); }
''', str(w3)); print('\n'.join('  ' + l for l in out.splitlines())); R['node3'] = out.splitlines()
save('u150', R)
