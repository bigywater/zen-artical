import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d115'); R = {}
pg = PG(9472).start()
models = "from django.db import models\nclass Author(models.Model):\n    name = models.CharField(max_length=20)\nclass Post(models.Model):\n    title = models.CharField(max_length=20)\n    author = models.ForeignKey(Author, on_delete=models.CASCADE)\n"
d = proj('d115', files={'lab/models.py': models}, databases=pg.databases(), apps=['django.contrib.contenttypes', 'lab'], middleware=[])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
pg.psql("insert into lab_author (name) values ('ann'); insert into lab_post (title, author_id) values ('p1', 1)")
def run(code, timeout=120): rc, out = pyscript(d, "import asyncio, logging, threading, time; logging.disable(logging.CRITICAL)\nfrom lab.models import *\nfrom django.db import connection, transaction\nfrom asgiref.sync import sync_to_async\n" + code, timeout); return out.rstrip()
print('== 一:外键的懒加载在 async 里')
o = run("""
async def main():
    p = await Post.objects.afirst()
    try: print('  post.author (没有 select_related):', p.author)
    except Exception as e: print('  post.author (没有 select_related) →', type(e).__name__ + ':', str(e)[:70])
    p = await Post.objects.select_related('author').afirst(); print('  select_related("author") 之后 post.author:', p.author.name)
    a = await p.__class__.author.get_queryset().aget() if False else None
    try: print('  反向 author.post_set.all() 遍历:', [x.title for x in p.author.post_set.all()])
    except Exception as e: print('  遍历 author.post_set.all() →', type(e).__name__)
    print('  async for 遍历 author.post_set.all():', [x.title async for x in p.author.post_set.all()])
asyncio.run(main())
""")
print(o); R['fk'] = o
print()
print('== 二:事务')
o = run("""
async def main():
    try:
        with transaction.atomic(): pass
    except Exception as e: print('  async 里 with transaction.atomic() →', type(e).__name__)
    try:
        async with transaction.atomic(): pass
    except Exception as e: print('  async with transaction.atomic() →', type(e).__name__ + ':', str(e)[:60])
    @sync_to_async
    def tx():
        with transaction.atomic(): Author.objects.create(name='tx'); return Author.objects.count()
    print('  把事务放进 sync_to_async 包起来的同步函数里 → 成功,Author 数', await tx())
asyncio.run(main())
""")
print(o); R['tx'] = o
print()
print('== 三:async ORM 到底在哪个线程里执行 SQL?(给 SQLCompiler.execute_sql 打点)')
o = run("""
from django.db.models.sql.compiler import SQLCompiler
orig = SQLCompiler.execute_sql; seen = []
def patched(self, *a, **k): seen.append(threading.current_thread().name); return orig(self, *a, **k)
SQLCompiler.execute_sql = patched
async def main():
    print('  事件循环所在线程:', threading.current_thread().name)
    await Post.objects.acount(); await Author.objects.aget(pk=1)
    print('  acount() / aget() 执行 SQL 的线程:', seen)
asyncio.run(main())
""")
print(o); R['thread'] = o
print()
print('== 四:并发:gather 10 个各要 0.2 s 的 async 查询(PostgreSQL pg_sleep),同时另开连接数一数 Django 用了几个数据库连接')
o = run("""
from django.db.models.expressions import RawSQL
import psycopg
def q(): return Author.objects.annotate(s=RawSQL('select pg_sleep(0.2)', [])).afirst()
async def count_conn():
    await asyncio.sleep(0.12)
    def f():
        c = psycopg.connect(host='127.0.0.1', port=%d, user='lab', dbname='lab', autocommit=True)
        return c.execute("select count(*) from pg_stat_activity where datname='lab' and pid <> pg_backend_pid() and state = 'active' and query like '%%%%pg_sleep%%%%'").fetchone()[0]
    return await asyncio.to_thread(f)
async def main():
    await Author.objects.acount()
    t0 = time.perf_counter(); res = await asyncio.gather(*[q() for _ in range(10)], count_conn()); print(f'  10 个 async 查询(默认 thread_sensitive)总耗时 {(time.perf_counter() - t0) * 1000:.0f} ms;此刻正在执行 pg_sleep 的连接数:', res[-1])
    @sync_to_async(thread_sensitive=False)
    def q2():
        try: return Author.objects.annotate(s=RawSQL('select pg_sleep(0.2)', [])).first()
        finally: connection.close()
    t0 = time.perf_counter(); res = await asyncio.gather(*[q2() for _ in range(10)], count_conn()); print(f'  10 个 thread_sensitive=False 的同步查询总耗时 {(time.perf_counter() - t0) * 1000:.0f} ms;此刻正在执行 pg_sleep 的连接数:', res[-1], '(每个线程各开自己的连接)')
asyncio.run(main())
""" % pg.port)
print(o); R['conc'] = o
pg.stop(); save('d115', R)
