import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f87'); R = {}
import dj, asyncio, threading
from flask import Flask, g, render_template_string, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.record_queries import get_recorded_queries
import sqlalchemy as sa
from sqlalchemy import event, orm
pg = dj.PG(9458, name='f87pg').start()
# ---- 带延迟的 TCP 代理(模拟数据库与应用不在同一台机器) ----
class DelayProxy:
    def __init__(self, target, port): self.target = target; self.port = port; self.delay = 0.0; self.loop = asyncio.new_event_loop(); self.ready = threading.Event(); threading.Thread(target=self.run, daemon=True).start(); self.ready.wait()
    def run(self):
        asyncio.set_event_loop(self.loop)
        async def pipe(r, w):
            try:
                while True:
                    d = await r.read(65536)
                    if not d: break
                    if self.delay: await asyncio.sleep(self.delay)
                    w.write(d); await w.drain()
            except Exception: pass
            finally:
                try: w.close()
                except Exception: pass
        async def handle(cr, cw):
            sr, sw = await asyncio.open_connection('127.0.0.1', self.target); await asyncio.gather(pipe(cr, sw), pipe(sr, cw))
        async def main():
            self.srv = await asyncio.start_server(handle, '127.0.0.1', self.port); self.ready.set(); await self.srv.serve_forever()
        self.loop.run_until_complete(main())
proxy = DelayProxy(pg.port, 9459)
try:
    app = Flask('__main__'); app.logger.disabled = True; app.config.update(SQLALCHEMY_DATABASE_URI=f'postgresql+psycopg://lab@127.0.0.1:{proxy.port}/lab', SQLALCHEMY_RECORD_QUERIES=True, SQLALCHEMY_ENGINE_OPTIONS={'pool_size': 5}); db = SQLAlchemy(app)
    class Author(db.Model):
        id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(20)); books = db.relationship('Book', back_populates='author')
    class Book(db.Model):
        id = db.Column(db.Integer, primary_key=True); title = db.Column(db.String(20)); author_id = db.Column(db.ForeignKey('author.id'), index=True); author = db.relationship(Author, back_populates='books')
    NA, NB = 100, 5
    with app.app_context():
        db.create_all()
        for i in range(NA): db.session.add(Author(name=f'a{i}', books=[Book(title=f'b{i}-{j}') for j in range(NB)]))
        db.session.commit(); db.session.remove()
    counts = []
    @app.before_request
    def _start(): g.nq = 0
    @event.listens_for(sa.engine.Engine, 'before_cursor_execute')
    def _count(conn, cur, stmt, params, ctx, many):
        if 'author' in stmt or 'book' in stmt:
            try: g.nq += 1
            except RuntimeError: pass
    @app.after_request
    def _hdr(r): r.headers['X-Query-Count'] = str(g.nq); return r
    TPL = "{% for a in authors %}{{ a.name }}:{{ a.books|length }};{% endfor %}"
    @app.get('/bad')
    def bad(): return ','.join(f'{a.name}:{len(a.books)}' for a in db.session.execute(sa.select(Author)).scalars())
    @app.get('/good')
    def good(): return ','.join(f'{a.name}:{len(a.books)}' for a in db.session.execute(sa.select(Author).options(orm.selectinload(Author.books))).scalars())
    @app.get('/tpl-bad')
    def tpl_bad(): return render_template_string(TPL, authors=db.session.execute(sa.select(Author)).scalars().all())
    @app.get('/tpl-good')
    def tpl_good(): return render_template_string(TPL, authors=db.session.execute(sa.select(Author).options(orm.selectinload(Author.books))).scalars().all())
    @app.get('/books-bad')
    def books_bad(): return ','.join(f'{b.title}@{b.author.name}' for b in db.session.execute(sa.select(Book)).scalars())
    @app.get('/raise')
    def raise_(): 
        try: return ','.join(f'{a.name}:{len(a.books)}' for a in db.session.execute(sa.select(Author).options(orm.raiseload('*'))).scalars())
        except Exception as e: return f'{type(e).__name__}: {str(e)[:70]}'
    @app.get('/where')
    def where():
        for a in db.session.execute(sa.select(Author).limit(3)).scalars(): len(a.books)
        return jsonify([[q.statement[:40].replace('\n', ' '), q.location.split('/')[-1].replace(' (', ' · ').rstrip(')')] for q in get_recorded_queries()])
    c = app.test_client()
    print(f'== 一:同一个页面(列出 {NA} 个作者各有几本书)两种写法:每个请求发了几条 SQL(用 g 计数,放进 X-Query-Count 响应头)')
    for p in ('/bad', '/good', '/tpl-bad', '/tpl-good', '/books-bad'):
        r = c.get(p); print(f'  {p:<11} → X-Query-Count = {r.headers["X-Query-Count"]}'); R.setdefault('count', {})[p] = int(r.headers['X-Query-Count'])
    print('  (/tpl-bad 的 N+1 藏在模板里:视图函数里没有任何循环,是模板里 a.books|length 触发的)')
    print()
    print('== 二:SQLALCHEMY_RECORD_QUERIES:每条语句的耗时与「是哪一行代码发出的」(location)')
    r = c.get('/where'); rows = r.get_json(); [print('  ', x) for x in rows[:3]]; R['where'] = rows[:3]
    print()
    print('== 三:开发期把漏掉的预加载变成错误:raiseload("*")')
    r = c.get('/raise'); print('  ', r.get_data(as_text=True)); R['raise'] = r.get_data(as_text=True)
    print()
    print('== 四:数据库在别的机器上时,N+1 被往返延迟放大(经过一个加了固定延迟的 TCP 代理,延迟每个方向各加一次)')
    print(f'  {"单向延迟":<10} {"/bad(1+N 条)":<16} {"/good(2 条)":<14} 倍数')
    R['lat'] = {}
    for dl in (0, 0.001, 0.005):
        proxy.delay = dl
        def t(p, k=5):
            c.get(p); L = []
            for _ in range(k): t0 = time.perf_counter(); c.get(p); L.append(ms(t0))
            return median(L)
        tb, tg = t('/bad'), t('/good'); print(f'  {dl * 1000:>4.0f} ms     {tb:>10.1f} ms    {tg:>8.1f} ms   {tb / tg:>5.1f}x'); R['lat'][str(dl)] = [tb, tg]
    proxy.delay = 0
    print()
    print('== 五:在测试里守住查询条数:断言一个页面的查询数不超过阈值')
    for p, limit in (('/good', 3), ('/bad', 3)):
        n = int(c.get(p).headers['X-Query-Count']); print(f'  {p:<6} 查询数 {n},阈值 {limit} → {"通过" if n <= limit else "失败(N+1)"}'); R.setdefault('assert', {})[p] = [n, n <= limit]
finally:
    pg.stop()
save('f87', R)
