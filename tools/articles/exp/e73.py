import sqlite3, os, tempfile, time, json
d = tempfile.mkdtemp(); path = os.path.join(d, 'a.db')
def files(): return sorted(f for f in os.listdir(d))
print("sqlite 库版本 =", sqlite3.sqlite_version, "| sqlite3 模块 autocommit 默认 =", sqlite3.connect(':memory:').autocommit == sqlite3.LEGACY_TRANSACTION_CONTROL and 'LEGACY_TRANSACTION_CONTROL' or 'other')

print("\n== 一、隐式事务:什么时候悄悄 BEGIN ==")
c = sqlite3.connect(path); c.execute("create table t(id integer primary key, v text)"); c.commit()
def st(label): print(f"  {label:<38} in_transaction = {c.in_transaction}")
st("connect + create table + commit 之后")
c.execute("select * from t"); st("执行 SELECT 之后")
c.execute("insert into t(v) values ('a')"); st("执行 INSERT 之后")
c.rollback(); st("rollback() 之后")
print("  rollback 后表里行数 =", c.execute("select count(*) from t").fetchone()[0])
c.execute("create table t2(x)"); st("执行 DDL(create table) 之后")

print("\n== 二、别的连接看不到未提交的数据 ==")
w = sqlite3.connect(path, timeout=0.2); r = sqlite3.connect(path, timeout=0.2)
w.execute("insert into t(v) values ('uncommitted')")
print("  写连接自己看到行数 =", w.execute("select count(*) from t").fetchone()[0])
print("  读连接看到行数     =", r.execute("select count(*) from t").fetchone()[0])
print("  事务进行中, 目录里的文件:", files())
w3 = sqlite3.connect(path, timeout=0.2)
try:
    w3.execute("insert into t(v) values ('second writer')")
except sqlite3.OperationalError as e:
    print("  第二个写连接: OperationalError:", e)
w.commit()
print("  commit 后, 读连接看到行数 =", r.execute("select count(*) from t").fetchone()[0], "| 文件:", files())

print("\n== 三、with conn: 只管提交/回滚, 不管关闭 ==")
x = sqlite3.connect(path)
with x:
    x.execute("insert into t(v) values ('in with')")
print("  with 块结束后 in_transaction =", x.in_transaction, "| 连接还能用:", x.execute("select count(*) from t").fetchone()[0], "行")
try:
    with x:
        x.execute("insert into t(v) values ('will roll back')"); raise ValueError("boom")
except ValueError: pass
print("  异常出块后行数 =", x.execute("select count(*) from t").fetchone()[0], "(回滚了)")

print("\n== 四、读游标不关, 写方 commit 会怎样(默认 DELETE 日志 vs WAL) ==")
def scenario(mode):
    p = os.path.join(tempfile.mkdtemp(), 'b.db')
    a = sqlite3.connect(p, timeout=0.3); a.execute(f"pragma journal_mode={mode}"); a.execute("create table t(v)"); a.executemany("insert into t values (?)", [(i,) for i in range(5)]); a.commit()
    b = sqlite3.connect(p, timeout=0.3)
    cur = b.execute("select v from t"); first = cur.fetchone()   # 读连接持有一个还没读完的查询
    a.execute("insert into t values (99)")
    res = []
    try:
        a.commit(); res.append("commit 成功")
    except sqlite3.OperationalError as e:
        res.append(f"commit 失败: {e}")
    rows_b = len(cur.fetchall()) + 1 if True else 0
    return mode, res[0], os.listdir(os.path.dirname(p)), a.execute("pragma journal_mode").fetchone()[0]
for m in ('delete', 'wal'):
    mode, res, fl, jm = scenario(m)
    print(f"  journal_mode={jm:<7} 读连接有未读完的查询时, 写方 {res}; 目录: {fl}")

print("\n== 五、1万次 INSERT: 每次 commit vs 一个事务 ==")
def bench(kind, sync):
    p = os.path.join(tempfile.mkdtemp(), 'c.db'); c = sqlite3.connect(p); c.execute(f"pragma synchronous={sync}"); c.execute("create table t(v)"); c.commit()
    t = time.perf_counter()
    if kind == 'each':
        for i in range(1000): c.execute("insert into t values (?)", (i,)); c.commit()
        n = 1000
    else:
        for i in range(10000): c.execute("insert into t values (?)", (i,))
        c.commit(); n = 10000
    return n, (time.perf_counter()-t)*1000
for kind, sync in (('each', 'full'), ('each', 'off'), ('one', 'full')):
    n, ms = bench(kind, sync)
    print(f"  {'每条 commit' if kind=='each' else '一个事务提交':<12} synchronous={sync:<4} {n:>5} 行 用时 {ms:8.1f} ms  → 每行 {ms/n*1000:8.1f} µs")
