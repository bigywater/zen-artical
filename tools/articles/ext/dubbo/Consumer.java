import org.apache.dubbo.config.*;
import org.apache.dubbo.config.bootstrap.DubboBootstrap;
import java.util.*;
public class Consumer {
    public static void main(String[] a) throws Exception {
        ReferenceConfig<Greeter> rc = new ReferenceConfig<>(); rc.setInterface(Greeter.class); rc.setVersion("1.0"); rc.setCheck(false); rc.setTimeout(1000); rc.setRetries(0);
        DubboBootstrap.getInstance().application(new ApplicationConfig("cons-app")).registry(new RegistryConfig("zookeeper://127.0.0.1:7300" + (a.length > 0 ? "?" + a[0] : ""))).reference(rc).start();
        Greeter g = rc.get(); System.out.println("CONSUMER_UP"); System.out.flush();
        while (true) { long t = System.currentTimeMillis(); String r; try { r = g.hi("x"); } catch (Throwable e) { r = "ERR " + e.getClass().getSimpleName(); } System.out.println(t + " CALL " + r); System.out.flush(); Thread.sleep(200); }
    }
}
