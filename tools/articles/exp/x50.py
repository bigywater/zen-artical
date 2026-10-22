import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x50'); CP = scp('org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><appender name="C" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>LOGLINE %msg %ex{2}%n</pattern></encoder></appender><root level="OFF"/><logger name="org.apache.catalina.core.ContainerBase.[Tomcat].[localhost].[/].[dispatcherServlet]" level="ERROR"><appender-ref ref="C"/></logger></configuration>'
MAIN = r'''
package demo;
import java.io.IOException; import java.util.*;
import jakarta.servlet.*; import jakarta.servlet.http.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty; import org.springframework.context.annotation.Bean;
import org.springframework.web.bind.annotation.*; import org.springframework.web.servlet.config.annotation.*; import org.springframework.web.cors.*; import org.springframework.web.filter.CorsFilter;
@SpringBootApplication @RestController
public class Main {
  @GetMapping("/plain") String plain() { return "plain"; }
  @CrossOrigin(origins = "https://a.example") @GetMapping("/ann") String ann() { return "ann"; }
  @CrossOrigin(origins = "https://a.example", allowedHeaders = "X-Token", methods = {RequestMethod.GET, RequestMethod.PUT}, maxAge = 600, allowCredentials = "true", exposedHeaders = "X-Total") @PutMapping("/ann-put") String annPut() { return "ann-put"; }
  @CrossOrigin @GetMapping("/open") String open() { return "open"; }
  @CrossOrigin(origins = "https://a.example") @GetMapping("/ann-boom") String annBoom() { throw new IllegalStateException("boom"); }
  @GetMapping("/api/boom") String apiBoom() { throw new IllegalStateException("boom"); }
  @GetMapping("/boom") String boom() { throw new IllegalStateException("boom"); }
  @PostMapping("/post-json") String postJson(@RequestBody Map<String, Object> m) { return "post-json"; }
  @GetMapping("/secured") String secured(HttpServletRequest rq) { return "secured:" + rq.getHeader("Authorization"); }
  @Bean @ConditionalOnProperty("app.global") WebMvcConfigurer cors() { return new WebMvcConfigurer() { public void addCorsMappings(CorsRegistry r) { r.addMapping("/api/**").allowedOrigins("https://b.example").allowedMethods("GET", "POST").allowedHeaders("*").maxAge(120); r.addMapping("/plain").allowedOriginPatterns("https://*.example").allowCredentials(true); } }; }
  @GetMapping("/api/x") String apiX() { return "api-x"; }
  @Bean @ConditionalOnProperty("app.filter") org.springframework.boot.web.servlet.FilterRegistrationBean<CorsFilter> corsFilter() { var cfg = new CorsConfiguration(); cfg.addAllowedOrigin("https://f.example"); cfg.addAllowedMethod("*"); cfg.addAllowedHeader("*"); var src = new UrlBasedCorsConfigurationSource(); src.registerCorsConfiguration("/**", cfg); var r = new org.springframework.boot.web.servlet.FilterRegistrationBean<>(new CorsFilter(src)); r.setOrder(Integer.MIN_VALUE); return r; }
  @Bean @ConditionalOnProperty("app.badconfig") WebMvcConfigurer bad() { return new WebMvcConfigurer() { public void addCorsMappings(CorsRegistry r) { r.addMapping("/**").allowedOrigins("*").allowCredentials(true); } }; }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x50', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
KEYS = ['Access-Control-Allow-Origin', 'Access-Control-Allow-Methods', 'Access-Control-Allow-Headers', 'Access-Control-Allow-Credentials', 'Access-Control-Max-Age', 'Access-Control-Expose-Headers', 'Vary']
import http.client
def req(app, m, p, hd=None, body=None):
    c = http.client.HTTPConnection('127.0.0.1', int(app.props['server.port']), timeout=10); c.request(m, p, headers=hd or {}, body=body); r = c.getresponse(); d = r.read().decode('utf-8', 'replace'); hs = r.getheaders(); c.close()
    cors = {}
    for k, v in hs:
        if k in KEYS: cors.setdefault(k.replace('Access-Control-', ''), []).append(v)
    cors = {k: (v[0] if len(v) == 1 else v) for k, v in cors.items()}
    d = re.sub(r'"timestamp":"[^"]*",?', '', d.strip())[:50]
    hd_ = ' '.join(f'{k.replace("Access-Control-", "").replace("Request-", "Req-")}: {v}' for k, v in (hd or {}).items() if k != 'Content-Type')
    print(f'  {m} {p}  [{hd_}] → {r.status}  body={d!r}'); print(f'      CORS 响应头:{cors if cors else "(没有)"}')
def pre(app, p, origin, method, headers=None):
    hd = {'Origin': origin, 'Access-Control-Request-Method': method}
    if headers: hd['Access-Control-Request-Headers'] = headers
    req(app, 'OPTIONS', p, hd)
def run(props, f, title):
    app = SApp(b, 'demo.Main', props=props).start(); print(f'== {title}'); f(app); app.stop()
print('Spring Boot 4.0.8 / Spring MVC 7.0.9(Tomcat 11.0.24)。用 Python http.client 手工带 Origin 头发请求,服务端是真实的 Tomcat')
def one(app):
    req(app, 'GET', '/plain', {'Origin': 'https://a.example'}); req(app, 'GET', '/plain'); pre(app, '/plain', 'https://a.example', 'GET')
run({}, one, '一:什么都不配置:带 Origin 的简单请求与预检')
def two(app):
    req(app, 'GET', '/ann', {'Origin': 'https://a.example'}); req(app, 'GET', '/ann', {'Origin': 'https://evil.example'}); req(app, 'GET', '/ann'); req(app, 'GET', '/ann', {'Origin': f'http://127.0.0.1:{app.props["server.port"]}'})
    pre(app, '/ann', 'https://a.example', 'GET'); pre(app, '/ann', 'https://evil.example', 'GET'); pre(app, '/ann', 'https://a.example', 'DELETE')
    print('== 二补:@CrossOrigin 的更多属性与默认值(allowedHeaders、methods、maxAge、allowCredentials、exposedHeaders;空的 @CrossOrigin)')
    pre(app, '/ann-put', 'https://a.example', 'PUT', 'X-Token'); pre(app, '/ann-put', 'https://a.example', 'PUT', 'X-Other'); req(app, 'PUT', '/ann-put', {'Origin': 'https://a.example'}); req(app, 'GET', '/open', {'Origin': 'https://any.example'}); pre(app, '/open', 'https://any.example', 'GET', 'X-Whatever')
run({}, two, '二:@CrossOrigin(只在这个方法上):允许的来源 / 不在列表的来源 / 方法不允许 / 头不允许;实际请求与预检的响应头')
def three(app):
    pre(app, '/api/x', 'https://b.example', 'POST', 'Content-Type'); pre(app, '/api/x', 'https://b.example', 'DELETE'); req(app, 'GET', '/api/x', {'Origin': 'https://b.example'})
    req(app, 'GET', '/plain', {'Origin': 'https://sub.example'}); req(app, 'GET', '/plain', {'Origin': 'https://a.other'})
    req(app, 'GET', '/ann', {'Origin': 'https://a.example'}); req(app, 'GET', '/api/boom', {'Origin': 'https://b.example'})
run({'app.global': 'true'}, three, '三:WebMvcConfigurer.addCorsMappings 的全局配置(/api/** 允许 b.example;/plain 用 originPatterns + allowCredentials)')
def four(app):
    req(app, 'GET', '/boom', {'Origin': 'https://f.example'}); req(app, 'GET', '/nope', {'Origin': 'https://f.example'}); pre(app, '/boom', 'https://f.example', 'POST', 'X-Any')
    req(app, 'GET', '/boom', {'Origin': 'https://other.example'})
run({'app.filter': 'true'}, four, '四:CorsFilter(最前面的 Filter):异常、404 的响应也带 CORS 头吗')
def five(app):
    req(app, 'GET', '/boom', {'Origin': 'https://a.example'}); req(app, 'GET', '/nope', {'Origin': 'https://a.example'}); req(app, 'GET', '/ann-boom', {'Origin': 'https://a.example'})
run({}, five, '五:对照:只有 @CrossOrigin 的方法,抛异常的方法和 404')
def six(app):
    req(app, 'GET', '/plain', {'Origin': 'https://a.example'}); pre(app, '/plain', 'https://a.example', 'GET'); time.sleep(0.3)
    for l in app.log().splitlines():
        if l.startswith('LOGLINE'): print('  服务端日志:' + l[8:].strip()[:330]); break
run({'app.badconfig': 'true'}, six, '六:allowedOrigins("*") 与 allowCredentials(true) 同时配置')
