import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f85'); R = {}
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy import event, orm
N_AUTH, N_BOOK = 10, 5
def setup(lazy):
    app = Flask('l'); app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'; db = SQLAlchemy(app)
    class Author(db.Model):
        id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(20))
        books = db.relationship('Book', back_populates='author', lazy=lazy)
    class Book(db.Model):
        id = db.Column(db.Integer, primary_key=True); title = db.Column(db.String(20)); author_id = db.Column(db.ForeignKey('author.id')); author = db.relationship(Author, back_populates='books')
    with app.app_context():
        db.create_all()
        for i in range(N_AUTH): db.session.add(Author(name=f'a{i}', books=[Book(title=f'b{i}-{j}') for j in range(N_BOOK)]))
        db.session.commit(); db.session.remove()
    return app, db, Author, Book
class Counter:
    def __init__(self, db): self.db = db; self.sql = []; event.listen(db.engine, 'before_cursor_execute', self._cb)
    def _cb(self, conn, cur, stmt, params, ctx, many): self.sql.append(' '.join(stmt.split()))
    def reset(self): self.sql.clear()
    def done(self): event.remove(self.db.engine, 'before_cursor_execute', self._cb)
def short(s, n=110): return s if len(s) <= n else s[:n] + '…'
print('== 一:默认 lazy="select":访问关系属性的那一刻才发 SQL,同一个对象第二次访问不再发')
app, db, Author, Book = setup('select')
with app.app_context():
    c = Counter(db); a = db.session.execute(sa.select(Author).limit(1)).scalar_one(); n0 = len(c.sql)
    print(f'  取出 1 个 Author:{n0} 条 SQL'); _ = a.books; n1 = len(c.sql); print(f'  第一次访问 a.books:新增 {n1 - n0} 条 →', short(c.sql[-1]))
    _ = a.books; _ = list(a.books); print(f'  再访问 a.books 两次:新增 {len(c.sql) - n1} 条'); R['lazy1'] = [n0, n1 - n0, len(c.sql) - n1]
    c.reset(); b = db.session.execute(sa.select(Book).where(Book.id == 1)).scalar_one(); c.reset(); _ = b.author; print(f'  多对一 b.author:{len(c.sql)} 条(Author 1 已经在这个 session 的身份映射里,直接取不发 SQL)'); R['m2o_cached'] = len(c.sql)
    db.session.expunge_all(); b = db.session.execute(sa.select(Book).where(Book.id == 1)).scalar_one(); c.reset(); _ = b.author; print(f'  清空 session 后再取 b.author:{len(c.sql)} 条 →', short(c.sql[-1])); R['m2o_fresh'] = len(c.sql)
    c.done()
print()
print('== 二:各种 lazy 策略:取 10 个作者并遍历每个人的 5 本书,各发了几条 SQL?')
print(f'  {"lazy=":<12} {"SQL 条数":<8} 说明')
R['modes'] = {}
for lazy in ('select', 'joined', 'subquery', 'selectin', 'immediate'):
    app, db, Author, Book = setup(lazy)
    with app.app_context():
        c = Counter(db); authors = db.session.execute(sa.select(Author)).unique().scalars().all(); total = sum(len(x.books) for x in authors)
        print(f'  {lazy:<12} {len(c.sql):<8} {short(c.sql[0], 80)}'); R['modes'][lazy] = [len(c.sql), total]; c.done()
import warnings
for lazy in ('raise', 'noload'):
    with warnings.catch_warnings(record=True) as wl:
        warnings.simplefilter('always'); app, db, Author, Book = setup(lazy)
    wl = [w for w in wl if 'Deprecation' in type(w.message).__name__]
    if wl: print('  (noload 触发的警告:', type(wl[0].message).__name__ + ':', str(wl[0].message)[:60] + '…)'); R['noload_warn'] = type(wl[0].message).__name__
    with app.app_context():
        c = Counter(db); authors = db.session.execute(sa.select(Author)).scalars().all()
        try: total = sum(len(x.books) for x in authors); r_ = f'访问到 {total} 本'
        except Exception as e: r_ = f'{type(e).__name__}: {str(e)[:70]}'
        print(f'  {lazy:<12} {len(c.sql):<8} 访问 books → {r_}'); R['modes'][lazy] = [len(c.sql), r_]; c.done()
print()
print('== 三:查询时用 options() 临时覆盖(模型上仍是默认 lazy="select")')
app, db, Author, Book = setup('select')
with app.app_context():
    c = Counter(db)
    for label, opt in (('不加 options', None), ('joinedload', orm.joinedload(Author.books)), ('selectinload', orm.selectinload(Author.books)), ('subqueryload', orm.subqueryload(Author.books)), ('raiseload', orm.raiseload(Author.books))):
        db.session.expunge_all(); c.reset(); q = sa.select(Author)
        if opt is not None: q = q.options(opt)
        authors = db.session.execute(q).unique().scalars().all()
        try: total = sum(len(x.books) for x in authors); r_ = f'{total} 本'
        except Exception as e: r_ = type(e).__name__
        print(f'  {label:<14} {len(c.sql):>3} 条 SQL,遍历 books → {r_}'); R.setdefault('opts', {})[label] = [len(c.sql), r_]
    c.done()
print()
print('== 四:离开 session 之后再访问没加载的关系 → DetachedInstanceError(第 82 篇);raiseload 在开发期暴露遗漏的 eager 加载')
with app.app_context():
    a = db.session.execute(sa.select(Author).limit(1)).scalar_one(); db.session.expunge(a)
    try: a.books; r_ = '读到了'
    except Exception as e: r_ = f'{type(e).__name__}'
    print('  对象 detached 后读 a.books →', r_); R['detached'] = r_
    a = db.session.execute(sa.select(Author).options(orm.raiseload(Author.books)).limit(1)).scalar_one()
    try: a.books
    except Exception as e: print('  raiseload 下读 a.books →', type(e).__name__, '|', str(e)[:90]); R['raiseload_msg'] = str(e)[:90]
print()
print('== 五:lazy="dynamic":关系变成一个可以继续过滤的查询(返回 AppenderQuery),每次访问都发 SQL')
app, db, Author, Book = setup('dynamic')
with app.app_context():
    c = Counter(db); a = db.session.execute(sa.select(Author).limit(1)).scalar_one(); c.reset()
    print('  a.books 的类型:', type(a.books).__name__); q = a.books.filter(Book.title.like('%-1')); print('  继续过滤 a.books.filter(...).all():', [b.title for b in q.all()], f'| 发了 {len(c.sql)} 条'); c.reset()
    a.books.count(); a.books.count(); print(f'  连续 count() 两次:发了 {len(c.sql)} 条(不缓存)'); R['dyn'] = [type(a.books).__name__, len(c.sql)]; c.done()
save('f85', R)
