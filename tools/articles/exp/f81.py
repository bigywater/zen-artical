import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f81'); R = {}
import dj
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
pg = dj.PG(9453, name='f81pg').start()
try:
    print('== 一:init_app 做了什么、没做什么:创建了 Engine,但没有连接数据库(用真实的 PostgreSQL 数一数连接)')
    def conns(): return int(pg.psql("select count(*) from pg_stat_activity where datname='lab' and pid <> pg_backend_pid()"))
    a = Flask('a'); a.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'; db = SQLAlchemy()
    print('  init_app 之前 PG 上的连接数:', conns())
    t0 = time.perf_counter(); db.init_app(a); t_cold = ms(t0)
    a_w = Flask('w'); a_w.config['SQLALCHEMY_DATABASE_URI'] = a.config['SQLALCHEMY_DATABASE_URI']; db_w = SQLAlchemy(); t0 = time.perf_counter(); db_w.init_app(a_w); t_init = ms(t0)
    print(f'  第一次 init_app 用时 {t_cold:.0f} ms(包含第一次导入 psycopg 等驱动),同一进程里再对另一个应用 init_app 只要 {t_init:.2f} ms')
    print(f'  init_app 之后:{conns()};app.extensions["sqlalchemy"] is db → {a.extensions["sqlalchemy"] is db}'); R['init'] = [conns(), t_init, t_cold]
    with a.app_context():
        e = db.engine; print('  db.engine 的类型:', type(e).__name__, '| 连接池:', type(e.pool).__name__, f'(pool_size={e.pool.size()})', '| db.engines 的键:', list(db.engines.keys())); R['pool'] = [type(e.pool).__name__, e.pool.size()]
        print('  访问 db.engine 之后连接数:', conns())
        t0 = time.perf_counter(); db.session.execute(sa.text('select 1')); t_first = ms(t0)
        print(f'  第一次执行 SQL 之后连接数:{conns()}(第一次执行 {t_first:.1f} ms)'); R['first'] = [conns(), t_first]
        t0 = time.perf_counter(); db.session.execute(sa.text('select 1')); print(f'  第二次执行 {ms(t0):.2f} ms'); R['second'] = ms(t0)
    print('  离开 app_context 之后连接数(session 被 remove,连接还给池,但池里仍保留):', conns()); R['after_ctx'] = conns()
    print()
    print('== 二:SQLite:相对路径的数据库文件落在哪?文件什么时候创建?')
    d = FT / 'f81sq'; shutil.rmtree(d, ignore_errors=True); d.mkdir()
    a = Flask('sq', instance_path=str(d / 'instance')); a.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'; db = SQLAlchemy(a)
    inst = pathlib.Path(a.instance_path)
    print('  init_app 之后 instance 目录存在:', inst.exists(), '| 文件:', sorted(p.name for p in inst.glob('*')) if inst.exists() else None)
    with a.app_context():
        print('  engine.url:', str(db.engine.url).replace(str(d), '<tmp>'))
        print('  执行 SQL 之前文件存在:', (inst / 'app.db').exists())
        db.session.execute(sa.text('select 1')); print('  执行 SQL 之后文件存在:', (inst / 'app.db').exists())
        R['sqlite'] = [str(db.engine.url).replace(str(d), '<tmp>'), (inst / 'app.db').exists(), type(db.engine.pool).__name__]; print('  连接池类型:', type(db.engine.pool).__name__)
    a = Flask('mem'); a.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'; db = SQLAlchemy(a)
    with a.app_context(): print('  sqlite 内存库的连接池:', type(db.engine.pool).__name__); R['mem'] = [type(db.engine.pool).__name__]
    print()
    print('== 三:配置项:SQLALCHEMY_ENGINE_OPTIONS 与 SQLALCHEMY_BINDS')
    a = Flask('cfg'); a.config.update(SQLALCHEMY_DATABASE_URI=f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab', SQLALCHEMY_ENGINE_OPTIONS={'pool_size': 2, 'max_overflow': 1, 'pool_pre_ping': True, 'pool_recycle': 300}, SQLALCHEMY_BINDS={'other': 'sqlite:///other.db'}); db = SQLAlchemy(a)
    with a.app_context():
        e = db.engine; print(f'  pool_size={e.pool.size()} max_overflow={e.pool._max_overflow} pre_ping={e.pool._pre_ping} recycle={e.pool._recycle}'); R['opts'] = [e.pool.size(), e.pool._max_overflow, e.pool._pre_ping, e.pool._recycle]
        print('  db.engines 的键:', list(db.engines.keys()), '| 绑定库的引擎:', str(db.engines['other'].url).replace(str(HERE), '<实验目录>')); R['binds'] = list(db.engines.keys(), ) if False else [str(k) for k in db.engines.keys()]
    print()
    print('== 四:模型注册与 create_all:模型类定义在 init_app 之前还是之后都行,create_all 必须在应用上下文里')
    a = Flask('m'); a.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'; db = SQLAlchemy()
    class User(db.Model):
        id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(30))
    print('  还没 init_app 就定义了模型:db.metadata.tables =', list(db.metadata.tables), '| __tablename__ =', User.__tablename__)
    db.init_app(a)
    try: db.create_all()
    except RuntimeError as e: print('  上下文外 create_all →', str(e).splitlines()[0]); R['noctx'] = str(e).splitlines()[0]
    with a.app_context():
        db.drop_all(); db.create_all(); print('  create_all 之后 PG 里的表:', pg.psql("select tablename from pg_tables where schemaname='public'")); R['tables'] = pg.psql("select tablename from pg_tables where schemaname='public'")
    print()
    print('== 五:同一个应用 init_app 两次;一个 SQLAlchemy 对象服务两个应用;db.session 的作用域')
    a = Flask('d'); a.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'; db = SQLAlchemy(a)
    try: db.init_app(a)
    except RuntimeError as e: print('  同一个应用 init_app 两次 →', str(e)[:110]); R['twice'] = str(e)[:110]
    with a.app_context():
        s1 = db.session(); s2 = db.session(); print('  同一个应用上下文里 db.session() 两次是同一个对象:', s1 is s2)
        with a.app_context(): s3 = db.session(); print('  嵌套的新应用上下文里是不同的 session:', s3 is not s1)
    R['scope'] = [s1 is s2, s3 is not s1]
    print('  离开上下文后原 session 是否还在事务中 →', s1.in_transaction())
    print()
    print('== 六:没配置 URI 的报错;URI 写错(未知方言)什么时候报错')
    a = Flask('e1'); db = SQLAlchemy()
    try: db.init_app(a)
    except Exception as e: print('  没有 URI →', type(e).__name__, str(e)[:90]); R['nouri'] = str(e)[:90]
    a = Flask('e2'); a.config['SQLALCHEMY_DATABASE_URI'] = 'nosuchdb://x/y'; db = SQLAlchemy()
    try: db.init_app(a); print('  init_app 成功?')
    except Exception as e: print('  未知方言的 URI 在 init_app 时就报错 →', type(e).__name__, str(e)[:90]); R['badurl'] = [type(e).__name__, str(e)[:90]]
    a = Flask('e3'); a.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg://lab@127.0.0.1:9459/lab'; db = SQLAlchemy(a)
    print('  端口没人监听的 PG URI:init_app 成功;', end=' ')
    with a.app_context():
        try: db.session.execute(sa.text('select 1'))
        except Exception as e: print('第一次执行 SQL 才报错 →', type(e).__name__); R['conn_fail'] = type(e).__name__
finally:
    pg.stop()
save('f81', R)
