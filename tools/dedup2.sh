#!/system/bin/sh
# SuperDL - BIZTONSAGOS duplikatum-takarito.
#
# FONTOS SZABALY: csak AZONOS MERETU fajlokat tekint duplikatumnak es torol.
# Ha egy csoportban eltero meretu fajlok vannak, azokhoz NEM NYUL, csak jelenti
# - mert azok kulon verziok is lehetnek (pl. "dal (1).mp3" es "dal (2).mp3"
# gyakran KET KULONBOZO felvetel, nem masolat!), vagy csonka feltoltes.
# Az ilyeneket a felhasznalo dontse el.
#
# Hasznalat:  sh dedup2.sh          -> csak jelentes (semmit nem valtoztat)
#             sh dedup2.sh --apply  -> a BIZTOS duplikatumok torlese

DIR=${2:-/sdcard/Music}
TMP=/data/local/tmp
cd "$DIR" || { echo "Nincs meg a mappa: $DIR"; exit 1; }

: > "$TMP/f2.tsv"
for f in *; do
  [ -f "$f" ] || continue
  sz=$(stat -c %s "$f" 2>/dev/null) || continue
  key=$(printf '%s' "$f" | sed 's/ ([0-9][0-9]*)\(\.[A-Za-z0-9]*\)$/\1/')
  printf '%s\t%s\t%s\n' "$key" "$sz" "$f" >> "$TMP/f2.tsv"
done

awk -F'\t' '
{
  key=$1; sz=$2+0; name=$3
  cnt[key]++
  all[key] = all[key] "\n" sz "\t" name
  if (!(key in firstsz)) { firstsz[key]=sz; keep[key]=name }
  if (sz != firstsz[key]) diff[key]=1
}
END {
  for (k in cnt) {
    if (cnt[k] < 2) continue
    n = split(all[k], arr, "\n")
    if (k in diff) {
      # Eltero meretek -> NEM NYULUNK HOZZA, csak jelentjuk
      print "FIGYELEM\t" k "\t"
      for (i=1;i<=n;i++) if (arr[i] != "") print "   ?\t" arr[i]
    } else {
      # Azonos meret -> biztos duplikatum: egyet megtartunk
      for (i=1;i<=n;i++) {
        if (arr[i] == "") continue
        split(arr[i], p, "\t")
        if (p[2] != keep[k]) print "DEL\t" p[2] "\t"
      }
      if (keep[k] != k) print "REN\t" keep[k] "\t" k
    }
  }
}' "$TMP/f2.tsv" > "$TMP/plan2.tsv"

echo "=== JELENTES ($DIR) ==="
d=0; r=0; w=0
while IFS="$(printf '\t')" read -r op a b; do
  case "$op" in
    DEL)      echo "  BIZTOS MASOLAT (torolheto): $a"; d=$((d+1)) ;;
    REN)      echo "  ATNEVEZES: $a -> $b"; r=$((r+1)) ;;
    FIGYELEM) echo "  !! ELTERO MERETUEK - NEM NYULOK HOZZA: $a"; w=$((w+1)) ;;
    "   ?")   echo "        $a  $b" ;;
  esac
done < "$TMP/plan2.tsv"
echo "--- $d biztos masolat, $r atnevezes, $w kezi donteset igenylo csoport"

if [ "$1" = "--apply" ]; then
  echo "=== VEGREHAJTAS (csak a biztos masolatok) ==="
  while IFS="$(printf '\t')" read -r op a b; do
    [ "$op" = "DEL" ] && rm -f "$a"
  done < "$TMP/plan2.tsv"
  while IFS="$(printf '\t')" read -r op a b; do
    [ "$op" = "REN" ] && mv -f "$a" "$b"
  done < "$TMP/plan2.tsv"
  echo "Kesz."
else
  echo "(Csak jelentes volt. Vegrehajtas: sh dedup2.sh --apply)"
fi
