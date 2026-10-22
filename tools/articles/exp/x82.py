import sys, os, re, time, json, shutil, subprocess, statistics, xml.etree.ElementTree as ET; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x82')
CP = scp('org.springframework.boot:spring-boot-starter-webmvc', 'org.springframework.boot:spring-boot-starter-test', 'org.springframework.boot:spring-boot-starter-webmvc-test', 'org.junit.platform:junit-platform-console')
IMP = '''package demo;
import org.springframework.boot.test.context.SpringBootTest; import org.springframework.boot.webmvc.test.autoconfigure.*; import org.springframework.test.context.bean.override.mockito.MockitoBean; import org.springframework.test.web.servlet.MockMvc; import org.springframework.test.context.*; import org.springframework.test.annotation.DirtiesContext; import org.springframework.beans.factory.annotation.Autowired; import org.springframework.context.ApplicationContext; import org.junit.jupiter.api.*; import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get; import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*; import static org.mockito.Mockito.when;
'''
FILES = {
 'src/demo/App.java': 'package demo;\nimport org.springframework.boot.autoconfigure.SpringBootApplication;\n@SpringBootApplication public class App {}\n',
 'src/demo/UserService.java': 'package demo;\nimport org.springframework.stereotype.Service;\n@Service public class UserService { public String name(int id) { return "user-" + id; } }\n',
 'src/demo/UserController.java': '''package demo;
import org.springframework.web.bind.annotation.*; import java.util.concurrent.atomic.AtomicInteger;
@RestController public class UserController {
  static final AtomicInteger CREATED = new AtomicInteger();
  static { Runtime.getRuntime().addShutdownHook(new Thread(() -> System.out.println("RES 整个 JVM 里 UserController 一共被创建了 " + CREATED.get() + " 次(= 创建的 Spring 上下文个数)"))); }
  final UserService s; UserController(UserService s) { this.s = s; System.out.println("RES     (新建上下文 #" + CREATED.incrementAndGet() + ")"); }
  @GetMapping("/users/{id}") String get(@PathVariable int id) { return s.name(id); }
}
''',
 'src/demo/Other.java': 'package demo;\nimport org.springframework.stereotype.Component;\n@Component public class Other {}\n@org.springframework.context.annotation.Configuration class Cfg2 { @org.springframework.context.annotation.Bean String b1() { return "b1"; } @org.springframework.context.annotation.Bean String b2() { return "b2"; } }\n',
 'logback.xml': '<configuration><root level="OFF"/></configuration>',
}
def cls(name, body): FILES[f'src/demo/{name}.java'] = IMP + body
cls('Plain', 'public class Plain { @Test void t() { System.out.println("RES [Plain] 不启动 Spring:" + new UserService().name(1)); } }')
def full(name, ann='', extra='', field=''):
    cls(name, f'''@SpringBootTest @AutoConfigureMockMvc {ann} public class {name} {{
  @Autowired MockMvc mvc; @Autowired ApplicationContext ctx; {field}
  @BeforeAll static void before() {{ System.out.println("RES >> {name}"); }}
  @Test void t() throws Exception {{ {extra} mvc.perform(get("/users/1")).andExpect(status().isOk()); System.out.println("RES    [{name}] Bean 定义 " + ctx.getBeanDefinitionCount() + " 个,GET /users/1 → " + mvc.perform(get("/users/1")).andReturn().getResponse().getContentAsString()); }}
}}''')
full('C1_Full1'); full('C2_Full2'); full('C3_FullMock', field='@MockitoBean UserService svc;', extra='when(svc.name(1)).thenReturn("mocked");')
full('C4_FullProp', ann='@TestPropertySource(properties = "x=1")'); full('C5_FullProfile', ann='@ActiveProfiles("t")')
cls('C6_Slice1', '''@WebMvcTest(UserController.class) public class C6_Slice1 {
  @Autowired MockMvc mvc; @Autowired ApplicationContext ctx; @MockitoBean UserService svc;
  @BeforeAll static void before() { System.out.println("RES >> C6_Slice1"); }
  @Test void t() throws Exception { when(svc.name(1)).thenReturn("mocked"); System.out.println("RES    [C6_Slice1] Bean 定义 " + ctx.getBeanDefinitionCount() + " 个,GET /users/1 → " + mvc.perform(get("/users/1")).andReturn().getResponse().getContentAsString()); } }''')
cls('C7_Slice2', '''@WebMvcTest(UserController.class) public class C7_Slice2 {
  @Autowired MockMvc mvc; @Autowired ApplicationContext ctx; @MockitoBean UserService svc;
  @BeforeAll static void before() { System.out.println("RES >> C7_Slice2"); }
  @Test void t() throws Exception { System.out.println("RES    [C7_Slice2] Bean 定义 " + ctx.getBeanDefinitionCount() + " 个"); } }''')
cls('C8_SliceNoMock', '''@WebMvcTest(UserController.class) public class C8_SliceNoMock {
  @Autowired MockMvc mvc;
  @BeforeAll static void before() { System.out.println("RES >> C8_SliceNoMock"); }
  @Test void t() throws Exception { mvc.perform(get("/users/1")); } }''')
cls('C9_Dirties', '''@SpringBootTest @DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD) public class C9_Dirties {
  @Autowired ApplicationContext ctx;
  @BeforeAll static void before() { System.out.println("RES >> C9_Dirties(2 个测试方法)"); }
  @Test void a() { System.out.println("RES    [C9_Dirties.a] Bean 定义 " + ctx.getBeanDefinitionCount() + " 个"); }
  @Test void b() { System.out.println("RES    [C9_Dirties.b] Bean 定义 " + ctx.getBeanDefinitionCount() + " 个"); } }''')
b = sbuild('x82', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def junit(classes, jopts=(), extra=()):
    t = time.time(); r = subprocess.run(['java', *jopts, '-Djunit.jupiter.testclass.order.default=org.junit.jupiter.api.ClassOrderer$ClassName', '-cp', str(b['out']) + ':' + b['cp'], 'org.junit.platform.console.ConsoleLauncher', 'execute', '--disable-banner', '--disable-ansi-colors', '--details=summary', *sum((['--select-class', 'demo.' + c] for c in classes), []), *extra], cwd=b['dir'], env=jenv('21'), capture_output=True, text=True, timeout=300)
    return tidy(r.stdout + r.stderr), r.returncode, (time.time() - t) * 1000
def res_lines(o): return [l[4:] for l in o.splitlines() if l.startswith('RES ')]
def summary(o):
    m = {k: re.search(rf'\[\s*(\d+) {k}\s*\]', o) for k in ('tests successful', 'tests failed', 'containers failed')}
    return ', '.join(f'{k} {v.group(1)}' for k, v in m.items() if v)
print('Spring Boot 4.0.8 / JDK 21 / JUnit Jupiter 6.0.3 / Mockito 5.20.0;用 JUnit Platform Console Launcher 直接跑测试类,每次一个独立 JVM;应用 = 一个 UserController + 一个 UserService')
print('== 一:不启动 Spring、@WebMvcTest 切片、@SpringBootTest 完整上下文,各自的上下文有多大、跑多久')
for lab, cl in (('Plain(不启动 Spring)', ['Plain']), ('C6_Slice1(@WebMvcTest)', ['C6_Slice1']), ('C1_Full1(@SpringBootTest + @AutoConfigureMockMvc)', ['C1_Full1'])):
    ts = []
    for i in range(3):
        o, rc, ms = junit(cl); ts.append(ms)
    print(f'  {lab}:整条命令(含 JVM 启动)3 次中位 {statistics.median(ts):.0f} ms(范围 {min(ts):.0f}~{max(ts):.0f});结果 {summary(o)}')
    for l in res_lines(o):
        if 'Bean 定义' in l or 'Plain' in l: print('    ' + l.strip())
print('== 二:上下文缓存(8 个测试类在同一个 JVM 里按类名顺序跑)')
o, rc, ms = junit(['C1_Full1', 'C2_Full2', 'C3_FullMock', 'C4_FullProp', 'C5_FullProfile', 'C6_Slice1', 'C7_Slice2', 'C9_Dirties'])
for l in res_lines(o): print('  ' + l)
print(f'  结果 {summary(o)},整条命令 {ms:.0f} ms')
print('== 三:@WebMvcTest 里没有 mock 掉 Service 会怎样')
o, rc, ms = junit(['C8_SliceNoMock'])
print(f'  退出码 {rc};{summary(o)}')
fl = [l.strip() for l in o.splitlines() if 'No qualifying bean' in l or 'UnsatisfiedDependencyException' in l or 'Failed to load ApplicationContext' in l or 'IllegalStateException' in l][:4]
for l in fl: print('    ' + l[:330])
