#!/usr/bin/env python3
"""Claude 미리보기 전용: docs/ 의 여러 페이지를 한 파일로 합칩니다 (#주소로 페이지 전환, 이미지 내장)."""
import os, re, base64, glob
ROOT = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(ROOT, 'docs')
OUT = os.path.join(ROOT, 'preview_single.html')

def token(path):
    path = re.sub(r'^(\.\./)+', '', path)
    if path in ('index.html', ''): return 'home'
    m = re.match(r'programs/(.+)\.html$', path)
    if m: return 'p-' + m.group(1)
    m = re.match(r'field/(.+)\.html$', path)
    if m: return 'f-' + re.sub(r'[^A-Za-z0-9._~-]', '', m.group(1))
    return path.replace('.html', '')

imgs = {}
def img_uri(name):
    if name not in imgs:
        b = open(os.path.join(DOCS, 'assets', 'img', name), 'rb').read()
        mt={'svg':'image/svg+xml','png':'image/png','webp':'image/webp'}.get(name.rsplit('.',1)[-1],'image/jpeg')
        imgs[name] = 'data:'+mt+';base64,' + base64.b64encode(b).decode()
    return imgs[name]

pages = [p for p in glob.glob(os.path.join(DOCS, '**', '*.html'), recursive=True)]
order = ['index.html', 'profile.html', 'programs.html']
pages.sort(key=lambda p: (os.path.relpath(p, DOCS) not in order, order.index(os.path.relpath(p, DOCS)) if os.path.relpath(p, DOCS) in order else 0, p))
sections, css, header, footer, script_blocks = [], None, None, None, []
for p in pages:
    rel = os.path.relpath(p, DOCS)
    h = open(p, encoding='utf-8').read()
    if css is None:
        css = re.search(r'<style>(.*?)</style>', h, re.S).group(1)
        header = re.search(r'(<header class="site-head">.*?</header>)', h, re.S).group(1)
        footer = re.search(r'(<footer class="site-foot">.*?</footer>)', h, re.S).group(1)
    main = re.search(r'<main id="main">(.*?)</main>', h, re.S).group(1)
    for s in re.findall(r'<script>(.*?)</script>', main, re.S): script_blocks.append(s)
    main = re.sub(r'<script>.*?</script>', '', main, flags=re.S)
    sections.append(f'<section class="pg" data-pg="{token(rel)}" hidden>{main}</section>')

body = header + '<main id="main">' + ''.join(sections) + '</main>' + footer
body = re.sub(r'href="((?:\.\./)*)contact\.html\?course=[^"]*"', 'href="#contact"', body)
body = re.sub(r'href="((?:\.\./)*)([A-Za-z0-9/_\-.]+\.html)(#[^"]*)?"', lambda m: f'href="#{token(m.group(2))}"', body)
body = re.sub(r'src="(?:\.\./)*assets/img/([^"]+)"', lambda m: f'src="{img_uri(m.group(1))}"', body)
body = body.replace('aria-current="page"', '')

js = r'''
(function(){
  var secs=[].slice.call(document.querySelectorAll('.pg')), navs=[].slice.call(document.querySelectorAll('.nav a'));
  function show(){
    var t=(location.hash||'#home').slice(1); var hit=secs.some(function(s){return s.dataset.pg===t}); if(!hit) t='home';
    secs.forEach(function(s){s.hidden=s.dataset.pg!==t});
    var top=t.indexOf('p-')===0?'programs':t.indexOf('f-')===0?'field':t;
    navs.forEach(function(a){ if(a.getAttribute('href')==='#'+top) a.setAttribute('aria-current','page'); else a.removeAttribute('aria-current');});
    window.scrollTo(0,0);
  }
  window.addEventListener('hashchange',show); show();
})();
'''
font = re.search(r'(@font-face\{.*?\})', open(os.path.join(ROOT, 'preview', 'index.html'), encoding='utf-8').read(), re.S)
html = ('<title>허진호 강사 홈페이지</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n<style>'
        + (font.group(1) if font else '') + '\n' + css + '</style>\n' + body
        + '<script>' + js + '</script>' + ''.join('<script>' + s + '</script>' for s in script_blocks))
open(OUT, 'w', encoding='utf-8').write(html)
print(OUT, len(html) // 1024, 'KB', len(sections), 'pages')
