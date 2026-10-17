import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u149'); R = {}
print('== 一:本机的平台常量与分隔符(只验证了 macOS;Windows / Linux 的行为没有在本机验证)')
r = tryit('u149a', '''
    use std::{env::consts, path::{self, Path, MAIN_SEPARATOR}};
    fn main() {
        println!("OS = {}  FAMILY = {}  ARCH = {}  cfg!(unix) = {}  cfg!(windows) = {}", consts::OS, consts::FAMILY, consts::ARCH, cfg!(unix), cfg!(windows));
        println!("MAIN_SEPARATOR = {:?}  is_separator('/') = {}  is_separator('\\\\') = {}", MAIN_SEPARATOR, path::is_separator('/'), path::is_separator('\\\\'));
        println!("反斜杠在本平台的路径里是普通字符:Path::new(\\"a\\\\\\\\b\\\\\\\\c\\").components().count() = {}(1 个组件);Path::new(\\"a/b/c\\").components().count() = {}", Path::new("a\\\\b\\\\c").components().count(), Path::new("a/b/c").components().count());
        println!("file_name(\\"C:\\\\\\\\dir\\\\\\\\file.txt\\") = {:?}(Windows 风格路径在这里就是一个怪异的文件名)", Path::new("C:\\\\dir\\\\file.txt").file_name());
    }
''', quiet_src=True); R['consts'] = r['out']
print()
print('== 二:大小写:macOS 默认的 APFS 大小写不敏感但保留大小写 —— Path 的相等比较是区分大小写的字符串/组件比较,而文件系统不是')
r = tryit('u149b', '''
    use std::{fs, path::Path};
    fn main() {
        let d = std::env::temp_dir().join("u149"); let _ = fs::remove_dir_all(&d); fs::create_dir_all(&d).unwrap();
        fs::write(d.join("Report.TXT"), "x").unwrap();
        for name in ["Report.TXT", "report.txt", "REPORT.TXT"] { println!("  exists({:<11}) = {}", name, d.join(name).exists()); }
        println!("  Path::new(\\"Report.TXT\\") == Path::new(\\"report.txt\\") → {}(Path 比较区分大小写)", Path::new("Report.TXT") == Path::new("report.txt"));
        println!("  read_dir 返回的名字:{:?}(保留创建时的大小写)", fs::read_dir(&d).unwrap().map(|e| e.unwrap().file_name()).collect::<Vec<_>>());
        let e = fs::write(d.join("report.txt"), "y").map(|_| "写入成功(覆盖了同一个文件)"); println!("  再写 report.txt:{:?};目录里仍然只有 {} 个文件", e, fs::read_dir(&d).unwrap().count());
        println!("  canonicalize(\\"report.txt\\") = {:?}(规范化后恢复真实大小写)", d.join("report.txt").canonicalize().unwrap().file_name().unwrap());
        fs::remove_dir_all(&d).unwrap();
    }
''', quiet_src=True); R['case'] = r['out']
print()
print('== 三:Unicode 规范化:\"é\" 可以是一个字符(NFC,U+00E9)或 e + 组合重音(NFD,U+0065 U+0301);在文件系统里它们是同一个名字吗?')
r = tryit('u149c', '''
    use std::fs;
    fn main() {
        let d = std::env::temp_dir().join("u149n"); let _ = fs::remove_dir_all(&d); fs::create_dir_all(&d).unwrap();
        let nfc = "caf\\u{e9}.txt"; let nfd = "cafe\\u{301}.txt";
        println!("  NFC 字节 {:?}", nfc.as_bytes()); println!("  NFD 字节 {:?}", nfd.as_bytes()); println!("  两个字符串相等吗 {}", nfc == nfd);
        fs::write(d.join(nfc), "x").unwrap();
        println!("  用 NFC 创建后,exists(NFC) = {}  exists(NFD) = {}", d.join(nfc).exists(), d.join(nfd).exists());
        let names: Vec<Vec<u8>> = fs::read_dir(&d).unwrap().map(|e| { use std::os::unix::ffi::OsStrExt; e.unwrap().file_name().as_bytes().to_vec() }).collect(); println!("  read_dir 返回的名字字节:{:?}", names);
        println!("  返回的是 NFC 吗 {};NFD 吗 {}", names[0] == nfc.as_bytes(), names[0] == nfd.as_bytes());
        fs::remove_dir_all(&d).unwrap();
    }
''', quiet_src=True); R['nfc'] = r['out']
print()
print('== 四:文件名限制:ASCII 文件名最长多少(二分);超过 255 字节的汉字文件名在这个文件系统上能创建吗;不允许 NUL')
r = tryit('u149d', '''
    use std::fs;
    fn main() {
        let d = std::env::temp_dir().join("u149l"); let _ = fs::remove_dir_all(&d); fs::create_dir_all(&d).unwrap();
        let (mut lo, mut hi) = (1usize, 1000usize);
        while lo + 1 < hi { let mid = (lo + hi) / 2; let p = d.join("a".repeat(mid)); if fs::write(&p, "").is_ok() { lo = mid; let _ = fs::remove_file(&p); } else { hi = mid; } }
        let e = fs::write(d.join("a".repeat(hi)), "").unwrap_err(); println!("  文件名最长 {} 字节;{} 字节失败:kind = {:?},os_error = {:?}", lo, hi, e.kind(), e.raw_os_error());
        let cjk = "汉".repeat(100); println!("  100 个汉字(UTF-8 共 {} 字节):{:?}", cjk.len(), fs::write(d.join(&cjk), "").map(|_| "成功").map_err(|e| e.raw_os_error()));
        let cjk = "汉".repeat(86); println!("  86 个汉字(UTF-8 共 {} 字节):{:?}", cjk.len(), fs::write(d.join(&cjk), "").map(|_| "成功").map_err(|e| e.raw_os_error()));
        println!("  路径里含 NUL:{:?}", fs::write(d.join("a\\0b"), "").map_err(|e| (e.kind(), e.to_string())));
        fs::remove_dir_all(&d).unwrap();
    }
''', quiet_src=True); R['limits'] = r['out']
print()
print('== 五:写跨平台代码的做法:用 Path/PathBuf 拼接而不是拼字符串;用 cfg 区分平台;展示:用字符串拼出来的路径与 join 的差别')
r = tryit('u149e', '''
    use std::path::{Path, PathBuf};
    fn main() {
        let base = "data"; let name = "x.txt";
        let s = format!("{}/{}", base, name); let p: PathBuf = Path::new(base).join(name);
        println!("  字符串拼接:{:?}  join:{:?}  在本平台相同: {}", s, p, Path::new(&s) == p);
        let comps = ["a", "b", "c.txt"].iter().collect::<PathBuf>(); println!("  从组件迭代器收集:{:?}", comps);
        #[cfg(unix)] println!("  cfg(unix) 分支被编译");
        #[cfg(windows)] println!("  cfg(windows) 分支被编译");
        println!("  只有被选中的 cfg 分支才存在于二进制里:本程序编译时 cfg!(windows) = {}", cfg!(windows));
    }
''', quiet_src=True); R['code'] = r['out']
save('u149', R)
