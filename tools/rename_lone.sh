#!/system/bin/sh
# A magyanos, zarojeles sorszamu fajlok nevenek megtisztitasa.
# CSAK akkor nevez at, ha a tiszta nev MEG NEM letezik (nincs utkozes).
DIR=/sdcard/Music
cd "$DIR" || exit 1
for f in *; do
  [ -f "$f" ] || continue
  clean=$(printf '%s' "$f" | sed 's/ ([0-9][0-9]*)\(\.[A-Za-z0-9]*\)$/\1/')
  if [ "$clean" != "$f" ] && [ ! -e "$clean" ]; then
    mv -f "$f" "$clean" && echo "ATNEVEZVE: $f  ->  $clean"
  fi
done
echo "--- Kesz. Fajlok: $(ls | wc -l)"
