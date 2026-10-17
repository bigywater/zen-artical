from lib import *
S = SS('k49')
L1 = [l for l in S(1) if l.startswith('  cj-') or 'Job …' in l or 'JobAlreadyActive' in l or 'cj-replace  SuccessfulDelete' in l][:24]
F1 = [['Allow', '每个整分一个,互相重叠'], ['Forbid', '上一个没跑完不创建,跑完才补'], ['Replace', '删掉上一个,再创建新的'], ['事件', 'JobAlreadyActive ×10 / SuccessfulDelete']]
F2 = [['suspend 150 秒', '错过 3 次整分'], ['恢复', '只补最近那次(-0.1 秒)'], ['之后', '回到正常整分调度']]
F3 = [['startingDeadlineSeconds=10', ''], ['恢复时错过了 31 秒', '那次不补'], ['下一个整分', '+29.0 秒才创建']]
F4 = [['status.lastScheduleTime', '13:54:00Z'], ['lastSuccessfulTime', '13:54:08Z'], ['保留', '成功 3 个、失败 1 个']]
PANELS = [('f', 'flow', 'CronJob 的调度'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("三个 CronJob 都是每分钟一次、每个 Job 睡 75 秒(必然重叠)。Allow:每个整分创建一个新 Job,共 5 个,同时有两个在跑。Forbid:第 1 个 Job 创建于 +4.0 秒;21:51:00 那次因为上一个还在运行不创建(事件 JobAlreadyActive,共 10 次),等上一个完成后才在 +81.0 秒补建 21:51 的 Job,之后 +160.0 秒、+238.0 秒——被跳过的调度没有丢,而是推迟补跑,越拖越晚。Replace:每个整分先 SuccessfulDelete 删掉上一个仍在运行的 Job 再创建新的,每个 Job 只活约 58~62 秒,从不跑完。", f=fl(F1, cur=[1], done=[0, 2], mark=[3]), t=tl(L1, mark=lidx(L1, 'cj-forbid(concurrencyPolicy', 'JobAlreadyActive', 'SuccessfulDelete'), done=lidx(L1, 'cj-allow(', 'cj-replace(')), kv=KV([['Allow', '默认,不管上一个'], ['Forbid', '上一个没跑完就不起新的,但没设 startingDeadlineSeconds 时会补跑'], ['Replace', '杀掉上一个,换新的']], ['Forbid'])),
    step("错过的调度:cj-miss 创建时 suspend: true,暂停约 150 秒(错过了 3 个整分)后恢复:只创建了一个 Job(最近那次整分 29860672,相对恢复时刻 -0.1 秒),没有把错过的都补上;之后每个整分一个(+33.9 秒、+93.9 秒)。", f=fl(F2, cur=[1], done=[0, 2]), t=tl(S(2), mark=lidx(S(2), 'cj-miss 暂停了约')), kv=KV([['错过的调度', '只补最近的一次,不是全部'], ['错过太多', '超过 100 次会放弃并报错(未验证)'], ['suspend', '暂停期间不创建任何 Job']], ['错过的调度'])),
    step("startingDeadlineSeconds: 10 的 cj-deadline:在某个整分之后约 31 秒恢复——那个整分已经晚了 31 秒、超过 10 秒的截止时间,所以没有补;第一个 Job 要等到下一个整分(恢复后 +29.0 秒)才创建,之后每 60 秒一个(+89.0、+149.0)。", f=fl(F3, cur=[1], done=[0, 2]), t=tl(S(3), mark=lidx(S(3), 'cj-deadline(startingDeadlineSeconds=10)')), kv=KV([['startingDeadlineSeconds', '错过调度时刻多久之内还能补'], ['不设', '一直可以补(上一节的 Forbid 就是这样越拖越晚)'], ['适合', '过时就没意义的定时任务']], ['startingDeadlineSeconds'])),
    step("状态与历史:cj-miss 的 status 里 lastScheduleTime=…13:54:00Z、lastSuccessfulTime=…13:54:08Z、active=0;默认 successfulJobsHistoryLimit=3、failedJobsHistoryLimit=1,Job 数量被控制在每个 CronJob 最近几个(SuccessfulDelete 事件:cj-allow 删除了最老的 29860670);命名空间里五个 CronJob 一共还剩 15 个 Job。", f=fl(F4, cur=[0, 1, 2]), t=tl(S(4), mark=lidx(S(4), 'cj-miss 的 status', '现存的 Job')), kv=KV([['lastScheduleTime', '最后一次创建 Job 的调度时刻'], ['historyLimit', '自动清理旧 Job,默认成功 3、失败 1'], ['不清理', 'Job 与 Pod 会越积越多']], ['historyLimit'])),
]
A = mkartk('k49', 49, 'Kubernetes,CronJob,concurrencyPolicy,startingDeadlineSeconds,错过的调度,真实验证,动画演示',
    '在 kind 集群里让 CronJob 真实跑 5 分钟:每个 Job 睡 75 秒、每分钟一次,Allow 每个整分创建一个互相重叠的 Job,Forbid 在上一个跑完后才补建被跳过的调度(+4.0、+81.0、+160.0、+238.0 秒,越拖越晚,事件 JobAlreadyActive ×10),Replace 每个整分先删掉上一个再创建新的;suspend 150 秒后恢复只补最近那一次;startingDeadlineSeconds=10 时错过 31 秒的调度不补,等下一个整分;默认保留成功 3 个、失败 1 个历史 Job。',
    'CronJob 看似简单,但上一次还没跑完怎么办、暂停之后会不会补跑、错过了怎么处理,每一条都有坑。这篇让五个 CronJob 在同一分钟起跑,真跑五分钟,把 concurrencyPolicy 三种取值、错过的调度、startingDeadlineSeconds 和历史清理都量出来。',
    [('+4 / +81 / +160 / +238 秒', 'concurrencyPolicy: Forbid 的 CronJob 创建各个 Job 的时刻(每个 Job 跑 75 秒,被跳过的整分调度推迟补跑)'), ('1 个', 'suspend 了 150 秒(错过 3 个整分)再恢复后立即创建的 Job 数'), ('+29.0 秒', 'startingDeadlineSeconds: 10 时,错过了 31 秒的调度不补,第一个 Job 直到下一个整分才创建')],
    [('三种并发策略', '<p>每个 Job 睡 75 秒、每分钟一次,所以相邻两个必然重叠。<b>Allow</b>(默认)每个整分都创建新 Job,同时有两个在跑。<b>Forbid</b>:21:51:00 那次因为上一个还在运行而不创建,事件 <code>JobAlreadyActive: Not starting job because prior execution is running and concurrency policy is Forbid</code>(累计 10 次);等上一个完成后,控制器发现 21:51 的调度还没执行,于是在 +81.0 秒补建它,之后 +160.0、+238.0 秒——被跳过的调度只是推迟,并且越拖越晚。<b>Replace</b>:每个整分先 <code>SuccessfulDelete</code> 删掉仍在运行的上一个 Job 再创建新的,每个 Job 活 58~62 秒,从不跑完。</p>'),
     ('错过的调度', '<p><code>suspend: true</code> 暂停约 150 秒(错过了 3 个整分)后恢复:只立刻创建了一个 Job——最近那次整分的(<code>cj-miss-29860672</code>,后缀是调度时刻的分钟数),没有把 3 次都补上;之后回到每个整分一个(+33.9 秒、+93.9 秒)。</p>'),
     ('startingDeadlineSeconds', '<p>设 <code>startingDeadlineSeconds: 10</code> 的 CronJob 在整分之后约 31 秒才恢复:那次调度已经晚了 31 秒,超过截止时间,不补;第一个 Job 要等到下一个整分(恢复后 +29.0 秒)才创建。不设这个字段时,错过的调度总是可以补,所以上面 Forbid 的 Job 才会越拖越晚。对“过时就没意义”的任务一定要设。</p>'),
     ('状态与历史', '<p><code>status.lastScheduleTime</code> 是最后一次创建 Job 的调度时刻,<code>lastSuccessfulTime</code> 是最后一次成功完成的时间。<code>successfulJobsHistoryLimit</code> 默认 3、<code>failedJobsHistoryLimit</code> 默认 1,多出来的旧 Job 会被自动删除(事件 <code>SuccessfulDelete</code>:<code>cj-allow</code> 删掉了最老的一个)。五个 CronJob 一共还剩 15 个 Job。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0);五个 CronJob 的 schedule 都是 "* * * * *",脚本等到整分前 4 秒创建它们(21:49:56,第一个整分 21:50:00),观察 287 秒,每 3 秒记录一次各 CronJob 名下的 Job;cj-allow/forbid/replace 的 Job 睡 75 秒,cj-miss 与 cj-deadline 的睡 5 秒并创建时 suspend: true;cj-miss 在 +150 秒恢复,cj-deadline 在某个整分之后约 31 秒恢复;Job 的名字后缀是调度时刻按分钟数计算的数字;每种情形各一次',
     '没有验证:错过超过 100 次调度时 CronJob 放弃并报错的行为;timeZone 字段;kube-controller-manager 重启期间的错过调度;successfulJobsHistoryLimit 为 0;CronJob 的 Job 因 Pod 失败重试与下一次调度的交互;大量 CronJob 在同一个整分触发时的创建延迟(这里观察到的创建时刻基本都在整分之后 0~4 秒内)'],
    'CronJob 的调度', PANELS)
