#!/usr/bin/env bash
# Baixa os VLIO bags das candidatas G0 do registro SJTU e confere o md5 declarado no manifesto de aquisição.
# O servidor não aceita Range (uma falha reinicia o arquivo do zero) e trava a partir da 4ª conexão simultânea
# por IP, por isso no máximo MAX_JOBS (padrão 3) downloads em paralelo. Não abre nem processa os bags.
#   scripts/fetch_botanic_g0.sh configs/botanic/g0_acquisition/*.json
set -u
cd "$(dirname "$0")/.."
MAX_JOBS=${MAX_JOBS:-3}
BASE=https://scidata.sjtu.edu.cn/api/records/kfjy8-ex881/files
LOG=data/raw/botanic/g0_download.log
log() { echo "$(date -Is) $*" | tee -a "$LOG"; }

fetch() {
  local path md5 name
  path=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['bag']['path'])" "$1")
  md5=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['bag']['md5'])" "$1")
  name=$(basename "$path")
  if [ -f "$path" ]; then log "$name já existe; pulando"; return 0; fi
  for attempt in $(seq 1 10); do
    log "$name tentativa $attempt"
    if curl -sSfL --speed-limit 10000 --speed-time 300 -o "$path.part" "$BASE/$name/content"; then
      if [ "$(md5sum "$path.part" | cut -d' ' -f1)" = "$md5" ]; then
        mv "$path.part" "$path"; log "$name OK md5 $md5"; return 0
      fi
      log "$name md5 divergente"
    else
      log "$name falha do curl ($?)"
    fi
    rm -f "$path.part"; sleep $((60 * attempt))
  done
  # falha de rede não é DATA_UNAVAILABLE: a decisão de indisponibilidade é registrada à parte, no inventário
  log "$name FALHA OPERACIONAL após 10 tentativas"; return 1
}

for m in "$@"; do
  while [ "$(jobs -rp | wc -l)" -ge "$MAX_JOBS" ]; do wait -n; done
  fetch "$m" &
done
wait
log "fim"
