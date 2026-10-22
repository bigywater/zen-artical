import sys, os, re, time, json, http.client, uuid; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x47'); CP = scp('org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.io.*; import java.nio.file.*; import java.util.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.web.bind.annotation.*; import org.springframework.web.multipart.*;
@SpringBootApplication @RestController
public class Main {
  @PostMapping("/up") String up(@RequestParam("file") MultipartFile f, @RequestParam(value = "note", required = false) String note) throws IOException {
    byte[] b = f.getBytes();
    return "name=" + f.getOriginalFilename() + " size=" + f.getSize() + " read=" + b.length + " note=" + note;
  }
  @PostMapping("/up-many") String many(@RequestParam("files") List<MultipartFile> fs) { return "files=" + fs.size() + " sizes=" + fs.stream().map(MultipartFile::getSize).toList(); }
  @PostMapping("/up-opt") String opt(@RequestParam(value = "file", required = false) MultipartFile f) { return "file=" + (f == null ? "null" : f.getOriginalFilename() + ":" + f.getSize() + (f.isEmpty() ? "(isEmpty)" : "")); }
  @PostMapping("/up-name") String name(@RequestParam("file") MultipartFile f) { return "originalFilename=[" + f.getOriginalFilename() + "]"; }
  @PostMapping("/up-part") String part(jakarta.servlet.http.HttpServletRequest rq) throws Exception { return "parts=" + rq.getParts().size(); }
  @PostMapping("/plain") String plain(@RequestParam String note) { return "note=" + note; }
  @ExceptionHandler(Exception.class) org.springframework.http.ResponseEntity<String> ex(Exception e) { return org.springframework.http.ResponseEntity.status(e instanceof MaxUploadSizeExceededException ? 413 : 400).body("[" + e.getClass().getSimpleName() + "] " + String.valueOf(e.getMessage()).replaceAll("\\s+", " ")); }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x47', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def mp(app, path, parts, ctype='multipart/form-data'):
    bd = '----zen' + uuid.uuid4().hex[:8]; out = b''
    for name, fn, data in parts:
        out += f'--{bd}\r\n'.encode() + (f'Content-Disposition: form-data; name="{name}"; filename="{fn}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() if fn is not None else f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()) + (data if isinstance(data, bytes) else data.encode()) + b'\r\n'
    out += f'--{bd}--\r\n'.encode()
    c = http.client.HTTPConnection('127.0.0.1', int(app.props['server.port']), timeout=30)
    c.putrequest('POST', path); c.putheader('Content-Type', f'{ctype}; boundary={bd}'); c.putheader('Content-Length', str(len(out))); c.endheaders(); note = ''
    try:
        for i in range(0, len(out), 65536): c.send(out[i:i + 65536])
    except OSError as e: note = f'(客户端还没发完,连接已被服务端关闭:{type(e).__name__})'
    try:
        r = c.getresponse(); d = r.read().decode('utf-8', 'replace'); return r.status, re.sub(r'"timestamp":"[^"]*",?', '', d.strip()) + (f' [Connection: {r.getheader("Connection")}, Content-Length: {r.getheader("Content-Length")}]' if r.status == 413 else '') + note
    except Exception as e: return 0, f'读响应失败 {type(e).__name__} {note}'
    finally: c.close()
def run(props, f, title):
    app = SApp(b, 'demo.Main', props=props).start(); print(f'== {title}'); f(app); app.stop()
def P(app, lab, path, parts, **kw):
    s, d = mp(app, path, parts, **kw); print(f'  {lab} → {s} {d[:210]}')
print('Spring Boot 4.0.8 / Spring Framework 7.0.9(内嵌 Tomcat 11.0.24;multipart 默认配置:spring.servlet.multipart.max-file-size=1MB、max-request-size=10MB、file-size-threshold=0)')
def one(app):
    P(app, '100 KB 文件 + 文本字段 note', '/up', [('file', 'a.bin', b'x' * 100_000), ('note', None, 'hello')])
    P(app, '同名多个文件 files(3 个)', '/up-many', [('files', 'a', b'1' * 10), ('files', 'b', b'2' * 20), ('files', 'c', b'3' * 30)])
    P(app, '文件名含路径 ../../etc/passwd', '/up-name', [('file', '../../etc/passwd', b'x')])
    P(app, '文件名含 Windows 路径 C:\\\\dir\\\\a.txt', '/up-name', [('file', 'C:\\dir\\a.txt', b'x')])
    P(app, '没带 file 部分(required=false)', '/up-opt', [('note', None, 'only-text')])
    P(app, '带了 file 但 0 字节', '/up-opt', [('file', 'empty.txt', b'')])
    P(app, '带了 file 部分但文件名为空', '/up-opt', [('file', '', b'abc')])
    P(app, '没带 file(required=true)', '/up', [('note', None, 'x')])
run({}, one, '一:默认配置下的上传(MultipartFile 的各种形态)')
def two(app):
    P(app, '文件 1,000,000 字节(1MB 以内)', '/up', [('file', 'a', b'x' * 1_000_000)])
    P(app, '文件 1,048,576 字节(正好 1MB)', '/up', [('file', 'a', b'x' * 1_048_576)])
    P(app, '文件 1,048,577 字节(超 1 字节)', '/up', [('file', 'a', b'x' * 1_048_577)])
    P(app, '文件 2 MB', '/up', [('file', 'a', b'x' * 2_097_152)])
    P(app, '3 个文件各 900 KB,共 2.7 MB(单个都没超 1MB)', '/up-many', [('files', f'f{i}', b'x' * 900_000) for i in range(3)])
    P(app, '12 个文件各 900 KB,共 10.8 MB(总量超 10MB)', '/up-many', [('files', f'f{i}', b'x' * 900_000) for i in range(12)])
run({}, two, '二:默认限制:单个文件 1MB、整个请求 10MB 是怎么触发的')
def three(app):
    P(app, '文件 3 MB', '/up', [('file', 'a', b'x' * 3_000_000)])
    P(app, '文件 6 MB(超 max-file-size=5MB)', '/up', [('file', 'a', b'x' * 6_000_000)])
    P(app, '3 个文件各 4MB 共 12MB(总量超 max-request-size=10MB)', '/up-many', [('files', f'f{i}', b'x' * 4_000_000) for i in range(3)])
run({'spring.servlet.multipart.max-file-size': '5MB', 'spring.servlet.multipart.max-request-size': '10MB'}, three, '三:max-file-size=5MB、max-request-size=10MB')
def four(app):
    P(app, '限制 -1(不限制):50 MB 文件', '/up', [('file', 'big', b'x' * 50_000_000)])
run({'spring.servlet.multipart.max-file-size': '-1', 'spring.servlet.multipart.max-request-size': '-1'}, four, '四:max-file-size=-1、max-request-size=-1(不限制)')
def five(app):
    P(app, '不是 multipart 的普通表单请求发到上传接口', '/plain', [('note', None, 'abc')], ctype='application/x-www-form-urlencoded')
    P(app, 'multipart.enabled=false 时发 multipart', '/up', [('file', 'a', b'x' * 10)])
run({'spring.servlet.multipart.enabled': 'false'}, five, '五:spring.servlet.multipart.enabled=false')

def six(app):
    for n in [10, 50, 51, 100]:
        P(app, f'{n} 个只有 1 字节的文本字段(整个请求不到 1 KB)', '/up-part', [(f'n{i}', None, 'y') for i in range(n)])
    P(app, '51 个部分,其中 1 个是文件', '/up-part', [('file', 'a', b'x')] + [(f'n{i}', None, 'y') for i in range(50)])
run({}, six, '六:部分(part)的个数:默认能有多少个')
def seven(app):
    for n in [50, 200, 201]:
        P(app, f'{n} 个文本字段', '/up-part', [(f'n{i}', None, 'y') for i in range(n)])
run({'server.tomcat.max-part-count': '200'}, seven, '七:server.tomcat.max-part-count=200')
