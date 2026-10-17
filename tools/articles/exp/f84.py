import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f84'); R = {}
import dj, logging, io, datetime as dt, enum
from typing import Optional
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
pg = dj.PG(9456, name='f84pg').start()
try:
    app = Flask('m'); app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'; db = SQLAlchemy(app)
    print('== 一:表名怎么来:类名转 snake_case;__tablename__ 覆盖;继承时的表名')
    class UserProfile(db.Model): id = db.Column(db.Integer, primary_key=True)
    class HTTPRequestLog(db.Model): id = db.Column(db.Integer, primary_key=True)
    class Custom(db.Model):
        __tablename__ = 'my_custom'; id = db.Column(db.Integer, primary_key=True)
    names = {c.__name__: c.__tablename__ for c in (UserProfile, HTTPRequestLog, Custom)}; print('  ', names); R['names'] = names
    print('== 二:没有主键的模型:定义类的那一刻就报错')
    try:
        class NoPk(db.Model):
            __tablename__ = 'nopk'; v = db.Column(db.Integer)
        print('  定义成功?')
    except Exception as e: print('  没有主键的模型 →', type(e).__name__ + ':', str(e).splitlines()[0][:130]); R['nopk'] = [type(e).__name__, str(e).splitlines()[0][:130]]
    print()
    print('== 三:Column 类型 → PostgreSQL 的 DDL;default 与 server_default 的区别;nullable')
    def newapp():
        a_ = Flask('m'); a_.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI']; return a_
    app2 = newapp(); db2 = SQLAlchemy(app2, metadata=sa.MetaData())
    class Ev(enum.Enum): a = 1; b = 2
    class Product(db2.Model):
        id = db2.Column(db2.Integer, primary_key=True)
        name = db2.Column(db2.String(30), nullable=False, unique=True)
        note = db2.Column(db2.Text)
        price = db2.Column(db2.Numeric(8, 2), default=0)
        active = db2.Column(db2.Boolean, default=True, server_default=sa.true())
        created = db2.Column(db2.DateTime, default=dt.datetime.now, server_default=sa.func.now())
        meta = db2.Column(db2.JSON)
        kind = db2.Column(db2.Enum(Ev, name='kind'))
        stock = db2.Column(db2.Integer, sa.CheckConstraint('stock >= 0'), nullable=False, default=0)
        __table_args__ = (sa.Index('ix_product_name_active', 'name', 'active'),)
    ddl = str(CreateTable(Product.__table__).compile(dialect=postgresql.dialect())).strip(); print('  SQLAlchemy 生成的 CREATE TABLE:'); print('\n'.join('    ' + l for l in ddl.splitlines())); R['ddl'] = ddl
    with app2.app_context():
        db2.drop_all(); db2.create_all()
        cols = pg.psql("select column_name||' '||data_type||' null='||is_nullable||' default='||coalesce(column_default,'-') from information_schema.columns where table_name='product' order by ordinal_position")
        print('  PG 里实际的列:'); print('\n'.join('    ' + l for l in cols.splitlines())); R['cols'] = cols
        idx = pg.psql("select indexname from pg_indexes where tablename='product' order by 1"); print('  PG 里的索引:', idx.replace('\n', ', ')); R['idx'] = idx
    print()
    print('== 四:default 是 Python 端在 INSERT 时填的;server_default 是数据库端的 DEFAULT:用 SQL 日志看 INSERT 里有没有这一列')
    buf = io.StringIO(); h = logging.StreamHandler(buf); lg = logging.getLogger('sqlalchemy.engine'); lg.addHandler(h); lg.setLevel(logging.INFO)
    with app2.app_context():
        db2.session.add(Product(name='p1')); db2.session.commit()
        db2.session.execute(sa.text("insert into product (name, stock) values ('raw', 1)")); db2.session.commit()
    lg.setLevel(logging.WARNING); lg.removeHandler(h)
    ins = [l for l in buf.getvalue().splitlines() if 'INSERT INTO product' in l and 'raw' not in l][0]; print('  ORM 发出的 INSERT(只显示列名部分):', ins.split('] ')[-1].split(' VALUES')[0] + ' VALUES (…)'); R['insert'] = ins.split('] ')[-1].split(' VALUES')[0]
    print('  结果行:', pg.psql("select name, price, active, to_char(created,'YYYY') ~ '^20' as created_ok, stock from product order by id"))
    print('  直接用 SQL 插入(绕过 ORM)时,只有 server_default 起作用:', pg.psql("select name, price, active, created is not null as created_ok, stock from product where name='raw'")); R['raw'] = pg.psql("select name, price, active, created is not null, stock from product where name='raw'")
    print()
    print('== 五:约束在数据库里:CheckConstraint 与 unique;违反时的异常类型')
    with app2.app_context():
        for label, o in (('stock=-1(CheckConstraint)', Product(name='c1', stock=-1)), ('重名 p1(unique)', Product(name='p1'))):
            db2.session.add(o)
            try: db2.session.commit()
            except Exception as e: print(f'  {label:<26} → {type(e).__name__} / 底层 {type(e.orig).__name__}'); R.setdefault('violations', {})[label] = [type(e).__name__, type(e.orig).__name__]; db2.session.rollback()
    print()
    print('== 六:SQLAlchemy 2.0 风格的 Mapped[] 注解:nullable 由类型决定')
    db3 = SQLAlchemy(newapp(), model_class=type('Base', (orm.DeclarativeBase,), {}))
    class Acct(db3.Model):
        id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
        name: orm.Mapped[str] = orm.mapped_column(sa.String(30))
        nick: orm.Mapped[Optional[str]]
        age: orm.Mapped[int] = orm.mapped_column(default=0)
    print('  ', str(CreateTable(Acct.__table__).compile(dialect=postgresql.dialect())).strip().replace('\n', '\n   ')); R['mapped'] = str(CreateTable(Acct.__table__).compile(dialect=postgresql.dialect())).strip()
    print()
    print('== 七:模型类上的东西:属性是什么、__table__、mapper')
    print('  Product.name 的类型:', type(Product.name).__name__, '| Product.__table__.name:', Product.__table__.name, '| 列:', [c.key for c in Product.__table__.columns][:5], '...'); R['attrs'] = [type(Product.name).__name__, Product.__table__.name]
    print('  mapper 的映射属性数:', len(sa.inspect(Product).attrs), '| 主键:', [c.name for c in sa.inspect(Product).primary_key])
    p = Product(name='tmp'); print('  实例的 p.name:', p.name, '| 没赋值的 p.note:', p.note, '| 没赋值的 p.price(default 还没生效):', p.price); R['inst'] = [p.name, p.note, str(p.price)]
    print()
    print('== 八:映射到已有的表(反射):不用写模型,db.reflect() 读出表结构')
    app4 = newapp()
    with app4.app_context():
        pg.psql('create table legacy (id serial primary key, title text not null, score int)')
        db4 = SQLAlchemy(app4, metadata=sa.MetaData()); db4.reflect(); t = db4.metadata.tables['legacy']
        print('  反射出的表 legacy 的列:', [(c.name, str(c.type), c.nullable) for c in t.columns]); R['reflect'] = [(c.name, str(c.type), c.nullable) for c in t.columns]
        print('  db.reflect() 是不是也把 product 反射进来:', 'product' in db4.metadata.tables)
finally:
    pg.stop()
save('f84', R)
