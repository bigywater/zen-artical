import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x39'); CP = scp('org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.io.IOException; import java.util.*;
import jakarta.servlet.*; import jakarta.servlet.http.*;
import org.springframework.boot.SpringApplication; import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.ConfigurableApplicationContext; import org.springframework.context.annotation.Bean;
import org.springframework.core.MethodParameter; import org.springframework.http.*; import org.springframework.http.converter.HttpMessageConverter; import org.springframework.http.server.ServerHttpRequest; import org.springframework.http.server.ServerHttpResponse;
import org.springframework.web.method.HandlerMethod; import org.springframework.web.bind.support.WebDataBinderFactory; import org.springframework.web.bind.annotation.*; import org.springframework.web.context.request.NativeWebRequest; import org.springframework.web.method.support.*; import org.springframework.web.servlet.*;
import org.springframework.web.servlet.config.annotation.*; import org.springframework.web.servlet.mvc.method.annotation.ResponseBodyAdvice;
@SpringBootApplication @RestController
public class Main {
  static synchronized void ev(String s) { System.out.println("RES EV " + s); System.out.flush(); }
  public record Trace(String id) { }
  @GetMapping("/hello/{name}") public Map<String, String> hello(@PathVariable String name, Trace t) { ev("      Controller 方法 hello(" + name + "," + t + ")"); return Map.of("hi", name); }
  @GetMapping("/boom") public String boom() { throw new IllegalStateException("控制器里抛异常"); }
  @PostMapping("/only-post") public String onlyPost() { return "ok"; }
  @Bean OncePerRequestFilterX filter() { return new OncePerRequestFilterX(); }
  public static class OncePerRequestFilterX extends org.springframework.web.filter.OncePerRequestFilter {
    protected void doFilterInternal(HttpServletRequest rq, HttpServletResponse rs, FilterChain ch) throws ServletException, IOException { if (rq.getRequestURI().equals("/probe")) { ch.doFilter(rq, rs); return; } ev("① Filter 进入 " + rq.getMethod() + " " + rq.getRequestURI()); try { ch.doFilter(rq, rs); } finally { ev("⑩ Filter 返回,状态码 " + rs.getStatus()); } } }
  @Bean WebMvcConfigurer cfg() { return new WebMvcConfigurer() {
    public void addInterceptors(InterceptorRegistry r) { r.addInterceptor(new HandlerInterceptor() {
      public boolean preHandle(HttpServletRequest q, HttpServletResponse s, Object h) { if (q.getRequestURI().equals("/probe")) return true; ev("③ Interceptor.preHandle,handler 类型 = " + h.getClass().getSimpleName() + (h instanceof HandlerMethod hm ? "(" + hm.getMethod().getName() + ")" : "")); return true; }
      public void postHandle(HttpServletRequest q, HttpServletResponse s, Object h, ModelAndView mv) { if (!q.getRequestURI().equals("/probe")) ev("⑧ Interceptor.postHandle"); }
      public void afterCompletion(HttpServletRequest q, HttpServletResponse s, Object h, Exception ex) { if (!q.getRequestURI().equals("/probe")) ev("⑨ Interceptor.afterCompletion,异常 = " + (ex == null ? "无" : ex.getClass().getSimpleName())); } }); }
    public void addArgumentResolvers(List<HandlerMethodArgumentResolver> rs) { rs.add(new HandlerMethodArgumentResolver() { public boolean supportsParameter(MethodParameter p) { return p.getParameterType() == Trace.class; }
      public Object resolveArgument(MethodParameter p, ModelAndViewContainer m, NativeWebRequest w, WebDataBinderFactory b) { ev("④ 自定义 HandlerMethodArgumentResolver 解析 Trace 参数"); return new Trace("t-1"); } }); } }; }
  @org.springframework.web.bind.annotation.ControllerAdvice public static class Adv implements ResponseBodyAdvice<Object> {
    public boolean supports(MethodParameter r, Class<? extends HttpMessageConverter<?>> c) { return true; }
    public Object beforeBodyWrite(Object body, MethodParameter r, MediaType t, Class<? extends HttpMessageConverter<?>> c, ServerHttpRequest q, ServerHttpResponse s) { ev("⑥ ResponseBodyAdvice.beforeBodyWrite,将用 " + c.getSimpleName() + " 写出"); return body; } }
  @org.springframework.web.bind.annotation.ControllerAdvice public static class Exc { @ExceptionHandler(IllegalStateException.class) public ResponseEntity<String> h(IllegalStateException e) { ev("⑦′ @ExceptionHandler 处理 " + e.getClass().getSimpleName()); return ResponseEntity.status(500).body("handled"); } }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(org.springframework.boot.Banner.Mode.OFF); ConfigurableApplicationContext c = app.run(a); 
    if (a.length > 0 && a[0].equals("structure")) {
      DispatcherServlet ds = c.getBean(DispatcherServlet.class); System.out.println("RES DispatcherServlet 是容器里的一个 Bean:" + ds.getClass().getSimpleName() + ";参数 detectAllHandlerMappings 默认由 Spring 决定");
      System.out.println("RES HandlerMapping(按顺序):" + c.getBeansOfType(HandlerMapping.class).values().stream().sorted(org.springframework.core.annotation.AnnotationAwareOrderComparator.INSTANCE).map(x -> x.getClass().getSimpleName()).toList());
      System.out.println("RES HandlerAdapter(按顺序):" + c.getBeansOfType(HandlerAdapter.class).values().stream().sorted(org.springframework.core.annotation.AnnotationAwareOrderComparator.INSTANCE).map(x -> x.getClass().getSimpleName()).toList());
      System.out.println("RES HandlerExceptionResolver(按顺序):" + c.getBeansOfType(org.springframework.web.servlet.HandlerExceptionResolver.class).values().stream().sorted(org.springframework.core.annotation.AnnotationAwareOrderComparator.INSTANCE).map(x -> x.getClass().getSimpleName()).toList());
      var ad = c.getBean(org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerAdapter.class); System.out.println("RES RequestMappingHandlerAdapter 的参数解析器 " + ad.getArgumentResolvers().size() + " 个,返回值处理器 " + ad.getReturnValueHandlers().size() + " 个,消息转换器 " + ad.getMessageConverters().size() + " 个:" + ad.getMessageConverters().stream().map(x -> x.getClass().getSimpleName().replace("HttpMessageConverter", "")).toList());
      var hm = c.getBean(org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerMapping.class); System.out.println("RES RequestMappingHandlerMapping 登记的处理方法 " + hm.getHandlerMethods().size() + " 个(含 Boot 自带的 /error):" + hm.getHandlerMethods().keySet().stream().map(Object::toString).sorted().toList());
      System.exit(0);
    } } }
'''
b = sbuild('x39', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def structure(): r = srun(b, 'demo.Main', args=['structure'], props={'server.port': 0, 'spring.main.web-application-type': 'servlet'}); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-1500:]]
print('Spring Boot 4.0.8(spring-boot-starter-webmvc,Spring MVC 7.0.9,内嵌 Tomcat 11)。DispatcherServlet 与一个请求的完整路径')
print('== 一:DispatcherServlet 背后有哪些组件(Boot 自动配置好之后)')
[print('  ' + l) for l in structure()]
app = SApp(b, 'demo.Main').start()
def call(method, path, body=None, headers=None):
    n0 = len(app.log().splitlines()); s_, d, h = app.get(path, method=method, body=body, headers=headers); time.sleep(0.2)
    return s_, d, [l[7:] for l in app.log().splitlines()[n0:] if l.startswith('RES EV ')]
print('== 二:一个成功请求 GET /hello/spring 经过的每个环节(带圈号的是各个扩展点被调用的先后)')
s_, d, ev = call('GET', '/hello/spring'); print(f'  响应:{s_} {d}'); [print('  ' + l) for l in ev]
print('== 三:控制器里抛异常的请求 GET /boom,有一个 @ExceptionHandler')
s_, d, ev = call('GET', '/boom'); print(f'  响应:{s_} {d}'); [print('  ' + l) for l in ev]
print('== 四:没有匹配的处理器:GET /nope(404)、GET /only-post(路径对但方法不对,405)。看 Filter 和 Interceptor 是否被调用')
for m_, p_ in (('GET', '/nope'), ('GET', '/only-post')):
    s_, d, ev = call(m_, p_); print(f'  {m_} {p_} → {s_}:' + (' | '.join(ev) if ev else '(没有任何记录)'))
app.stop()
