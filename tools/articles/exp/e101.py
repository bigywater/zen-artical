import os, sys, subprocess, tempfile, textwrap, json, time, re, shutil

HERE = os.environ['HERE']; W = os.path.realpath(tempfile.mkdtemp()); os.chdir(W)
V = HERE + '/venv/bin'
E = dict(os.environ); E.pop('HTTP_PROXY', None); E.pop('HTTPS_PROXY', None)
E['VIRTUALENV_OVERRIDE_APP_DATA'] = os.path.join(HERE, 'vdata'); E['PATH'] = '/opt/homebrew/bin:/usr/bin:/bin'; E['NO_COLOR'] = '1'; E['PY_COLORS'] = '0'
E['NOX_DEFAULT_VENV_BACKEND'] = 'venv'
def w(path, body):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True); open(path, 'w').write(textwrap.dedent(body).lstrip())
def run(args, **kw):
    t = time.perf_counter(); r = subprocess.run(args, capture_output=True, text=True, env=E, cwd=W, **kw); el = time.perf_counter() - t
    return r.returncode, (r.stdout + r.stderr).strip().replace(W, '<项目>').replace(HERE, '<scratch>'), el

w('feat.py', '''
    import sys
    def features():
        out = {"python": ".".join(map(str, sys.version_info[:3]))}
        try:
            import annotationlib; out["annotationlib"] = True
        except ImportError:
            out["annotationlib"] = False
        try:
            compile('t"hello {1}"', "<t>", "eval"); out["t_strings"] = True
        except SyntaxError:
            out["t_strings"] = False
        return out
''')
w('check.py', '''
    import sys
    from feat import features
    f = features()
    parts = sys.executable.split("/"); k = next(i for i, x in enumerate(parts) if x in (".tox", ".nox"))
    print("  解释器:", "/".join(parts[k:k + 2]), "| 版本", f["python"])
    print("  annotationlib(3.14 才有):", f["annotationlib"], "| t-string 语法(3.14 才有):", f["t_strings"])
    assert f["t_strings"], "本项目需要 3.14 的 t-string"
''')
print("== 一、tox: 一份配置, 多个解释器 ==")
w('tox.ini', '''
    [tox]
    envlist = py312, py314
    skipsdist = true

    [testenv]
    skip_install = true
    commands = python check.py
''')
print(open('tox.ini').read().strip())
print("\n$ tox   (第一次: 需要创建两个虚拟环境)")
rc, out, t1 = run([V + '/tox', '-e', 'py312,py314', '--skip-missing-interpreters=false', '-c', 'tox.ini']); 
print(f"  返回码 {rc} | 耗时 {t1:.1f} s"); print("\n".join("  " + l for l in out.splitlines() if ('py3' in l and 'commands' in l) or '解释器' in l or 'annotationlib' in l or 'AssertionError' in l or 'FAIL' in l or ' OK' in l or 'exit' in l))
print("  .tox 目录:", sorted(os.listdir('.tox')), "| py312 里的 python:", os.path.realpath('.tox/py312/bin/python').replace('/opt/homebrew/Cellar', '<brew>') if os.path.exists('.tox/py312/bin/python') else '?')
print("\n$ tox   (第二次: 环境已存在, 直接复用)")
rc2, out2, t2 = run([V + '/tox', '-e', 'py312,py314', '-c', 'tox.ini']); print(f"  返回码 {rc2} | 耗时 {t2:.1f} s")
print("\n$ tox -r   (强制重建环境)")
rc3, out3, t3 = run([V + '/tox', '-r', '-e', 'py312,py314', '-c', 'tox.ini']); print(f"  返回码 {rc3} | 耗时 {t3:.1f} s")
print("\n  tox 的汇总行:"); print("\n".join("    " + l for l in out.splitlines() if l.strip().startswith(('py312:', 'py314:', 'evaluation')) and ('FAIL' in l or 'OK' in l or 'failed' in l)))

print("\n== 二、nox: 用 Python 代码写同样的事 ==")
w('noxfile.py', '''
    import nox
    nox.options.default_venv_backend = "venv"
    nox.options.reuse_existing_virtualenvs = False

    @nox.session(python=["3.12", "3.14"])
    def tests(session):
        session.run("python", "check.py")

    @nox.session(python="3.14")
    def only_new(session):
        # 用 Python 写逻辑: 按解释器版本决定要不要做某件事
        if session.python == "3.14":
            session.log("这一步只在 3.14 上做")
        session.run("python", "-c", "import sys; print('  only_new 在', sys.version_info[:2])")
''')
print(open('noxfile.py').read().strip())
rc, out, tl = run([V + '/nox', '-l', '-f', 'noxfile.py']); print("\n$ nox -l\n" + "\n".join("  " + l for l in out.splitlines()))
rc, out, tn = run([V + '/nox', '-f', 'noxfile.py', '-s', 'tests'])
print(f"\n$ nox -s tests   返回码 {rc} | 耗时 {tn:.1f} s"); print("\n".join("  " + l for l in out.splitlines() if l.strip().startswith(('nox >', '解释器', 'annotationlib')) or '解释器' in l or 'annotationlib' in l))
print("  .nox 目录:", sorted(os.listdir('.nox')))
rc, out, _ = run([V + '/nox', '-f', 'noxfile.py', '-s', 'only_new']); print("\n$ nox -s only_new"); print("\n".join("  " + l for l in out.splitlines() if 'nox >' in l or 'only_new' in l))
json.dump({'t': [t1, t2, t3, tn]}, open(HERE + '/out/101.json', 'w'))
