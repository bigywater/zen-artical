package common

import (
	"encoding/hex"
	"fmt"
	"io"
	"net"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"golang.org/x/net/http2"
	"golang.org/x/net/http2/hpack"
)

// Event 是抓包代理看到的一个 HTTP/2 帧。
type Event struct {
	T      time.Duration
	Dir    string // "C→S" 或 "S→C"
	Type   string
	Flags  string
	Stream uint32
	Len    uint32
	Info   string
	Data   []byte // DATA 帧的载荷(完整拷贝)
}

// Tap 是一个 TCP 代理:原样转发字节,同时把两个方向的 HTTP/2 帧解析出来。
type Tap struct {
	Addr   string
	ln     net.Listener
	target string
	mu     sync.Mutex
	Events []Event
	start  time.Time
	Conns  int
	conns  []net.Conn
	Latency time.Duration // 客户端→服务端方向每个数据块转发前先串行地等这么久(会累加)
	DropCS, DropSC atomic.Bool // 置位后丢弃该方向的所有数据(模拟黑洞:连接没断,但对方什么也收不到)
	DelayCS, DelaySC time.Duration // 流水线式的延迟:每个数据块晚到这么久,不累加(模拟单向传播延迟)
	BytesCS, BytesSC int64
}

func NewTap(target string) *Tap {
	port := FreePort()
	ln, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
	if err != nil {
		panic(err)
	}
	t := &Tap{Addr: ln.Addr().String(), ln: ln, target: target, start: time.Now()}
	go t.accept()
	return t
}

func (t *Tap) Close() { t.ln.Close() }

func (t *Tap) Reset() {
	t.mu.Lock()
	t.Events = nil
	t.start = time.Now()
	t.mu.Unlock()
}

func (t *Tap) snapshot() []Event {
	t.mu.Lock()
	defer t.mu.Unlock()
	return append([]Event(nil), t.Events...)
}
func (t *Tap) Snapshot() []Event { return t.snapshot() }

func (t *Tap) accept() {
	for {
		c, err := t.ln.Accept()
		if err != nil {
			return
		}
		s, err := net.Dial("tcp", t.target)
		if err != nil {
			c.Close()
			continue
		}
		t.mu.Lock()
		t.Conns++
		t.conns = append(t.conns, c, s)
		t.mu.Unlock()
		pr1, pw1 := io.Pipe()
		pr2, pw2 := io.Pipe()
		go t.parse("C→S", pr1, true)
		go t.parse("S→C", pr2, false)
		lcs := newLine(s, &t.DelayCS)
		lcs.drop = &t.DropCS
		lsc := newLine(c, &t.DelaySC)
		lsc.drop = &t.DropSC
		go func() {
			io.Copy(io.MultiWriter(&delayW{lcs, &t.Latency}, pw1, &countW{t, &t.BytesCS}), c)
			pw1.Close(); lcs.Close(); s.Close()
		}()
		go func() {
			io.Copy(io.MultiWriter(lsc, pw2, &countW{t, &t.BytesSC}), s)
			pw2.Close(); lsc.Close(); c.Close()
		}()
	}
}

func flagStr(f http2.Flags, ft http2.FrameType) string {
	var out []string
	switch ft {
	case http2.FrameData:
		if f.Has(http2.FlagDataEndStream) { out = append(out, "END_STREAM") }
		if f.Has(http2.FlagDataPadded) { out = append(out, "PADDED") }
	case http2.FrameHeaders:
		if f.Has(http2.FlagHeadersEndStream) { out = append(out, "END_STREAM") }
		if f.Has(http2.FlagHeadersEndHeaders) { out = append(out, "END_HEADERS") }
		if f.Has(http2.FlagHeadersPriority) { out = append(out, "PRIORITY") }
	case http2.FrameSettings, http2.FramePing:
		if f.Has(http2.FlagSettingsAck) { out = append(out, "ACK") }
	}
	return strings.Join(out, "|")
}

func (t *Tap) add(e Event) {
	t.mu.Lock()
	e.T = time.Since(t.start)
	t.Events = append(t.Events, e)
	t.mu.Unlock()
}

func (t *Tap) parse(dir string, r io.Reader, client bool) {
	if client {
		pre := make([]byte, 24)
		if _, err := io.ReadFull(r, pre); err != nil {
			return
		}
		t.add(Event{Dir: dir, Type: "PREFACE", Len: 24, Info: fmt.Sprintf("%q", pre[:16])})
	}
	fr := http2.NewFramer(io.Discard, r)
	fr.ReadMetaHeaders = hpack.NewDecoder(4096, nil)
	fr.SetMaxReadFrameSize(1 << 24)
	for {
		f, err := fr.ReadFrame()
		if err != nil {
			io.Copy(io.Discard, r)
			return
		}
		h := f.Header()
		e := Event{Dir: dir, Type: h.Type.String(), Flags: flagStr(h.Flags, h.Type), Stream: h.StreamID, Len: h.Length}
		switch f := f.(type) {
		case *http2.MetaHeadersFrame:
			var kv []string
			for _, hf := range f.Fields {
				kv = append(kv, hf.Name+": "+hf.Value)
			}
			e.Info = strings.Join(kv, "; ")
		case *http2.DataFrame:
			e.Data = append([]byte(nil), f.Data()...)
			n := len(e.Data)
			if n > 24 { n = 24 }
			e.Info = hex.EncodeToString(e.Data[:n])
		case *http2.SettingsFrame:
			var kv []string
			f.ForeachSetting(func(s http2.Setting) error { kv = append(kv, fmt.Sprintf("%s=%d", s.ID, s.Val)); return nil })
			e.Info = strings.Join(kv, " ")
		case *http2.WindowUpdateFrame:
			e.Info = fmt.Sprintf("增量 %d", f.Increment)
		case *http2.GoAwayFrame:
			e.Info = fmt.Sprintf("最后流 %d,错误码 %s,附加数据 %q", f.LastStreamID, f.ErrCode, f.DebugData())
		case *http2.RSTStreamFrame:
			e.Info = "错误码 " + f.ErrCode.String()
		case *http2.PingFrame:
			e.Info = fmt.Sprintf("%x", f.Data)
		}
		t.add(e)
	}
}

// Dump 打印抓到的帧(跳过 skip 指定类型的帧)。
func (t *Tap) Dump(skip ...string) {
	sk := map[string]bool{}
	for _, s := range skip { sk[s] = true }
	for _, e := range t.snapshot() {
		if sk[e.Type] { continue }
		extra := ""
		if e.Flags != "" { extra = " [" + e.Flags + "]" }
		fmt.Printf("  %7.2fms %s %-13s 流 %d 长 %-4d%s  %s\n", float64(e.T.Microseconds())/1000, e.Dir, e.Type, e.Stream, e.Len, extra, e.Info)
	}
}

type countW struct {
	t *Tap
	n *int64
}

func (w *countW) Write(p []byte) (int, error) {
	w.t.mu.Lock()
	*w.n += int64(len(p))
	w.t.mu.Unlock()
	return len(p), nil
}

// Bytes 返回目前为止两个方向的 TCP 字节数。
func (t *Tap) Bytes() (int64, int64) {
	t.mu.Lock()
	defer t.mu.Unlock()
	return t.BytesCS, t.BytesSC
}

// ResetBytes 清零字节计数。
func (t *Tap) ResetBytes() {
	t.mu.Lock()
	t.BytesCS, t.BytesSC = 0, 0
	t.mu.Unlock()
}

// CutAll 立刻关闭代理上所有已建立的连接(模拟中途断网)。
func (t *Tap) CutAll() {
	t.mu.Lock()
	cs := append([]net.Conn(nil), t.conns...)
	t.mu.Unlock()
	for _, c := range cs {
		c.Close()
	}
}

type delayW struct {
	w io.Writer
	d *time.Duration
}

func (d *delayW) Write(p []byte) (int, error) {
	if *d.d > 0 {
		time.Sleep(*d.d)
	}
	return d.w.Write(p)
}

type lineItem struct {
	due time.Time
	b   []byte
}

// lineW 是一条延迟线:Write 立刻返回,数据在到期时间之后才写给下游,顺序不变。
type lineW struct {
	drop *atomic.Bool
	w    io.Writer
	d    *time.Duration
	ch   chan lineItem
	done chan struct{}
}

func newLine(w io.Writer, d *time.Duration) *lineW {
	l := &lineW{w: w, d: d, ch: make(chan lineItem, 1<<16), done: make(chan struct{})}
	go l.run()
	return l
}
func (l *lineW) Write(p []byte) (int, error) {
	if l.drop != nil && l.drop.Load() {
		return len(p), nil
	}
	l.ch <- lineItem{time.Now().Add(*l.d), append([]byte(nil), p...)}
	return len(p), nil
}
func (l *lineW) run() {
	for it := range l.ch {
		if x := time.Until(it.due); x > 0 {
			time.Sleep(x)
		}
		l.w.Write(it.b)
	}
	close(l.done)
}
func (l *lineW) Close() { close(l.ch); <-l.done }

// ResetConns 把连接计数清零。
func (t *Tap) ResetConns() {
	t.mu.Lock()
	t.Conns = 0
	t.mu.Unlock()
}
