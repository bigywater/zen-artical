import sys, os, re, time, pty, select, termios, tty; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j265'); R = {}
MAIN = r'''
import java.io.*; import java.lang.reflect.*; import java.nio.charset.*; import java.util.*;
public class Main {
  public static void main(String[] a) throws Exception {
    String mode = a[0]; Console c = System.console();
    if (mode.equals("avail")) {
      String term = "(无 isTerminal 方法)"; if (c != null) { try { Method m = Console.class.getMethod("isTerminal"); term = "isTerminal() = " + m.invoke(c); } catch (NoSuchMethodException e) { } }
      System.out.println("RES System.console() " + (c == null ? "== null" : "!= null(" + c.getClass().getName() + ");" + term) + ";System.in.available() 可读 = " + (System.in != null) + ";jdk.console = " + System.getProperty("jdk.console"));
    } else if (mode.equals("read")) {
      if (c == null) { System.out.println("RES console 为 null,无法读取"); return; }
      String name = c.readLine("姓名: "); char[] pw = c.readPassword("密码: "); System.out.println("RES 读到姓名 " + name + ",密码长度 " + (pw == null ? "null" : pw.length) + ",密码首字符 " + (pw == null ? "-" : pw[0]));
      if (pw != null) { Arrays.fill(pw, '\0'); System.out.println("RES 用完后 Arrays.fill 清零,pw[0] = " + (int) pw[0]); }
    } else if (mode.equals("scanner")) {
      System.out.print("密码(用 Scanner 读): "); System.out.flush(); String s = new Scanner(System.in).nextLine(); System.out.println("RES Scanner 读到长度 " + s.length());
    } else if (mode.equals("eof")) {
      char[] pw = c.readPassword("密码: "); System.out.println("RES 输入 Ctrl-D 之后 readPassword 返回 " + (pw == null ? "null" : "长度 " + pw.length + " 的数组")); String l = c.readLine("再读一行: "); System.out.println("RES 之后 readLine 返回 " + (l == null ? "null" : l));
    } else if (mode.equals("charset")) {
      String cs = "(无 charset 方法)"; if (c != null) { try { cs = String.valueOf(Console.class.getMethod("charset").invoke(c)); } catch (NoSuchMethodException e) { } }
      System.out.println("RES Console.charset() = " + cs + ";Charset.defaultCharset() = " + Charset.defaultCharset() + ";stdout.encoding = " + System.getProperty("stdout.encoding") + ";native.encoding = " + System.getProperty("native.encoding"));
    }
  }
}
'''
d = jdir('j265a'); (d / 'Main.java').write_text(MAIN)
for jdk in ('17', '21', '27'):
    rc = subprocess.run([JDKS[jdk] + '/bin/javac', '-d', f'out{jdk}', 'Main.java'], cwd=d, env=jenv(jdk), capture_output=True, text=True)
    if rc.returncode: print(rc.stderr[:2500]); sys.exit()
def pipe_run(jdk, mode, flags=()):
    r = subprocess.run([JDKS[jdk] + '/bin/java', *flags, '-cp', f'out{jdk}', 'Main', mode], cwd=d, env=jenv(jdk), input='', capture_output=True, text=True, timeout=60); return [l[4:] for l in (r.stdout + r.stderr).splitlines() if l.startswith('RES ')] or [(r.stdout + r.stderr).strip()[:200]]
def pty_run(jdk, mode, inputs, flags=(), env_extra=None, timeout=20):
    """在伪终端里运行 java;inputs 是 [(等待出现的提示, 要发送的字节)]。返回终端上看到的全部输出(含回显),发送点标为 <<发送>>。"""
    master, slave = pty.openpty(); e = jenv(jdk); e.update(env_extra or {})
    p = subprocess.Popen([JDKS[jdk] + '/bin/java', *flags, '-cp', f'out{jdk}', 'Main', mode], cwd=d, env=e, stdin=slave, stdout=slave, stderr=slave, close_fds=True); os.close(slave)
    buf = b''; idx = 0; mark = 0; t0 = time.time()
    while time.time() - t0 < timeout:
        r, _, _ = select.select([master], [], [], 0.2)
        if r:
            try: chunk = os.read(master, 4096)
            except OSError: break
            if not chunk: break
            buf += chunk
        if idx < len(inputs) and inputs[idx][0].encode() in buf[mark:]:
            time.sleep(0.3); os.write(master, inputs[idx][1]); idx += 1; buf += '<<发送>>'.encode(); mark = len(buf)
        elif p.poll() is not None and not r: break
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill()
    try:
        while True:
            r, _, _ = select.select([master], [], [], 0.3)
            if not r: break
            chunk = os.read(master, 4096)
            if not chunk: break
            buf += chunk
    except OSError: pass
    os.close(master); return buf.decode('utf8', 'replace')
def clean(t): return t.replace('\r\n', '⏎').replace('\r', '').replace('\n', '⏎')
print('== 一:System.console() 在 JDK 17 / 21 / 27 上:stdin/stdout 是管道时,与在伪终端(pty)里')
for jdk in ('17', '21', '27'):
    print(f'  [JDK {jdk}] 管道:' + ' '.join(pipe_run(jdk, 'avail')))
    print(f'  [JDK {jdk}] 伪终端:' + ' '.join(l[4:] for l in clean(pty_run(jdk, 'avail', [])).split('⏎') if l.startswith('RES ')))
print('  [JDK 27] 管道 + -Djdk.console=java.base:' + ' '.join(pipe_run('27', 'avail', ('-Djdk.console=java.base',))))
print('== 二:回显:在伪终端里依次输入姓名 alice 与密码 Secret123!(readLine / readPassword 与 Scanner)')
for jdk in ('17', '21', '27'):
    t = pty_run(jdk, 'read', [('姓名: ', b'alice\n'), ('密码: ', b'Secret123!\n')]); tc = clean(t)
    print(f'  [JDK {jdk}] readLine + readPassword 的终端内容:{tc}'); print(f'      密码 Secret123! 出现在终端输出里 = {"Secret123!" in t};姓名 alice 的回显在终端里 = {"alice⏎" in clean(t).replace("<<发送>>", "")}')
    t = pty_run(jdk, 'scanner', [('密码(用 Scanner 读): ', b'Secret123!\n')]); print(f'  [JDK {jdk}] Scanner:{clean(t)}' + f'  → 密码 Secret123! 出现在终端输出里 = {"Secret123!" in t}(终端回显)')
print('== 三:EOF 与字符集')
for jdk in ('21', '27'):
    t = pty_run(jdk, 'eof', [('密码: ', b'\x04'), ('再读一行: ', b'\x04')]); print(f'  [JDK {jdk}] Ctrl-D:{clean(t)}')
for jdk in ('17', '21', '27'):
    print(f'  [JDK {jdk}] 伪终端,默认环境:' + ' '.join(l[4:] for l in clean(pty_run(jdk, 'charset', [])).split('⏎') if l.startswith('RES ')))
print(f'  [JDK 21] 伪终端,LC_ALL=C:' + ' '.join(l[4:] for l in clean(pty_run('21', 'charset', [], env_extra={'LC_ALL': 'C'})).split('⏎') if l.startswith('RES ')))
print(f'  [JDK 21] 管道:' + ' '.join(pipe_run('21', 'charset')))
