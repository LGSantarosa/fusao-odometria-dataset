#!/usr/bin/env bash
# Baixa os VLIO bags das candidatas G0 do registro SJTU e confere o md5 declarado no manifesto de aquisição.
# O servidor não aceita Range: uma falha reinicia o arquivo do zero. Não abre nem processa os bags.
#   scripts/fetch_botanic_g0.sh configs/botanic/g0_acquisition/*.json
set -u
cd "$(dirname "$0")/.."
BASE=https://scidata.sjtu.edu.cn/api/records/kfjy8-ex881/files
LOG=data/raw/botanic/g0_download.log
log() { echo "$(date -Is) $*" | tee -a "$LOG"; }

fetch() {
  local path md5 name
  path=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['bag']['path'])" "$1")
  md5=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['bag']['md5'])" "$1")
  name=$(basename "$path")
  if [ -f "$path" ]; then log "$name já existe; pulando"; return 0; fi
  for attempt in 1 2 3 4 5; do
    log "$name tentativa $attempt"
    if curl -sSfL --speed-limit 10000 --speed-time 300 -o "$path.part" "$BASE/$name/content"; then
      if [ "$(md5sum "$path.part" | cut -d' ' -f1)" = "$md5" ]; then
        mv "$path.part" "$path"; log "$name OK md5 $md5"; return 0
      fi
      log "$name md5 divergente"
    else
      log "$name falha do curl ($?)"
    fi
    rm -f "$path.part"; sleep 60
  done
  log "$name INDISPONIVEL após 5 tentativas"; return 1
}

for m in "$@"; do fetch "$m" & done
wait
log "fim"
