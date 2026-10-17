from lib import *
S = SS('f132')
R = J('f132')
steps = [
    step("flask run --debug 时,一个出错的视图(除以零,函数里还有一行硬编码的字符串)返回 500 的页面里有:「Werkzeug Debugger」标识、出错的源码行(return 1 / 0)、文件路径 app.py、异常类型 ZeroDivisionError、交互式控制台的脚本,以及源码里那个硬编码字符串(source 上下文里原样显示);页面里没有 SECRET_KEY 的值(它在配置里,没出现在这个栈帧的源码里)。调试页面把源码、路径、代码结构都交给了访问者,启动日志里只有「* Debug mode: on」。", t=tl(S(1)), done=lidx(S(1), 'Werkzeug Debugger', '源码行', '文件路径', '异常类型', '控制台', '局部变量值'), mark=lidx(S(1), 'SECRET_KEY'), kv=KV([['调试页面', '源码 + 路径 + 异常 + 控制台'], ['启动日志', 'Debug mode: on']], ['调试页面'])),
    step("不开 debug 的 flask run:同样的出错页面只有一个通用的「500 Internal Server Error」,以上七项全是 False,没有源码、路径、异常类型。生产环境应该只看到这个页面,详细的堆栈留在服务端日志里。", t=tl(S(2)), done=lidx(S(2), '500', 'False'), kv=KV([['debug 关闭', '通用 500 页面,不泄漏细节']], ['debug 关闭'])),
    step("gunicorn 加载 app.debug = True 的应用:出错时返回 gunicorn 的通用 Internal Server Error 页面,没有 Werkzeug 调试器;堆栈(ZeroDivisionError)记录在 gunicorn 的日志里,不在响应里。调试器是 flask run(Werkzeug 开发服务器)附带的,换成 gunicorn 部署就没有了——但 app.debug 仍然为真会影响别的行为(例如 JSON 缩进),部署时不要开。", t=tl(S(3)), done=lidx(S(3), '状态码', '含调试器页面', 'gunicorn 日志'), kv=KV([['gunicorn', '没有 Werkzeug 调试器'], ['堆栈', '在服务端日志里']], ['gunicorn'])),
    step("调试服务器默认只监听 127.0.0.1:flask run --debug 的启动日志是「Running on http://127.0.0.1:端口」;加 --host 0.0.0.0 之后日志是「Running on all addresses (0.0.0.0)」,对外可达——带着调试器对外就把上一节的页面交给了任何能访问这个端口的人。", t=tl(S(4)), mark=lidx(S(4), '0.0.0.0'), done=lidx(S(4), '默认'), kv=KV([['默认', '只监听本机'], ['--host 0.0.0.0', '对外可达,不要和 debug 一起用']], ['--host 0.0.0.0'])),
    step("开关的优先关系:flask run(无参数)没有调试器;flask run --debug 有;FLASK_DEBUG=1 flask run 有;而 FLASK_DEBUG=0 flask run --debug 也有——命令行的 --debug 压过了环境变量。检查部署配置时两处都要看。", t=tl(S(5)), done=lidx(S(5), '--debug', 'FLASK_DEBUG=1'), mark=lidx(S(5), 'FLASK_DEBUG=0'), kv=KV([['--debug', '压过 FLASK_DEBUG=0'], ['无参数', '没有调试器']], ['--debug'])),
]
A = mkartf('f132', 132, 'Flask,Debugger,开发模式,信息泄漏,真实验证,动画演示',
    '防御向地验证 Flask 调试器的暴露面:flask run --debug 时错误页面带出源码、路径、异常类型和交互式控制台;不开 debug 只有通用 500;gunicorn 下没有 Werkzeug 调试器、堆栈留在服务端日志;调试服务器默认只监听 127.0.0.1;--debug 参数压过 FLASK_DEBUG=0。',
    '开发模式的调试器到底暴露了什么?生产环境会不会误开?用 gunicorn 部署还有调试器吗?这篇用真实的 flask run 与 gunicorn 对比同一个出错的页面,并检查几种开关的优先关系(只看页面里有什么,没有尝试使用控制台)。',
    [('7 项', '调试页面里检查的信息项,debug 开启时 6 项出现,关闭时 0 项'), ('127.0.0.1', '调试服务器默认监听的地址'), ('--debug 优先', 'FLASK_DEBUG=0 加 --debug 仍然开启调试器')],
    [('调试页面里有什么', '<p>上一篇:<a href="flask-login-lockout.html">登录失败锁定</a>;下一篇:<a href="flask-security-headers.html">安全响应头</a>。</p>'), ('关闭 debug', None), ('gunicorn', None), ('监听地址', None), ('开关的优先关系', '<p>调试器的 PIN 保护与交互式控制台本篇没有验证,也没有尝试使用控制台。</p>')],
    steps, [ENV_F + '。flask run 与 gunicorn', '没有验证:调试器 PIN 的生成与保护强度、WERKZEUG_DEBUG_PIN 与 use_evalex 的作用、uwsgi 与其它服务器、反向代理后面调试页面的可达性、Docker 里 host 绑定的常见误配'], '开发模式 Debugger 风险')
