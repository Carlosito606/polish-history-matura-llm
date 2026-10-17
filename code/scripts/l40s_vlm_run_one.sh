#!/bin/bash
# run_one.sh NAME [extra llama-server args]: start ONE vision llama-server on :18110 (--cache-ram 0 -np 1),
# describe the 19 mock2023 images, record per-image latency (meta json) and peak VRAM, stop OUR server only.
# exit 3 = not enough free VRAM (nothing started).
set -u
NAME=$1; shift
V=/scratch/vlm; D=$V/models/$NAME; PORT=18110
LS=/scratch/ovl/opt/llama/current/llama-server
PKG=/scratch/mock/wmt-matura/data_cke/mock2023
mkdir -p $V/out $V/logs
MM=$(ls $D/*.gguf | grep -i mmproj | head -1)
M=$(ls $D/*.gguf | grep -iv mmproj | head -1)
[ -f "$M" ] && [ -f "$MM" ] || { echo "$NAME: files missing"; exit 2; }
NEED=$(( ( $(stat -c %s "$M") + $(stat -c %s "$MM") ) / 1048576 + 2048 ))
FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
if [ "$FREE" -lt "$NEED" ]; then echo "$NAME: free ${FREE} MiB < need ${NEED} MiB"; exit 3; fi
curl -sf http://127.0.0.1:$PORT/health >/dev/null && { echo "port $PORT busy"; exit 4; }
echo "$(date +%T) $NAME start (free ${FREE} MiB, need ${NEED} MiB)"
nohup $LS -m "$M" --mmproj "$MM" --host 127.0.0.1 --port $PORT -ngl 999 -c 8192 -np 1 --cache-ram 0 \
  -fa on --jinja --no-warmup --alias "$NAME" "$@" > $V/logs/$NAME.server.log 2>&1 < /dev/null &
SPID=$!
echo $SPID > $V/logs/server.pid
( peak=0; while kill -0 $SPID 2>/dev/null; do
    u=$(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits | awk -F', ' -v p=$SPID '$1==p{print $2}')
    [ -n "$u" ] && [ "$u" -gt "$peak" ] && { peak=$u; echo $peak > $V/logs/$NAME.vram; }
    sleep 1; done ) &
MON=$!
up=0; for i in $(seq 1 300); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && { up=1; break; }; kill -0 $SPID 2>/dev/null || break; sleep 1; done
if [ $up = 1 ]; then
  echo "$(date +%T) $NAME up after ${i}s"
  /opt/conda/bin/python $V/describe_images.py $PKG --url http://127.0.0.1:$PORT --out $V/out/image_vlm_$NAME.json \
    > $V/logs/$NAME.describe.log 2>&1
  RC=$?
else
  echo "$NAME: server did not come up"; tail -5 $V/logs/$NAME.server.log; RC=5
fi
kill $SPID 2>/dev/null; sleep 3; kill -9 $SPID 2>/dev/null; kill $MON 2>/dev/null; rm -f $V/logs/server.pid
echo "$(date +%T) $NAME rc=$RC peakVRAM=$(cat $V/logs/$NAME.vram 2>/dev/null)MiB $(tail -1 $V/logs/$NAME.describe.log 2>/dev/null)"
exit $RC
