import sys, os, re, time, json, socket, struct, base64, hashlib, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x63'); CP = scp('org.springframework.boot:spring-boot-starter-websocket')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.io.IOException; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean; import org.springframework.messaging.handler.annotation.*; import org.springframework.messaging.simp.config.MessageBrokerRegistry; import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;
import org.springframework.stereotype.Controller; import org.springframework.web.socket.*; import org.springframework.web.socket.config.annotation.*; import org.springframework.web.socket.handler.*; import org.springframework.web.socket.server.standard.ServletServerContainerFactoryBean;
@SpringBootApplication @EnableWebSocket @EnableWebSocketMessageBroker @Controller
public class Main implements WebSocketConfigurer, WebSocketMessageBrokerConfigurer {
  public static class Echo extends TextWebSocketHandler {
    public void afterConnectionEstablished(WebSocketSession s) { System.out.println("RES EV 连接建立:session=" + s.getId().substring(0, 4) + " 线程=" + Thread.currentThread().getName() + " 协议=" + s.getAcceptedProtocol()); }
    protected void handleTextMessage(WebSocketSession s, TextMessage m) throws IOException { s.sendMessage(new TextMessage("echo:" + (m.getPayloadLength() > 40 ? "<" + m.getPayloadLength() + " 字节>" : m.getPayload()))); }
    public void afterConnectionClosed(WebSocketSession s, CloseStatus st) { System.out.println("RES EV 连接关闭:" + st); }
    public void handleTransportError(WebSocketSession s, Throwable e) { System.out.println("RES EV 传输错误:" + e.getClass().getSimpleName()); }
  }
  public static class Conc extends TextWebSocketHandler {
    final boolean safe; Conc(boolean safe) { this.safe = safe; }
    protected void handleTextMessage(WebSocketSession s0, TextMessage m) throws Exception {
      WebSocketSession s = safe ? new ConcurrentWebSocketSessionDecorator(s0, 5000, 1 << 20) : s0; AtomicInteger errs = new AtomicInteger(), ok = new AtomicInteger(); AtomicReference<String> first = new AtomicReference<>(""); CountDownLatch l = new CountDownLatch(2);
      for (int t = 0; t < 2; t++) { final int tt = t; new Thread(() -> { for (int i = 0; i < 300; i++) { try { s.sendMessage(new TextMessage("t" + tt + "-" + i)); ok.incrementAndGet(); } catch (Exception e) { if (errs.incrementAndGet() == 1) first.set(e.getClass().getSimpleName() + ": " + String.valueOf(e.getMessage()).replaceAll("\\s+", " ")); } } l.countDown(); }).start(); }
      l.await(); Thread.sleep(200); try { s0.sendMessage(new TextMessage("SUMMARY ok=" + ok.get() + " errors=" + errs.get() + " first=" + first.get())); } catch (Exception e) { System.out.println("RES EV 汇总发送失败 " + e.getClass().getSimpleName()); }
    } }
  public void registerWebSocketHandlers(WebSocketHandlerRegistry r) { r.addHandler(new Echo(), "/ws/echo").setAllowedOrigins("*"); r.addHandler(new Conc(false), "/ws/conc-raw").setAllowedOrigins("*"); r.addHandler(new Conc(true), "/ws/conc-safe").setAllowedOrigins("*"); }
  public void registerStompEndpoints(org.springframework.web.socket.config.annotation.StompEndpointRegistry r) { r.addEndpoint("/stomp").setAllowedOrigins("*"); }
  public void configureMessageBroker(MessageBrokerRegistry r) {
    r.setApplicationDestinationPrefixes("/app"); var sb = r.enableSimpleBroker("/topic");
    if (System.getProperty("hb") != null) { var ts = new ThreadPoolTaskScheduler(); ts.setPoolSize(1); ts.initialize(); sb.setHeartbeatValue(new long[]{Long.parseLong(System.getProperty("hb")), Long.parseLong(System.getProperty("hb"))}).setTaskScheduler(ts); }
  }
  @MessageMapping("/hello") @SendTo("/topic/greetings") public String hello(String name) { System.out.println("RES EV @MessageMapping 收到 '" + name + "' 线程=" + Thread.currentThread().getName()); return "Hello, " + name; }
  @Bean @ConditionalOnProperty("bigbuf") ServletServerContainerFactoryBean bigBuf() { var f = new ServletServerContainerFactoryBean(); f.setMaxTextMessageBufferSize(65536); return f; }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x63', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
class WS:
    def __init__(self, port, path, headers=None):
        self.s = socket.create_connection(('127.0.0.1', port), 10); key = base64.b64encode(os.urandom(16)).decode()
        req = f'GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nOrigin: http://x.example\r\n' + ''.join(f'{k}: {v}\r\n' for k, v in (headers or {}).items()) + '\r\n'
        self.s.sendall(req.encode()); buf = b''
        while b'\r\n\r\n' not in buf: buf += self.s.recv(4096)
        head, self.buf = buf.split(b'\r\n\r\n', 1); lines = head.decode().split('\r\n'); self.status = lines[0]; self.h = {l.split(':', 1)[0].lower(): l.split(':', 1)[1].strip() for l in lines[1:] if ':' in l}
        self.ok_accept = self.h.get('sec-websocket-accept') == base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
    def send(self, text, op=1):
        p = text.encode() if isinstance(text, str) else text; n = len(p); mask = os.urandom(4); hdr = bytes([0x80 | op])
        hdr += bytes([0x80 | n]) if n < 126 else (bytes([0x80 | 126]) + struct.pack('>H', n) if n < 65536 else bytes([0x80 | 127]) + struct.pack('>Q', n))
        self.s.sendall(hdr + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(p)))
    def _read(self, n):
        while len(self.buf) < n:
            d = self.s.recv(65536)
            if not d: raise ConnectionError('closed')
            self.buf += d
        r, self.buf = self.buf[:n], self.buf[n:]; return r
    def recv(self, timeout=3):
        self.s.settimeout(timeout)
        try:
            b0, b1 = self._read(2); op = b0 & 0x0f; n = b1 & 0x7f
            if n == 126: n = struct.unpack('>H', self._read(2))[0]
            elif n == 127: n = struct.unpack('>Q', self._read(8))[0]
            p = self._read(n); return op, p
        except socket.timeout: return None, None
        except ConnectionError: return -1, b''
    def recv_text(self, timeout=3):
        op, p = self.recv(timeout)
        if op == 1: return p.decode()
        if op == 8: return 'CLOSE code=%d' % struct.unpack('>H', p[:2])[0] if len(p) >= 2 else 'CLOSE'
        return None if op is None else f'(op={op})'
    def close(self): 
        try: self.s.close()
        except Exception: pass
def stomp(ws_text): return ws_text
def frame(cmd, headers=None, body=''): return cmd + '\n' + ''.join(f'{k}:{v}\n' for k, v in (headers or {}).items()) + '\n' + body + '\0'
def show_frame(t):
    if t is None: return '(超时,没有收到)'
    return t.replace('\0', '').replace('\n', ' | ').strip(' |')
def evs(app, n0): return [l[7:] for l in app.log().splitlines()[n0:] if l.startswith('RES EV ')]
def run(props, f, title, head=True):
    app = SApp(b, 'demo.Main', props=props).start(); print(f'== {title}' if head else f'  -- {title}'); f(app); app.stop()
print('Spring Boot 4.0.8 / Spring Framework 7.0.9(spring-boot-starter-websocket,Tomcat 11.0.24);客户端是 Python 手写的最小 WebSocket 客户端(握手、掩码、帧收发),STOMP 帧手工拼')
def one(app):
    port = int(app.props['server.port']); n0 = len(app.log().splitlines()); ws = WS(port, '/ws/echo')
    print(f'  握手响应:{ws.status};Upgrade={ws.h.get("upgrade")};Connection={ws.h.get("connection")};Sec-WebSocket-Accept 校验通过={ws.ok_accept}')
    ws.send('hello'); print('  发送 hello → 收到', ws.recv_text()); ws.send('x' * 4000); print('  发送 4000 字节 → 收到', ws.recv_text()); ws.send('x' * 8192); print('  发送 8192 字节 → 收到', ws.recv_text()); ws.send('x' * 8193); print('  发送 8193 字节 → 收到', ws.recv_text()); ws.close(); time.sleep(0.3)
    [print('  (服务端)' + e) for e in evs(app, n0)]
run({}, one, '一:原生 WebSocket:握手、回显,以及消息大小的默认上限')
def two(app):
    port = int(app.props['server.port']); ws = WS(port, '/ws/echo'); ws.send('x' * 20000); print('  bigbuf:发送 20000 字节 →', ws.recv_text()); ws.send('x' * 65536); print('  发送 65536 字节 →', ws.recv_text()); ws.send('x' * 65537); print('  发送 65537 字节 →', ws.recv_text()); ws.close()
run({'bigbuf': 'true'}, two, '二:ServletServerContainerFactoryBean.setMaxTextMessageBufferSize(65536)')
def three(app):
    port = int(app.props['server.port'])
    for path, lab in [('/ws/conc-raw', '直接用 session.sendMessage,两个线程各发 300 条'), ('/ws/conc-safe', '用 ConcurrentWebSocketSessionDecorator 包起来,两个线程各发 300 条')]:
        ws = WS(port, path); ws.send('go'); got = 0; summary = None
        while True:
            t = ws.recv_text(timeout=3)
            if t is None or t.startswith('CLOSE') or t == '(op=-1)': summary = summary or ('(连接状态:' + str(t) + ')'); break
            if t.startswith('SUMMARY'): summary = t; break
            got += 1
        print(f'  {lab}:客户端收到 {got} 条普通消息;{summary}'); ws.close()
run({}, three, '三:多个线程同时向同一个 session 发消息')
def four(app):
    port = int(app.props['server.port']); n0 = len(app.log().splitlines())
    c1 = WS(port, '/stomp'); c2 = WS(port, '/stomp'); c3 = WS(port, '/stomp')
    for i, c in enumerate((c1, c2, c3), 1): c.send(frame('CONNECT', {'accept-version': '1.2', 'heart-beat': '0,0'})); print(f'  客户端 {i} CONNECT → ', show_frame(c.recv_text()))
    c1.send(frame('SUBSCRIBE', {'id': 'sub-1', 'destination': '/topic/greetings'})); c2.send(frame('SUBSCRIBE', {'id': 'sub-2', 'destination': '/topic/greetings'})); time.sleep(0.2)
    c3.send(frame('SEND', {'destination': '/app/hello', 'content-type': 'text/plain'}, 'Tom')); time.sleep(0.3)
    print('  客户端 3(没订阅)发 SEND /app/hello "Tom" 之后:')
    for i, c in enumerate((c1, c2, c3), 1): print(f'    客户端 {i} 收到:', show_frame(c.recv_text(timeout=1)))
    c3.send(frame('SEND', {'destination': '/topic/greetings', 'content-type': 'text/plain'}, '绕过 @MessageMapping,直接发到 /topic')); time.sleep(0.3)
    print('  客户端 3 直接 SEND 到 /topic/greetings(不经过 @MessageMapping):')
    for i, c in enumerate((c1, c2), 1): print(f'    客户端 {i} 收到:', show_frame(c.recv_text(timeout=1)))
    c3.send(frame('SEND', {'destination': '/app/unknown', 'content-type': 'text/plain'}, 'x')); print('  SEND 到没有 @MessageMapping 的 /app/unknown →', show_frame(c3.recv_text(timeout=1)))
    time.sleep(0.2); [print('  (服务端)' + e) for e in evs(app, n0)]
    for c in (c1, c2, c3): c.close()
run({}, four, '四:STOMP:订阅、@MessageMapping 与 @SendTo 的广播、绕过应用目的地')
def five(app):
    port = int(app.props['server.port']); c = WS(port, '/stomp'); c.send(frame('CONNECT', {'accept-version': '1.2', 'heart-beat': '10000,10000'})); print('  客户端声明 heart-beat:10000,10000 →', show_frame(c.recv_text()))
run({}, five, '五:心跳:简单代理默认配置')
run({'hb': '5000'}, five, '五补:enableSimpleBroker 设置 heartbeat 5000 并提供 TaskScheduler', False)
def six_pair():
    a = SApp(b, 'demo.Main', props={}, name='appA').start(); bb = SApp(b, 'demo.Main', props={}, name='appB').start(); print('== 六:两个应用实例(简单代理在内存里,各管各的)')
    pa, pb = int(a.props['server.port']), int(bb.props['server.port'])
    sa = WS(pa, '/stomp'); sa.send(frame('CONNECT', {'accept-version': '1.2'})); sa.recv_text(); sa.send(frame('SUBSCRIBE', {'id': 's', 'destination': '/topic/greetings'}))
    sb2 = WS(pb, '/stomp'); sb2.send(frame('CONNECT', {'accept-version': '1.2'})); sb2.recv_text(); sb2.send(frame('SEND', {'destination': '/app/hello', 'content-type': 'text/plain'}, 'Alice')); time.sleep(0.4)
    print('  订阅者连在实例 A,发送者连在实例 B 发 SEND /app/hello → 实例 A 上的订阅者收到:', show_frame(sa.recv_text(timeout=1.5)))
    sb2.send(frame('SUBSCRIBE', {'id': 's', 'destination': '/topic/greetings'})); time.sleep(0.2); sb2.send(frame('SEND', {'destination': '/app/hello', 'content-type': 'text/plain'}, 'Bob')); time.sleep(0.4)
    print('  同一个发送者(实例 B)自己订阅后再发 Bob:实例 B 上的订阅者收到:', show_frame(sb2.recv_text(timeout=1.5)), ';实例 A 上的订阅者收到:', show_frame(sa.recv_text(timeout=1.0)))
    sa.close(); sb2.close(); a.stop(); bb.stop()
six_pair()
