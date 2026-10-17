from lib import *
S = SS('f71')
R = J('f71')
steps = [
    step("扩展可以先不带 app 构造:SQLAlchemy() 此时没有绑定任何应用。init_app 之前访问 db.engine 抛 RuntimeError「Working outside of application context.」;init_app 之后,应用上下文里 db.engine 是 Engine;用另一个没 init_app 的应用的上下文访问,抛「The current Flask app is not registered with this 'SQLAlchemy' instance」。init_app 的结果登记在 app.extensions 里(['sqlalchemy'])。", t=tl(S(1)), done=lidx(S(1), 'init_app 之后', 'app.extensions'), mark=lidx(S(1), 'RuntimeError'), kv=KV([['构造', '可以不带 app'], ['init_app 之前', 'RuntimeError'], ['登记位置', 'app.extensions']], ['init_app 之前'])),
    step("SQLAlchemy 在 init_app 时读一次配置:init_app 之后把 SQLALCHEMY_DATABASE_URI 改成 other.db,引擎仍然指向内存库(sqlite:///%3Amemory%3A);init_app 时根本没有 URI,直接抛 RuntimeError「Either 'SQLALCHEMY_DATABASE_URI' or 'SQLALCHEMY_BINDS' must be set.」。", t=tl(S(2)), done=lidx(S(2), '引擎实际指向'), mark=lidx(S(2), 'must be set'), kv=KV([['init_app 之后改 URI', '不生效'], ['init_app 时没有 URI', 'RuntimeError']], ['init_app 之后改 URI'])),
    step("不同扩展读配置的时机不一样:Flask-Caching 在 init_app 里按 CACHE_TYPE 建好缓存对象,之后把 CACHE_TYPE 改成 NullCache,cache.get 仍然拿到 1(还是 SimpleCache);Flask-Login 的 login_view 在未登录时才读,init_app 之后设置依然有效(late_login)。", t=tl(S(3)), done=lidx(S(3), 'Flask-Login'), mark=lidx(S(3), 'Flask-Caching'), kv=KV([['Flask-Caching', 'init_app 时读'], ['Flask-Login login_view', '用到时才读']], ['Flask-Caching'])),
    step("一个扩展对象可以服务多个应用:同一个 db 对象在 x、y 两个应用的上下文里得到的引擎不同(True)。状态存在各自的 app.extensions 里,而不是扩展对象自己身上。", t=tl(S(4)), done=lidx(S(4), '引擎不同'), kv=KV([['状态存放', 'app.extensions[...]'], ['同一个 db', '两个应用两个引擎']], ['状态存放'])),
    step("工厂里 init_app 的位置:先 init_app 再设置配置,抛 RuntimeError「Either 'SQLALCHEMY_DATABASE_URI' or 'SQLALCHEMY_BINDS' must be set.」;先设置配置再 init_app 成功。", t=tl(S(5)), done=lidx(S(5), '成功'), mark=lidx(S(5), 'RuntimeError'), kv=KV([['顺序', '先配置,后 init_app']], ['顺序'])),
    step("自己写扩展时的两种写法:LazyExt 在方法里用 current_app.config,init_app 之后改配置能看到(改后(lazy));EagerExt 把值存在 self 上,改配置看不到(hello),并且同一个对象给两个应用 init_app 时,第二次的值覆盖第一次(第一个应用的上下文里 greet() 得到的是 g2 的值)。", t=tl(S(6)), done=lidx(S(6), '改后'), mark=lidx(S(6), '被第二次 init_app 覆盖'), kv=KV([['Lazy', '读 current_app.config'], ['Eager', '存 self,多应用会串']], ['Eager'])),
]
A = mkartf('f71', 71, 'Flask,扩展,init_app,配置,真实验证,动画演示',
    '实测 Flask 扩展的初始化时机:init_app 之前访问抛 RuntimeError;SQLAlchemy 与 Flask-Caching 在 init_app 时读一次配置、之后改无效,Flask-Login 用到时才读;一个扩展对象服务多个应用;工厂里先配置后 init_app;自己写扩展为什么要把状态放进 app.extensions。',
    '扩展什么时候读配置?为什么 init_app 之后改配置有时生效、有时不生效?一个扩展对象能不能给多个应用用?这篇用 SQLAlchemy、Flask-Caching、Flask-Login 和两个自己写的小扩展逐项验证。',
    [('init_app', '扩展与应用绑定的入口,状态存在 app.extensions'), ('读一次', 'SQLAlchemy 与 Flask-Caching 在 init_app 时读配置,之后改不生效'), ('current_app', '自己写扩展时,在方法里读配置才能跟着应用走')],
    [('构造与 init_app', '<p>上一篇:<a href="flask-application-factory.html">Application Factory</a>;下一篇:<a href="flask-flask-login-flow.html">Flask-Login 登录流程</a>。</p>'), ('配置读一次', None), ('不同扩展的差别', None), ('一个扩展多个应用', None), ('工厂里的顺序', None), ('自己写扩展', '<p>这一节是后面第 80 篇「自定义扩展」的铺垫。</p>')],
    steps, [ENV_F + '。Flask-Caching 2.5.1、Flask-Login 0.6.3', '没有验证:Flask-SQLAlchemy 的 SQLALCHEMY_ENGINE_OPTIONS 等其它配置项的读取时机、其它扩展的 init_app 细节、扩展用 app.extensions 以外方式存状态(如模块全局变量)时的多线程行为'], 'Extension 初始化时机')
