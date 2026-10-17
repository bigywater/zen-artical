import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u135'); R = {}
print('== 一:拆开路径:parent / file_name / file_stem / extension / components')
r = tryit('u135a', '''
    #![allow(unused)]
    use std::path::{Path, PathBuf};
    fn main() {
        for s in ["/home/u/docs/report.final.pdf", "notes.tar.gz", ".bashrc", "dir/", "/", "a/b/.."] {
            let p = Path::new(s);
            println!("  {:<32} parent={:<22} file_name={:<18} stem={:<14} ext={:<8}", format!("{:?}", s), format!("{:?}", p.parent()), format!("{:?}", p.file_name()), format!("{:?}", p.file_stem()), format!("{:?}", p.extension()));
        }
        println!("  components(\\"a//b/./c/../d\\"): {:?}", Path::new("a//b/./c/../d").components().map(|c| format!("{:?}", c)).collect::<Vec<_>>());
    }
''', quiet_src=True); R['parts'] = r['out']
print()
print('== 二:join 的陷阱:拼接绝对路径会替换整个前缀;push 同样;with_extension / with_file_name')
r = tryit('u135b', '''
    use std::path::{Path, PathBuf};
    fn main() {
        let base = Path::new("/data/app");
        println!("  /data/app.join(\\"x/y.txt\\") = {:?}", base.join("x/y.txt"));
        println!("  /data/app.join(\\"/etc/passwd\\") = {:?}(拼接绝对路径,前缀被丢掉)", base.join("/etc/passwd"));
        println!("  /data/app.join(\\"../secret\\") = {:?}(.. 原样保留,不会被规范化)", base.join("../secret"));
        let mut p = PathBuf::from("/data"); p.push("a"); p.push("/b"); println!("  PathBuf::push 连续 push(\\"a\\") 与 push(\\"/b\\") = {:?}", p);
        println!("  with_extension(\\"md\\"): {:?}  with_extension(\\"\\"): {:?}  with_file_name(\\"z\\"): {:?}", Path::new("a/b.txt").with_extension("md"), Path::new("a/b.txt").with_extension(""), Path::new("a/b.txt").with_file_name("z"));
        println!("  \\"a.tar.gz\\".extension() = {:?}(只取最后一段),file_stem = {:?}", Path::new("a.tar.gz").extension(), Path::new("a.tar.gz").file_stem());
    }
''', quiet_src=True); R['join'] = r['out']
print()
print('== 三:按组件比较,不是按字符串:starts_with / strip_prefix / 相等 都忽略重复分隔符与结尾斜杠,但不解析 ..')
r = tryit('u135c', '''
    use std::path::Path;
    fn main() {
        println!("  \\"/a/b\\".starts_with(\\"/a\\") = {}   \\"/ab\\".starts_with(\\"/a\\") = {}(按组件,/ab 不是 /a 的子路径)", Path::new("/a/b").starts_with("/a"), Path::new("/ab").starts_with("/a"));
        println!("  \\"/a//b/\\" == \\"/a/b\\" = {}   \\"/a/./b\\" == \\"/a/b\\" = {}   \\"/a/c/../b\\" == \\"/a/b\\" = {}", Path::new("/a//b/") == Path::new("/a/b"), Path::new("/a/./b") == Path::new("/a/b"), Path::new("/a/c/../b") == Path::new("/a/b"));
        println!("  strip_prefix(\\"/a\\"):{:?}  strip_prefix(\\"/x\\"):{:?}", Path::new("/a/b/c").strip_prefix("/a"), Path::new("/a/b/c").strip_prefix("/x").map_err(|e| e.to_string()));
        println!("  \\"foo.txt\\".ends_with(\\"txt\\") = {}(按组件:txt 不是整个文件名)   ends_with(\\"foo.txt\\") = {}", Path::new("foo.txt").ends_with("txt"), Path::new("foo.txt").ends_with("foo.txt"));
    }
''', quiet_src=True); R['cmp'] = r['out']
print()
print('== 四:路径不一定是 UTF-8:Unix 的路径类型 OsStr 可以装任意字节;to_str 返回 Option,display / to_string_lossy 有损;在 macOS 的文件系统上创建这样的文件名则被拒绝')
r = tryit('u135d', '''
    #![allow(unused)]
    use std::{ffi::OsStr, os::unix::ffi::OsStrExt, path::Path, fs};
    fn main() {
        let dir = std::env::temp_dir().join("u135"); let _ = fs::remove_dir_all(&dir); fs::create_dir_all(&dir).unwrap();
        let name = OsStr::from_bytes(b"bad_\\xff\\xfe_name.txt"); let p = dir.join(name);
        println!("  构造路径本身没问题。文件名字节:{:?}", p.file_name().unwrap().as_bytes());
        println!("  to_str() = {:?}(不是合法 UTF-8,所以是 None)", p.to_str());
        println!("  to_string_lossy() 的文件名部分 = {:?}(非法字节被替换成 U+FFFD)", p.to_string_lossy().rsplit('/').next().unwrap());
        let ok = Path::new("ascii.txt"); println!("  对照:合法 UTF-8 路径 to_str() = {:?}", ok.to_str());
        match fs::write(&p, "x") { Ok(()) => println!("  在这个文件系统上创建该文件成功"), Err(e) => println!("  在这个文件系统上创建该文件失败:{}(kind = {:?})", e, e.kind()) }
        let _ = fs::remove_dir_all(&dir);
    }
''', quiet_src=True); R['nonutf'] = r['out']
print()
print('== 五:canonicalize 才真正解析 .. 与符号链接,但要求路径存在;不存在会报错')
r = tryit('u135e', '''
    use std::{fs, path::Path};
    fn main() {
        let d = std::env::temp_dir().join("u135e"); let _ = fs::remove_dir_all(&d); fs::create_dir_all(d.join("real/sub")).unwrap(); std::os::unix::fs::symlink(d.join("real"), d.join("link")).unwrap();
        let weird = d.join("link/sub/../sub"); println!("  未规范化:{}", weird.strip_prefix(&d).unwrap().display());
        let c = weird.canonicalize().unwrap(); println!("  canonicalize 之后相对 d:{}(.. 被折叠、符号链接被解析成 real)", c.strip_prefix(d.canonicalize().unwrap()).unwrap().display());
        println!("  不存在的路径 canonicalize: {:?}", d.join("nope/../x").canonicalize().map_err(|e| e.kind()));
        println!("  is_absolute: {} / {}", Path::new("/x").is_absolute(), Path::new("x/y").is_absolute());
        fs::remove_dir_all(&d).unwrap();
    }
''', quiet_src=True); R['canon'] = r['out']
save('u135', R)
