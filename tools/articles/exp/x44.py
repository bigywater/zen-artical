import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x44'); CP = scp('org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.io.IOException; import java.util.*;
import jakarta.servlet.*; import jakarta.servlet.http.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.web.servlet.FilterRegistrationBean; import org.springframework.context.annotation.Bean;
import org.springframework.web.bind.annotation.*; import org.springframework.web.method.HandlerMethod; import org.springframework.web.servlet.*; import org.springframework.web.servlet.config.annotation.*; import org.springframework.web.filter.OncePerRequestFilter;
@SpringBootApplication @RestController
public class Main {
  static synchronized void ev(String s) { System.out.println("RES EV " + s); System.out.flush(); }
  @GetMapping("/api/hi") String hi() { ev("      Controller /api/hi"); return "hi"; }
  @GetMapping("/open/hi") String open() { ev("      Controller /open/hi"); return "open"; }
  @PostMapping("/api/body") String body(@RequestBody String b) { ev("      Controller 读到 body = " + b); return "got:" + b; }
  @Bean FilterRegistrationBean<Filter> f1() { var r = new FilterRegistrationBean<Filter>(new Named("F1")); r.setOrder(1); return r; }
  @Bean FilterRegistrationBean<Filter> f2() { var r = new FilterRegistrationBean<Filter>(new Named("F2")); r.setOrder(2); return r; }
  @Bean FilterRegistrationBean<Filter> once() { var r = new FilterRegistrationBean<Filter>(new Once()); r.setOrder(3); return r; }
  @Bean FilterRegistrationBean<Filter> reader() { var r = new FilterRegistrationBean<Filter>(new BodyReader()); r.setOrder(4); r.addUrlPatterns("/api/body"); r.setEnabled(Boolean.getBoolean("readbody")); return r; }
  public static class Named implements Filter { final String n; Named(String n) { this.n = n; }
    public void doFilter(ServletRequest rq, ServletResponse rs, FilterChain ch) throws IOException, ServletException { HttpServletRequest h = (HttpServletRequest) rq; if (h.getRequestURI().equals("/probe")) { ch.doFilter(rq, rs); return; } ev(n + " 进入 " + h.getRequestURI() + " [" + h.getDispatcherType() + "]"); ch.doFilter(rq, rs); ev(n + " 返回"); } }
  public static class Once extends OncePerRequestFilter { protected void doFilterInternal(HttpServletRequest rq, HttpServletResponse rs, FilterChain ch) throws ServletException, IOException { if (rq.getRequestURI().equals("/probe")) { ch.doFilter(rq, rs); return; } ev("Once(OncePerRequestFilter) 进入 " + rq.getRequestURI() + " [" + rq.getDispatcherType() + "]"); ch.doFilter(rq, rs); } }
  public static class BodyReader implements Filter { public void doFilter(ServletRequest rq, ServletResponse rs, FilterChain ch) throws IOException, ServletException { String b = new String(rq.getInputStream().readAllBytes()); ev("BodyReader 在 Filter 里把请求体读完了:" + b); ch.doFilter(rq, rs); } }
  static class Ic implements HandlerInterceptor { final String n; final boolean block; Ic(String n, boolean block) { this.n = n; this.block = block; }
    public boolean preHandle(HttpServletRequest q, HttpServletResponse s, Object h) { ev(n + ".preHandle [" + q.getDispatcherType() + "] handler=" + (h instanceof HandlerMethod hm ? hm.getMethod().getName() : h.getClass().getSimpleName())); if (block) { ev(n + " 返回 false,中止"); s.setStatus(403); } return !block; }
    public void postHandle(HttpServletRequest q, HttpServletResponse s, Object h, ModelAndView m) { ev(n + ".postHandle"); }
    public void afterCompletion(HttpServletRequest q, HttpServletResponse s, Object h, Exception e) { ev(n + ".afterCompletion"); } }
  @Bean WebMvcConfigurer cfg() { return new WebMvcConfigurer() { public void addInterceptors(InterceptorRegistry r) { r.addInterceptor(new Ic("A", false)).order(1).addPathPatterns("/api/**", "/open/**", "/nope**"); r.addInterceptor(new Ic("B", Boolean.getBoolean("blockB"))).order(2).addPathPatterns("/api/**"); } }; }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x44', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(props, reqs, title):
    app = SApp(b, 'demo.Main', props=props).start(); print(f'== {title}')
    for m_, p_, kw in reqs:
        n0 = len(app.log().splitlines()); s, d, h = app.get(p_, method=m_, **kw); time.sleep(0.2); ev = [l[7:] for l in app.log().splitlines()[n0:] if l.startswith('RES EV ')]
        print(f'  {m_} {p_} → {s} {d.strip()[:40]}'); [print('      ' + l) for l in ev]
    app.stop()
print('Spring Boot 4.0.8 / Spring MVC 7.0.9。Filter 与 HandlerInterceptor:Filter F1(order 1)、F2(order 2)、OncePerRequestFilter Once(order 3);拦截器 A(order 1,路径 /api/**、/open/**、/nope**)与 B(order 2,路径 /api/**)')
run({}, [('GET', '/api/hi', {}), ('GET', '/open/hi', {})], '一:顺序与路径范围(A、B 的 preHandle 按 order 升序,postHandle / afterCompletion 倒过来)')
run({'blockB': 'true'}, [('GET', '/api/hi', {})], '二:拦截器 B 的 preHandle 返回 false')
run({}, [('GET', '/nope', {}), ('GET', '/static-missing.css', {})], '三:没有处理器的请求(404):Filter 调用几次、拦截器调用几次')
JSON = {'headers': {'Content-Type': 'text/plain'}}
run({}, [('POST', '/api/body', {'body': 'payload', **JSON})], '四:不读请求体的 Filter(对照)')
run({'readbody': 'true'}, [('POST', '/api/body', {'body': 'payload', **JSON})], '五:Filter 里把请求体读完之后,Controller 的 @RequestBody 还能读到吗')
