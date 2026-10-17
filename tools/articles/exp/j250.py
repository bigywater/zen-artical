import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j250'); R = {}
MAIN = r'''
import java.net.*; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
public class Main {
  static final InheritableThreadLocal<String> ITL = new InheritableThreadLocal<>();
  static String info(Thread t) { return t.getName() + "(daemon=" + t.isDaemon() + ", prio=" + t.getPriority() + ")"; }
  public static void main(String[] a) throws Exception {
    String mode = a[0];
    if (mode.equals("main")) {
      System.out.println("== 一:线程的名字、daemon 与优先级:new Thread 继承创建者,Executors.defaultThreadFactory 不继承");
      Thread plain = new Thread(() -> { }); System.out.println("  main 线程里 new Thread:" + info(plain));
      AtomicReference<String> fromDaemon = new AtomicReference<>(), fromPrio = new AtomicReference<>(), factoryFromDaemon = new AtomicReference<>();
      Thread d = new Thread(() -> { fromDaemon.set(info(new Thread(() -> { }))); factoryFromDaemon.set(info(Executors.defaultThreadFactory().newThread(() -> { }))); }); d.setDaemon(true); d.start(); d.join();
      Thread p = new Thread(() -> fromPrio.set(info(new Thread(() -> { })))); p.setPriority(9); p.start(); p.join();
      System.out.println("  在 daemon 线程里 new Thread:" + fromDaemon.get() + ";在 daemon 线程里用 defaultThreadFactory:" + factoryFromDaemon.get()); System.out.println("  在优先级 9 的线程里 new Thread:" + fromPrio.get());
      ExecutorService ex = Executors.newFixedThreadPool(2); Set<String> names = new TreeSet<>(); CountDownLatch l = new CountDownLatch(4); for (int i = 0; i < 4; i++) ex.submit(() -> { names.add(info(Thread.currentThread()) + " 组 " + Thread.currentThread().getThreadGroup().getName()); l.countDown(); try { Thread.sleep(50); } catch (InterruptedException e) { } }); l.await(); ex.shutdown(); System.out.println("  固定线程池 2 个线程的默认名字:" + names);
      System.out.println("== 二:未捕获异常:execute 与 submit 的区别,以及线程被替换");
      List<String> log = Collections.synchronizedList(new ArrayList<>()); AtomicInteger made = new AtomicInteger();
      ThreadFactory tf = r -> { Thread t = new Thread(r, "worker-" + made.incrementAndGet()); t.setUncaughtExceptionHandler((th, e) -> log.add("handler 收到:线程 " + th.getName() + ",异常 " + e.getMessage())); return t; };
      ExecutorService ex2 = Executors.newFixedThreadPool(1, tf); Future<?> f = ex2.submit(() -> { throw new RuntimeException("submit 里的异常"); }); try { f.get(); } catch (ExecutionException e) { log.add("submit:handler 没有被调用;Future.get() 抛 ExecutionException(" + e.getCause().getMessage() + ")"); }
      ex2.submit(() -> log.add("第二个任务在 " + Thread.currentThread().getName() + " 上运行")).get(); ex2.execute(() -> { throw new RuntimeException("execute 里的异常"); }); Thread.sleep(200);
      ex2.submit(() -> log.add("execute 抛异常之后的任务在 " + Thread.currentThread().getName() + " 上运行")).get(); log.add("ThreadFactory 一共创建了 " + made.get() + " 个线程"); ex2.shutdown(); log.forEach(s -> System.out.println("  " + s));
      System.out.println("== 三:线程池里的线程在创建时“拍下”创建者的上下文:context ClassLoader 与 InheritableThreadLocal");
      ClassLoader mainCl = Thread.currentThread().getContextClassLoader(); URLClassLoader custom = new URLClassLoader("custom-loader", new URL[0], mainCl); ITL.set("main-的值");
      ExecutorService ex3 = Executors.newFixedThreadPool(1); AtomicReference<Thread> first = new AtomicReference<>();
      Thread submitter = new Thread(() -> { Thread.currentThread().setContextClassLoader(custom); ITL.set("submitter-的值"); try { ex3.submit(() -> first.set(Thread.currentThread())).get(); } catch (Exception e) { } }, "submitter"); submitter.start(); submitter.join();
      ex3.submit(() -> System.out.println("  池线程(由 submitter 线程第一次提交时创建)的 context ClassLoader = " + Thread.currentThread().getContextClassLoader().getName() + ",InheritableThreadLocal = " + ITL.get())).get();
      System.out.println("  main 线程现在的 context ClassLoader = " + Thread.currentThread().getContextClassLoader().getClass().getSimpleName() + "(" + Thread.currentThread().getContextClassLoader().getName() + "),InheritableThreadLocal = " + ITL.get() + ";main 再提交任务也不会更新池线程的这两个值"); ex3.shutdown();
      System.out.println("== 五:线程什么时候被创建:ThreadFactory 的调用次数");
      AtomicInteger calls = new AtomicInteger(); ThreadFactory counting = r -> { calls.incrementAndGet(); return new Thread(r); }; ThreadPoolExecutor tp = new ThreadPoolExecutor(2, 4, 100, TimeUnit.MILLISECONDS, new LinkedBlockingQueue<>(2), counting);
      System.out.println("  new ThreadPoolExecutor(2, 4, 队列 2):构造后 ThreadFactory 调用 " + calls.get() + " 次(线程是惰性创建的)");
      CountDownLatch go = new CountDownLatch(1); String st = ""; for (int i = 1; i <= 6; i++) { tp.execute(() -> { try { go.await(); } catch (InterruptedException e) { } }); st += "第 " + i + " 个任务后 " + calls.get() + " 次,"; } System.out.println("  连续提交 6 个阻塞任务:" + st.substring(0, st.length() - 1));
      go.countDown(); Thread.sleep(500); System.out.println("  任务结束 500 ms 后(keepAlive 100 ms,默认不回收核心线程):池大小 " + tp.getPoolSize() + ",ThreadFactory 累计 " + calls.get() + " 次"); tp.allowCoreThreadTimeOut(true); Thread.sleep(500); System.out.println("  allowCoreThreadTimeOut(true) 后再等 500 ms:池大小 " + tp.getPoolSize()); tp.shutdown();
      Thread v = Thread.ofVirtual().name("v-", 0).unstarted(() -> { }); Thread v2 = Thread.ofVirtual().name("v-", 0).unstarted(() -> { }); v.setPriority(10); v.setDaemon(true);
      ThreadFactory vf = Thread.ofVirtual().name("vt-", 0).factory(); Thread v3 = vf.newThread(() -> { }); Thread v4 = vf.newThread(() -> { });
      System.out.println("  虚拟线程:ThreadFactory 生成的名字 " + v3.getName() + "、" + v4.getName() + ",isDaemon() = " + v3.isDaemon() + ",isVirtual() = " + v3.isVirtual() + ",setPriority(10) 之后 getPriority() = " + v.getPriority() + ";setDaemon(false) 会抛 " + tryDaemonFalse(v3));
    } else if (mode.equals("exit-nondaemon")) { ExecutorService ex = Executors.newFixedThreadPool(2); ex.submit(() -> 1).get(); System.out.println("main 结束,没有 shutdown(非 daemon 线程池)");
    } else if (mode.equals("exit-daemon")) { ExecutorService ex = Executors.newFixedThreadPool(2, r -> { Thread t = new Thread(r); t.setDaemon(true); return t; }); ex.submit(() -> 1).get(); System.out.println("main 结束,没有 shutdown(daemon 线程池)"); }
  }
  static String tryDaemonFalse(Thread t) { try { t.setDaemon(false); return "没有抛"; } catch (Exception e) { return e.getClass().getSimpleName() + ":" + e.getMessage(); } }
}
'''
d = jdir('j250a'); (d / 'Main.java').write_text(MAIN); E = jenv('21')
rc = subprocess.run(['javac', '-d', 'out', 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2500]); sys.exit()
o = subprocess.run(['java', '-cp', 'out', 'Main', 'main'], cwd=d, env=E, capture_output=True, text=True, timeout=120); out = o.stdout + o.stderr
secs = {}
cur = None
for l in out.splitlines():
    if l.startswith('== '): cur = l; secs[cur] = []
    elif cur: secs[cur].append(l)
for h in secs:
    if h.startswith('== 五'):
        print('== 四:JVM 能不能退出:main 结束后线程池没有 shutdown(非 daemon 线程与 daemon 线程两种 ThreadFactory,各跑一次,5 秒超时)')
        for mode in ('exit-nondaemon', 'exit-daemon'):
            t0 = time.perf_counter()
            try: r = subprocess.run(['java', '-cp', 'out', 'Main', mode], cwd=d, env=E, capture_output=True, text=True, timeout=5); st = f'JVM 在 {time.perf_counter() - t0:.1f} s 内退出,退出码 {r.returncode}'; msg = r.stdout.strip()
            except subprocess.TimeoutExpired as ex: st = f'5 秒后 JVM 仍未退出(被杀掉)'; msg = (ex.stdout or b'').decode().strip()
            print(f'  {mode}:输出 "{msg}";{st}')
    print(h); [print(l) for l in secs[h]]
