import os, sys, subprocess, tempfile, textwrap, json, unittest

W = os.path.realpath(tempfile.mkdtemp()); os.chdir(W)
def w(path, body):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True); open(path, 'w').write(textwrap.dedent(body).lstrip())
def P(x): return x.replace(W, '<项目>')
E = dict(os.environ); E.pop('HTTP_PROXY', None); E.pop('HTTPS_PROXY', None)
def run(args): 
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, env=E, cwd=W); return P((r.stdout + r.stderr).strip())

w('tests/__init__.py', "")
w('tests/test_math.py', '''
    import unittest
    print("  [import] tests/test_math.py 被导入")
    class TestAdd(unittest.TestCase):
        def test_b_second(self): pass
        def test_a_first(self): pass
        def test_c_third(self): pass
        def helper_check(self): raise AssertionError("不会被当成测试")
        def check_things(self): raise AssertionError("不会被当成测试")
    class NotATestCase:
        def test_ignored(self): raise AssertionError("不继承 TestCase, unittest 不会收集")
''')
w('tests/test_strings.py', '''
    import unittest
    print("  [import] tests/test_strings.py 被导入")
    class TestUpper(unittest.TestCase):
        def test_upper(self): self.assertEqual("a".upper(), "A")
        @unittest.skip("演示跳过")
        def test_skipped(self): pass
        @unittest.expectedFailure
        def test_expected_fail(self): self.assertEqual(1, 2)
''')
w('tests/strings_test.py', '''
    import unittest
    print("  [import] tests/strings_test.py 被导入 (不该出现: 文件名不匹配 test*.py)")
    class TestSuffix(unittest.TestCase):
        def test_x(self): pass
''')
w('tests/check_util.py', '''
    import unittest
    print("  [import] tests/check_util.py 被导入 (不该出现)")
    class TestU(unittest.TestCase):
        def test_x(self): pass
''')
w('tests/test_broken.py', '''
    import unittest
    import module_that_does_not_exist
''')
w('tests/nopkg/test_deep.py', '''
    import unittest
    print("  [import] tests/nopkg/test_deep.py 被导入")
    class TestDeep(unittest.TestCase):
        def test_deep(self): pass
''')
w('tests/pkg/__init__.py', "")
w('tests/pkg/test_inner.py', '''
    import unittest
    print("  [import] tests/pkg/test_inner.py 被导入")
    class TestInner(unittest.TestCase):
        def test_inner(self): pass
''')

print("== 一、目录结构 ==")
for root, dirs, files in sorted(os.walk('tests')):
    dirs[:] = sorted(d for d in dirs if d != '__pycache__')
    for f in sorted(files):
        if f.endswith('.py'): print("  ", os.path.join(root, f))

print("\n== 二、python -m unittest discover -v ==")
print(run(['-m', 'unittest', 'discover', '-s', 'tests', '-t', '.', '-v']))

print("\n== 三、只想看「会找到哪些」: 用 TestLoader 逐个模块记录 ==")
sys.path.insert(0, W)
seen = []
class SpyLoader(unittest.TestLoader):
    def loadTestsFromModule(self, module, *a, **k):
        suite = super().loadTestsFromModule(module, *a, **k); seen.append((module.__name__, suite.countTestCases())); return suite
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf): suite = SpyLoader().discover('tests', top_level_dir='.')
print("  discover 过程中 loadTestsFromModule 被调用的模块及其找到的用例数:")
for n, c in seen: print(f"     {n:<26} {c}")
print("  总用例数 suite.countTestCases() =", suite.countTestCases())
def names(s):
    for t in s:
        if isinstance(t, unittest.TestSuite): yield from names(t)
        else: yield t.id()
ids = sorted(names(suite)); print("  全部用例 id:"); [print("     ", i) for i in ids]

print("\n== 四、执行顺序: 同一个类里按方法名字母序(源码里写的顺序是 b, a, c) ==")
print("\n".join("  " + l for l in run(['-m', 'unittest', '-v', 'tests.test_math.TestAdd']).splitlines()[0:5] if l.strip()))

print("\n== 五、-k 过滤 与 不带参数的 python -m unittest ==")
print("$ python -m unittest discover -s tests -t . -k upper -v")
print("\n".join("  " + l for l in run(['-m', 'unittest', 'discover', '-s', 'tests', '-t', '.', '-k', 'upper', '-v']).splitlines() if l.startswith(('test_', 'tests.', 'Ran', 'FAILED', 'OK'))))
print("$ python -m unittest      (不带参数, 等价于 discover)")
print("\n".join("  " + l for l in run(['-m', 'unittest']).splitlines() if l.startswith(('Ran', 'FAILED', 'OK'))))
json.dump({'seen': seen, 'ids': ids}, open(os.path.join(os.environ['HERE'], 'out/97.json'), 'w'), ensure_ascii=False)
