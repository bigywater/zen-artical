import org.apache.curator.framework.*;
import org.apache.curator.framework.recipes.locks.*;
import org.apache.curator.retry.*;
public class Holder {
    public static void main(String[] a) throws Exception {
        CuratorFramework c = CuratorFrameworkFactory.builder().connectString("127.0.0.1:" + a[0]).sessionTimeoutMs(3000).retryPolicy(new ExponentialBackoffRetry(100, 5)).build(); c.start(); c.blockUntilConnected();
        c.getConnectionStateListenable().addListener((cf, s) -> System.out.println(System.currentTimeMillis() + " STATE " + s));
        InterProcessMutex m = new InterProcessMutex(c, "/hl"); m.acquire(); System.out.println(System.currentTimeMillis() + " ACQUIRED"); System.out.flush();
        Thread.sleep(Long.parseLong(a[1]));
        System.out.println(System.currentTimeMillis() + " AFTER_SLEEP isOwnedByCurrentThread=" + m.isOwnedByCurrentThread() + " isAcquiredInThisProcess=" + m.isAcquiredInThisProcess());
        System.out.flush(); System.exit(0);
    }
}
