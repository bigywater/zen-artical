import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f86'); R = {}
import dj
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy import event, orm
pg = dj.PG(9457, name='f86pg').start()
try:
    app = Flask('j'); app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'; db = SQLAlchemy(app)
    class Author(db.Model):
        id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(20)); bio = db.Column(db.Text)
        books = db.relationship('Book', back_populates='author')
    class Book(db.Model):
        id = db.Column(db.Integer, primary_key=True); title = db.Column(db.String(20)); author_id = db.Column(db.ForeignKey('author.id'), index=True); author = db.relationship(Author, back_populates='books')
        reviews = db.relationship('Review')
    class Review(db.Model):
        id = db.Column(db.Integer, primary_key=True); book_id = db.Column(db.ForeignKey('book.id'), index=True); text = db.Column(db.String(20))
    NA, NB, NR = 300, 10, 3
    with app.app_context():
        db.create_all(); bio = 'x' * 4000
        for i in range(NA):
            db.session.add(Author(name=f'a{i}', bio=bio, books=[Book(title=f'b{i}-{j}', reviews=[Review(text='r') for _ in range(NR)]) for j in range(NB)]))
        db.session.commit(); db.session.remove()
    sql = []
    def cb(conn, cur, stmt, params, ctx, many): sql.append(' '.join(stmt.split()))
    with app.app_context(): event.listen(db.engine, 'before_cursor_execute', cb)
    def run(q, expunge=True):
        sql.clear(); db.session.expunge_all(); t0 = time.perf_counter(); rows = db.session.execute(q).unique().scalars().all()
        n = sum(len(a.books) for a in rows) if rows and hasattr(rows[0], 'books') else 0; return ms(t0), len(sql), len(rows), n
    def med(q, k=7): L = [run(q) for _ in range(k)]; return median([x[0] for x in L]), L[0][1], L[0][2], L[0][3]
    with app.app_context():
        print('== 一:两者发出的 SQL 长什么样(只取 5 个作者看)')
        sql.clear(); db.session.expunge_all(); db.session.execute(sa.select(Author).options(orm.joinedload(Author.books)).limit(5)).unique().scalars().all(); print('  joinedload + limit(5):'); [print('    ', s[:210]) for s in sql]; R['sql_joined_limit'] = sql[0]
        sql.clear(); db.session.expunge_all(); db.session.execute(sa.select(Author).options(orm.selectinload(Author.books)).limit(5)).scalars().all(); print('  selectinload + limit(5):'); [print('    ', s[:210]) for s in sql]; R['sql_selectin'] = list(sql)
        print()
        print('== 二:joinedload 一对多时必须 .unique():不调用会怎样')
        try: db.session.execute(sa.select(Author).options(orm.joinedload(Author.books))).scalars().all(); r_ = '成功'
        except Exception as e: r_ = f'{type(e).__name__}: {str(e)[:110]}'
        print('  ', r_); R['unique_err'] = r_
        print()
        print(f'== 三:取 {NA} 个作者(每人一个 4000 字节的 bio 列)和他们的 {NB} 本书:耗时与数据库返回的行数')
        rows = {}
        for label, q in (('不预加载(lazy,N+1)', sa.select(Author)), ('joinedload', sa.select(Author).options(orm.joinedload(Author.books))), ('selectinload', sa.select(Author).options(orm.selectinload(Author.books)))):
            t, ns, na, nb = med(q); rows[label] = (t, ns, na, nb); print(f'  {label:<22} {t:>7.1f} ms  SQL {ns:>3} 条  作者 {na} 本书 {nb}')
        R['cmp'] = {k: list(v) for k, v in rows.items()}
        sql.clear(); db.session.expunge_all(); cur = db.session.connection().exec_driver_sql("select count(*) from author a left join book b on b.author_id=a.id").scalar(); R['join_rows'] = cur; print(f'  JOIN 的结果集行数:{cur}(作者的 bio 在每一行里都重复一遍),selectin 的两条查询分别返回 {NA} 与 {NA * NB} 行')
    print()
    print(f'== 四:多层嵌套 Author → books → reviews({NA}×{NB}×{NR} 行):joinedload 链 vs selectinload 链')
    with app.app_context():
        for label, opt in (('joinedload 链', orm.joinedload(Author.books).joinedload(Book.reviews)), ('selectinload 链', orm.selectinload(Author.books).selectinload(Book.reviews))):
            q = sa.select(Author).options(opt); t, ns, na, nb = med(q, 5); print(f'  {label:<16} {t:>8.1f} ms  SQL {ns} 条'); R.setdefault('nest', {})[label] = [t, ns]
        sql.clear(); db.session.expunge_all(); db.session.execute(sa.select(Author).options(orm.joinedload(Author.books).joinedload(Book.reviews))).unique().scalars().all(); print('  joinedload 链返回的行数 =', R['join_rows'] * NR, '(作者 × 书 × 评论 的乘积)')
    print()
    print('== 五:多对一:joinedload 不会让行数增加(每本书只有一个作者)')
    with app.app_context():
        for label, opt in (('joinedload(Book.author)', orm.joinedload(Book.author)), ('selectinload(Book.author)', orm.selectinload(Book.author))):
            q = sa.select(Book).options(opt).limit(1500); sql.clear(); L = []
            for _ in range(5): db.session.expunge_all(); t0 = time.perf_counter(); rows_ = db.session.execute(q).unique().scalars().all(); [b.author.name for b in rows_]; L.append(ms(t0))
            print(f'  {label:<26} {median(L):>7.1f} ms  SQL {len(sql) // 5} 条/次  书 {len(rows_)}'); R.setdefault('m2o', {})[label] = [median(L), len(sql) // 5]
    print()
    print('== 六:selectinload 的 IN 列表分块:每块最多 500 个主键(再加 900 个没有书的作者,共 1200 个)')
    with app.app_context():
        for i in range(NA, 1200): db.session.add(Author(name=f'a{i}', bio='y'))
        db.session.commit(); db.session.remove()
        for n in (300, 600, 1200):
            sql.clear(); db.session.expunge_all(); db.session.execute(sa.select(Author).options(orm.selectinload(Author.books)).limit(n)).scalars().all(); print(f'  {n:>5} 个作者:{len(sql)} 条 SQL'); R.setdefault('chunk', {})[n] = len(sql)
finally:
    pg.stop()
save('f86', R)
