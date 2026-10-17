import sys, os, re, time, hashlib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j242'); R = {}
MAIN = r'''
import java.util.*; import java.util.concurrent.*; import java.util.random.*; import java.util.stream.*;
public class Main {
  enum Color { RED, GREEN }
  record Key(String a) {}
  public static void main(String[] args) throws Exception {
    String mode = args[0];
    if (mode.equals("seq")) {
      Random r = new Random(42); StringBuilder b = new StringBuilder(); for (int i = 0; i < 5; i++) b.append(r.nextInt(100)).append(' ');
      System.out.println("Random(42).nextInt(100) x5: " + b);
      Random g = new Random(42); System.out.println("Random(42).nextGaussian x3: " + String.format("%.6f %.6f %.6f", g.nextGaussian(), g.nextGaussian(), g.nextGaussian()));
      SplittableRandom s = new SplittableRandom(42); b = new StringBuilder(); for (int i = 0; i < 5; i++) b.append(s.nextInt(100)).append(' ');
      System.out.println("SplittableRandom(42).nextInt(100) x5: " + b);
      RandomGenerator l = RandomGeneratorFactory.of("L64X128MixRandom").create(42); b = new StringBuilder(); for (int i = 0; i < 5; i++) b.append(l.nextInt(100)).append(' ');
      System.out.println("L64X128MixRandom(42).nextInt(100) x5: " + b);
      List<Integer> list = new ArrayList<>(IntStream.rangeClosed(1, 10).boxed().toList()); Collections.shuffle(list, new Random(42)); System.out.println("Collections.shuffle(1..10, Random(42)): " + list);
      System.out.println("new Random(42).ints(5, 0, 100): " + new Random(42).ints(5, 0, 100).boxed().toList());
      System.out.println("UUID.nameUUIDFromBytes(\"user-1\"): " + UUID.nameUUIDFromBytes("user-1".getBytes()));
    } else if (mode.equals("tlr")) {
      String set; try { ThreadLocalRandom.current().setSeed(42); set = "setSeed 成功"; } catch (UnsupportedOperationException e) { set = "setSeed 抛 UnsupportedOperationException"; }
      System.out.println(set + ";ThreadLocalRandom.nextInt(1000000) = " + ThreadLocalRandom.current().nextInt(1000000) + ";UUID.randomUUID() = " + UUID.randomUUID().toString().substring(0, 8) + "…;SecureRandom.nextInt = " + new java.security.SecureRandom().nextInt(1000000));
    } else if (mode.equals("shared")) {
      Random r = new Random(42); int T = 8, N = 1000; long[] sums = new long[T]; Thread[] ts = new Thread[T]; long[][] first = new long[T][1];
      for (int t = 0; t < T; t++) { int k = t; ts[t] = new Thread(() -> { long sum = 0; for (int i = 0; i < N; i++) { int v = r.nextInt(1000); if (i == 0) first[k][0] = v; sum += v; } sums[k] = sum; }); }
      for (Thread t : ts) t.start(); for (Thread t : ts) t.join();
      long total = Arrays.stream(sums).sum(); System.out.println("共享 Random(42):8 个线程各取 1000 个。各线程的和 " + Arrays.toString(sums) + ";总和 " + total);
      SplittableRandom root = new SplittableRandom(42); SplittableRandom[] kids = new SplittableRandom[T]; for (int t = 0; t < T; t++) kids[t] = root.split(); long[] ss = new long[T]; Thread[] ts2 = new Thread[T];
      for (int t = 0; t < T; t++) { int k = t; ts2[t] = new Thread(() -> { long sum = 0; for (int i = 0; i < N; i++) sum += kids[k].nextInt(1000); ss[k] = sum; }); }
      for (Thread t : ts2) t.start(); for (Thread t : ts2) t.join();
      System.out.println("按线程序号 split():各线程的和 " + Arrays.toString(ss) + ";总和 " + Arrays.stream(ss).sum());
    } else if (mode.equals("par")) {
      Random r = new Random(42); List<Integer> a = IntStream.range(0, 2000).parallel().map(i -> r.nextInt(1000)).boxed().collect(Collectors.toList());
      List<Integer> b = IntStream.range(0, 2000).parallel().map(i -> new SplittableRandom(42 + i * 0x9E3779B97F4A7C15L).nextInt(1000)).boxed().collect(Collectors.toList());
      System.out.println("并行流里共享 Random(42):前 8 个值 " + a.subList(0, 8) + ",全体哈希 " + Integer.toHexString(a.hashCode()) + ";每个下标各自派生种子:前 8 个值 " + b.subList(0, 8) + ",全体哈希 " + Integer.toHexString(b.hashCode()));
    } else if (mode.equals("hash2")) {
      for (int i = 0; i < 3; i++) new Object().hashCode(); System.out.println("seed 来源:先对 3 个无关对象调用 hashCode(),再取 Color.RED.hashCode() = " + Integer.toHexString(Color.RED.hashCode()));
    } else if (mode.equals("hash")) {
      System.out.println("seed 来源:\"login\".hashCode() = " + "login".hashCode() + ";Color.RED.hashCode() = " + Integer.toHexString(Color.RED.hashCode()) + ";new Object().hashCode() = " + Integer.toHexString(new Object().hashCode()) + ";Objects.hash(Color.RED, 1) = " + Integer.toHexString(Objects.hash(Color.RED, 1)) + ";Key(\"a\").hashCode() = " + new Key("a").hashCode() + ";List.of(Color.GREEN).hashCode() = " + Integer.toHexString(List.of(Color.GREEN).hashCode()));
    }
  }
}
'''
def one(mode, jdk='21', jopts=()):
    r = jrun('j242a' + jdk, {'Main.java': MAIN}, jdk=jdk, args=(mode,), jopts=jopts, clean=False, timeout=60)
    if r['crc'] != 0: print(r['cout'][:2000]); sys.exit()
    return r['out']
print('== 一:同一个种子在 JDK 17 / 21 / 27 上:Random、SplittableRandom、L64X128MixRandom、Collections.shuffle')
outs = {j: one('seq', j) for j in ('17', '21', '27')}
for l in outs['21'].splitlines(): print('  JDK 21  ' + l)
for j in ('17', '27'): print(f'  JDK {j} 与 JDK 21 的输出是否逐字相同:', outs[j] == outs['21'])
print('== 二:不能设种子的随机源,重复运行 5 次(新 JVM)')
tl_ = [one('tlr') for _ in range(5)]; [print('  ' + o) for o in tl_]
print('== 三:一个 Random(42) 被 8 个线程共享,与每线程 split() 的 SplittableRandom;各重复 6 次(新 JVM)')
sh = [one('shared') for _ in range(6)]
a_ = [o.splitlines()[0] for o in sh]; b_ = [o.splitlines()[1] for o in sh]
print('  共享 Random 的 6 次输出里,各线程的和各不相同的次数:', len(set(a_)), '种;总和:', sorted(set(re.findall(r'总和 (\d+)', ' '.join(a_)))))
print('  示例(第 1 次):' + a_[0]); print('  示例(第 2 次):' + a_[1])
print('  split() 的 6 次输出共有', len(set(b_)), '种;示例:' + b_[0])
print('== 四:并行流里生成数据(2000 个),重复 5 次(新 JVM)')
pr_ = [one('par') for _ in range(5)]
for o in pr_: print('  ' + o)
print('  共享 Random 的哈希共', len(set(re.findall(r'共享 Random\(42\):前 8 个值 \[[^\]]*\],全体哈希 (\w+)', ' '.join(pr_)))), '种;各下标派生种子的哈希共', len(set(re.findall(r'派生种子:前 8 个值 \[[^\]]*\],全体哈希 (\w+)', ' '.join(pr_)))), '种')
print('== 五:用 hashCode 派生种子:同一个环境重复 3 次,再换 JDK 与 JVM 参数')
for _ in range(3): print('  JDK 21 默认:' + one('hash').split('seed 来源:')[1])
for lab, jdk, jo in (('JDK 17', '17', ()), ('JDK 27', '27', ()), ('JDK 21 + -Duser.timezone=America/Los_Angeles', '21', ('-Duser.timezone=America/Los_Angeles',)), ('JDK 21 + -XX:+UseSerialGC', '21', ('-XX:+UseSerialGC',)), ('JDK 21 + -Xmx64m', '21', ('-Xmx64m',))):
    print(f'  {lab}:' + one('hash', jdk, jo).split('seed 来源:')[1])
print('  JDK 21 默认,代码里先对 3 个无关对象调用了 hashCode():' + one('hash2').split('seed 来源:')[1])
