import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f89'); R = {}
import dj
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy import event, orm
pg = dj.PG(9460, name='f89pg').start()
try:
    app = Flask('f'); app.logger.disabled = True; app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'; db = SQLAlchemy(app)
    class Author(db.Model):
        id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(20)); created = db.Column(db.DateTime, server_default=sa.func.now())
        books = db.relationship('Book', back_populates='author')
    class Book(db.Model):
        id = db.Column(db.Integer, primary_key=True); title = db.Column(db.String(20)); author_id = db.Column(db.ForeignKey('author.id')); author = db.relationship(Author, back_populates='books')
    sql = []
    with app.app_context():
        db.drop_all(); db.create_all(); event.listen(db.engine, 'before_cursor_execute', lambda c, cur, st, p, ctx, m: sql.append(' '.join(st.split())))
    def other(q): return pg.psql(q)
    def short(s, n=95): return s if len(s) <= n else s[:n] + '…'
    print('== 一:flush 把 SQL 发给数据库(在事务里),别的连接看不到;commit 之后才可见')
    with app.app_context():
        a = Author(name='f1'); print('  add 之前主键 a.id =', a.id); db.session.add(a); print('  add 之后、flush 之前 a.id =', a.id)
        sql.clear(); db.session.flush(); print(f'  flush 之后 a.id = {a.id},发了 {len(sql)} 条:', [short(x) for x in sql[:3]])
        print('  此时另一个连接查询 author 表里 f1 的行数:', other("select count(*) from author where name='f1'"), '(本会话自己查询能看到)'); R['vis_flush'] = other("select count(*) from author where name='f1'")
        db.session.commit(); print('  commit 之后另一个连接查询:', other("select count(*) from author where name='f1'")); R['vis_commit'] = other("select count(*) from author where name='f1'")
    print()
    print('== 二:autoflush:查询之前会自动 flush 待写入的对象')
    with app.app_context():
        sql.clear(); db.session.add(Author(name='auto')); n = db.session.execute(sa.select(sa.func.count()).select_from(Author).where(Author.name == 'auto')).scalar()
        print(f'  add 之后直接查询:count = {n}(查询之前先发了 INSERT:', [short(x, 30) for x in sql], ')'); R['autoflush'] = [n, [x.split()[0] for x in sql]]
        db.session.rollback()
        sql.clear(); db.session.add(Author(name='auto')); 
        with db.session.no_autoflush: n = db.session.execute(sa.select(sa.func.count()).select_from(Author).where(Author.name == 'auto')).scalar()
        print(f'  no_autoflush 里查询:count = {n}(发了 {[x.split()[0] for x in sql]},INSERT 还没发)'); R['no_autoflush'] = [n, [x.split()[0] for x in sql]]
        db.session.rollback()
    print()
    print('== 三:flush 之后 server_default 的值要不要再读一次?(PostgreSQL 上)')
    with app.app_context():
        a = Author(name='sd'); db.session.add(a); sql.clear(); db.session.flush()
        print('  flush 之后 a.created 属性是否已加载:', 'created' in sa.inspect(a).dict, '| flush 发了', len(sql), '条', [x.split()[0] for x in sql])
        sql.clear(); v = a.created; print(f'  访问 a.created → 再发 {len(sql)} 条 SELECT 去取;值的类型 {type(v).__name__}'); R['sd'] = [len(sql), type(v).__name__]
        db.session.rollback()
    print()
    print('== 四:flush 的 SQL 顺序与批量:先 INSERT author 再 INSERT book(按外键依赖排序);100 个对象一条语句')
    with app.app_context():
        au = Author(name='dep'); bk = [Book(title=f'b{i}', author=au) for i in range(3)]
        db.session.add_all(bk[::-1]); sql.clear(); db.session.flush(); print('  把 3 本书(反序)加进 session 后 flush,SQL 顺序:', [x.split(' ')[2] for x in sql]); R['order'] = [x.split(' ')[2] for x in sql]
        db.session.rollback()
        sql.clear(); db.session.add_all([Author(name=f'm{i}') for i in range(100)]); db.session.flush(); print(f'  100 个 Author 一次 flush:发了 {len(sql)} 条 SQL(psycopg 的 insertmanyvalues 批量插入)'); R['batch'] = len(sql)
        db.session.rollback()
    print()
    print('== 五:flush 之后 rollback 能撤销已经发出的 INSERT')
    with app.app_context():
        db.session.add(Author(name='gone')); db.session.flush(); db.session.rollback(); print('  flush 后 rollback,库里的 gone:', other("select count(*) from author where name='gone'"))
    print()
    print('== 六:一次 flush 一个对象 vs 全部加完再 commit(1000 个 Author,各 5 次取中位数)')
    res = {}
    for label in ('每个对象都 flush', '每个对象都 commit', '全部 add 后一次 commit'):
        L = []
        for _ in range(5):
            with app.app_context():
                t0 = time.perf_counter()
                if label == '每个对象都 flush':
                    for i in range(1000): db.session.add(Author(name='x')); db.session.flush()
                    db.session.commit()
                elif label == '每个对象都 commit':
                    for i in range(1000): db.session.add(Author(name='x')); db.session.commit()
                else:
                    db.session.add_all([Author(name='x') for i in range(1000)]); db.session.commit()
                L.append(ms(t0)); db.session.execute(sa.delete(Author).where(Author.name == 'x')); db.session.commit()
        res[label] = median(L); print(f'  {label:<24} {median(L):>8.1f} ms')
    R['cost'] = res
finally:
    pg.stop()
save('f89', R)
