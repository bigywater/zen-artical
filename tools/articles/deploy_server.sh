#!/bin/bash
# 把本地库部署到服务器(整库快照替换:服务器上有、本地没有的数据会被覆盖,所以运行前先对比两边,见下一行)。
# 运行前的检查(只读):备份服务器库后,比较两边各表的行数和内容;确认服务器没有本地缺少的行再运行。
# 用法(在 zen 根目录):bash tools/articles/deploy_server.sh
# 做的事:本地库快照 -> 上传为 db.sqlite3.new -> 校验 -> 旧库改名留底 -> 换库 -> migrate/collectstatic/build_static(用 deploy 用户)-> 重启 zen -> 验证。
set -euo pipefail
S=root@60.205.138.114
STAMP=$(date +%Y%m%d-%H%M%S)
VERIFY="${VERIFY:-network-layered-model.html rabbitmq-amqp-model.html}"
SERIES="${SERIES:-network rabbitmq}"
cd "$(dirname "$0")/../.."
SNAP=$(mktemp -d)/local.sqlite3
sqlite3 db.sqlite3 ".backup $SNAP"
[ "$(sqlite3 "$SNAP" 'pragma integrity_check')" = ok ]
echo "本地快照:文章 $(sqlite3 "$SNAP" 'select count(*) from tech_article'),系列 $(sqlite3 "$SNAP" 'select count(*) from tech_series')"

scp -q "$SNAP" $S:/srv/site/zen/db.sqlite3.new
ssh $S "STAMP=$STAMP VERIFY='$VERIFY' SERIES='$SERIES' bash -s" <<'REMOTE'
set -euo pipefail; cd /srv/site/zen
[ "$(sqlite3 db.sqlite3.new "pragma integrity_check")" = ok ]
sqlite3 db.sqlite3 ".backup /srv/site/db-backups/zen-db-before-$STAMP.sqlite3"
chown deploy:deploy db.sqlite3.new; chmod --reference=db.sqlite3 db.sqlite3.new
mv db.sqlite3 /srv/site/db-backups/zen-db-replaced-$STAMP.sqlite3.old
mv db.sqlite3.new db.sqlite3
# /etc/zen.env 里的密钥含 ")",不能 source,逐行读
cat > /tmp/zen_run.sh <<"EOF"
set -e
while IFS== read -r k v; do case "$k" in ""|\#*) ;; *) export "$k=$v";; esac; done < /etc/zen.env
cd /srv/site/zen
/srv/site/venv-zen/bin/python manage.py migrate --noinput
/srv/site/venv-zen/bin/python manage.py collectstatic --noinput
/srv/site/venv-zen/bin/python manage.py build_static
EOF
chmod 755 /tmp/zen_run.sh
su -s /bin/bash deploy -c "bash /tmp/zen_run.sh"
rm -f /tmp/zen_run.sh
systemctl restart zen; sleep 3; systemctl is-active zen
for u in $VERIFY; do
  printf "%s -> " "$u"; curl -s -o /dev/null -w "%{http_code}\n" --resolve bigywater.tech:443:127.0.0.1 "https://bigywater.tech/$u" -k || true
done
for k in $SERIES; do printf "/series/$k/ -> "; curl -s -o /dev/null -w "%{http_code}\n" --resolve bigywater.tech:443:127.0.0.1 "https://bigywater.tech/series/$k/" -k || true; done
sqlite3 db.sqlite3 "select count(*) from tech_article"
REMOTE
