import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f61'); R = {}
import timeit
from flask import Flask, render_template_string
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, select, func
from sqlalchemy.orm import selectinload, joinedload, relationship
from jinja2 import Environment, StrictUndefined, Undefined, DebugUndefined
app = Flask('lz'); app.logger.disabled = True; app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
db = SQLAlchemy(app)
class Author(db.Model):
    id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(50)); books = db.relationship('Book', backref='author')
class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True); title = db.Column(db.String(50)); author_id = db.Column(db.ForeignKey('author.id'))
stmts = []
with app.app_context():
    db.create_all()
    for i in range(20): a = Author(name=f'作者{i}', books=[Book(title=f'书{i}-{j}') for j in range(3)]); db.session.add(a)
    db.session.commit()
    @event.listens_for(db.engine, 'before_cursor_execute')
    def count(conn, cur, statement, params, context, executemany): stmts.append(statement.split('\n')[0][:60])
    def sel(): return len([s for s in stmts if s.strip().upper().startswith('SELECT')])
    def run(label, tpl, make):
        stmts.clear(); db.session.expire_all(); db.session.close(); kw = make(); before = sel(); out = render_template_string(tpl, **kw); total = sel()
        R.setdefault('sql', {})[label] = [before, total - before, total]; print(f'  {label:<44} 查询阶段 {before:>2} 条 + 渲染阶段 {total - before:>2} 条 = 共 {total:>2} 条 SELECT'); return out
    print('== 一:模板里访问懒加载的关系属性:每个作者访问一次 books 就多一条 SQL(N+1)')
    tpl = '{% for a in authors %}{{ a.name }}:{{ a.books|length }};{% endfor %}'
    run('循环里访问 a.books|length(懒加载)', tpl, lambda: dict(authors=db.session.scalars(select(Author)).all()))
    print('  语句示例:', stmts[:3]); R['sample'] = stmts[:3]
    run('视图里 selectinload 预加载', tpl, lambda: dict(authors=db.session.scalars(select(Author).options(selectinload(Author.books))).all()))
    run('视图里 joinedload 预加载', tpl, lambda: dict(authors=db.session.scalars(select(Author).options(joinedload(Author.books))).unique().all()))
    print()
    print('== 二:把 Query 对象直接传进模板:迭代几次就执行几次;模板里调 count() 又是一条')
    run('模板里循环两遍 Query', '{% for a in q %}{{ a.id }}{% endfor %}|{% for a in q %}{{ a.id }}{% endfor %}', lambda: dict(q=db.session.query(Author)))
    run('先 .all() 再循环两遍', '{% for a in rows %}{{ a.id }}{% endfor %}|{% for a in rows %}{{ a.id }}{% endfor %}', lambda: dict(rows=db.session.query(Author).all()))
    run('模板里调 q.count() 再循环一遍', '{{ q.count() }}:{% for a in q %}{{ a.id }}{% endfor %}', lambda: dict(q=db.session.query(Author)))
app.app_context().push()
print()
print('== 三:生成器只能遍历一次——第二个循环是空的;|list 或先转成列表')
def gen(): yield from range(3)
print('  循环两遍同一个生成器:', repr(render_template_string('{% for x in g %}{{ x }}{% endfor %}|{% for x in g %}{{ x }}{% endfor %}', g=gen())))
print('  先 |list:', repr(render_template_string('{% set xs = g|list %}{% for x in xs %}{{ x }}{% endfor %}|{% for x in xs %}{{ x }}{% endfor %}', g=gen()))); R['gen'] = [render_template_string('{% for x in g %}{{ x }}{% endfor %}|{% for x in g %}{{ x }}{% endfor %}', g=gen()), render_template_string('{% set xs = g|list %}{% for x in xs %}{{ x }}{% endfor %}|{% for x in xs %}{{ x }}{% endfor %}', g=gen())]
print()
print('== 四:Undefined 的行为:缺失的变量输出空;读缺失变量的属性才报错;不同 Undefined 类的差别')
class Obj:
    @property
    def bad(self): raise AttributeError('属性里的 AttributeError 被模板吞掉')
    @property
    def good(self): return 'ok'
    def method(self): return 'm'
cases = [('{{ missing }}', {}), ('{{ missing.attr }}', {}), ('{{ missing|default("默认") }}', {}), ('{{ d.k }}', {'d': {}}), ('{{ d["k"] }}', {'d': {}}), ('{{ d.k.z }}', {'d': {}}), ('{% if missing %}真{% else %}假{% endif %}', {}), ('{% if d.k.z is defined %}已定义{% else %}未定义{% endif %}', {'d': {}}), ('{{ o.good }}|{{ o.nope }}|[{{ o.bad }}]', {'o': Obj()}), ('{{ o.method }}', {'o': Obj()}), ('{{ o.method() }}', {'o': Obj()}), ('{{ missing + 1 }}', {}), ('{{ missing|length }}', {}), ('{% for x in missing %}x{% endfor %}完', {})]
R['undef'] = {}
for tpl, kw in cases:
    try: out = render_template_string(tpl, **kw)
    except Exception as e: out = f'{type(e).__name__}: {e}'
    R['undef'][tpl] = out; print(f'  {tpl:<48} → {out}')
print()
print('== 五:换成 StrictUndefined(开发时能尽早发现拼写错误)')
for cls in (Undefined, StrictUndefined, DebugUndefined):
    env = Environment(undefined=cls); res = []
    for tpl in ('{{ missing }}', '{% if missing %}真{% else %}假{% endif %}', '{{ missing|default("默认") }}'):
        try: res.append(env.from_string(tpl).render())
        except Exception as e: res.append(f'{type(e).__name__}')
    R.setdefault('undef_cls', {})[cls.__name__] = res; print(f'  {cls.__name__:<16}', res)
save('f61', R)
