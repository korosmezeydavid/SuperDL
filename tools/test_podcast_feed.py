import urllib.request, re

url = 'https://media.rss.com/partizanpodcast/feed.xml'
req = urllib.request.Request(url, headers={'User-Agent': 'SuperDL/1.9'})
body = urllib.request.urlopen(req, timeout=25).read().decode('utf-8', 'ignore')
print('Feed meret:', len(body), 'karakter')

items = re.findall(r'<item>(.*?)</item>', body, re.S)
print('Epizodok szama:', len(items))

for it in items[:3]:
    t = re.search(r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', it, re.S)
    enc = re.search(r'<enclosure[^>]*url="([^"]+)"', it)
    dur = re.search(r'<itunes:duration>(.*?)</itunes:duration>', it)
    title = t.group(1).strip()[:45] if t else '?'
    duration = dur.group(1) if dur else '?'
    audio = 'VAN' if enc else 'NINCS'
    print(' -', title, '| hossz:', duration, '| hang:', audio)
