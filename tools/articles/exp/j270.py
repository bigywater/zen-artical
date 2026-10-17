import sys, os, re, time, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j270'); R = {}
MAIN = r'''
import javax.crypto.*; import javax.crypto.spec.*; import java.io.*; import java.nio.file.*; import java.security.*; import java.util.*;
public class Main {
  static void say(String s) { System.out.println("RES " + s); }
  static String err(Throwable t) { Throwable c = t; StringBuilder b = new StringBuilder(t.getClass().getSimpleName()); while (c.getCause() != null) { c = c.getCause(); b.append(" ← ").append(c.getClass().getSimpleName()).append(":").append(c.getMessage()); } if (t.getCause() == null) b.append(":").append(t.getMessage()); return b.toString(); }
  static final SecretKeySpec KEY = new SecretKeySpec(new byte[16], "AES");
  static byte[] gcmEnc(byte[] pt, byte[] iv) throws Exception { Cipher c = Cipher.getInstance("AES/GCM/NoPadding"); c.init(Cipher.ENCRYPT_MODE, KEY, new GCMParameterSpec(128, iv)); return c.doFinal(pt); }
  static Cipher gcmDec(byte[] iv) throws Exception { Cipher c = Cipher.getInstance("AES/GCM/NoPadding"); c.init(Cipher.DECRYPT_MODE, KEY, new GCMParameterSpec(128, iv)); return c; }
  static byte[] cbcEnc(byte[] pt, byte[] iv, String pad) throws Exception { Cipher c = Cipher.getInstance("AES/CBC/" + pad); c.init(Cipher.ENCRYPT_MODE, KEY, new IvParameterSpec(iv)); return c.doFinal(pt); }
  static Cipher cbcDec(byte[] iv, String pad) throws Exception { Cipher c = Cipher.getInstance("AES/CBC/" + pad); c.init(Cipher.DECRYPT_MODE, KEY, new IvParameterSpec(iv)); return c; }
  /** 读取 CipherInputStream 直到 EOF 或异常,返回 [读到的字节数, 异常描述] */
  static String drain(InputStream in) { long n = 0; byte[] buf = new byte[4096]; try { int r; while ((r = in.read(buf)) > 0) n += r; return "读到 " + n + " 字节,正常到达 EOF"; } catch (Throwable t) { return "读到 " + n + " 字节后抛出 " + err(t); } }
  public static void main(String[] a) throws Exception {
    String mode = a[0]; byte[] iv12 = new byte[12], iv16 = new byte[16]; byte[] pt = new byte[1 << 20]; new Random(1).nextBytes(pt);
    if (mode.equals("tamper")) {
      byte[] ct = gcmEnc(pt, iv12); say("1 MiB 明文的 GCM 密文 " + ct.length + " 字节(多了 16 字节的标签)");
      say("GCM 未篡改:" + drain(new CipherInputStream(new ByteArrayInputStream(ct), gcmDec(iv12))));
      byte[] t1 = ct.clone(); t1[ct.length - 100] ^= 1; say("GCM 密文倒数第 100 个字节翻转 1 位:" + drain(new CipherInputStream(new ByteArrayInputStream(t1), gcmDec(iv12))));
      byte[] t2 = ct.clone(); t2[10] ^= 1; say("GCM 密文第 10 个字节翻转 1 位:" + drain(new CipherInputStream(new ByteArrayInputStream(t2), gcmDec(iv12))));
      byte[] t3 = ct.clone(); t3[ct.length - 1] ^= 1; say("GCM 标签的最后 1 位翻转:" + drain(new CipherInputStream(new ByteArrayInputStream(t3), gcmDec(iv12))));
      byte[] cb = cbcEnc(pt, iv16, "PKCS5Padding"); byte[] c1 = cb.clone(); c1[cb.length - 100] ^= 1; say("CBC(PKCS5Padding,无认证)密文倒数第 100 个字节翻转 1 位:" + drain(new CipherInputStream(new ByteArrayInputStream(c1), cbcDec(iv16, "PKCS5Padding"))));
      byte[] c2 = cb.clone(); c2[cb.length - 5] ^= 1; say("CBC 最后一个密文块里翻转 1 位:" + drain(new CipherInputStream(new ByteArrayInputStream(c2), cbcDec(iv16, "PKCS5Padding"))));
      // 读取前缀:每次读 1 字节,统计在异常之前拿到了多少明文
      InputStream in = new CipherInputStream(new ByteArrayInputStream(t1), gcmDec(iv12)); int first = -2; try { first = in.read(); say("GCM 被篡改的流第一次 read() 返回 " + first); } catch (Throwable t) { say("GCM 被篡改的流第一次 read():" + err(t) + "(第一个字节就读不到,说明明文在标签验证通过之前不会交给调用者)"); }
    } else if (mode.equals("trunc")) {
      byte[] ct = gcmEnc(pt, iv12); say("GCM 密文去掉最后 16 字节(标签):" + drain(new CipherInputStream(new ByteArrayInputStream(Arrays.copyOf(ct, ct.length - 16)), gcmDec(iv12))));
      say("GCM 密文去掉最后 1 字节:" + drain(new CipherInputStream(new ByteArrayInputStream(Arrays.copyOf(ct, ct.length - 1)), gcmDec(iv12))));
      say("GCM 密文去掉前半(只留后 1000 字节):" + drain(new CipherInputStream(new ByteArrayInputStream(Arrays.copyOfRange(ct, ct.length - 1000, ct.length)), gcmDec(iv12))));
      say("GCM 密文只剩 10 字节(比标签短):" + drain(new CipherInputStream(new ByteArrayInputStream(Arrays.copyOf(ct, 10)), gcmDec(iv12))));
      say("GCM 空密文(0 字节):" + drain(new CipherInputStream(new ByteArrayInputStream(new byte[0]), gcmDec(iv12))));
      byte[] cb = cbcEnc(pt, iv16, "PKCS5Padding"); say("CBC 密文(PKCS5Padding)完整:" + drain(new CipherInputStream(new ByteArrayInputStream(cb), cbcDec(iv16, "PKCS5Padding"))));
      say("CBC 密文在块边界截掉最后 1 个块(16 字节):" + drain(new CipherInputStream(new ByteArrayInputStream(Arrays.copyOf(cb, cb.length - 16)), cbcDec(iv16, "PKCS5Padding"))));
      byte[] nop = cbcEnc(Arrays.copyOf(pt, 1 << 20), iv16, "NoPadding"); say("CBC/NoPadding 密文在块边界截掉最后 1 个块:" + drain(new CipherInputStream(new ByteArrayInputStream(Arrays.copyOf(nop, nop.length - 16)), cbcDec(iv16, "NoPadding"))) + "(没有任何错误,明文悄悄少了 16 字节)");
      say("CBC 密文截掉最后 5 字节(不在块边界):" + drain(new CipherInputStream(new ByteArrayInputStream(Arrays.copyOf(cb, cb.length - 5)), cbcDec(iv16, "PKCS5Padding"))));
    } else if (mode.equals("close")) {
      byte[] ct = gcmEnc(pt, iv12); byte[] t1 = ct.clone(); t1[ct.length - 100] ^= 1;
      CipherInputStream in = new CipherInputStream(new ByteArrayInputStream(t1), gcmDec(iv12)); try { in.close(); say("被篡改的 GCM 流没有读取就 close():没有异常"); } catch (Throwable t) { say("被篡改的 GCM 流没有读取就 close():" + err(t)); }
      CipherInputStream in2 = new CipherInputStream(new ByteArrayInputStream(ct), gcmDec(iv12)); in2.read(new byte[100]); try { in2.close(); say("未篡改的 GCM 流读了 100 字节就 close():没有异常"); } catch (Throwable t) { say("未篡改的 GCM 流读了 100 字节就 close():" + err(t)); }
      CipherInputStream in3 = new CipherInputStream(new ByteArrayInputStream(t1), gcmDec(iv12)); try { in3.read(new byte[100]); } catch (Throwable t) { say("被篡改的流读 100 字节:" + err(t)); } try { in3.close(); say("该流再 close():没有异常"); } catch (Throwable t) { say("该流再 close():" + err(t)); }
      say("markSupported() = " + new CipherInputStream(new ByteArrayInputStream(ct), gcmDec(iv12)).markSupported() + ";available() 在读取前 = " + new CipherInputStream(new ByteArrayInputStream(ct), gcmDec(iv12)).available() + ";skip(1000) = " + new CipherInputStream(new ByteArrayInputStream(ct), gcmDec(iv12)).skip(1000));
      Path f = Files.createTempFile("j270", ".bin"); try { Cipher c = Cipher.getInstance("AES/GCM/NoPadding"); c.init(Cipher.ENCRYPT_MODE, KEY, new GCMParameterSpec(128, iv12)); OutputStream os = new CipherOutputStream(Files.newOutputStream(f), c); os.write(pt, 0, 1000); os.flush(); long noClose = Files.size(f);
        say("CipherOutputStream(GCM)写 1000 字节后 flush() 但没有 close():文件 " + noClose + " 字节(= 62 个完整的 16 字节分组;剩下 8 字节密文和 16 字节标签要等 close() 才写出,完整的文件是 1016 字节)"); os.close(); say("close() 之后文件 " + Files.size(f) + " 字节");
        Cipher c2 = Cipher.getInstance("AES/GCM/NoPadding"); c2.init(Cipher.ENCRYPT_MODE, KEY, new GCMParameterSpec(128, iv12)); OutputStream os2 = new CipherOutputStream(Files.newOutputStream(f), c2); os2.write(pt, 0, 1000); /* 故意不 close */ long noClose2 = Files.size(f); say("写 1000 字节后既不 flush 也不 close:文件 " + noClose2 + " 字节(同样只有完整分组)");
        byte[] partial = Files.readAllBytes(f); say("不 close 的文件用 CipherInputStream 解密:" + drain(new CipherInputStream(new ByteArrayInputStream(partial), gcmDec(iv12)))); } finally { Files.deleteIfExists(f); }
    } else if (mode.equals("mem")) {
      int mb = Integer.parseInt(a[1]); String alg = a[2]; Path f = Files.createTempFile("j270mem", ".bin"); Path o = Files.createTempFile("j270memo", ".bin");
      try { byte[] chunk = new byte[1 << 20]; new Random(2).nextBytes(chunk);
        if (alg.equals("gcm")) { Cipher c = Cipher.getInstance("AES/GCM/NoPadding"); c.init(Cipher.ENCRYPT_MODE, KEY, new GCMParameterSpec(128, iv12)); try (OutputStream os = new CipherOutputStream(Files.newOutputStream(f), c)) { for (int i = 0; i < mb; i++) os.write(chunk); } }
        else { Cipher c = Cipher.getInstance("AES/CBC/PKCS5Padding"); c.init(Cipher.ENCRYPT_MODE, KEY, new IvParameterSpec(iv16)); try (OutputStream os = new CipherOutputStream(Files.newOutputStream(f), c)) { for (int i = 0; i < mb; i++) os.write(chunk); } }
        say(alg.toUpperCase() + " 加密 " + mb + " MiB 成功(-Xmx" + Runtime.getRuntime().maxMemory() / (1 << 20) + "m):密文文件 " + Files.size(f) / (1 << 20) + " MiB");
        Cipher d = alg.equals("gcm") ? gcmDec(iv12) : cbcDec(iv16, "PKCS5Padding"); long t0 = System.nanoTime(); long n = 0; try (InputStream in = new CipherInputStream(Files.newInputStream(f), d)) { byte[] buf = new byte[1 << 16]; int r; while ((r = in.read(buf)) > 0) n += r; }
        say(alg.toUpperCase() + " 用 CipherInputStream 解密 " + mb + " MiB:成功,读到 " + n / (1 << 20) + " MiB,耗时 " + (System.nanoTime() - t0) / 1_000_000 + " ms");
      } catch (OutOfMemoryError e) { say(alg.toUpperCase() + " 处理 " + mb + " MiB(-Xmx" + Runtime.getRuntime().maxMemory() / (1 << 20) + "m):OutOfMemoryError:" + e.getMessage()); } catch (Throwable t) { say(alg.toUpperCase() + " 处理 " + mb + " MiB:" + err(t)); } finally { Files.deleteIfExists(f); Files.deleteIfExists(o); }
    }
  }
}
'''
d = jdir('j270a'); (d / 'Main.java').write_text(MAIN); E = jenv('21')
rc = subprocess.run(['javac', '-d', 'out', 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2500]); sys.exit()
def jv(*args, flags=(), timeout=300):
    r = subprocess.run(['java', *flags, '-cp', 'out', 'Main', *args], cwd=d, env=E, capture_output=True, text=True, timeout=timeout); return [l[4:] for l in (r.stdout + r.stderr).splitlines() if l.startswith('RES ')] or [(r.stdout + r.stderr).strip()[:500]]
print('== 一:篡改:读到多少字节之后才发现(1 MiB 明文)')
for l in jv('tamper'): print('  ' + l)
print('== 二:截断')
for l in jv('trunc'): print('  ' + l)
print('== 三:close()、flush() 与标签')
for l in jv('close'): print('  ' + l)
print('== 四:内存:GCM 与 CBC 用 CipherInputStream 解密大文件(-Xmx128m)')
for mb in (10, 20, 30, 40, 50, 100, 200):
    for alg in ('gcm', 'cbc'):
        for l in jv('mem', str(mb), alg, flags=('-Xmx128m',)): print('  ' + l)
