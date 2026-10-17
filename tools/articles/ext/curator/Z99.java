import org.apache.zookeeper.server.quorum.*;
import org.apache.zookeeper.server.quorum.flexible.*;
import java.lang.reflect.*;
import java.net.InetSocketAddress;
import java.util.*;

public class Z99 {
    public static void main(String[] a) throws Exception {
        Field uf = sun.misc.Unsafe.class.getDeclaredField("theUnsafe"); uf.setAccessible(true); sun.misc.Unsafe u = (sun.misc.Unsafe) uf.get(null);
        FastLeaderElection fle = (FastLeaderElection) u.allocateInstance(FastLeaderElection.class);
        QuorumPeer qp = new QuorumPeer(); Map<Long, QuorumPeer.QuorumServer> m = new HashMap<>();
        for (long i = 1; i <= 3; i++) m.put(i, new QuorumPeer.QuorumServer(i, new InetSocketAddress("127.0.0.1", 9000 + (int) i), new InetSocketAddress("127.0.0.1", 9100 + (int) i)));
        qp.setQuorumVerifier(new QuorumMaj(m), false);
        Field sf = FastLeaderElection.class.getDeclaredField("self"); sf.setAccessible(true); sf.set(fle, qp);
        Method mt = FastLeaderElection.class.getDeclaredMethod("totalOrderPredicate", long.class, long.class, long.class, long.class, long.class, long.class); mt.setAccessible(true);
        System.out.println("== 一:对真实的 FastLeaderElection.totalOrderPredicate(newId, newZxid, newEpoch, curId, curZxid, curEpoch) 做穷举:epoch ∈ {1,2},zxid ∈ {5,6},id ∈ {1,2},共 " + (8 * 8) + " 组,与源码阅读得到的规则逐组比对");
        long[] eps = {1, 2}, zx = {5, 6}, ids = {1, 2}; int n = 0, bad = 0, trues = 0;
        for (long ne : eps) for (long nz : zx) for (long ni : ids) for (long ce : eps) for (long cz : zx) for (long ci : ids) {
            boolean real = (Boolean) mt.invoke(fle, ni, nz, ne, ci, cz, ce);
            boolean mine = ne > ce || (ne == ce && (nz > cz || (nz == cz && ni > ci)));
            n++; if (real != mine) bad++; if (real) trues++;
        }
        System.out.println("  比对 " + n + " 组:不一致 " + bad + " 组;返回 true 的 " + trues + " 组(其余 " + (n - trues) + " 组为 false,其中 8 组是完全相同的两张票:相同的票不会替换当前投票)");
        System.out.println("  几个具体例子(new = 收到的票,cur = 当前投票):");
        long[][] ex = {{3, 0x100000002L, 1, 1, 0x100000035L, 1}, {1, 0x100000035L, 1, 3, 0x100000002L, 1}, {3, 5, 1, 2, 5, 1}, {2, 5, 1, 3, 5, 1}, {1, 5, 2, 3, 99, 1}, {1, 5, 1, 1, 5, 1}};
        String[] why = {"同 epoch,zxid 更小", "同 epoch,zxid 更大", "同 epoch、同 zxid,id 更大", "同 epoch、同 zxid,id 更小", "epoch 更大(即使 zxid 小得多)", "两张票完全相同"};
        for (int i = 0; i < ex.length; i++) { boolean r = (Boolean) mt.invoke(fle, ex[i][0], ex[i][1], ex[i][2], ex[i][3], ex[i][4], ex[i][5]); System.out.printf("    new(id=%d,zxid=0x%x,epoch=%d) vs cur(id=%d,zxid=0x%x,epoch=%d) → %s  // %s%n", ex[i][0], ex[i][1], ex[i][2], ex[i][3], ex[i][4], ex[i][5], r, why[i]); }
        long MIN = Long.MIN_VALUE; boolean obs = (Boolean) mt.invoke(fle, MIN, MIN, MIN, 1L, 0L, 0L), obs2 = (Boolean) mt.invoke(fle, 1L, 0L, 0L, MIN, MIN, MIN);
        System.out.println("  观察者的初始选票是 (id=Long.MIN_VALUE, zxid=Long.MIN_VALUE, epoch=Long.MIN_VALUE):它去挑战任何参与者的选票 → " + obs + ";参与者的选票挑战观察者的初始选票 → " + obs2);
        System.exit(0);
    }
}
