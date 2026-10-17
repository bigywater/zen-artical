import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d99'); R = {}
models = "from django.db import models\nclass Author(models.Model):\n    name = models.CharField(max_length=20)\nclass Post(models.Model):\n    title = models.CharField(max_length=20)\n    author = models.ForeignKey(Author, on_delete=models.CASCADE)\n"
tests = '''
from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from lab.models import Author, Post
class QueryCountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        a = Author.objects.create(name='a'); Post.objects.bulk_create([Post(title=f't{i}', author=a) for i in range(5)])
    def test_pass_exact(self):
        with self.assertNumQueries(1): list(Post.objects.all())
    def test_fail_n_plus_one(self):
        with self.assertNumQueries(2): [p.author.name for p in Post.objects.all()]
    def test_fixed_with_select_related(self):
        with self.assertNumQueries(1): [p.author.name for p in Post.objects.select_related('author')]
    def test_capture_upper_bound(self):
        with CaptureQueriesContext(connection) as ctx: [p.author.name for p in Post.objects.select_related('author')]
        self.assertLessEqual(len(ctx), 1, 'queries: %s' % [q['sql'][:60] for q in ctx.captured_queries])
    def test_atomic_counts_savepoints(self):
        with self.assertNumQueries(3):
            with transaction.atomic(): Author.objects.create(name='x')
class TxTests(TransactionTestCase):
    def test_atomic_counts_begin_commit(self):
        with self.assertNumQueries(3):
            with transaction.atomic(): Author.objects.create(name='x')
'''
d = proj('d99', files={'lab/models.py': models, 'lab/tests.py': tests}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab')
rc, out = manage(d, 'test', 'lab', '-v', '2')
lines = out.splitlines()
print('== 一:运行 manage.py test lab -v 2 的结果')
for l in lines:
    if re.search(r'^test_|\.\.\. (ok|FAIL|ERROR)$|^(Ran|OK|FAILED)', l): print('  ', l)
R['summary'] = [l for l in lines if re.search(r'\.\.\. (ok|FAIL|ERROR)$|^(Ran|OK|FAILED)', l)]
print()
print('== 二:assertNumQueries 失败时的报错原文(把每条 SQL 列出来)')
i = next(k for k, l in enumerate(lines) if l.startswith('FAIL: test_fail_n_plus_one') or 'test_fail_n_plus_one' in l and l.startswith('FAIL'))
blk = []
for l in lines[i:i + 30]:
    blk.append(l[:170])
    if l.startswith('----') and len(blk) > 6: break
print('  ' + '\n  '.join(blk[:22])); R['fail_msg'] = blk[:22]
print()
print('== 三:数据库里的 TestCase 与 TransactionTestCase:同一段 atomic 代码的查询数')
print('  TestCase 包了一层事务,所以 atomic 变成 SAVEPOINT / RELEASE SAVEPOINT(3 条:SAVEPOINT + INSERT + RELEASE);TransactionTestCase 没有外层事务,atomic 是 BEGIN / COMMIT(同样 3 条)。数字相同,但里面的内容不同。')
rc, o = pyscript(d, """
import logging; logging.disable(logging.CRITICAL)
from django.test.runner import DiscoverRunner
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.test import TestCase, TransactionTestCase
import unittest
from lab.models import Author
class A(TestCase):
    def test(self):
        with CaptureQueriesContext(connection) as c:
            with transaction.atomic(): Author.objects.create(name='x')
        print('TestCase        :', [q['sql'][:34] for q in c.captured_queries])
class B(TransactionTestCase):
    def test(self):
        with CaptureQueriesContext(connection) as c:
            with transaction.atomic(): Author.objects.create(name='x')
        print('TransactionTest :', [q['sql'][:34] for q in c.captured_queries])
r = DiscoverRunner(verbosity=0); r.setup_test_environment(); old = r.setup_databases()
suite = unittest.TestSuite([A('test'), B('test')]); unittest.TextTestRunner(verbosity=0, stream=open(__import__('os').devnull, 'w')).run(suite)
r.teardown_databases(old); r.teardown_test_environment()
""")
print('  ' + o.strip().replace('\n', '\n  ')); R['tx'] = o.strip()
save('d99', R)
