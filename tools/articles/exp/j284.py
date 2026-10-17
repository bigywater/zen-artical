import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j284'); R = {}
CP = mcp('org.eclipse.jetty.ee10.websocket:jetty-ee10-websocket-jakarta-server:12.0.16', 'org.eclipse.jetty.ee10:jetty-ee10-servlet:12.0.16', 'org.eclipse.jetty:jetty-server:12.0.16', 'org.slf4j:slf4j-simple:2.0.13')
MAIN = r'''
import jakarta.websocket.*; import jakarta.websocket.server.*; import org.eclipse.jetty.ee10.servlet.ServletContextHandler; import org.eclipse.jetty.ee10.websocket.jakarta.server.config.JakartaWebSocketServletContainerInitializer; import org.eclipse.jetty.server.Server; import org.eclipse.jetty.server.ServerConnector;
import java.net.*; import java.net.http.*; import java.nio.ByteBuffer; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
public class Main {
  static long T0 = System.nanoTime(); static long ms() { return (System.nanoTime() - T0) / 1_000_000; }
  static synchronized void say(String s) { System.out.println("RES [" + String.format("%5d", ms()) + " ms] " + s); } static void sec(String s) { System.out.println("SEC " + s); }
  static String th() { String n = Thread.currentThread().getName(); return n.replaceAll("[0-9a-f]{6,}", "…").replaceAll("-\\d+$", "-N"); }
  static final AtomicInteger INSTANCES = new AtomicInteger();
  @ServerEndpoint("/ws/chat") public static class Chat { final int id = INSTANCES.incrementAndGet(); Session sess;
    @OnOpen public void open(Session s, EndpointConfig c) { sess = s; say("服务端 @OnOpen:endpoint 实例 #" + id + ",session " + s.getId().substring(0, 4) + "…,线程 " + th() + ",默认 maxIdleTimeout = " + s.getMaxIdleTimeout() + " ms,maxTextMessageBufferSize = " + s.getMaxTextMessageBufferSize()); }
    @OnMessage public String msg(String m, Session s) { say("服务端 @OnMessage:实例 #" + id + ",线程 " + th() + ",长度 " + m.length() + (m.length() < 20 ? ",内容 " + m : "")); if (m.equals("boom")) throw new IllegalStateException("@OnMessage 里抛出的异常"); if (m.equals("bigreason")) { try { s.close(new CloseReason(CloseReason.CloseCodes.NORMAL_CLOSURE, "x".repeat(200))); } catch (Throwable t) { say("服务端 s.close(reason 200 字符):" + t.getClass().getSimpleName() + ":" + t.getMessage()); } return "bigreason-handled"; } return "echo:" + (m.length() > 20 ? m.length() + " chars" : m); }
    @OnError public void err(Session s, Throwable t) { say("服务端 @OnError:实例 #" + id + ",线程 " + th() + "," + t.getClass().getSimpleName() + ":" + String.valueOf(t.getMessage()).replaceAll("\\s+", " ").substring(0, Math.min(90, String.valueOf(t.getMessage()).length()))); }
    @OnClose public void close(Session s, CloseReason r) { say("服务端 @OnClose:实例 #" + id + ",线程 " + th() + ",code = " + r.getCloseCode().getCode() + " (" + r.getCloseCode() + "),reason = \"" + r.getReasonPhrase() + "\""); } }
  @ServerEndpoint("/ws/big") public static class Big { @OnOpen public void open(Session s) { s.setMaxTextMessageBufferSize(512 * 1024); say("服务端(big)@OnOpen:把 maxTextMessageBufferSize 调到 512 KiB"); } @OnMessage public String m(String m) { say("服务端(big)@OnMessage:收到 " + m.length() + " 字符"); return "ok:" + m.length(); } @OnError public void e(Session s, Throwable t) { say("服务端(big)@OnError " + t.getClass().getSimpleName()); } @OnClose public void c(CloseReason r) { say("服务端(big)@OnClose code = " + r.getCloseCode().getCode()); } }
  @ServerEndpoint("/ws/idle") public static class Idle { @OnOpen public void open(Session s) { s.setMaxIdleTimeout(800); say("服务端(idle)@OnOpen:setMaxIdleTimeout(800)"); } @OnMessage public String m(String m) { return m; } @OnError public void e(Session s, Throwable t) { say("服务端(idle)@OnError " + t.getClass().getSimpleName() + ":" + String.valueOf(t.getMessage()).replaceAll("\\s+", " ")); } @OnClose public void c(CloseReason r) { say("服务端(idle)@OnClose code = " + r.getCloseCode().getCode() + " (" + r.getCloseCode() + "),reason = \"" + r.getReasonPhrase() + "\""); } }
  @ServerEndpoint("/ws/send") public static class Send { Session s; @OnOpen public void open(Session s) { this.s = s; } @OnMessage public void m(String m) throws Exception {
      if (!m.equals("go")) return; int T = 4, N = 500; AtomicInteger ok = new AtomicInteger(), fail = new AtomicInteger(); AtomicReference<String> first = new AtomicReference<>(); List<Thread> ts = new ArrayList<>();
      for (int t = 0; t < T; t++) { Thread th = new Thread(() -> { for (int i = 0; i < N; i++) { try { s.getBasicRemote().sendText("x"); ok.incrementAndGet(); } catch (Throwable e) { fail.incrementAndGet(); first.compareAndSet(null, e.getClass().getSimpleName() + ":" + String.valueOf(e.getMessage()).replaceAll("\\s+", " ")); } } }); ts.add(th); th.start(); } for (Thread t : ts) t.join();
      say("服务端(send):" + T + " 个线程各自对同一个 session 调用 getBasicRemote().sendText " + N + " 次:成功 " + ok + ",失败 " + fail + (first.get() == null ? "" : ",第一个异常 " + first.get()));
      AtomicInteger ok2 = new AtomicInteger(), fail2 = new AtomicInteger(); ts.clear(); for (int t = 0; t < T; t++) { Thread th = new Thread(() -> { for (int i = 0; i < N; i++) { try { synchronized (s) { s.getBasicRemote().sendText("y"); } ok2.incrementAndGet(); } catch (Throwable e) { fail2.incrementAndGet(); } } }); ts.add(th); th.start(); } for (Thread t : ts) t.join(); say("服务端(send):同样的发送放进 synchronized (session):成功 " + ok2 + ",失败 " + fail2);
      AtomicInteger ok3 = new AtomicInteger(), fail3 = new AtomicInteger(); ts.clear(); for (int t = 0; t < T; t++) { Thread th = new Thread(() -> { for (int i = 0; i < N; i++) { try { s.getAsyncRemote().sendText("z"); ok3.incrementAndGet(); } catch (Throwable e) { fail3.incrementAndGet(); } } }); ts.add(th); th.start(); } for (Thread t : ts) t.join(); say("服务端(send):改用 getAsyncRemote().sendText(并发调用):调用成功 " + ok3 + ",抛出异常 " + fail3); } @OnError public void e(Session s, Throwable t) { say("服务端(send)@OnError " + t.getClass().getSimpleName()); } }
  static class Cl implements WebSocket.Listener { final String name; final CountDownLatch closed = new CountDownLatch(1); final List<String> got = Collections.synchronizedList(new ArrayList<>()); final StringBuilder buf = new StringBuilder(); Cl(String n) { name = n; }
    public void onOpen(WebSocket w) { say("客户端(" + name + ") onOpen"); w.request(Long.MAX_VALUE); }
    public CompletionStage<?> onText(WebSocket w, CharSequence d, boolean last) { buf.append(d); if (last) { String s = buf.toString(); buf.setLength(0); got.add(s); if (s.length() > 1 && s.length() < 40) say("客户端(" + name + ") onText:" + s); } return null; }
    public CompletionStage<?> onClose(WebSocket w, int code, String reason) { say("客户端(" + name + ") onClose:code = " + code + ",reason = \"" + reason + "\""); closed.countDown(); return null; }
    public void onError(WebSocket w, Throwable e) { say("客户端(" + name + ") onError:" + e.getClass().getSimpleName() + ":" + String.valueOf(e.getMessage()).replaceAll("\\s+", " ")); closed.countDown(); } }
  static WebSocket connect(String path, Cl l) throws Exception { return HttpClient.newHttpClient().newWebSocketBuilder().buildAsync(URI.create("ws://127.0.0.1:9800" + path), l).get(5, TimeUnit.SECONDS); }
  public static void main(String[] a) throws Exception {
    Server server = new Server(); ServerConnector conn = new ServerConnector(server); conn.setPort(9800); server.addConnector(conn); ServletContextHandler ctx = new ServletContextHandler("/"); server.setHandler(ctx);
    JakartaWebSocketServletContainerInitializer.configure(ctx, (c, container) -> { container.addEndpoint(Chat.class); container.addEndpoint(Big.class); container.addEndpoint(Idle.class); container.addEndpoint(Send.class); }); server.start();
    try {
      sec("== 一:一次正常连接:回调的顺序、endpoint 实例与线程");
      Cl c1 = new Cl("A"); WebSocket w1 = connect("/ws/chat", c1); Thread.sleep(200); w1.sendText("hello", true).get(); Thread.sleep(200); w1.sendText("again", true).get(); Thread.sleep(200); say("客户端(A)发起正常关闭 sendClose(1000, \"bye\")"); w1.sendClose(1000, "bye").get(); c1.closed.await(3, TimeUnit.SECONDS); Thread.sleep(300);
      Cl c2 = new Cl("B"); WebSocket w2 = connect("/ws/chat", c2); Thread.sleep(200); w2.sendText("second-connection", true).get(); Thread.sleep(200); w2.sendClose(1000, "done").get(); c2.closed.await(3, TimeUnit.SECONDS); Thread.sleep(300);
      sec("== 二:几种关闭方式:客户端直接断开(abort)、服务端 @OnMessage 抛异常、空闲超时、过长的 reason");
      Cl c3 = new Cl("C"); WebSocket w3 = connect("/ws/chat", c3); Thread.sleep(200); say("客户端(C)调用 abort()(不发送 close 帧,直接断开 TCP)"); w3.abort(); Thread.sleep(800);
      Cl c4 = new Cl("D"); WebSocket w4 = connect("/ws/chat", c4); Thread.sleep(200); w4.sendText("boom", true).get(); c4.closed.await(3, TimeUnit.SECONDS); Thread.sleep(300);
      Cl c5 = new Cl("E"); WebSocket w5 = connect("/ws/idle", c5); long t0 = System.nanoTime(); c5.closed.await(5, TimeUnit.SECONDS); say("客户端(E)一直空闲,从连接到被关闭用了约 " + (System.nanoTime() - t0) / 1_000_000 + " ms"); Thread.sleep(200);
      Cl c6 = new Cl("F"); WebSocket w6 = connect("/ws/chat", c6); Thread.sleep(200); w6.sendText("bigreason", true).get(); Thread.sleep(500); w6.sendClose(1000, "end").get(); c6.closed.await(3, TimeUnit.SECONDS); Thread.sleep(300);
      sec("== 三:消息大小限制");
      Cl c7 = new Cl("G"); WebSocket w7 = connect("/ws/chat", c7); Thread.sleep(200); w7.sendText("x".repeat(100_000), true).get(); c7.closed.await(3, TimeUnit.SECONDS); Thread.sleep(300);
      Cl c8 = new Cl("H"); WebSocket w8 = connect("/ws/big", c8); Thread.sleep(200); w8.sendText("x".repeat(100_000), true).get(); Thread.sleep(500); w8.sendClose(1000, "ok").get(); c8.closed.await(3, TimeUnit.SECONDS); Thread.sleep(300);
      sec("== 四:对同一个 session 并发发送");
      Cl c9 = new Cl("I"); WebSocket w9 = connect("/ws/send", c9); Thread.sleep(200); w9.sendText("go", true).get(); Thread.sleep(2500); say("客户端(I)实际收到的消息条数 " + c9.got.size()); try { w9.sendClose(1000, "ok").get(2, TimeUnit.SECONDS); } catch (Exception e) { }
    } finally { server.stop(); }
  }
}
'''
d = jdir('j284a'); write(d, {'Main.java': MAIN}); E = jenv('21'); (d / 'out').mkdir(exist_ok=True)
rc = subprocess.run(['javac', '-d', 'out', '-cp', CP, 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:3500]); sys.exit()
r = subprocess.run(['java', '-Dorg.slf4j.simpleLogger.defaultLogLevel=error', '-cp', 'out:' + CP, 'Main'], cwd=d, env=E, capture_output=True, text=True, timeout=240)
for l in (r.stdout + r.stderr).splitlines():
    if l.startswith('SEC '): print(l[4:])
    elif l.startswith('RES '): print('  ' + l[4:])
    elif r.returncode != 0 and l.strip(): print('  ! ' + l[:220])
