import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u158'); R = {}
base = RS / 'proj' / 'u158'; shutil.rmtree(base, ignore_errors=True); (base / 'src').mkdir(parents=True)
(base / 'Cargo.toml').write_text('[package]\nname = "docs"\nversion = "0.1.0"\nedition = "2024"\n')
(base / 'src' / 'lib.rs').write_text(textwrap.dedent('''
    //! # docs crate
    //!
    //! ```
    //! assert_eq!(docs::double(4), 8);
    //! ```

    /// 把数字翻倍。
    ///
    /// # Examples
    ///
    /// ```
    /// use docs::double;
    /// assert_eq!(double(21), 42);
    /// ```
    ///
    /// 隐藏行(以 `# ` 开头)会被编译运行,但不显示在文档里:
    ///
    /// ```
    /// # use docs::double;
    /// # let x = 5;
    /// assert_eq!(double(x), 10);
    /// ```
    pub fn double(n: i32) -> i32 { n * 2 }

    /// 会 panic 的函数。
    ///
    /// ```should_panic
    /// docs::boom();
    /// ```
    ///
    /// ```no_run
    /// // 只编译,不运行(例如会连接网络或无限循环的例子)
    /// loop { docs::boom(); }
    /// ```
    ///
    /// ```ignore
    /// 这段根本不是合法的 Rust,被 ignore 了
    /// ```
    ///
    /// ```compile_fail
    /// let x: i32 = "不是整数";
    /// ```
    pub fn boom() { panic!("boom") }

    /// 故意写错的文档示例(第二个测试会失败):
    ///
    /// ```
    /// assert_eq!(docs::triple(2), 7);
    /// ```
    pub fn triple(n: i32) -> i32 { n * 3 }

    /// 私有函数的文档示例也会被运行:
    ///
    /// ```
    /// assert!(true);
    /// ```
    #[allow(dead_code)]
    fn private_fn() {}
'''))
def ct(args): return cargo(['test', '--doc'] + args, base, timeout=600)
print('== 一:cargo test --doc:每个 ``` 代码块是一个独立的测试(单独编译成一个小程序并运行);总览(先跳过会失败的 triple)')
rc, o = ct(['--', '--skip', 'triple']); L = [l.strip() for l in o.splitlines() if l.strip().startswith(('test ', 'running', 'test result'))]; print('\n'.join('  ' + l.replace(str(RS), '<实验目录>') for l in L)); R['all'] = L
print()
print('== 二:代码块标注的含义:无标注(编译 + 运行)、should_panic、no_run、ignore、compile_fail,以及隐藏行 # —— 在测试名里都能看到')
tags = [l for l in L if 'src/lib.rs' in l]; print('  测试名(带行号):'); print('\n'.join('    ' + l.replace(str(RS), '<实验目录>') for l in tags)); R['tags'] = tags
print()
print('== 三:文档测试像外部使用者一样依赖当前 crate(要写 use docs::... 或完整路径),并且 edition 2024 下 rustdoc 把可以合并的测试编译成一个 bundle')
rc, o = ct(['--', '--list']); print('  --list:', [l.strip() for l in o.splitlines() if ': test' in l][:3], '…'); R['list'] = [l.strip() for l in o.splitlines() if ': test' in l]
print()
print('== 四:一个失败的文档测试:输出里会显示被编译的程序和失败原因,定位到 lib.rs 的行')
rc, o = ct(['triple']); L = [l.replace(str(RS), '<实验目录>') for l in o.splitlines() if l.strip() and 'Compiling' not in l]; print(f'  退出码 {rc}'); print('\n'.join('  ' + l for l in L[-14:])); R['fail'] = [rc, L[-14:]]
print()
print('== 五:文档示例会随 API 变化而失效 —— 把 double 重命名为 twice 之后,引用 double 的文档测试编译失败')
(base / 'src' / 'lib.rs').write_text((base / 'src' / 'lib.rs').read_text().replace('pub fn double(n: i32) -> i32 { n * 2 }', 'pub fn twice(n: i32) -> i32 { n * 2 }'))
rc, o = ct(['--', '--skip', 'triple']); L = [l.strip() for l in o.splitlines() if l.strip().startswith('test src') or 'error[' in l or 'no function' in l or 'test result' in l][:12]; print(f'  把 double 重命名为 twice 之后:'); print('\n'.join('    ' + l.replace(str(RS), '<实验目录>') for l in L)); R['api'] = [l.replace(str(RS), '<实验目录>') for l in L]
save('u158', R)
