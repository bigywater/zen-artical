import org.apache.curator.framework.*;
import org.apache.curator.framework.recipes.cache.*;
import org.apache.curator.framework.state.*;
import org.apache.curator.retry.*;
public class CacheProbe {
    public static void main(String[] a) throws Exception {
        CuratorFramework c = CuratorFrameworkFactory.builder().connectString("127.0.0.1:" + a[0]).sessionTimeoutMs(3000).retryPolicy(new ExponentialBackoffRetry(100, 5)).build(); c.start(); c.blockUntilConnected();
        c.getConnectionStateListenable().addListener((cf, s) -> { System.out.println(System.currentTimeMillis() + " STATE " + s); System.out.flush(); });
        CuratorCache cache = CuratorCache.build(c, "/cfg"); cache.start();
        String last = null;
        while (true) { var d = cache.get("/cfg"); String v = d.isPresent() ? new String(d.get().getData()) : "<none>"; if (!v.equals(last)) { System.out.println(System.currentTimeMillis() + " VAL " + v); System.out.flush(); last = v; } Thread.sleep(20); }
    }
}
