package demo;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.ServiceInstance;
import org.springframework.cloud.client.discovery.DiscoveryClient;
import org.springframework.core.env.Environment;
import org.springframework.web.bind.annotation.*;
import java.util.*;

@SpringBootApplication
@RestController
public class DemoApp {
    final DiscoveryClient dc; final Environment env;
    public DemoApp(DiscoveryClient dc, Environment env) { this.dc = dc; this.env = env; }
    public static void main(String[] a) { SpringApplication.run(DemoApp.class, a); }
    @GetMapping("/hello") public String hello() { return "hi from " + env.getProperty("server.port"); }
    @GetMapping("/cfg") public String cfg() { return String.valueOf(env.getProperty("demo.msg", "<unset>")); }
    @GetMapping("/instances/{n}") public List<String> inst(@PathVariable String n) { List<String> r = new ArrayList<>(); for (ServiceInstance s : dc.getInstances(n)) r.add(s.getHost() + ":" + s.getPort() + " id=" + s.getInstanceId()); Collections.sort(r); return r; }
    @GetMapping("/services") public List<String> services() { return dc.getServices(); }
}
