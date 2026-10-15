# Dependências com commit fixo. Sourced pelos scripts de build.
# pin_clone DIR URL REV: clona e faz checkout de REV se DIR ainda não existe.
pin_clone() {
  [ -d "$1" ] || { git clone -q "$2" "$1" && git -C "$1" checkout -q "$3"; }
}

# apply_patches DIR PATCH...: idempotente (aplica se ainda não aplicado; senão exige que já esteja aplicado).
apply_patches() {
  local d=$1 p; shift
  for p in "$@"; do
    if git -C "$d" apply --check "$p" 2>/dev/null; then git -C "$d" apply "$p"; else git -C "$d" apply --check -R "$p"; fi
  done
}

# verify_pin DIR REV [PATCH...]: os arquivos de DIR têm de ser exatamente REV + patches (independe de HEAD: aceita os
# patches já commitados por cima de REV). Recusa outra revisão, edição, patch que não aplica sobre REV, arquivo não
# rastreado fora do .gitignore e submódulo inicializado em outro commit, sujo ou com arquivo não rastreado.
verify_pin() {
  local d=$1 rev=$2 tmp exp act p; shift 2
  tmp=$(mktemp -d)
  GIT_INDEX_FILE=$tmp/exp git -C "$d" read-tree "$rev"
  for p in "$@"; do
    GIT_INDEX_FILE=$tmp/exp git -C "$d" apply --cached "$p" \
      || { rm -rf "$tmp"; echo "erro: $p não aplica sobre $rev em $d" >&2; return 1; }
  done
  exp=$(GIT_INDEX_FILE=$tmp/exp git -C "$d" write-tree)
  GIT_INDEX_FILE=$tmp/act git -C "$d" read-tree HEAD
  GIT_INDEX_FILE=$tmp/act git -C "$d" add -u   # gitlinks dos submódulos = HEAD de cada um
  act=$(GIT_INDEX_FILE=$tmp/act git -C "$d" write-tree)
  rm -rf "$tmp"
  [ "$exp" = "$act" ] || { echo "erro: $d não corresponde a $rev + patches (git -C $d diff $rev)" >&2; return 1; }
  [ -z "$(git -C "$d" ls-files --others --exclude-standard)" ] \
    || { echo "erro: $d tem arquivos não rastreados (git -C $d ls-files --others --exclude-standard)" >&2; return 1; }
  git -C "$d" submodule foreach --quiet --recursive \
    'git diff --quiet HEAD && test -z "$(git ls-files --others --exclude-standard)" \
     || { echo "erro: submódulo $displaypath sujo ou com arquivos não rastreados" >&2; exit 1; }'
}
