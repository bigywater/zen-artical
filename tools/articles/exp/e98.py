import os, sys, subprocess, tempfile, textwrap, json, time, re

HERE = os.environ['HERE']; W = os.path.realpath(tempfile.mkdtemp()); os.chdir(W)
PY = HERE + '/venv/bin/python'
E = dict(os.environ); E.pop('HTTP_PROXY', None); E.pop('HTTPS_PROXY', None)
def w(path, body): open(path, 'w').write(textwrap.dedent(body).lstrip())
def pt(*args):
    r = subprocess.run([PY, '-m', 'pytest', '-p', 'no:cacheprovider', '--no-header', '-W', 'ignore', *args], capture_output=True, text=True, env=E, cwd=W)
    return (r.stdout + r.stderr).strip().replace(W + '/', '')
print("pytest 版本:", subprocess.run([PY, '-m', 'pytest', '--version'], capture_output=True, text=True).stdout.strip() or subprocess.run([PY, '-m', 'pytest', '--version'], capture_output=True, text=True).stderr.strip())

w('slug.py', '''
    import re
    def slugify(s):
        s = s.strip().lower()
        s = re.sub(r"[^a-z0-9]+", "-", s)
        return s.strip("-")
''')
w('test_slug.py', '''
    import pytest
    from slug import slugify

    @pytest.mark.parametrize("raw, expected", [
        ("Hello World", "hello-world"),
        ("  spaced  out  ", "spaced-out"),
        ("Already-Slug", "already-slug"),
        ("Café Crème", "cafe-creme"),         # 期望「去重音」, 但 slugify 没做
        ("", ""),
        ("---", ""),
        ("A_B_C", "a-b-c"),
        ("a--b", "a-b"),
        ("Ünï", "uni"),                        # 又一个「期望去重音」的用例
        ("2026年9月", "2026-9"),
    ])
    def test_slugify(raw, expected):
        assert slugify(raw) == expected
''')
print("\n== 一、8 组参数 = 8 个独立用例, 失败的能精确定位 ==")
print(pt('test_slug.py', '-v', '--tb=line', '-rf'))

w('test_loop.py', '''
    from slug import slugify
    CASES = [("Hello World", "hello-world"), ("Café Crème", "cafe-creme"), ("A_B_C", "a-b-c"),
        ("a--b", "a-b"), ("Ünï", "uni"), ("2026年9月", "2026-9")]
    def test_slugify_loop():
        for raw, expected in CASES:
            assert slugify(raw) == expected, (raw, expected)
''')
print("\n== 二、对照: 写成 for 循环 ==")
print(pt('test_loop.py', '-v', '--tb=line'))

w('test_ids.py', '''
    import pytest
    @pytest.mark.parametrize("x", [1, "a b", None, 3.5, (1, 2), [1], {"k": 1}, object(), b"raw", "长" * 60])
    def test_default_ids(x): pass

    @pytest.mark.parametrize("x, y", [pytest.param(1, 2, id="small"), pytest.param(10**9, 2, id="big"),
                                       pytest.param(0, 0, id="zero", marks=pytest.mark.skip(reason="演示")),
                                       pytest.param(-1, 1, id="known-bug", marks=pytest.mark.xfail(reason="已知问题"))])
    def test_custom(x, y): assert x + y > 0
''')
print("\n== 三、用例 id 是怎么生成的 ==")
out = pt('test_ids.py', '--collect-only', '-q')
print("\n".join(l for l in out.splitlines() if '::' in l))
print("  运行(-v):"); print("\n".join(l for l in pt('test_ids.py', '-v', '-k', 'custom').splitlines() if '::' in l or 'passed' in l or 'skipped' in l or 'xfail' in l))

w('test_matrix.py', '''
    import pytest
    @pytest.mark.parametrize("browser", ["chrome", "firefox", "safari"])
    @pytest.mark.parametrize("os_", ["mac", "linux", "win", "bsd"])
    def test_matrix(browser, os_): pass
''')
print("\n== 四、叠加两个 parametrize = 笛卡尔积 ==")
out = pt('test_matrix.py', '--collect-only', '-q'); lines = [l for l in out.splitlines() if '::' in l]
print(f"  3 个浏览器 × 4 个系统 → {len(lines)} 个用例; 前 5 个 id:"); [print("    ", l) for l in lines[:5]]
print("  选择其中一个: pytest 'test_matrix.py::test_matrix[mac-firefox]' →", pt('test_matrix.py::test_matrix[mac-firefox]', '-v').splitlines()[0].split(' ')[0:2])
print("  -k 'firefox and not win' →", pt('test_matrix.py', '--collect-only', '-q', '-k', 'firefox and not win').splitlines()[-1])

w('test_shared.py', '''
    import pytest
    SHARED = []
    @pytest.mark.parametrize("box", [SHARED, SHARED, SHARED])
    def test_shared_list(box):
        box.append(1)
        assert len(box) == 1, f"想当然每次都是全新列表, 实际长度 {len(box)}"
''')
print("\n== 五、陷阱: 可变对象在各个用例之间是同一个 ==")
print("\n".join(l for l in pt('test_shared.py', '--tb=line').splitlines() if 'assert' in l.lower() or 'passed' in l or 'failed' in l))

w('gen.py', '''
    import pytest
    N = 3000
    @pytest.mark.parametrize("n", range(N))
    def test_many(n): assert n * 2 == n + n
    def test_loop():
        for n in range(N): assert n * 2 == n + n
''')
print("\n== 六、开销: 3000 个参数化用例 vs 一个用例里循环 3000 次 ==")
def timed(*a):
    t = time.perf_counter(); o = pt(*a); return (time.perf_counter() - t), o.splitlines()[-1]
tp, lp = timed('gen.py', '-k', 'test_many'); tl, ll = timed('gen.py', '-k', 'test_loop')
print(f"  参数化 3000 例: 总耗时 {tp:.2f} s | {lp}")
print(f"  单个用例循环:   总耗时 {tl:.2f} s | {ll}")
json.dump({'lines': lines, 'tp': tp, 'tl': tl}, open(HERE + '/out/98.json', 'w'), ensure_ascii=False)
