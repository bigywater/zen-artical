import org.apache.dubbo.config.*;
import org.apache.dubbo.config.bootstrap.DubboBootstrap;
public class Provider {
    public static void main(String[] a) throws Exception {
        String reg = "zookeeper://127.0.0.1:7300" + (a.length > 2 ? "?" + a[2] : "");
        ProtocolConfig pc = new ProtocolConfig("dubbo", Integer.parseInt(a[0])); pc.setHost("127.0.0.1");
        ServiceConfig<Greeter> sc = new ServiceConfig<>(); sc.setInterface(Greeter.class); sc.setRef(new GreeterImpl(a[1])); sc.setVersion("1.0");
        DubboBootstrap.getInstance().application(new ApplicationConfig("prov-app")).registry(new RegistryConfig(reg)).protocol(pc).service(sc).start();
        System.out.println("PROVIDER_UP " + a[1]); System.out.flush(); Thread.sleep(Long.MAX_VALUE);
    }
}
