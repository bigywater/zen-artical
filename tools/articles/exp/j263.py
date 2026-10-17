import sys, os, re, time, signal, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j263'); R = {}
data = JT / 'j263data'; shutil.rmtree(data, ignore_errors=True); data.mkdir(parents=True)
MAIN = r'''
import java.io.*; import java.nio.file.*; import java.util.*; import java.util.concurrent.*;
public class Main {
  static void say(String s) { System.out.println("RES " + s); }
  static String out(Process p) throws Exception { return new String(p.getInputStream().readAllBytes()).trim(); }
  static String err(Throwable t) { return t.getClass().getSimpleName() + ":" + String.valueOf(t.getMessage()).replaceAll("/private/tmp/\\S+/j263data", "<data>"); }
  public static void main(String[] a) throws Exception {
    String mode = a[0]; Path data = Path.of(a[1]);
    if (mode.equals("inject")) {
      String evil = "hi; touch " + data + "/PWNED_shell"; Path f1 = data.resolve("PWNED_shell"), f2 = data.resolve("PWNED_args");
      Process p = new ProcessBuilder("sh", "-c", "echo " + evil).start(); String o1 = out(p); p.waitFor(); say("拼接进 sh -c 的字符串:输出 " + o1.replace(data.toString(), "<data>") + ";标记文件 PWNED_shell 被创建 = " + Files.exists(f1));
      Process q = new ProcessBuilder("echo", "hi; touch " + data + "/PWNED_args").start(); String o2 = out(q); q.waitFor(); say("作为单独的参数传给 echo:输出 " + o2.replace(data.toString(), "<data>") + ";标记文件 PWNED_args 被创建 = " + Files.exists(f2));
      Path f3 = data.resolve("PWNED_args2"); Process r = new ProcessBuilder("sh", "-c", "echo \"$1\"", "sh", "hi; touch " + f3).start(); String o3 = out(r); r.waitFor(); say("必须用 shell 时,把输入放在位置参数里(sh -c 'echo \"$1\"' sh <输入>):输出 " + o3.replace(data.toString(), "<data>") + ";标记文件 PWNED_args2 被创建 = " + Files.exists(f3));
      Process s = Runtime.getRuntime().exec("echo 'a b' \"c d\""); say("Runtime.exec(String) 按空白切分、不识别引号:echo 'a b' \"c d\" 的输出是 " + out(s));
      Process t = new ProcessBuilder("echo", "a b", "c d").start(); say("ProcessBuilder(\"echo\", \"a b\", \"c d\") 的输出是 " + out(t));
      Files.writeString(data.resolve("one.txt"), "x"); Process g = new ProcessBuilder("echo", "*").directory(data.toFile()).start(); String og = out(g); Process g2 = new ProcessBuilder("sh", "-c", "echo *").directory(data.toFile()).start(); say("echo * 不经过 shell 时不展开:" + og + ";经过 sh -c 时被展开成工作目录里的文件名:" + out(g2).replace("PWNED_shell", "PWNED_shell"));
    } else if (mode.equals("pipe")) {
      for (int n : new int[]{1000, 16384, 20000, 65536, 70000, 1_000_000}) {
        Process p = new ProcessBuilder("sh", "-c", "head -c " + n + " /dev/zero").start(); boolean fin = p.waitFor(1500, TimeUnit.MILLISECONDS); say("子进程向 stdout 写 " + n + " 字节、Java 不读:" + (fin ? "1.5 s 内正常退出" : "1.5 s 后仍然没退出(写满管道被阻塞)")); if (!fin) { p.destroyForcibly(); p.waitFor(); } }
      Process p = new ProcessBuilder("sh", "-c", "head -c 1000000 /dev/zero").redirectOutput(ProcessBuilder.Redirect.DISCARD).start(); say("redirectOutput(DISCARD):写 1,000,000 字节,退出 = " + p.waitFor(1500, TimeUnit.MILLISECONDS));
      Path lf = data.resolve("out.log"); Process p2 = new ProcessBuilder("sh", "-c", "head -c 1000000 /dev/zero").redirectOutput(lf.toFile()).start(); say("redirectOutput(文件):退出 = " + p2.waitFor(1500, TimeUnit.MILLISECONDS) + ",文件大小 " + Files.size(lf));
      Process p3 = new ProcessBuilder("sh", "-c", "head -c 1000000 /dev/zero >&2; echo done").start(); boolean fin3 = p3.waitFor(1500, TimeUnit.MILLISECONDS); say("只读 stdout、子进程大量写 stderr(1,000,000 字节):" + (fin3 ? "正常退出" : "1.5 s 后仍未退出——stderr 管道写满")); if (!fin3) { p3.destroyForcibly(); p3.waitFor(); }
      Process p4 = new ProcessBuilder("sh", "-c", "head -c 1000000 /dev/zero >&2; echo done").redirectErrorStream(true).start(); byte[] all = p4.getInputStream().readAllBytes(); say("redirectErrorStream(true) 并读完合并后的流:读到 " + all.length + " 字节,退出码 " + p4.waitFor());
      Process p5 = new ProcessBuilder("sh", "-c", "echo out1; echo err1 >&2; echo out2; echo err2 >&2").redirectErrorStream(true).start(); say("redirectErrorStream(true) 的合并结果:" + out(p5).replace("\n", " | "));
    } else if (mode.equals("env")) {
      ProcessBuilder pb = new ProcessBuilder("printenv", "PATH"); String pa = out(pb.start()); say("子进程默认继承环境:printenv PATH 的前 30 个字符 = " + pa.substring(0, Math.min(30, pa.length())) + "(与 Java 进程相同:" + pa.equals(System.getenv("PATH")) + ")");
      Path fake = data.resolve("fakebin"); Files.createDirectories(fake); Path fe = fake.resolve("uname"); Files.writeString(fe, "#!/bin/sh\necho FAKE-UNAME\n"); fe.toFile().setExecutable(true);
      ProcessBuilder pb2 = new ProcessBuilder("uname"); pb2.environment().put("PATH", fake + ":" + System.getenv("PATH")); say("子进程环境的 PATH 里把假的 uname 所在目录放在最前面:pb.start() 运行的是 " + out(pb2.start()) + "(可执行文件的查找用的是 Java 进程自己的 PATH);而用 sh -c uname(由子进程里的 shell 按子进程的 PATH 查找)运行的是 " + out(shUname(fake).start()));
      ProcessBuilder pb3 = new ProcessBuilder("printenv"); pb3.environment().clear(); Process p3 = pb3.start(); say("environment().clear() 之后 printenv 输出 " + out(p3).length() + " 个字符、退出码 " + p3.waitFor() + "(即使子进程环境里没有 PATH,start() 也找到了 printenv)");
      ProcessBuilder pb4 = new ProcessBuilder("sh", "-c", "echo \"MY=$MY HOME=${HOME:-(未设置)}\""); pb4.environment().put("MY", "1"); pb4.environment().remove("HOME"); say("environment().put / remove:" + out(pb4.start()));
    } else if (mode.equals("errors")) {
      String[][] cases = {{"命令不存在", "no-such-command-xyz"}, {"命令存在但工作目录不存在", "echo"}, {"文件存在但没有执行权限", "<noexec>"}, {"命令是一个目录", "<dir>"}, {"参数里含 NUL 字符", "echo"}, {"空命令字符串", ""}};
      Path noexec = data.resolve("noexec.sh"); Files.writeString(noexec, "#!/bin/sh\necho hi\n"); noexec.toFile().setExecutable(false);
      for (String[] c : cases) { try { ProcessBuilder pb = new ProcessBuilder(c[1].equals("<noexec>") ? noexec.toString() : c[1].equals("<dir>") ? data.toString() : c[1]); if (c[0].contains("NUL")) pb.command("echo", "a\0b"); if (c[0].contains("工作目录")) pb.directory(data.resolve("missing-dir").toFile()); Process p = pb.start(); say(c[0] + ":启动成功,退出码 " + p.waitFor()); } catch (Throwable t) { say(c[0] + ":" + err(t)); } }
      try { new ProcessBuilder(new ArrayList<String>()).start(); } catch (Throwable t) { say("命令列表为空:" + err(t)); }
      try { char[] big = new char[3_000_000]; Arrays.fill(big, 'x'); new ProcessBuilder("echo", new String(big)).start(); say("3 MB 的参数:启动成功"); } catch (Throwable t) { say("3 MB 的参数:" + err(t)); }
      Process e = new ProcessBuilder("sh", "-c", "exit 3").start(); say("退出码:sh -c 'exit 3' 的 waitFor = " + e.waitFor());
    }
  }
}
'''
MAIN = MAIN.replace("  static String err(Throwable t)", "  static ProcessBuilder shUname(Path fake) { ProcessBuilder x = new ProcessBuilder(\"sh\", \"-c\", \"uname\"); x.environment().put(\"PATH\", fake + \":\" + System.getenv(\"PATH\")); return x; }\n  static String err(Throwable t)")
d = jdir('j263a'); (d / 'Main.java').write_text(MAIN); E = jenv('21')
rc = subprocess.run(['javac', '-d', 'out', 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2500]); sys.exit()
def jv(mode, timeout=120):
    r = subprocess.run(['java', '-cp', 'out', 'Main', mode, str(data)], cwd=d, env=E, capture_output=True, text=True, timeout=timeout); o = r.stdout + r.stderr; return [l[4:] for l in o.splitlines() if l.startswith('RES ')] or [o.strip()[:600]]
print('== 一:命令注入与参数切分')
for l in jv('inject'): print('  ' + l)
print('== 二:不读输出时管道写满会让子进程阻塞;几种重定向方式')
for l in jv('pipe'): print('  ' + l)
print('== 三:环境变量与可执行文件的查找')
for l in jv('env'): print('  ' + l)
print('== 四:启动失败的错误信息')
for l in jv('errors'): print('  ' + l)
shutil.rmtree(data, ignore_errors=True)
