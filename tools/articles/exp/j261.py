import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j261'); R = {}
MAIN = r'''
import java.net.*; import java.nio.*; import java.nio.channels.*; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
public class Main {
  static final int PORT = 9741; static final List<AsynchronousSocketChannel> KEEP = new CopyOnWriteArrayList<>(); static long T0 = System.nanoTime(); static long ms() { return (System.nanoTime() - T0) / 1_000_000; }
  static String tn() { return Thread.currentThread().getName(); }
  static void say(String s) { System.out.println("RES " + s); }
  public static void main(String[] a) throws Exception {
    String mode = a[0];
    if (mode.equals("threads")) {
      AsynchronousChannelGroup g = AsynchronousChannelGroup.withFixedThreadPool(2, r -> { Thread t = new Thread(r); t.setName("aio-" + t.getId()); return t; });
      AsynchronousServerSocketChannel srv = AsynchronousServerSocketChannel.open(g).bind(new InetSocketAddress("127.0.0.1", PORT)); CountDownLatch done = new CountDownLatch(1); Set<String> acceptT = ConcurrentHashMap.newKeySet(), readT = ConcurrentHashMap.newKeySet(); AtomicInteger directReads = new AtomicInteger(), reads = new AtomicInteger();
      srv.accept(null, new CompletionHandler<AsynchronousSocketChannel, Object>() { public void completed(AsynchronousSocketChannel c, Object o) { acceptT.add(tn()); ByteBuffer b = ByteBuffer.allocate(16); c.read(b, null, new CompletionHandler<Integer, Object>() { public void completed(Integer n, Object x) { readT.add(tn()); reads.incrementAndGet(); done.countDown(); } public void failed(Throwable t, Object x) { } }); } public void failed(Throwable t, Object o) { } });
      AsynchronousSocketChannel cl = AsynchronousSocketChannel.open(); Future<Void> f = cl.connect(new InetSocketAddress("127.0.0.1", PORT)); f.get(); Thread.sleep(100); cl.write(ByteBuffer.wrap("hi".getBytes())).get(); done.await();
      say("accept 回调运行在线程 " + acceptT + ";read 回调运行在线程 " + readT + "(主线程是 " + tn() + ",固定线程池 2 个线程)"); cl.close(); srv.close(); g.shutdownNow();
    } else if (mode.equals("depth")) {
      int maxOnStack = Integer.getInteger("sun.nio.ch.maxCompletionHandlersOnStack", -1);
      AsynchronousChannelGroup g = AsynchronousChannelGroup.withFixedThreadPool(1, r -> new Thread(r, "aio")); AsynchronousServerSocketChannel srv = AsynchronousServerSocketChannel.open(g).bind(new InetSocketAddress("127.0.0.1", PORT)); int N = 5000; byte[] payload = new byte[N]; Arrays.fill(payload, (byte) 'x');
      Future<AsynchronousSocketChannel> acc = srv.accept(); AsynchronousSocketChannel cl = AsynchronousSocketChannel.open(); cl.connect(new InetSocketAddress("127.0.0.1", PORT)).get(); AsynchronousSocketChannel sc = acc.get();
      cl.write(ByteBuffer.wrap(payload)).get(); Thread.sleep(200); // 5000 字节已经在 socket 缓冲里,全部可立即读出
      AtomicInteger count = new AtomicInteger(), maxDepth = new AtomicInteger(), calls = new AtomicInteger(); AtomicLong total = new AtomicLong(); CountDownLatch done = new CountDownLatch(1); int base = new Throwable().getStackTrace().length; Map<Integer, Integer> depthHist = new TreeMap<>(); Set<String> threads = ConcurrentHashMap.newKeySet();
      ByteBuffer buf = ByteBuffer.allocate(1);
      sc.read(buf, null, new CompletionHandler<Integer, Object>() { public void completed(Integer n, Object o) { int depth = new Throwable().getStackTrace().length; synchronized (depthHist) { depthHist.merge(depth, 1, Integer::sum); } maxDepth.accumulateAndGet(depth, Math::max); threads.add(tn()); if (total.addAndGet(n) >= N) { done.countDown(); return; } buf.clear(); sc.read(buf, null, this); } public void failed(Throwable t, Object o) { done.countDown(); } });
      done.await(10, TimeUnit.SECONDS); int distinct = depthHist.size(); int mx = depthHist.keySet().stream().mapToInt(i -> i).max().orElse(0); int mn = depthHist.keySet().stream().mapToInt(i -> i).min().orElse(0);
      say("sun.nio.ch.maxCompletionHandlersOnStack = " + (maxOnStack < 0 ? "默认(未设置)" : maxOnStack) + ":每次读 1 字节、共 " + N + " 次回调,运行在线程 " + threads + ";回调里栈深度最小 " + mn + "、最大 " + mx + ",共 " + distinct + " 种深度");
      List<String> top = new ArrayList<>(); depthHist.forEach((k, v) -> { if (top.size() < 8) top.add(k + "×" + v); }); say("  栈深度分布(前几种):" + top);
      cl.close(); sc.close(); srv.close(); g.shutdownNow();
    } else if (mode.equals("pending")) {
      AsynchronousServerSocketChannel srv = AsynchronousServerSocketChannel.open().bind(new InetSocketAddress("127.0.0.1", PORT)); Future<AsynchronousSocketChannel> acc = srv.accept(); AsynchronousSocketChannel cl = AsynchronousSocketChannel.open(); cl.connect(new InetSocketAddress("127.0.0.1", PORT)).get(); AsynchronousSocketChannel sc = acc.get();
      Future<Integer> r1 = sc.read(ByteBuffer.allocate(8)); try { sc.read(ByteBuffer.allocate(8)); say("第二个 read 成功了"); } catch (Throwable t) { say("已有一个 read 未完成时再调 read:" + t.getClass().getSimpleName()); }
      cl.write(ByteBuffer.wrap("abc".getBytes())).get(); say("第一个 read 之后完成:" + r1.get() + " 字节");
      Future<Integer> w1 = null; int issued = 0; while (true) { w1 = cl.write(ByteBuffer.allocate(1 << 20)); issued++; Thread.sleep(50); if (!w1.isDone()) break; if (issued > 200) break; }
      say("对端不读,连续发起 1 MiB 的 write:第 " + issued + " 个 write 在 50 ms 后仍未完成(此前每个都立即完成了)"); try { cl.write(ByteBuffer.allocate(8)); say("第二个 write 成功了"); } catch (Throwable t) { say("已有一个 write 未完成时再调 write:" + t.getClass().getSimpleName()); }
      try { cl.connect(new InetSocketAddress("127.0.0.1", PORT)); } catch (Throwable t) { say("已连接的通道再 connect:" + t.getClass().getSimpleName()); }
      sc.close(); cl.close(); srv.close();
      AsynchronousSocketChannel un = AsynchronousSocketChannel.open(); try { un.read(ByteBuffer.allocate(8)); } catch (Throwable t) { say("未连接就 read:" + t.getClass().getSimpleName()); } un.close();
      ByteBuffer ro = ByteBuffer.allocate(8).asReadOnlyBuffer(); AsynchronousServerSocketChannel s2 = AsynchronousServerSocketChannel.open().bind(new InetSocketAddress("127.0.0.1", PORT)); Future<AsynchronousSocketChannel> a2 = s2.accept(); AsynchronousSocketChannel c2 = AsynchronousSocketChannel.open(); c2.connect(new InetSocketAddress("127.0.0.1", PORT)).get(); a2.get(); try { c2.read(ro); } catch (Throwable t) { say("用只读 ByteBuffer 做 read 的目标:" + t.getClass().getSimpleName()); } c2.close(); s2.close();
    } else if (mode.equals("partial")) {
      AsynchronousServerSocketChannel srv = AsynchronousServerSocketChannel.open().bind(new InetSocketAddress("127.0.0.1", PORT)); Future<AsynchronousSocketChannel> acc = srv.accept(); AsynchronousSocketChannel cl = AsynchronousSocketChannel.open(); cl.connect(new InetSocketAddress("127.0.0.1", PORT)).get(); AsynchronousSocketChannel sc = acc.get();
      ByteBuffer big = ByteBuffer.allocate(16 << 20); long t0 = System.nanoTime(); int first = cl.write(big).get(); say("对端一直不读时,write(16 MiB 的 ByteBuffer) 第一次完成写了 " + first + " 字节(= " + first / 1024 + " KiB),缓冲区还剩 " + big.remaining() + " 字节,耗时 " + (System.nanoTime() - t0) / 1_000_000 + " ms");
      int rounds = 1; long wrote = first; AtomicBoolean stop = new AtomicBoolean(); Thread rd = new Thread(() -> { ByteBuffer rb = ByteBuffer.allocate(1 << 20); try { while (!stop.get()) { rb.clear(); if (sc.read(rb).get() < 0) break; } } catch (Exception e) { } }); rd.setDaemon(true); rd.start();
      while (big.hasRemaining()) { wrote += cl.write(big).get(); rounds++; } say("对端开始读之后,要连续调用 write " + rounds + " 次才写完 16 MiB(共 " + wrote + " 字节)");
      stop.set(true); cl.close(); sc.close(); srv.close();
    } else if (mode.equals("timeout")) {
      AsynchronousServerSocketChannel srv = AsynchronousServerSocketChannel.open().bind(new InetSocketAddress("127.0.0.1", PORT)); Future<AsynchronousSocketChannel> acc = srv.accept(); AsynchronousSocketChannel cl = AsynchronousSocketChannel.open(); cl.connect(new InetSocketAddress("127.0.0.1", PORT)).get(); AsynchronousSocketChannel sc = acc.get();
      CountDownLatch l = new CountDownLatch(1); long t0 = System.nanoTime(); sc.read(ByteBuffer.allocate(8), 300, TimeUnit.MILLISECONDS, null, new CompletionHandler<Integer, Object>() { public void completed(Integer n, Object o) { l.countDown(); } public void failed(Throwable t, Object o) { say("read(300 ms 超时) 的 failed 回调:" + t.getClass().getSimpleName() + ",用时 " + (System.nanoTime() - t0) / 1_000_000 + " ms,回调线程 " + tn()); l.countDown(); } }); l.await();
      try { Future<Integer> f = sc.read(ByteBuffer.allocate(8)); cl.write(ByteBuffer.wrap("z".getBytes())).get(); say("超时之后再 read:没有立即抛异常,结果 = " + f.get(1, TimeUnit.SECONDS)); } catch (Throwable t) { say("超时之后再 read:" + t.getClass().getSimpleName() + (t.getCause() != null ? "(原因 " + t.getCause().getClass().getSimpleName() + ")" : "")); }
      say("超时之后通道 isOpen = " + sc.isOpen()); cl.close(); sc.close(); srv.close();
    } else if (mode.equals("fail")) {
      Thread.setDefaultUncaughtExceptionHandler((t, e) -> say("默认 UncaughtExceptionHandler 收到(线程 " + t.getName() + "):" + e));
      AtomicInteger made = new AtomicInteger(); AsynchronousChannelGroup g = AsynchronousChannelGroup.withFixedThreadPool(1, r -> { Thread t = new Thread(r, "aio-" + made.incrementAndGet()); return t; });
      AsynchronousServerSocketChannel srv = AsynchronousServerSocketChannel.open(g).bind(new InetSocketAddress("127.0.0.1", PORT)); CountDownLatch done = new CountDownLatch(1);
      srv.accept(null, new CompletionHandler<AsynchronousSocketChannel, Object>() { public void completed(AsynchronousSocketChannel c, Object o) { KEEP.add(c); say("accept 回调在线程 " + tn() + " 里抛出 RuntimeException"); throw new RuntimeException("回调里的异常"); } public void failed(Throwable t, Object o) { } });
      AsynchronousSocketChannel cl = AsynchronousSocketChannel.open(); cl.connect(new InetSocketAddress("127.0.0.1", PORT)).get(); Thread.sleep(500);
      Future<AsynchronousSocketChannel> f2 = srv.accept(); AsynchronousSocketChannel cl2 = AsynchronousSocketChannel.open(); cl2.connect(new InetSocketAddress("127.0.0.1", PORT)).get(); AsynchronousSocketChannel acc2 = f2.get(2, TimeUnit.SECONDS); say("回调抛异常之后:ThreadFactory 一共创建了 " + made.get() + " 个线程;下一个 accept 的 Future 在 2 秒内完成了");
      long t0 = System.nanoTime(); g.shutdown(); say("group.shutdown() 之后 isShutdown = " + g.isShutdown() + ",isTerminated = " + g.isTerminated() + "(还有打开的通道)"); say("awaitTermination(500 ms) = " + g.awaitTermination(500, TimeUnit.MILLISECONDS)); cl.close(); cl2.close(); srv.close();
      say("关闭了客户端通道 cl、cl2 和监听通道 srv 之后 awaitTermination(1 s) = " + g.awaitTermination(1, TimeUnit.SECONDS) + "(accept 得到的两个服务端通道还开着)");
      acc2.close(); say("再关闭第二个 accept 得到的通道之后 awaitTermination(1 s) = " + g.awaitTermination(1, TimeUnit.SECONDS)); for (AsynchronousSocketChannel k : KEEP) k.close(); say("最后关闭第一个 accept 得到的通道(就是抛异常的回调里拿到的那个)之后 awaitTermination(2 s) = " + g.awaitTermination(2, TimeUnit.SECONDS) + ",isTerminated = " + g.isTerminated() + ",耗时 " + (System.nanoTime() - t0) / 1_000_000 + " ms");
    }
    System.exit(0);
  }
}
'''
d = jdir('j261a'); (d / 'Main.java').write_text(MAIN); E = jenv('21')
rc = subprocess.run(['javac', '-d', 'out', 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2500]); sys.exit()
def jv(mode, flags=(), timeout=60):
    r = subprocess.run(['java', *flags, '-cp', 'out', 'Main', mode], cwd=d, env=E, capture_output=True, text=True, timeout=timeout); o = r.stdout + r.stderr
    return [l[4:] for l in o.splitlines() if l.startswith('RES ')] or [o.strip()[:300]]
print('== 一:完成回调运行在哪个线程')
for l in jv('threads'): print('  ' + l)
print('== 二:数据已经就绪时的“直接调用”与栈深度:对端先写了 5000 字节,服务端每次读 1 字节、在回调里再发起下一次读(1 个线程的线程组)')
for lab, fl in (('默认', ()), ('-Dsun.nio.ch.maxCompletionHandlersOnStack=0', ('-Dsun.nio.ch.maxCompletionHandlersOnStack=0',)), ('-Dsun.nio.ch.maxCompletionHandlersOnStack=64', ('-Dsun.nio.ch.maxCompletionHandlersOnStack=64',))):
    print(f'  [{lab}]'); [print('      ' + l) for l in jv('depth', fl)]
print('== 三:同一个通道上的并发限制')
for l in jv('pending'): print('  ' + l)
print('== 四:部分写:write 完成时不一定写完了整个 ByteBuffer')
for l in jv('partial'): print('  ' + l)
print('== 五:读超时')
for l in jv('timeout'): print('  ' + l)
print('== 六:回调抛异常与线程组关闭')
for l in jv('fail'): print('  ' + l)
