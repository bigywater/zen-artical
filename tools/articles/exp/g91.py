import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g91')
SRC = r'''
package main

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"fmt"
	"io"
	"os"
	"sync"
	"sync/atomic"
	"time"
)

// ---- 一个只用来观察连接池行为的假驱动:每条查询睡 20 ms,记录打开/关闭的连接数 ----
var opens, closes atomic.Int64

type drv struct{}

func (drv) Open(name string) (driver.Conn, error) { opens.Add(1); return &conn{}, nil }

type conn struct{}

func (*conn) Prepare(q string) (driver.Stmt, error) { return &stmt{}, nil }
func (*conn) Close() error                          { closes.Add(1); return nil }
func (*conn) Begin() (driver.Tx, error)             { return nil, fmt.Errorf("no tx") }

type stmt struct{}

func (*stmt) Close() error  { return nil }
func (*stmt) NumInput() int { return -1 }
func (*stmt) Exec(args []driver.Value) (driver.Result, error) {
	time.Sleep(20 * time.Millisecond)
	return driver.RowsAffected(1), nil
}
func (*stmt) Query(args []driver.Value) (driver.Rows, error) {
	time.Sleep(20 * time.Millisecond)
	return &rows{}, nil
}

type rows struct{ done bool }

func (*rows) Columns() []string { return []string{"n"} }
func (*rows) Close() error      { return nil }
func (r *rows) Next(dest []driver.Value) error {
	if r.done { return io.EOF }
	r.done = true
	dest[0] = int64(1)
	return nil
}

func reset() { opens.Store(0); closes.Store(0) }

func burst(db *sql.DB, n int) time.Duration {
	var wg sync.WaitGroup
	t0 := time.Now()
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); db.Exec("x") }()
	}
	wg.Wait()
	return time.Since(t0)
}

func ms(d time.Duration) float64 { return float64(d.Microseconds()) / 1000 }

func main() {
	sql.Register("fake", drv{})
	switch os.Args[1] {
	case "maxopen":
		for _, mo := range []int{0, 5, 1} {
			reset()
			db, _ := sql.Open("fake", "")
			db.SetMaxOpenConns(mo)
			db.SetMaxIdleConns(100)
			d := burst(db, 50)
			st := db.Stats()
			label := fmt.Sprintf("MaxOpenConns=%d", mo)
			if mo == 0 { label = "MaxOpenConns=0(不限制)" }
			fmt.Printf("  50 个并发 Exec(各 20 ms),%-22s 总用时 %6.1f ms,驱动打开了 %2d 个连接;Stats:Open %d、InUse %d、Idle %d、WaitCount %d、WaitDuration %.0f ms\n", label, ms(d), opens.Load(), st.OpenConnections, st.InUse, st.Idle, st.WaitCount, ms(st.WaitDuration))
			db.Close()
		}
	case "idle":
		reset()
		db, _ := sql.Open("fake", "")
		fmt.Printf("  默认 MaxIdleConns = 2(未设置)\n")
		burst(db, 10)
		st := db.Stats()
		fmt.Printf("  第一波 10 个并发 Exec 之后:驱动打开 %d 个连接、已关闭 %d 个;Stats:Open %d、Idle %d、MaxIdleClosed %d\n", opens.Load(), closes.Load(), st.OpenConnections, st.Idle, st.MaxIdleClosed)
		o1 := opens.Load()
		burst(db, 10)
		fmt.Printf("  第二波 10 个并发 Exec 之后:又打开了 %d 个连接\n", opens.Load()-o1)
		db.Close()
		reset()
		db2, _ := sql.Open("fake", "")
		db2.SetMaxIdleConns(10)
		burst(db2, 10)
		o1 = opens.Load()
		burst(db2, 10)
		fmt.Printf("  SetMaxIdleConns(10):第一波打开 %d 个,第二波又打开 %d 个\n", o1, opens.Load()-o1)
		db2.Close()
	case "lifetime":
		reset()
		db, _ := sql.Open("fake", "")
		db.SetMaxIdleConns(5)
		db.SetConnMaxLifetime(100 * time.Millisecond)
		for i := 0; i < 30; i++ { db.Exec("x"); time.Sleep(30 * time.Millisecond) }
		st := db.Stats()
		fmt.Printf("  ConnMaxLifetime=100ms,串行执行 30 次 Exec(每次间隔 30 ms,约 1.5 秒):驱动共打开 %d 个连接;Stats:MaxLifetimeClosed %d\n", opens.Load(), st.MaxLifetimeClosed)
		db.Close()
		reset()
		db2, _ := sql.Open("fake", "")
		db2.SetMaxIdleConns(5)
		for i := 0; i < 30; i++ { db2.Exec("x"); time.Sleep(30 * time.Millisecond) }
		fmt.Printf("  不设 ConnMaxLifetime 的对照:驱动共打开 %d 个连接\n", opens.Load())
		db2.Close()
	case "idletime":
		reset()
		db, _ := sql.Open("fake", "")
		db.SetMaxIdleConns(5)
		db.SetConnMaxIdleTime(50 * time.Millisecond)
		db.Exec("x")
		t0 := time.Now()
		for _, at := range []time.Duration{300, 900, 1200, 2500} {
			time.Sleep(at*time.Millisecond - time.Since(t0))
			st := db.Stats()
			fmt.Printf("  ConnMaxIdleTime=50ms,Exec 之后连接一直空闲;%4.0f ms 时:Open %d、Idle %d、MaxIdleTimeClosed %d(驱动已关闭 %d 个)\n", ms(time.Since(t0)), st.OpenConnections, st.Idle, st.MaxIdleTimeClosed, closes.Load())
		}
		db.Close()
	case "leak":
		reset()
		db, _ := sql.Open("fake", "")
		db.SetMaxOpenConns(1)
		r, _ := db.Query("x") // 取了 rows 但没有关闭、也没有读完
		_ = r
		ctx, cancel := context.WithTimeout(context.Background(), 300*time.Millisecond)
		defer cancel()
		t0 := time.Now()
		_, err := db.ExecContext(ctx, "x")
		st := db.Stats()
		fmt.Printf("  MaxOpenConns=1,第一个 Query 的 rows 没有 Close:第二条语句 %.0f ms 后失败:%v;Stats:InUse %d、WaitCount %d\n", ms(time.Since(t0)), err, st.InUse, st.WaitCount)
		r.Close()
		_, err = db.Exec("x")
		fmt.Printf("  rows.Close() 之后再执行:err = %v\n", err)
		db.Close()
	}
}
'''
d = gdir('sp1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=300)
    return tidy(p.stdout + p.stderr)
print('== 一:MaxOpenConns 限制同时打开的连接数(用一个自己写的假驱动,每条语句睡 20 ms,Go 1.27.1,macOS;连接池逻辑在 database/sql 里,与驱动无关)')
print(run('maxopen'))
print('== 二:MaxIdleConns 默认值 2:池里能留多少空闲连接')
print(run('idle'))
print('== 三:ConnMaxLifetime')
print(run('lifetime'))
print('== 四:ConnMaxIdleTime')
print(run('idletime'))
print('== 五:rows 不关闭会占着连接')
print(run('leak'))
print('== 六:文档与源码')
print('  database/sql/sql.go 的 connectionCleaner:' + ' '.join(x.strip() for x in open(GOROOT + '/src/database/sql/sql.go').read().split('func (db *DB) connectionCleaner(d time.Duration) {')[1].split('\n')[1:6] if x.strip()))
r, o = go(gdir('doc1'), 'doc', 'database/sql.DB.SetMaxIdleConns')
print('  ' + ' '.join(l.strip() for l in o.split('\n')[3:14] if l.strip()))
r, o = go(gdir('doc1'), 'doc', 'database/sql.DB.SetConnMaxLifetime')
print('  ' + ' '.join(l.strip() for l in o.split('\n')[3:10] if l.strip()))
