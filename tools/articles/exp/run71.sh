cd "$(dirname "$0")/.."
export PORTFILE=$PWD/out/71.port MARKFILE=$PWD/out/71.marks; rm -f $PORTFILE
python3 exp/e71.py > out/71.txt 2>&1 &
PY=$!
while [ ! -s $PORTFILE ]; do sleep 0.02; done; P=$(cat $PORTFILE)
: > out/71.samples
while kill -0 $PY 2>/dev/null; do
  T=$(perl -MTime::HiRes=time -e 'printf "%.3f",time')
  S=$(netstat -an | awk -v p=".$P" '$1 ~ /^tcp/ && ($4 ~ p"$" || $5 ~ p"$") {print $4" "$5" "$6}' | sort | tr '\n' ';')
  echo "$T $S" >> out/71.samples
  sleep 0.08
done
