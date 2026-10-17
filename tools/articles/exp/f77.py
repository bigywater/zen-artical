import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f77'); R = {}
import email, email.policy, threading, time, smtplib
from flask import Flask
from flask_mail import Mail, Message, BadHeaderError
from aiosmtpd.controller import Controller
PORT = 9661
class H:
    def __init__(self): self.msgs = []; self.delay = 0
    async def handle_DATA(self, server, session, envelope):
        import asyncio
        if self.delay: await asyncio.sleep(self.delay)
        self.msgs.append((id(session), envelope.mail_from, list(envelope.rcpt_tos), envelope.content)); return '250 OK'
h = H(); ctl = Controller(h, hostname='127.0.0.1', port=PORT); ctl.start()
def mk(**cfg):
    a = Flask('m'); a.config.update(MAIL_SERVER='127.0.0.1', MAIL_PORT=PORT, MAIL_DEFAULT_SENDER='noreply@lab.test', **cfg); return a, Mail(a)
try:
    print('== 一:真的发出去:本机起一个 SMTP 服务(aiosmtpd),看服务端收到的原始邮件')
    a, mail = mk()
    with a.app_context():
        msg = Message('订单 #42 已发货', recipients=['u@x.test'], body='您好,订单已发货。', html='<p>您好,<b>订单已发货</b>。</p>'); mail.send(msg)
    sid, frm, to, raw = h.msgs[-1]; m = email.message_from_bytes(raw, policy=email.policy.default)
    print(f'  信封:MAIL FROM={frm} RCPT TO={to}')
    for k in ('From', 'To', 'Subject', 'Content-Type', 'MIME-Version'): print(f'  {k}: {str(m[k])[:80]}')
    print('  原始 Subject 头(未解码):', re.search(rb'Subject: (.*)', raw).group(1).decode())
    print('  MIME 结构:', [(p.get_content_type(), p.get_content_charset()) for p in m.walk()])
    R['one'] = dict(frm=frm, to=to, subject=str(m['Subject']), raw_subject=re.search(rb'Subject: (.*)', raw).group(1).decode(), parts=[p.get_content_type() for p in m.walk()])
    print()
    print('== 二:附件与多个收件人、抄送、Reply-To;信封收件人 vs 头里的收件人')
    with a.app_context():
        msg = Message('报表', recipients=['a@x.test', 'b@x.test'], cc=['c@x.test'], bcc=['hidden@x.test'], reply_to='support@lab.test', body='见附件')
        msg.attach('r.csv', 'text/csv', 'id,v\n1,2\n'.encode()); mail.send(msg)
    sid, frm, to, raw = h.msgs[-1]; m = email.message_from_bytes(raw, policy=email.policy.default)
    print('  信封 RCPT TO:', to); print('  头 To:', m['To'], '| Cc:', m['Cc'], '| Bcc 头是否存在:', m['Bcc'] is not None, '| Reply-To:', m['Reply-To'])
    print('  MIME 结构:', [(p.get_content_type(), p.get_filename()) for p in m.walk()])
    R['two'] = dict(rcpt=to, bcc_header=m['Bcc'] is not None, parts=[p.get_content_type() for p in m.walk()])
    print()
    print('== 三:测试时不真发:TESTING=True 时 suppress 默认打开(在 init_app 时读取);record_messages 收集 outbox')
    n0 = len(h.msgs); a2, mail2 = mk(TESTING=True)
    with a2.app_context(), mail2.record_messages() as outbox:
        mail2.send(Message('t', recipients=['u@x.test'], body='b'))
        print(f'  TESTING=True 发 1 封:outbox 里 {len(outbox)} 封,SMTP 服务端新增 {len(h.msgs) - n0} 封;扩展里的 suppress = {a2.extensions["mail"].suppress}(配置里并没有写入 MAIL_SUPPRESS_SEND 这个键:{"MAIL_SUPPRESS_SEND" in a2.config})'); R['test'] = [len(outbox), len(h.msgs) - n0]
        print('  outbox[0].subject / recipients:', outbox[0].subject, outbox[0].recipients)
    a3, mail3 = mk(TESTING=True, MAIL_SUPPRESS_SEND=False)
    with a3.app_context(): mail3.send(Message('t2', recipients=['u@x.test'], body='b'))
    print(f'  TESTING=True 但显式 MAIL_SUPPRESS_SEND=False:服务端新增 {len(h.msgs) - n0} 封'); R['test2'] = len(h.msgs) - n0
    print()
    print('== 四:头注入:主题里带换行 → BadHeaderError(Flask-Mail 在发送前检查)')
    a, mail = mk()
    with a.app_context():
        try: mail.send(Message('hi\r\nBcc: evil@x.test', recipients=['u@x.test'], body='b')); r = '发出去了'
        except BadHeaderError as e: r = f'BadHeaderError: {e}'
        try: mail.send(Message('hi', recipients=['u@x.test\r\nBcc: evil@x.test'], body='b')); r2 = '发出去了'
        except BadHeaderError as e: r2 = f'BadHeaderError: {e}'
    print('  主题带换行 →', r); print('  收件人带换行 →', r2); R['inj'] = [r, r2]
    print()
    print('== 五:同步发送会卡住请求:SMTP 服务端 0.5 秒才回应;直接 send vs 放线程里 send')
    h.delay = 0.5
    with a.app_context():
        t0 = time.perf_counter(); mail.send(Message('slow', recipients=['u@x.test'], body='b')); sync = ms(t0)
    try: Message('x', recipients=['u@x.test'], body='b'); r_ = '成功'
    except RuntimeError as e: r_ = f'RuntimeError: {str(e).splitlines()[0]}'
    print('  在应用上下文之外构造 Message(没有显式 sender)→', r_); R['msg_ctx'] = r_
    def bg(app_):
        with app_.app_context(): mail.send(Message('thr', recipients=['u@x.test'], body='b'))
    t0 = time.perf_counter(); th = threading.Thread(target=bg, args=(a,)); th.start(); spawn = ms(t0); th.join(); total = ms(t0)
    print(f'  同步 send:{sync:.0f} ms;线程里 send:启动线程 {spawn:.2f} ms 就返回(邮件在后台继续,总共 {total:.0f} ms)'); R['async'] = [sync, spawn, total]
    h.delay = 0
    print()
    print('== 六:SMTP 服务不可用:send 抛什么异常?(端口没人监听)')
    a4 = Flask('m4'); a4.config.update(MAIL_SERVER='127.0.0.1', MAIL_PORT=9669, MAIL_DEFAULT_SENDER='n@lab.test'); mail4 = Mail(a4)
    with a4.app_context():
        t0 = time.perf_counter()
        try: mail4.send(Message('x', recipients=['u@x.test'], body='b'))
        except Exception as e: print(f'  {type(e).__name__}: {e}(耗时 {ms(t0):.0f} ms)'); R['down'] = f'{type(e).__name__}: {e}'
    @a4.get('/send')
    def send_view(): mail4.send(Message('x', recipients=['u@x.test'], body='b')); return 'ok'
    a4.config['PROPAGATE_EXCEPTIONS'] = False; a4.logger.disabled = True
    r = a4.test_client().get('/send'); print('  视图里不处理这个异常 → HTTP', r.status_code); R['down_http'] = r.status_code
    print()
    print('== 七:一个连接发多封:mail.connect() 复用连接 vs 每封各建连接(10 封)')
    a, mail = mk(); n0 = len(h.msgs)
    with a.app_context():
        t0 = time.perf_counter()
        for i in range(10): mail.send(Message(f'a{i}', recipients=['u@x.test'], body='b'))
        t_each = ms(t0); ids_each = {x[0] for x in h.msgs[n0:]}; n1 = len(h.msgs)
        t0 = time.perf_counter()
        with mail.connect() as conn:
            for i in range(10): conn.send(Message(f'b{i}', recipients=['u@x.test'], body='b'))
        t_conn = ms(t0); ids_conn = {x[0] for x in h.msgs[n1:]}
    print(f'  每封各 mail.send:{t_each:.0f} ms,服务端看到 {len(ids_each)} 个 SMTP 会话;一个 mail.connect():{t_conn:.0f} ms,{len(ids_conn)} 个会话'); R['conn'] = [t_each, len(ids_each), t_conn, len(ids_conn)]
finally:
    ctl.stop()
save('f77', R)
