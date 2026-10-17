import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f104'); R = {}
import dj, base64
from flask import Flask, request, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
pg = dj.PG(9471, name='f104pg').start()
try:
    app = Flask('p'); app.logger.disabled = True; app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'; db = SQLAlchemy(app)
    class Post(db.Model):
        id = db.Column(db.Integer, primary_key=True); title = db.Column(db.String(30))
    N = 200000
    with app.app_context():
        db.create_all(); db.session.execute(sa.text(f"insert into post (title) select 'p' || g from generate_series(1,{N}) g")); db.session.commit()
    @app.get('/offset')
    def offset_view():
        page = request.args.get('page', 1, type=int); size = 20
        rows = db.session.execute(sa.select(Post).order_by(Post.id).limit(size).offset((page - 1) * size)).scalars().all(); return jsonify(ids=[r.id for r in rows])
    @app.get('/keyset')
    def keyset_view():
        after = request.args.get('after', type=int); q = sa.select(Post).order_by(Post.id).limit(20)
        if after is not None: q = q.where(Post.id > after)
        rows = db.session.execute(q).scalars().all(); return jsonify(ids=[r.id for r in rows], next=rows[-1].id if rows else None)
    @app.get('/cursor')
    def cursor_view():
        c = request.args.get('cursor'); after = 0
        if c:
            try: after = json.loads(base64.urlsafe_b64decode(c.encode()))['after']; assert isinstance(after, int)
            except Exception: abort(400, description='bad cursor')
        rows = db.session.execute(sa.select(Post).where(Post.id > after).order_by(Post.id).limit(20)).scalars().all()
        return jsonify(ids=[r.id for r in rows][:3], next=base64.urlsafe_b64encode(json.dumps({'after': rows[-1].id}).encode()).decode() if rows else None)
    @app.get('/paginate')
    def paginate_view():
        p = db.paginate(sa.select(Post).order_by(Post.id), page=request.args.get('page', type=int), per_page=request.args.get('per_page', type=int), max_per_page=100)
        return jsonify(page=p.page, per_page=p.per_page, total=p.total, pages=p.pages, n=len(p.items), has_next=p.has_next, first=p.items[0].id if p.items else None)
    c = app.test_client()
    print(f'== 一:OFFSET 分页的耗时随页码增大({N} 行,每页 20 条,每个位置取 7 次中位数)')
    R['offset'] = {}
    for page in (1, 1000, 5000, 9999):
        c.get(f'/offset?page={page}'); L = []
        for _ in range(7): t0 = time.perf_counter(); c.get(f'/offset?page={page}'); L.append(ms(t0))
        print(f'  第 {page:>5} 页(OFFSET {(page - 1) * 20:>6}) {median(L):>7.2f} ms'); R['offset'][page] = median(L)
    print()
    print('== 二:键集(keyset)分页:同样的位置,用 WHERE id > 上一页最后一个 id')
    R['keyset'] = {}
    for page in (1, 1000, 5000, 9999):
        after = (page - 1) * 20; c.get(f'/keyset?after={after}'); L = []
        for _ in range(7): t0 = time.perf_counter(); c.get(f'/keyset?after={after}'); L.append(ms(t0))
        print(f'  从 id>{after:>6} 开始 {median(L):>7.2f} ms'); R['keyset'][page] = median(L)
    with app.app_context():
        print('  EXPLAIN(OFFSET 199980):', ' | '.join(sa.text('x').text for _ in []) or db.session.execute(sa.text('explain select * from post order by id limit 20 offset 199980')).scalars().all()[0][:80])
        print('  EXPLAIN(id > 199980):  ', db.session.execute(sa.text('explain select * from post where id > 199980 order by id limit 20')).scalars().all()[0][:80])
        print('  (EXPLAIN 估算成本:OFFSET 约 7728,keyset 约 4.6——OFFSET 要先数过前面的 199980 行)')
        t0 = time.perf_counter(); n = db.session.execute(sa.text('select count(*) from post')).scalar(); tc = ms(t0); print(f'  顺便:select count(*) 取总数 {tc:.1f} ms({n} 行)'); R['count'] = tc
    print()
    print('== 三:翻页过程中数据变化:按 id 升序翻页,看完第 1 页后删掉前面的一行')
    with app.app_context(): db.session.execute(sa.text('create table q (id int primary key)')); db.session.execute(sa.text('insert into q select generate_series(1,10)')); db.session.commit()
    def pg_(page, size=3, after=None):
        with app.app_context():
            if after is None: return [r[0] for r in db.session.execute(sa.text(f'select id from q order by id limit {size} offset {(page - 1) * size}'))]
            return [r[0] for r in db.session.execute(sa.text(f'select id from q where id > {after} order by id limit {size}'))]
    p1 = pg_(1); pg.psql('delete from q where id = 1'); p2 = pg_(2); k2 = pg_(None, after=p1[-1]); print('  第 1 页 ids =', p1, '→ 此时删掉 id=1 → OFFSET 的第 2 页 =', p2, '(漏掉了 4)| keyset 的下一页 =', k2); R['consistency'] = [p1, p2, k2]
    print()
    print('== 四:游标编码:base64 的 JSON;被篡改的游标返回 400')
    r = c.get('/cursor'); cur = r.get_json()['next']; print('  第一页返回的 next =', cur, '→ 解码:', base64.urlsafe_b64decode(cur.encode()).decode()); r2 = c.get(f'/cursor?cursor={cur}'); print('  用它取第二页的前 3 个 id:', r2.get_json()['ids']); R['cursor'] = [cur, r2.get_json()['ids']]
    import urllib.parse as up
    for bad in ('###', base64.urlsafe_b64encode(b'{"after": "x"}').decode()): r = c.get('/cursor?cursor=' + up.quote(bad)); print(f'  篡改的游标 {bad[:14]!r:<18} →', r.status_code); R.setdefault('badcur', []).append(r.status_code)
    print('  (游标只是编码不是加密——客户端能读也能伪造,服务端必须校验;不要把敏感值放进游标)')
    print()
    print('== 五:db.paginate() 的行为')
    R['paginate'] = {}
    for q in ('', '?page=3&per_page=50', '?per_page=1000', '?page=0', '?page=99999', '?page=abc', '?per_page=0'):
        r = c.get('/paginate' + q); print(f'  /paginate{q:<22} → {r.status_code} {r.get_json() if r.is_json else r.get_data(as_text=True)[:40]}'); R['paginate'][q] = [r.status_code, r.get_json() if r.is_json else None]
finally:
    pg.stop()
save('f104', R)
