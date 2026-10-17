import sys, os, re, time, signal, plistlib, glob; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j266'); R = {}
NODE = '/j266test_zen'
MAIN = r'''
import java.util.*; import java.util.prefs.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
public class Main {
  static final String NODE = "/j266test_zen";
  static void say(String s) { System.out.println("RES " + s); }
  public static void main(String[] a) throws Exception {
    String mode = a[0]; Preferences root = Preferences.userRoot();
    switch (mode) {
      case "info" -> { say("userRoot 实现类 " + root.getClass().getName() + ",absolutePath = " + root.absolutePath() + ",isUserNode = " + root.isUserNode()); Preferences p = root.node(NODE); say("节点 " + p.absolutePath() + " 的 name = " + p.name() + ",parent = " + p.parent().absolutePath()); p.put("k", "v"); say("put 之后 get = " + p.get("k", "?") + ",keys() = " + Arrays.toString(p.keys())); try { Preferences sys = Preferences.systemRoot(); sys.node("/j266test_zen_sys").put("k", "v"); sys.node("/j266test_zen_sys").flush(); say("systemRoot 写入并 flush 成功"); } catch (Throwable t) { say("systemRoot 写入:" + t.getClass().getSimpleName() + ":" + String.valueOf(t.getMessage()).replaceAll("\\s+", " ")); } }
      case "put-exit" -> { Preferences p = root.node(NODE); p.put("exit_noflush", "yes"); say("put 之后正常退出(没有 flush)"); }
      case "put-kill" -> { Preferences p = root.node(NODE); p.put("kill_noflush", "yes"); say("put 之后立刻等待被 kill -9(没有 flush)"); System.out.flush(); Thread.sleep(60_000); }
      case "put-flush-kill" -> { Preferences p = root.node(NODE); p.put("kill_flushed", "yes"); p.flush(); say("put + flush 之后等待被 kill -9"); System.out.flush(); Thread.sleep(60_000); }
      case "get" -> { Preferences p = root.node(NODE); say("读到 " + Arrays.toString(p.keys()) + ";exit_noflush=" + p.get("exit_noflush", "无") + ";kill_noflush=" + p.get("kill_noflush", "无") + ";kill_flushed=" + p.get("kill_flushed", "无")); }
      case "limits" -> { Preferences p = root.node(NODE);
        String[][] cs = {{"key 80 个字符", "k".repeat(80), "v"}, {"key 81 个字符", "k".repeat(81), "v"}, {"value 8192 个字符", "k", "v".repeat(8192)}, {"value 8193 个字符", "k", "v".repeat(8193)}};
        for (String[] c : cs) { try { p.put(c[1], c[2]); say(c[0] + ":成功"); } catch (Throwable t) { say(c[0] + ":" + t.getClass().getSimpleName() + ":" + String.valueOf(t.getMessage()).replaceAll("\\s+", " ").replaceAll("([kvn])\\1{10,}", "$1…($1 重复)")); } }
        try { root.node(NODE + "/" + "n".repeat(81)); say("节点名 81 个字符:成功"); } catch (Throwable t) { say("节点名 81 个字符:" + t.getClass().getSimpleName() + ":" + t.getMessage().replaceAll("n{10,}", "n…")); }
        try { p.put(null, "v"); } catch (Throwable t) { say("key 为 null:" + t.getClass().getSimpleName()); } try { p.put("k", "a\0b"); say("value 含 NUL:成功"); } catch (Throwable t) { say("value 含 NUL:" + t.getClass().getSimpleName()); } }
      case "types" -> { Preferences p = root.node(NODE); p.putInt("i", 42); p.putBoolean("b", true); p.putDouble("d", 3.5); p.putByteArray("ba", new byte[]{1, 2, 3, (byte) 200}); p.put("s", "hello");
        say("getInt(i) = " + p.getInt("i", -1) + ",getInt(s)(值是字符串 hello)= " + p.getInt("s", -1) + ",getBoolean(s) = " + p.getBoolean("s", true) + ",getBoolean(b) = " + p.getBoolean("b", false) + ",getDouble(d) = " + p.getDouble("d", 0) + ",getByteArray(ba) = " + Arrays.toString(p.getByteArray("ba", null)) + ",get(不存在, null) = " + p.get("nope", null) + ",getInt(不存在, 7) = " + p.getInt("nope", 7));
        say("putInt(\"i\") 存的字符串是 " + p.get("i", "?") + ",putBoolean 存的是 " + p.get("b", "?") + ",putByteArray 存的是 " + p.get("ba", "?") + "(Base64),putDouble 存的是 " + p.get("d", "?")); p.remove("i"); say("remove 之后 getInt(i, -1) = " + p.getInt("i", -1)); }
      case "listener" -> { Preferences p = root.node(NODE); List<String> ev = new CopyOnWriteArrayList<>(); p.addPreferenceChangeListener(e -> ev.add(e.getKey() + "=" + e.getNewValue() + "(线程 " + Thread.currentThread().getName() + ")")); p.addNodeChangeListener(new NodeChangeListener() { public void childAdded(NodeChangeEvent e) { ev.add("childAdded " + e.getChild().name()); } public void childRemoved(NodeChangeEvent e) { ev.add("childRemoved " + e.getChild().name()); } });
        p.put("watch", "1"); Thread.sleep(300); say("本进程 put 之后收到的事件:" + ev); ev.clear(); say("READY"); System.out.flush(); Thread.sleep(3500); say("等待另一个进程写入 watch=2 之后(未 sync)收到的事件:" + ev + ";get(watch) = " + p.get("watch", "?")); p.sync(); Thread.sleep(300); say("调用 sync() 之后:get(watch) = " + p.get("watch", "?") + ",事件:" + ev); }
      case "writer2" -> { Preferences p = root.node(NODE); p.put("watch", "2"); p.flush(); say("writer 已写入 watch=2 并 flush"); }
      case "cleanup" -> { Preferences p = root.node(NODE); p.removeNode(); root.flush(); boolean exists = root.nodeExists(NODE); say("removeNode + flush 之后 nodeExists = " + exists);
        try { Preferences sys = Preferences.systemRoot(); if (sys.nodeExists("/j266test_zen_sys")) { sys.node("/j266test_zen_sys").removeNode(); sys.flush(); } } catch (Throwable t) { } }
    }
  }
}
'''
d = jdir('j266a'); (d / 'Main.java').write_text(MAIN); E = jenv('21')
rc = subprocess.run(['javac', '-d', 'out', 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2500]); sys.exit()
def jv(mode, timeout=60):
    r = subprocess.run(['java', '-cp', 'out', 'Main', mode], cwd=d, env=E, capture_output=True, text=True, timeout=timeout); return [l[4:] for l in (r.stdout + r.stderr).splitlines() if l.startswith('RES ') and 'READY' not in l] or [(r.stdout + r.stderr).strip()[:300]]
def launch(mode): return subprocess.Popen(['java', '-cp', 'out', 'Main', mode], cwd=d, env=E, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
def readto(p, key, timeout=20):
    out = []; t0 = time.time()
    while time.time() - t0 < timeout:
        l = p.stdout.readline()
        if not l: break
        out.append(l.strip())
        if key in l: break
    return out
PLISTS = glob.glob(os.path.expanduser('~/Library/Preferences/com.apple.java.util.prefs*'))
def plist_has(key): 
    r = subprocess.run(['defaults', 'read', 'com.apple.java.util.prefs'], capture_output=True, text=True); return ('j266test_zen' in r.stdout), r.stdout
print('== 一:Preferences 在这台机器(macOS)上的实现与存储位置')
jv('cleanup')
for l in jv('info'): print('  ' + l)
print('  存储文件:' + ', '.join(os.path.basename(p) for p in glob.glob(os.path.expanduser('~/Library/Preferences/*java*prefs*'))) )
has, txt = plist_has('j266test_zen'); print(f'  defaults read com.apple.java.util.prefs 里含有 j266test_zen = {has}')
print('== 二:什么时候真的写进存储:put 之后 正常退出 / kill -9 / flush 之后 kill -9,再用新进程读')
jv('cleanup'); jv('put-exit'); print('  put 之后正常退出 → 新进程读到:' + ' '.join(jv('get')))
jv('cleanup')
p = launch('put-kill'); readto(p, '等待被 kill'); p.send_signal(signal.SIGKILL); p.wait(); print('  put(不 flush)后立刻 kill -9 → 新进程读到:' + ' '.join(jv('get')))
p = launch('put-flush-kill'); readto(p, '等待被 kill'); p.send_signal(signal.SIGKILL); p.wait(); print('  put + flush 后 kill -9 → 新进程读到:' + ' '.join(jv('get')))
print('== 三:长度限制与取值类型')
jv('cleanup')
for l in jv('limits'): print('  ' + l)
jv('cleanup')
for l in jv('types'): print('  ' + l)
print('== 四:另一个进程改了值之后,本进程什么时候看到、监听器收不收到')
jv('cleanup'); p = launch('listener'); pre = readto(p, 'READY'); [print('  ' + l[4:]) for l in pre if l.startswith('RES ') and 'READY' not in l]; time.sleep(0.3); print('  另一个进程:' + ' '.join(jv('writer2'))); rest = p.communicate(timeout=30)[0]; [print('  ' + l[4:]) for l in rest.splitlines() if l.startswith('RES ')]
print('== 五:清理')
for l in jv('cleanup'): print('  ' + l)
has, txt = plist_has('j266test_zen'); print(f'  清理后 defaults read 里仍含有 j266test_zen = {has}')
