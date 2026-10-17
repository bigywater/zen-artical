import os, sys, subprocess, tempfile, textwrap, json, shutil, time, importlib.metadata as md

HERE = os.environ['HERE']; W = os.path.realpath(tempfile.mkdtemp()); os.chdir(W)
E = dict(os.environ); E.pop('HTTP_PROXY', None); E.pop('HTTPS_PROXY', None); E['BUILD_LOG'] = os.path.join(W, 'b.log')
def P(x): return x.replace(W, '<工作目录>')
def sh(args, **kw): return subprocess.run(args, capture_output=True, text=True, env=E, **kw)

os.makedirs('proj/backend'); os.makedirs('proj/src/hello_app')
shutil.copy(HERE + '/exp/mybackend2.py', 'proj/backend/mybackend.py')
open('proj/pyproject.toml', 'w').write(textwrap.dedent('''
    [build-system]
    requires = []
    build-backend = "mybackend"
    backend-path = ["backend"]

    [project]
    name = "hello-app"
    version = "0.2.0"

    [project.scripts]
    hello-cli = "hello_app.cli:main"

    [project.entry-points."hello_app.plugins"]
    upper = "hello_app.plugins:upper"
    reverse = "hello_app.plugins:reverse"
'''))
open('proj/src/hello_app/__init__.py', 'w').write("print('  [hello_app 包被导入了]')\n")
open('proj/src/hello_app/cli.py', 'w').write("import sys\ndef main():\n    print('hello-cli 运行, argv =', sys.argv[1:])\n    return 0\n")
open('proj/src/hello_app/plugins.py', 'w').write("print('  [plugins 模块被导入了]')\ndef upper(s): return s.upper()\ndef reverse(s): return s[::-1]\n")

print("== 一、新建一个干净的虚拟环境, 安装项目 ==")
sh([sys.executable, '-m', 'venv', 'env'])
py = os.path.join(W, 'env/bin/python')
r = sh([HERE + '/venv/bin/python', '-m', 'pip', '--python', py, 'install', '--no-deps', '--no-index', './proj'])
print("  pip install ./proj → 返回码", r.returncode, "|", P(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else P(r.stderr[-200:]))
di = [d for d in os.listdir('env/lib/python3.14/site-packages') if d.endswith('.dist-info')]
print("  site-packages 里的 dist-info:", di)
di = [d for d in di if d.startswith('hello_app')]
print("  hello_app 的 entry_points.txt 内容:"); print("    " + open(f'env/lib/python3.14/site-packages/{di[0]}/entry_points.txt').read().strip().replace('\n', '\n    '))

print("\n== 二、console_scripts: pip 生成的启动脚本 ==")
print("  env/bin/ 里多了:", [f for f in os.listdir('env/bin') if 'hello' in f])
print("  env/bin/hello-cli 的内容:"); print("    " + P(open('env/bin/hello-cli').read().strip().replace(W, '<工作目录>')).replace('\n', '\n    '))
r = sh([os.path.join(W, 'env/bin/hello-cli'), 'a', 'b']); print("  运行 hello-cli a b →", r.stdout.strip() or r.stderr.strip())

print("\n== 三、插件发现: 在另一个进程里按组名查 entry_points ==")
code = textwrap.dedent('''
    import importlib.metadata as md, sys
    eps = md.entry_points(group="hello_app.plugins")
    print("  找到", len(eps), "个:", sorted(e.name for e in eps))
    print("  此时 hello_app 被导入了吗?", "hello_app" in sys.modules, "(只读了元数据文件, 没导入代码)")
    for e in sorted(eps, key=lambda e: e.name): print(f"  EntryPoint: name={e.name!r} value={e.value!r} group={e.group!r} dist={e.dist.name}=={e.dist.version}")
    f = eps["upper"].load()
    print("  load() 之后 hello_app 被导入了吗?", "hello_app" in sys.modules)
    print("  upper('abc') =", f("abc"))
''')
print(P(sh([py, '-c', code]).stdout.rstrip()))

print("\n== 四、不装包, 手工放一个 dist-info 也能被「发现」 ==")
sp = os.path.join(W, 'env/lib/python3.14/site-packages'); fake = os.path.join(sp, 'fake_plugin-1.0.dist-info'); os.makedirs(fake)
open(fake + '/METADATA', 'w').write("Metadata-Version: 2.1\nName: fake-plugin\nVersion: 1.0\n")
open(fake + '/entry_points.txt', 'w').write("[hello_app.plugins]\nghost = nowhere.module:func\n")
code2 = textwrap.dedent('''
    import importlib.metadata as md
    eps = md.entry_points(group="hello_app.plugins")
    print("  现在找到:", sorted(e.name for e in eps))
    try: eps["ghost"].load()
    except Exception as e: print("  ghost 的 load() →", type(e).__name__ + ":", e)
''')
print(sh([py, '-c', code2]).stdout.rstrip()); shutil.rmtree(fake)

print("\n== 五、卸载后 ==")
r = sh([HERE + '/venv/bin/python', '-m', 'pip', '--python', py, 'uninstall', '-y', 'hello-app']); print("  pip uninstall →", r.returncode)
print("  env/bin/ 里还有 hello-cli?", os.path.exists('env/bin/hello-cli'), "| 再查 entry_points:", sh([py, '-c', 'import importlib.metadata as md; print(sorted(e.name for e in md.entry_points(group="hello_app.plugins")))']).stdout.strip())

print("\n== 六、entry_points() 要扫描所有已安装的包: 数量越多越慢 ==")
res = []
for n in (0, 100, 400, 1600):
    d = tempfile.mkdtemp()
    for i in range(n):
        di_ = os.path.join(d, f'pkg{i}-1.0.dist-info'); os.makedirs(di_)
        open(di_ + '/METADATA', 'w').write(f"Metadata-Version: 2.1\nName: pkg{i}\nVersion: 1.0\n")
        open(di_ + '/entry_points.txt', 'w').write(f"[x.plugins]\np{i} = m{i}:f\n")
    code3 = f"import sys, time; sys.path.insert(0, {d!r}); import importlib.metadata as md; t = time.perf_counter(); e = md.entry_points(group='x.plugins'); print((time.perf_counter() - t) * 1000, len(e))"
    ts = sorted(float(sh([sys.executable, '-c', code3]).stdout.split()[0]) for _ in range(5))[2]
    res.append((n, ts)); shutil.rmtree(d)
    print(f"  额外 {n:>5} 个已安装的包(每个一个 entry point): entry_points(group=...) 用时 {ts:7.2f} ms (5 次取中位数)")
json.dump({'res': res}, open(HERE + '/out/95.json', 'w'))
