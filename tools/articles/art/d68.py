from lib import *
R = J('d68'); ty = R['types']; bd = R['big_default']; bm = R['big_mem']
steps = [
    step(f"默认 FILE_UPLOAD_MAX_MEMORY_SIZE 是 2.5 MiB:上传 1 MiB、2 MiB → InMemoryUploadedFile(文件内容在内存里);3 MiB、50 MiB → TemporaryUploadedFile(写到磁盘临时文件,{ty['50']['tmp_dir']} 下,视图里 temporary_file_path() 存在)。阈值是「超过就落盘」。", t=tl([f"{mb} MiB → {ty[mb]['cls']}" + ('(临时文件存在)' if ty[mb].get('tmp_exists') else '') for mb in ('1', '2', '3', '50')], cur=[0, 1], mark=[2, 3]), kv=KV([['≤ 2.5 MiB', '内存'], ['> 2.5 MiB', '磁盘临时文件']], ['> 2.5 MiB'])),
    step(f"上传 200 MiB:默认配置下 gunicorn worker 从 {bd['base']:.0f} MiB 到峰值 {bd['peak']:.0f} MiB(几乎不涨,内容是分块流式写进临时文件的);把 FILE_UPLOAD_MAX_MEMORY_SIZE 调到 1 GiB(且 DATA_UPLOAD_MAX_MEMORY_SIZE=None)后,同样的 200 MiB 全部留在内存,峰值 {bm['peak']:.0f} MiB。", b=bars([['默认(落盘)峰值 RSS(MiB)', bd['peak'], f"{bd['peak']:.0f}"], ['阈值调大(内存)峰值 RSS(MiB)', bm['peak'], f"{bm['peak']:.0f}"]], bm['peak'] * 1.1, done=[0], mark=[1]), kv=KV([['内存', f"{bd['peak']:.0f} vs {bm['peak']:.0f} MiB"]], ['内存'])),
    step(f"FILE_UPLOAD_TEMP_DIR 指定临时文件目录:设置后 5 MiB 的上传,临时文件出现在指定目录({'与设置一致' if R['tempdir']['tmp_dir'] == R['tempdir']['want'] else '与设置不一致'});不设置则用系统临时目录。磁盘临时目录要有足够空间,并且是 Django 进程可写的。", t=tl(['FILE_UPLOAD_TEMP_DIR = ' + R['tempdir']['want'][-40:], '临时文件目录 = ' + str(R['tempdir']['tmp_dir'])[-40:]], done=[1]), kv=KV([['临时目录', 'FILE_UPLOAD_TEMP_DIR']], ['临时目录'])),
]
A = dict(
    n=68, series='django', tags='Django,文件上传,内存,临时文件,gunicorn,真实验证,动画演示',
    desc=f'在 gunicorn 上实测文件上传:默认 FILE_UPLOAD_MAX_MEMORY_SIZE=2.5 MiB,≤ 阈值是 InMemoryUploadedFile、超过是磁盘上的 TemporaryUploadedFile;200 MiB 上传 worker 峰值 {bd["peak"]:.0f} MiB(落盘)vs {bm["peak"]:.0f} MiB(阈值调大后留在内存);FILE_UPLOAD_TEMP_DIR 指定临时目录。',
    lead='用户上传一个 200 MB 的文件,Django 会把它整个读进内存吗?什么时候写临时文件?这篇在真实 gunicorn 上直接量 worker 的内存,并看不同大小的上传得到什么对象。',
    facts=[('2.5 MiB', 'FILE_UPLOAD_MAX_MEMORY_SIZE 默认值:不超过在内存,超过写临时文件'), (f'{bd["peak"]:.0f} vs {bm["peak"]:.0f} MiB', '上传 200 MiB 时 worker 峰值内存:默认(落盘)vs 阈值调到 1 GiB'), ('FILE_UPLOAD_TEMP_DIR', '指定临时文件目录,上传前后由 Django 创建与清理')],
    body=[
        sec('内存还是磁盘', '', term('', blk('d68', 1)), '<p>请求体是分块读取并交给「上传处理器」的。默认的 <code>MemoryFileUploadHandler</code> 在内容小于阈值时把它留在内存,超过则由 <code>TemporaryFileUploadHandler</code> 写入临时文件。</p>'),
        sec('大文件的内存', '', term('', blk('d68', 2)), term('', blk('d68', 3)), '<p>默认设置下上传大文件不会撑爆内存;只有主动调大阈值才会。这不是说安全——磁盘临时文件占用与上传并发数成正比(本文没有测并发)。</p>'),
        sec('临时目录', '', term('', blk('d68', 4)), '<p>视图返回、响应发出后临时文件被清理(视图里能看到文件存在)。</p>'),
        sec('分步演示:上传到哪里', '', demo('文件上传的内存与临时文件', [('t', 'term', '输出'), ('b', 'bars', '内存'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。gunicorn 26.2 1 worker;客户端用 http.client 手工发送 multipart 流;内存每 20 ms 用 ps 采样', '没有验证:并发上传时磁盘占用、上传处理器的自定义(FILE_UPLOAD_HANDLERS)、反向代理(nginx)对请求体的缓冲、上传中途断开时临时文件的清理、Linux 上 /tmp 的 tmpfs 情形'],
)
