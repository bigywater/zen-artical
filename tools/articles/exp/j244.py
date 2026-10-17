import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j244'); R = {}
pg = PGI(9501).start()
def q(sql, db='lab'):
    r = subprocess.run([f'{PGBIN}/psql', '-h', '127.0.0.1', '-p', '9501', '-U', 'lab', '-d', db, '-qAt', '-v', 'ON_ERROR_STOP=1', '-c', sql], capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip().replace('psql:<stdin>:1: ', '')
def fresh(name, setup):
    q(f'DROP DATABASE IF EXISTS {name}'); q(f'CREATE DATABASE {name}'); rc, o = q(setup, name); assert rc == 0, o
def short(o): return re.sub(r'\s+', ' ', o.split('\n')[0].replace('ERROR:  ', '').replace('ERROR: ', ''))[:110]
try:
    print('== 一:回滚 = 旧版本代码重新面对新版本的表结构:v1 的 3 条 SQL(INSERT name+age、SELECT id,name,age、UPDATE age = age + 1)在 8 种迁移之后能否运行')
    V1 = [('INSERT', "INSERT INTO users(name, age) VALUES ('new', 30)"), ('SELECT', 'SELECT id, name, age FROM users'), ('UPDATE', 'UPDATE users SET age = age + 1')]
    BASE = "CREATE TABLE users(id serial primary key, name text not null, age int); INSERT INTO users(name, age) VALUES ('a', 1), ('b', 2)"
    cases = [('M1 新增可空列 email', BASE, 'ALTER TABLE users ADD COLUMN email text'),
             ('M2 新增 NOT NULL 列(表里有 2 行,无默认值)', BASE, 'ALTER TABLE users ADD COLUMN email text NOT NULL'),
             ('M3 新增 NOT NULL 列(空表,无默认值)', "CREATE TABLE users(id serial primary key, name text not null, age int)", 'ALTER TABLE users ADD COLUMN email text NOT NULL'),
             ('M4 新增 NOT NULL 列并带默认值', BASE, "ALTER TABLE users ADD COLUMN email text NOT NULL DEFAULT ''"),
             ('M5 列改名 name → full_name', BASE, 'ALTER TABLE users RENAME COLUMN name TO full_name'),
             ('M6 删除列 age', BASE, 'ALTER TABLE users DROP COLUMN age'),
             ('M7 age 改成 text', BASE, 'ALTER TABLE users ALTER COLUMN age TYPE text USING age::text'),
             ('M8 age 从 int 改成 bigint', BASE, 'ALTER TABLE users ALTER COLUMN age TYPE bigint')]
    for name, setup, mig in cases:
        fresh('m1', setup); rc, o = q(mig, 'm1')
        if rc != 0: print(f'  [{name}] 迁移本身失败:{short(o)}'); continue
        res = []
        for lab, s in V1: rc, o = q(s, 'm1'); res.append(f'{lab} ' + ('成功' if rc == 0 else '失败(' + short(o) + ')'))
        print(f'  [{name}] ' + ';'.join(res))
    print('== 二:回滚迁移(down)与再次升级:v2 在新结构下写入的数据与被压缩掉的信息')
    fresh('m2', "CREATE TABLE users(id serial primary key, name text not null, age int, status text); INSERT INTO users(name, age, status) VALUES ('a',1,'active'),('b',2,'inactive'),('c',3,'pending'),('d',4,'banned'),('e',5,'active')")
    rc, before = q("SELECT md5(string_agg(id||name||coalesce(age::text,'')||status, '|' ORDER BY id)) FROM users", 'm2')
    q("ALTER TABLE users ADD COLUMN status_code int; UPDATE users SET status_code = CASE status WHEN 'active' THEN 1 WHEN 'inactive' THEN 2 ELSE 0 END; ALTER TABLE users DROP COLUMN status", 'm2')
    print('  up:status(文本)→ status_code(1 = active,2 = inactive,其它 = 0)并删除 status 列')
    q("ALTER TABLE users ADD COLUMN status text; UPDATE users SET status = CASE status_code WHEN 1 THEN 'active' WHEN 2 THEN 'inactive' ELSE 'unknown' END; ALTER TABLE users DROP COLUMN status_code", 'm2')
    rc, after = q("SELECT md5(string_agg(id||name||coalesce(age::text,'')||status, '|' ORDER BY id)) FROM users", 'm2'); rc, rows = q("SELECT id||' '||status FROM users ORDER BY id", 'm2')
    print(f'  down 之后表结构与迁移前相同(列 id/name/age/status),但数据校验和 {"一致" if before == after else "不一致"}(前 {before[:8]}… / 后 {after[:8]}…);status 现在是:' + ' ,'.join(rows.split('\n')) + '(原来 c = pending、d = banned)')
    fresh('m2b', "CREATE TABLE users(id serial primary key, name text not null)")
    q("ALTER TABLE users ADD COLUMN email text", 'm2b'); q("INSERT INTO users(name, email) VALUES ('x','x@a.com'),('y','y@a.com'),('z','z@a.com')", 'm2b')
    rc, n1 = q("SELECT count(*) FROM users WHERE email IS NOT NULL", 'm2b'); q("ALTER TABLE users DROP COLUMN email", 'm2b'); q("ALTER TABLE users ADD COLUMN email text", 'm2b'); rc, n2 = q("SELECT count(*) FROM users WHERE email IS NOT NULL", 'm2b')
    print(f'  v2 上线后写入了 {n1} 行 email;回滚(DROP COLUMN email)再重新升级(ADD COLUMN email)后有 email 的行:{n2}')
    print('== 三:Java 序列化:v2 写的数据,v1 读(模拟回滚);v1 写的数据,v2 读(模拟升级)')
    MAIN = r"""
import java.io.*; import java.nio.file.*;
public class Main { public static void main(String[] a) throws Exception { String mode = a[0]; Path p = Path.of(a[1]);
  if (mode.equals("write")) try (ObjectOutputStream o = new ObjectOutputStream(Files.newOutputStream(p))) { Order x = new Order(); x.id = 7; x.name = "widget"; Order.fill(x); o.writeObject(x); }
  else if (mode.equals("rewrite")) { Order x; try (ObjectInputStream i = new ObjectInputStream(Files.newInputStream(p))) { x = (Order) i.readObject(); } try (ObjectOutputStream o = new ObjectOutputStream(Files.newOutputStream(p))) { o.writeObject(x); } }
  else try (ObjectInputStream i = new ObjectInputStream(Files.newInputStream(p))) { Order x = (Order) i.readObject(); System.out.println("读到 " + x); } } }
"""
    def order(fields, uid): return 'import java.io.*; public class Order implements Serializable { ' + (f'private static final long serialVersionUID = {uid}L; ' if uid else '') + 'int id; String name; ' + fields + (' static void fill(Order x) { x.coupon = "VIP-99"; }' if 'coupon' in fields else ' static void fill(Order x) { }') + ' public String toString() { return "Order{id=" + id + ", name=" + name + (' + ('", coupon=" + coupon' if 'coupon' in fields else '""') + ') + "}"; } }'
    def build(tag, fields, uid):
        d = jdir('j244' + tag); (d / 'Main.java').write_text(MAIN); (d / 'Order.java').write_text(order(fields, uid)); E = jenv('21')
        r = subprocess.run(['javac', '-d', 'out', 'Main.java', 'Order.java'], cwd=d, env=E, capture_output=True, text=True); assert r.returncode == 0, r.stderr; return d
    def run(d, *args):
        r = subprocess.run(['java', '-cp', 'out', 'Main', *args], cwd=d, env=jenv('21'), capture_output=True, text=True); return re.sub(r'\s+', ' ', (r.stdout + r.stderr).strip().split('\n')[0] + ((' ' + (r.stdout + r.stderr).strip().split('\n')[1].strip()) if r.stderr and 'InvalidClass' in r.stderr and len((r.stdout + r.stderr).strip().split('\n')) > 1 and False else ''))[:230]
    f = JT / 'j244.bin'
    for label, f1, f2, uid in (('没有 serialVersionUID(v2 新增字段 coupon)', '', 'String coupon;', 0), ('固定 serialVersionUID = 1(v2 新增字段 coupon)', '', 'String coupon;', 1)):
        d1 = build('a1', f1, uid); d2 = build('a2', f2, uid)
        print(f'  [{label}]')
        run(d2, 'write', str(f)); print('    v2 写文件;v1 读:' + run(d1, 'read', str(f)))
        run(d1, 'write', str(f)); print('    v1 写文件;v2 读:' + run(d2, 'read', str(f)))
    d1 = build('b1', '', 1); d2 = build('b2', 'String coupon;', 1)
    run(d2, 'write', str(f)); print('  往返:v2 写入 coupon = VIP-99 → v2 自己读:' + run(d2, 'read', str(f)))
    run(d1, 'rewrite', str(f)); print('  回滚到 v1,v1 读出再写回(不改任何内容)→ 再升级回 v2 读:' + run(d2, 'read', str(f)) + '(v1 的类里没有 coupon,字段被静默丢弃)')
    print('== 四:滚动发布的混合版本窗口:v1(读写 name)与 v2(扩展阶段新增 full_name)同时写同一张表,各 100 行')
    for label, v2sql in (('v2 只写新列 full_name', "INSERT INTO users(full_name) SELECT 'v2-' || g FROM generate_series(1,100) g"), ('v2 双写 name 与 full_name', "INSERT INTO users(name, full_name) SELECT 'v2-' || g, 'v2-' || g FROM generate_series(1,100) g")):
        fresh('m4', "CREATE TABLE users(id serial primary key, name text); ALTER TABLE users ADD COLUMN full_name text")
        q("INSERT INTO users(name) SELECT 'v1-' || g FROM generate_series(1,100) g", 'm4'); q(v2sql, 'm4')
        rc, a = q("SELECT count(*) FROM users WHERE name IS NULL", 'm4'); rc, b = q("SELECT count(*) FROM users WHERE full_name IS NULL", 'm4')
        q("UPDATE users SET full_name = name WHERE full_name IS NULL AND name IS NOT NULL", 'm4'); rc, c = q("SELECT count(*) FROM users WHERE full_name IS NULL", 'm4')
        print(f'  [{label}] 共 200 行:v1 读 name 时看到 NULL 的行 {a};v2 读 full_name 时看到 NULL 的行 {b};回填 UPDATE ... SET full_name = name 之后 v2 看到 NULL 的行 {c}')
finally:
    pg.stop()
