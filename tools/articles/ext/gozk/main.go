package main

import (
	"bufio"
	"fmt"
	"os"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/go-zookeeper/zk"
)

var stdin = bufio.NewReader(os.Stdin)

func must(err error) {
	if err != nil {
		panic(err)
	}
}
func connect(addr string, to time.Duration) (*zk.Conn, <-chan zk.Event) {
	c, ev, err := zk.Connect([]string{addr}, to, zk.WithLogInfo(false))
	must(err)
	return c, ev
}
func waitSession(ev <-chan zk.Event) {
	for e := range ev {
		if e.State == zk.StateHasSession {
			return
		}
	}
}

func main() {
	addr := "127.0.0.1:7300"
	c, ev := connect(addr, 6*time.Second)
	waitSession(ev)
	go func() {
		for range ev {
		}
	}()
	fmt.Println("== 一:基本调用与错误值:Create / Get / Set(带 version)/ 错误对照")
	acl := zk.WorldACL(zk.PermAll)
	_, err := c.Create("/g", []byte("v0"), 0, acl)
	must(err)
	_, err = c.Create("/g", nil, 0, acl)
	fmt.Println("  Create 已存在 →", err, "| errors.Is(err, zk.ErrNodeExists) =", err == zk.ErrNodeExists)
	_, _, err = c.Get("/nope")
	fmt.Println("  Get 不存在 →", err)
	_, st, _ := c.Get("/g")
	_, err = c.Set("/g", []byte("v1"), st.Version)
	must(err)
	_, err = c.Set("/g", []byte("v2"), st.Version)
	fmt.Println("  Set 用旧 version →", err)
	_, err = c.Create("/e", nil, zk.FlagEphemeral, acl)
	must(err)
	_, err = c.Create("/e/x", nil, 0, acl)
	fmt.Println("  临时节点下建子节点 →", err)
	p, err := c.Create("/g/seq-", nil, zk.FlagSequence, acl)
	fmt.Println("  FlagSequence 返回的路径 →", p, err)
	fmt.Println()

	fmt.Println("== 二:watch 是一次性的 channel:GetW 返回 (data, stat, <-chan Event);不重新注册就收不到第二次变化")
	_, _, wch, err := c.GetW("/g")
	must(err)
	c.Set("/g", []byte("a"), -1)
	e1 := <-wch
	fmt.Println("  第一次变化收到:", e1.Type, e1.Path)
	c.Set("/g", []byte("b"), -1)
	select {
	case e := <-wch:
		fmt.Println("  第二次变化(没有重新 GetW)收到:", e.Type, "(读到零值事件:watch 的 channel 触发一次后就被关闭)")
	case <-time.After(500 * time.Millisecond):
		fmt.Println("  第二次变化(没有重新 GetW):500 ms 内没有收到任何事件")
	}
	var cnt int32
	stop := make(chan struct{})
	done := make(chan struct{})
	go func() {
		for {
			_, _, ch, err := c.GetW("/g")
			if err != nil {
				return
			}
			select {
			case <-ch:
				atomic.AddInt32(&cnt, 1)
			case <-stop:
				close(done)
				return
			}
		}
	}()
	time.Sleep(200 * time.Millisecond)
	for i := 0; i < 200; i++ {
		c.Set("/g", []byte(fmt.Sprintf("r%d", i)), -1)
	}
	time.Sleep(800 * time.Millisecond)
	close(stop)
	<-done
	d, _, _ := c.Get("/g")
	fmt.Printf("  循环里重新 GetW:连续 Set 200 次,收到 %d 次事件;最终值 %s\n", atomic.LoadInt32(&cnt), d)
	fmt.Println()

	fmt.Println("== 三:并发:2000 次 Create,单 goroutine 顺序执行 vs 64 个 goroutine 同时发")
	c.Create("/s", nil, 0, acl)
	c.Create("/p", nil, 0, acl)
	t := time.Now()
	for i := 0; i < 2000; i++ {
		c.Create(fmt.Sprintf("/s/n%d", i), []byte("x"), 0, acl)
	}
	ts := time.Since(t).Seconds()
	t = time.Now()
	var wg sync.WaitGroup
	for g := 0; g < 64; g++ {
		wg.Add(1)
		go func(g int) {
			defer wg.Done()
			for i := g; i < 2000; i += 64 {
				c.Create(fmt.Sprintf("/p/n%d", i), []byte("x"), 0, acl)
			}
		}(g)
	}
	wg.Wait()
	tp := time.Since(t).Seconds()
	fmt.Printf("  顺序 %.0f 个/s(%.2f s);64 goroutine %.0f 个/s(%.2f s);%.1f 倍\n", 2000/ts, ts, 2000/tp, tp, ts/tp)
	fmt.Println()

	fmt.Println("== 四:Multi:原子地建两个节点,第二个已存在时整体失败(第一个也不会建)")
	c.Create("/m2", nil, 0, acl)
	_, err = c.Multi(&zk.CreateRequest{Path: "/m1", Data: []byte("1"), Acl: acl}, &zk.CreateRequest{Path: "/m2", Data: []byte("2"), Acl: acl})
	ex, _, _ := c.Exists("/m1")
	fmt.Println("  Multi(建 /m1, 建已存在的 /m2) →", err, "| /m1 存在 =", ex)
	_, err = c.Multi(&zk.CreateRequest{Path: "/m3", Data: []byte("1"), Acl: acl}, &zk.CreateRequest{Path: "/m4", Data: []byte("2"), Acl: acl})
	ex3, _, _ := c.Exists("/m3")
	ex4, _, _ := c.Exists("/m4")
	fmt.Println("  Multi(建 /m3, 建 /m4) →", err, "| /m3 =", ex3, "/m4 =", ex4)
	fmt.Println()

	fmt.Println("== 五:自带的锁 zk.NewLock:10 个 goroutine(各自独立连接)各做 20 次「读 → 加 1 → 写回」")
	c.Create("/ctr", []byte("0"), 0, acl)
	var wg2 sync.WaitGroup
	t = time.Now()
	for g := 0; g < 10; g++ {
		wg2.Add(1)
		go func() {
			defer wg2.Done()
			cc, ee := connect(addr, 6*time.Second)
			waitSession(ee)
			go func() {
				for range ee {
				}
			}()
			l := zk.NewLock(cc, "/glock", acl)
			for i := 0; i < 20; i++ {
				must(l.Lock())
				d, st, _ := cc.Get("/ctr")
				var v int
				fmt.Sscanf(string(d), "%d", &v)
				cc.Set("/ctr", []byte(fmt.Sprint(v+1)), st.Version)
				must(l.Unlock())
			}
			cc.Close()
		}()
	}
	wg2.Wait()
	d, _, _ = c.Get("/ctr")
	kids, _, _ := c.Children("/glock")
	sort.Strings(kids)
	fmt.Printf("  最终 %s / 200,用时 %.1f s;/glock 下现在的子节点数 %d\n", d, time.Since(t).Seconds(), len(kids))
	l := zk.NewLock(c, "/glock2", acl)
	l.Lock()
	k2, _, _ := c.Children("/glock2")
	fmt.Println("  持有锁时的锁节点名:", strings.Join(k2, ","))
	l.Unlock()
	fmt.Println()

	fmt.Println("== 六:服务端重启期间的调用(Go 客户端是「立即失败」还是「等待」)")
	for _, to := range []time.Duration{3 * time.Second} {
		cc, ee := connect(addr, to)
		var mu sync.Mutex
		var evs []string
		t0 := time.Now()
		go func() {
			for e := range ee {
				mu.Lock()
				evs = append(evs, fmt.Sprintf("%.1fs %s", time.Since(t0).Seconds(), e.State))
				mu.Unlock()
			}
		}()
		time.Sleep(500 * time.Millisecond)
		fmt.Println("STOP_ZK")
		stdin.ReadString('\n')
		time.Sleep(300 * time.Millisecond)
		for i := 0; i < 3; i++ {
			t1 := time.Now()
			_, _, err := cc.Get("/g")
			mu.Lock()
			evs = append(evs, fmt.Sprintf("%.1fs 调用 Get → %v(耗时 %.0f ms)", time.Since(t0).Seconds(), err, float64(time.Since(t1).Milliseconds())))
			mu.Unlock()
			time.Sleep(700 * time.Millisecond)
		}
		fmt.Println("STARTING")
		time.Sleep(6 * time.Second)
		t1 := time.Now()
		_, _, err = cc.Get("/g")
		mu.Lock()
		evs = append(evs, fmt.Sprintf("%.1fs 服务端恢复后 Get → %v(耗时 %.0f ms)", time.Since(t0).Seconds(), err, float64(time.Since(t1).Milliseconds())))
		mu.Unlock()
		time.Sleep(300 * time.Millisecond)
		mu.Lock()
		for _, e := range evs {
			fmt.Println("  " + e)
		}
		mu.Unlock()
		cc.Close()
	}
	fmt.Println("DONE")
}
