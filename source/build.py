#!/usr/bin/env python3
"""허진호 강사 사이트 빌드 스크립트.

content/ 의 YAML·마크다운을 읽어 docs/ 에 정적 HTML을 만듭니다 (GitHub Pages가 docs/ 를 그대로 공개).
  python3 build.py            # 실제 사이트용 (docs/)
  python3 build.py --preview  # Claude 미리보기용 (preview/, 폰트 내장)
"""
import json, os, re, shutil, sys, glob, base64, datetime
import yaml, markdown
from jinja2 import Environment, BaseLoader

ROOT = os.path.dirname(os.path.abspath(__file__))
PREVIEW = '--preview' in sys.argv
OUT = os.path.join(ROOT, 'preview' if PREVIEW else 'docs')

def load(name):
    with open(os.path.join(ROOT, 'content', name), encoding='utf-8') as f:
        return yaml.safe_load(f)

P = load('profile.yml'); PROG = load('programs.yml'); HIST = load('history.yml'); MEDIA = load('media.yml')
for _e in MEDIA['episodes']: _e['series_name']=_e.get('series') or '리더의 한 장면'
P.setdefault('naver_verification', ''); P.setdefault('google_verification', '')
for _h in HIST.get('recent') or []: _h['date']=str(_h['date'])
ARCH = load('history_archive.yml')['archive']
import collections as _c
def _norm(o): return re.sub(r'\s+',' ',re.sub(r'^\(주\)|\(주\)$|㈜|주식회사','',str(o))).strip()
_by=_c.defaultdict(lambda:_c.OrderedDict())
for h in (HIST.get('recent') or []):
    if h.get('status') or h.get('confirm'): continue
    _by[h['date'][:4]].setdefault(_norm(h['org']),[])
    if h['course'] not in _by[h['date'][:4]][_norm(h['org'])]: _by[h['date'][:4]][_norm(h['org'])].append(h['course'])
for a in ARCH:
    y=str(a['year']); o=_norm(a['org'])
    if not o or o=='None': continue
    lst=_by[y].setdefault(o,[])
    c=str(a['course'] or '').strip()
    if c and c!='None' and c not in lst: lst.append(c)
from clients_map import ALIAS, EXCLUDE, S as SECTOR, PUBLIC
_cnt=_c.Counter()
for y in _by:
    for o in list(_by[y]):
        a=ALIAS.get(o,o)
        if a!=o:
            lst=_by[y].pop(o); t=_by[y].setdefault(a,[])
            for c in lst:
                if c not in t: t.append(c)
for h in (HIST.get('recent') or []):
    if not h.get('status'): _cnt[ALIAS.get(_norm(h['org']),_norm(h['org']))]+=h.get('sessions') or 1
for a in ARCH: _cnt[ALIAS.get(_norm(a['org']),_norm(a['org']))]+=1
BY_YEAR=[(y,sorted(_by[y].items())) for y in sorted(_by,reverse=True)]
from clients_map import GROUP, GROUP_ORDER, PUBLIC_GROUPS
_g=_c.defaultdict(list)
for o,n in _cnt.most_common():
    if o in EXCLUDE or o not in SECTOR: continue
    _g[GROUP[SECTOR[o]]].append(o)
CLIENTS={'corp':[{'label':k,'orgs':_g[k]} for k in GROUP_ORDER if _g.get(k) and k not in PUBLIC_GROUPS],
         'public':[{'label':k,'orgs':_g[k]} for k in GROUP_ORDER if _g.get(k) and k in PUBLIC_GROUPS]}
COURSES = PROG['courses']; CMAP = {c['slug']: c for c in COURSES}
CATS = PROG['categories']

def reviews():
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'content', 'reviews', '*.md')), reverse=True):
        raw = open(f, encoding='utf-8').read()
        m = re.match(r'^---\n(.*?)\n---\n(.*)$', raw, re.S)
        meta = yaml.safe_load(m.group(1)); body = m.group(2)
        meta['slug'] = os.path.splitext(os.path.basename(f))[0]
        meta['html'] = markdown.markdown(body)
        meta['date'] = str(meta['date'])
        out.append(meta)
    return out
REVIEWS = reviews()
_og=_c.OrderedDict()
for r in REVIEWS: _og.setdefault(r['org'],[]).append(r)
ORGS=[]
for i,(o,rs) in enumerate(sorted(_og.items(), key=lambda kv: max(x['date'] for x in kv[1]), reverse=True),1):
    ORGS.append({'name':o,'slug':f'o{i:02d}','reviews':sorted(rs,key=lambda x:x['date'],reverse=True),'courses':list(dict.fromkeys(x['course'] for x in rs))})
for o in ORGS:
    for r in o['reviews']: r['org_slug']=o['slug']

env = Environment(loader=BaseLoader(), autoescape=True, trim_blocks=True, lstrip_blocks=True)
env.tests['search_year'] = lambda v, y: str(v).startswith(y)
BASE = env.from_string(open(os.path.join(ROOT, 'templates', 'base.html'), encoding='utf-8').read())
CSS = open(os.path.join(ROOT, 'templates', 'style.css'), encoding='utf-8').read()
NAV = [('profile.html', '프로필', 'profile'), ('programs.html', '프로그램', 'programs'),
       ('videos.html', '강의영상', 'videos'), ('field.html', '강의현장', 'field'), ('contact.html', '교육문의', 'contact')]

def hours(h):
    m = re.findall(r'[\d.]+', str(h or ''))
    return float(m[-1]) if m else 0

FONT_FACE = ''
PAGES = []

def render(path, title, desc, active, body_tpl, **ctx):
    depth = path.count('/')
    root = '../' * depth
    content = env.from_string(body_tpl).render(root=root, p=P, CMAP=CMAP, CATS=CATS, COURSES=COURSES,
                                               HIST=HIST, MEDIA=MEDIA, REVIEWS=REVIEWS, ORGS=ORGS, BY_YEAR=BY_YEAR, CLIENTS=CLIENTS, hours=hours, **ctx)
    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Person", "name": "허진호", "jobTitle": "기업교육 강사, 땡큐플러스 대표",
        "worksFor": {"@type": "Organization", "name": "땡큐플러스 (Thank U Plus)"},
        "alumniOf": "연세대학교", "email": P['email'], "url": P['site_url'],
        "image": P['site_url'] + '/assets/img/profile.jpg',
        "knowsAbout": ["리더십", "팀장 리더십", "기획력", "보고서 작성", "업무관리", "문제해결", "소통과 협업", "조직활성화"],
        "sameAs": [u for u in [P['blog'], P.get('youtube')] if u]}, ensure_ascii=False)
    html = BASE.render(page_title=title, page_desc=desc, p=P, path='' if path == 'index.html' else path,
                       nav=NAV, active=active, root=root, content=content, css=CSS, jsonld=jsonld,
                       preview=PREVIEW, body_only=(PREVIEW and path == 'index.html'), font_face=FONT_FACE)
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, 'w', encoding='utf-8').write(html)
    PAGES.append(path)

# ---------------- page bodies ----------------
INDEX = r'''
<section class="brand-band"><div class="wrap"><div class="band-in">
  <p class="band-mark">Thank U Plus<span class="dot">.<img class="band-fig" src="{{ root }}assets/img/tup-figure.svg" alt=""></span></p>
  <p class="band-tag"><b>오늘</b>보다 나은 <b>내일</b>을 위하여</p>
</div></div></section>
<section class="hero"><div class="wrap">
  <div class="hero-grid">
    <div>
      <h1>리더와 구성원이<br><em>함께 일하는 방식</em>을 바꾸는 강의</h1>
      <p class="role">허진호 강사 · 땡큐플러스 대표</p>
      <p class="intro">{{ p.intro }}</p>
      <div class="cta-row">
        <a class="btn primary" href="{{ root }}programs.html">과정 살펴보기</a>
        <a class="btn ghost" href="{{ root }}contact.html">교육 문의 · 제안서 요청</a>
      </div>
    </div>
    <figure class="portrait cut"><img src="{{ root }}assets/img/profile-cut.png" alt="허진호 강사 프로필 사진" width="541" height="820"><figcaption>허진호 · 연세대학교 산업교육학 석사</figcaption></figure>
  </div>
  <div class="stats">
    {% for s in p.stats %}<div class="stat"><div class="num">{{ s.num }}</div><div class="lbl">{{ s.label }}</div><div class="note">{{ s.note }}</div></div>{% endfor %}
  </div>
</div></section>

<section class="section"><div class="wrap">
  <div class="sec-head"><div><p class="eyebrow">Programs</p><h2 class="h2">대표 과정</h2>
  <p class="lede">대상과 시간에 맞춰 모듈을 다시 구성해 제안합니다. 과정명을 누르면 세부 커리큘럼(제안서 요약본)을 볼 수 있습니다.</p></div>
  <a class="more" href="{{ root }}programs.html">전체 과정 보기 →</a></div>
  {% for cat in CATS %}
  <div class="cat">
    <div><h3 class="cat-name">{{ cat.name }}</h3><p class="cat-desc">{{ cat.desc }}</p></div>
    <div class="course-list">
      {% for c in COURSES if c.cat == cat.id %}
      <a class="course" href="{{ root }}programs/{{ c.slug }}.html"><span class="t">{{ c.title }}</span><span class="s">{{ c.subtitle }}</span><span class="m">{{ c.target }} · {{ c.hours }}</span></a>
      {% endfor %}
    </div>
  </div>
  {% endfor %}
</div></section>

<section class="section tint"><div class="wrap">
  <div class="sec-head"><div><p class="eyebrow">Scene Series</p><h2 class="h2">리더의 한 장면 · 일잘러의 한 장면</h2>
  <p class="lede">강의장에서 실제로 나누는 이야기를 짧은 영상으로 옮겼습니다. 리더를 위한 '리더의 한 장면', 실무자를 위한 '일잘러의 한 장면' 두 시리즈로 소개합니다.</p></div>
  <a class="more" href="{{ root }}videos.html">영상 전체 보기 →</a></div>
  <div class="cards">
    {% for e in MEDIA.episodes %}
    <a class="card" href="{{ root }}videos.html#{{ e.slug }}"><img src="{{ root }}assets/img/{{ e.thumb }}" alt=""><span class="k">{{ e.series or '리더의 한 장면' }} · {{ e.theme }}</span><span class="t">{{ e.title }}</span><span class="d">{{ e.desc }}</span></a>
    {% endfor %}
  </div>
</div></section>

<section class="section"><div class="wrap">
  <div class="sec-head"><div><p class="eyebrow">Field</p><h2 class="h2">강의 후기</h2>
  <p class="lede">회사명을 누르면 그 회사에서 언제, 어떤 대상과 어떤 과정을 진행했는지 볼 수 있습니다.</p></div>
  <a class="more" href="{{ root }}field.html">강의 후기 전체 보기 →</a></div>
  <div class="org-chips">{% for o in ORGS[:24] %}<a class="org-chip" href="{{ root }}field/{{ o.slug }}.html">{{ o.name }}</a>{% endfor %}</div>
  <div class="rev-grid" style="margin-top:24px">
  {% for r in REVIEWS[:4] %}
    <a class="rev-card" href="{{ root }}field/{{ r.slug }}.html"><span class="k">{{ r.org }}</span><span class="t">{{ r.course }}</span><span class="d">{{ r.target }}</span></a>
  {% endfor %}
  </div>
</div></section>

<section class="band"><div class="wrap">
  <div><h2>우리 회사에 맞는 과정이 필요하신가요?</h2><p>대상·인원·일정을 알려 주시면 맞춤 커리큘럼과 표준 제안서를 보내 드립니다.</p></div>
  <a class="btn" href="{{ root }}contact.html">교육 문의하기</a>
</div></section>
'''

PROFILE = r'''
<section class="brand-band"><div class="wrap"><div class="band-in">
  <p class="band-mark">Thank U Plus<span class="dot">.<img class="band-fig" src="{{ root }}assets/img/tup-figure.svg" alt=""></span></p>
  <p class="band-tag"><b>오늘</b>보다 나은 <b>내일</b>을 위하여</p>
</div></div></section>
<section class="pf-hero"><div class="wrap pf-grid">
  <div class="pf-photo"><img src="{{ root }}assets/img/profile-cut.png" alt="허진호 강사" width="541" height="820"></div>
  <div class="pf-text">
    <p class="pf-kicker">리더십 · 비즈니스 스킬 · 조직개발 교육 전문</p>
    <h1>땡큐플러스 <em>허진호 대표</em>입니다</h1>
    <p class="pf-lead">기업과 공공기관 구성원을 대상으로 리더십, 비즈니스 스킬(업무성과), 조직개발·HRD를 강의합니다.
    <b>교육담당자 7년, 컨설턴트 5년, 강사 13년</b>의 경험으로 현업을 이해하고, 고객사가 원하는 내용으로 과정을 맞춤 구성합니다.</p>
    <h2 class="pf-sub">약력</h2>
    <ul class="pf-cv">
      {% for e in p.education|reverse %}<li><span class="per">학력</span><span class="org">{{ e }}</span></li>{% endfor %}
      {% for c in p.career %}<li><span class="per">{{ c.period }}</span><span class="org">{{ c.org }}</span> <span class="rl">{{ c.role }}</span></li>{% endfor %}
    </ul>
    <p class="pf-contact"><b>M.</b> <span class="sel">{{ p.phone }}</span><i>|</i><b>E.</b> <span class="sel">{{ p.email }}</span></p>
  </div>
</div></section>
<section class="section tint"><div class="wrap">
  <p class="eyebrow">Strengths</p><h2 class="h2" style="margin-bottom:28px">강의의 특징</h2>
  <div class="strengths">{% for s in p.strengths %}<div><h3>{{ s.title }}</h3><p>{{ s.text }}</p></div>{% endfor %}</div>
</div></section>
<section class="section"><div class="wrap">
  <p class="eyebrow">Areas</p><h2 class="h2" style="margin-bottom:24px">강의 분야</h2>
  <div class="blocks">{% for a in p.areas %}<div><h3>{{ a.name }}</h3><div class="chips">{% for i in a['items'] %}<span class="chip">{{ i }}</span>{% endfor %}</div></div>{% endfor %}</div>
</div></section>
<section class="section"><div class="wrap two-col">
  <div class="feat">
    <p class="eyebrow">Track Record</p><h2 class="h2">대표 강의 이력</h2>

    {% for f in HIST.featured %}<h3>{{ f.area }}</h3><ul>{% for i in f['items'] %}<li>{{ i }}</li>{% endfor %}</ul>{% endfor %}
  </div>
  <aside class="side">
    <div class="box"><h3>컨설팅 프로젝트</h3><ul>{% for i in p.projects %}<li>{{ i }}</li>{% endfor %}</ul></div>
    <div class="box"><h3>수료 과정</h3><ul>{% for i in p.certificates %}<li>{{ i }}</li>{% endfor %}</ul></div>
  </aside>
</div></section>
<section class="section tint cli-sec"><div class="wrap">
    <p class="eyebrow">Clients</p><h2 class="h2">주요 출강처</h2>
    <h3>기업</h3>
    <div class="table-scroll"><table class="cli-table"><tbody>
    {% for g in CLIENTS.corp %}<tr><th scope="row">{{ g.label }}</th><td>{{ g.orgs|join(', ') }}</td></tr>{% endfor %}
    </tbody></table></div>
    <h3>공공기관 · 학교</h3>
    <div class="table-scroll"><table class="cli-table"><tbody>
    {% for g in CLIENTS.public %}<tr><th scope="row">{{ g.label }}</th><td>{{ g.orgs|join(', ') }}</td></tr>{% endfor %}
    </tbody></table></div>
</div></section>
<section class="section"><div class="wrap yr-wrap">
    <p class="eyebrow">History</p><h2 class="h2">연도별 강의 이력</h2>
    <p class="lede">연도를 누르면 그해 강의한 기업·기관과 과정을 볼 수 있습니다.</p>
    <div class="years">
    {% for y, orgs in BY_YEAR %}
      <details class="yr-d"><summary>{{ y }}년</summary>
        <ul class="yr-list">{% for o, cs in orgs %}<li><b>{{ o }}</b>{% if cs %} <span class="note-s">{{ cs|join(' · ') }}</span>{% endif %}</li>{% endfor %}</ul>
      </details>
    {% endfor %}
    </div>
</div></section>
'''

PROGRAMS = r'''
<section class="page-head"><div class="wrap"><p class="crumb">프로그램</p><h1>과정 안내</h1>
<p class="lede">아래 과정은 표준 구성입니다. 대상·시간·조직 상황에 맞춰 모듈을 빼거나 더해 맞춤 제안서를 만들어 드립니다.</p></div></section>
<section class="section"><div class="wrap">
  {% for cat in CATS %}
  <div class="cat">
    <div><h2 class="cat-name">{{ cat.name }}</h2><p class="cat-desc">{{ cat.desc }}</p></div>
    <div class="course-list">
      {% for c in COURSES if c.cat == cat.id %}
      <a class="course" href="{{ root }}programs/{{ c.slug }}.html"><span class="t">{{ c.title }}</span><span class="s">{{ c.summary }}</span><span class="m">{{ c.target }} · {{ c.hours }}</span></a>
      {% endfor %}
    </div>
  </div>
  {% endfor %}
</div></section>
'''

COURSE = r'''
{% set cat = (CATS|selectattr('id','equalto',c.cat)|first) %}
<section class="page-head"><div class="wrap">
  <p class="crumb"><a href="{{ root }}programs.html">프로그램</a> / {{ cat.name }}</p>
  <h1>{{ c.title }}</h1><p class="lede">{{ c.subtitle }}</p>
  <dl class="facts"><div class="fact"><dt>대상</dt><dd>{{ c.target }}</dd></div><div class="fact"><dt>시간</dt><dd>{{ c.hours }}</dd></div><div class="fact"><dt>분야</dt><dd>{{ cat.name }}</dd></div></dl>
</div></section>
<section class="section"><div class="wrap two-col">
  <div>
    <p class="eyebrow">Overview</p><h2 class="h2">과정 개요</h2>
    <p style="margin-top:12px;max-width:65ch">{{ c.summary }}</p>
    {% if c.modules %}
    <h2 class="h2" style="margin:40px 0 16px">표준 커리큘럼</h2>
    {% set mx = c.modules|map(attribute='hours')|map('string')|list %}
    <div class="table-scroll"><table class="agenda">
      <thead><tr><th>모듈</th><th>주요 내용</th><th>시간</th></tr></thead>
      <tbody>{% for m in c.modules %}<tr><td class="mod">{{ m.name }}</td><td><ul>{% for pt in m.points %}<li>{{ pt }}</li>{% endfor %}</ul></td>
      <td class="hr">{{ m.hours or '맞춤' }}{% if hours(m.hours) %}<div class="hbar" style="width:{{ (hours(m.hours) / 4 * 100)|round|int if hours(m.hours) < 4 else 100 }}%"></div>{% endif %}</td></tr>{% endfor %}</tbody>
    </table></div>
    <p class="note-s" style="margin-top:10px">표준 제안서 요약본입니다. 시간 배분과 실습 주제는 고객사 상황에 맞춰 조정합니다.</p>
    {% endif %}
  </div>
  <aside class="side">
    {% if c.signature %}<div class="box"><h3>이 과정의 대표 사례 · 실습</h3><ul>{% for s in c.signature %}<li>{{ s }}</li>{% endfor %}</ul></div>{% endif %}
    {% set rec = HIST.recent|selectattr('program','equalto',c.slug)|rejectattr('status')|list %}
    {% set recorgs = rec|map(attribute='org')|unique|list %}
    {% if recorgs %}<div class="box"><h3>최근 강의 고객사</h3><p class="note-s">{{ recorgs[:10]|join(' · ') }}</p></div>{% endif %}
    {% set revs = REVIEWS|selectattr('program','equalto',c.slug)|list %}
    {% if revs %}<div class="box"><h3>강의 후기</h3><ul>{% for r in revs[:4] %}<li><a href="{{ root }}field/{{ r.slug }}.html">{{ r.org }}</a></li>{% endfor %}</ul></div>{% endif %}
    {% if c.records %}<div class="box"><h3>대표 강의 이력</h3><ul>{% for s in c.records %}<li>{{ s }}</li>{% endfor %}</ul></div>{% endif %}
    {% set eps = MEDIA.episodes|selectattr('program','equalto',c.slug)|list %}
    {% if eps %}<div class="box"><h3>관련 영상</h3><ul>{% for e in eps %}<li><a href="{{ root }}videos.html#{{ e.slug }}">{{ e.title }}</a></li>{% endfor %}</ul></div>{% endif %}
    <div class="box"><h3>전체 제안서가 필요하신가요?</h3><p class="note-s" style="margin-bottom:12px">회사명·대상·일정을 남겨 주시면 맞춤 제안서를 보내 드립니다.</p><a class="btn primary" href="{{ root }}contact.html?course={{ c.slug }}">제안서 요청하기</a></div>
  </aside>
</div></section>
'''

VIDEOS = r'''
<section class="page-head"><div class="wrap"><p class="crumb">강의영상</p><h1>리더의 한 장면 · 일잘러의 한 장면</h1>
<p class="lede">강의장에서 실제로 나누는 이야기를 5~7분 영상으로 옮겼습니다. 리더를 위한 '리더의 한 장면', 실무자를 위한 '일잘러의 한 장면'입니다.</p></div></section>
{% for sname, sdesc in [('리더의 한 장면','팀장·파트장 등 팀을 이끄는 리더를 위한 이야기'),('일잘러의 한 장면','기획·보고·문제해결 등 실무자를 위한 이야기')] %}
{% set eps = MEDIA.episodes | selectattr('series_name','equalto',sname) | list %}
{% if eps %}
<section class="section"><div class="wrap">
  <p class="eyebrow">{{ sdesc }}</p><h2 class="h2" style="margin-bottom:16px">{{ sname }}</h2>
  <div class="cards">
  {% for e in eps %}
    <article class="card" id="{{ e.slug }}">
      {% if e.youtube %}<div style="position:relative;padding-top:56.25%;border-radius:8px;overflow:hidden;background:#000"><iframe src="https://www.youtube-nocookie.com/embed/{{ e.youtube }}" title="{{ e.title }}" style="position:absolute;inset:0;width:100%;height:100%;border:0" allow="accelerometer; encrypted-media; gyroscope; picture-in-picture" allowfullscreen loading="lazy"></iframe></div>{% else %}<img src="{{ root }}assets/img/{{ e.thumb }}" alt="">{% endif %}
      <span class="k">{{ e.theme }}</span><h2 class="t" style="font-size:var(--fs-m)">{{ e.title }}</h2><p class="d">{{ e.desc }}</p>
      <p class="d">{% if e.youtube %}<a href="https://www.youtube.com/watch?v={{ e.youtube }}" target="_blank" rel="noopener">유튜브에서 보기</a>{% if e.shorts %} · <a href="https://www.youtube.com/shorts/{{ e.shorts }}" target="_blank" rel="noopener">쇼츠</a>{% endif %}{% else %}<span class="tag">공개 예정</span>{% endif %}
      {% if CMAP.get(e.program) %} · 관련 과정 <a href="{{ root }}programs/{{ e.program }}.html">{{ CMAP[e.program].title }}</a>{% endif %}</p>
    </article>
  {% endfor %}
  </div>
</div></section>
{% endif %}
{% endfor %}
<section class="section tint"><div class="wrap">
  <p class="eyebrow">Lecture Clips</p><h2 class="h2" style="margin-bottom:16px">강의 장면</h2>
  <ul>{% for v in MEDIA.clips %}<li>{{ v.title }} {% if v.youtube %}<a href="https://www.youtube.com/watch?v={{ v.youtube }}" target="_blank" rel="noopener">보기</a>{% else %}<span class="tag">공개 예정</span>{% endif %}</li>{% endfor %}</ul>
</div></section>
'''

FIELD = r'''
<section class="page-head"><div class="wrap"><p class="crumb">강의현장</p><h1>강의 후기</h1>
<p class="lede">과정별 강의 현장과 강의 포인트를 정리했습니다. 교안 이미지와 현장 사진은 네이버 블로그에서 볼 수 있습니다.</p></div></section>
<section class="section"><div class="wrap">
  <div class="rv-grid">
  {% for r in REVIEWS %}
    <a class="rv-card" href="{{ root }}field/{{ r.slug }}.html">
      <span class="rv-cover img"><img src="{{ root }}assets/img/rv/{{ r.slug }}.jpg" alt="{{ r.course }} 표지" loading="lazy"></span>
      <span class="rv-t">{{ r.course }}</span><span class="rv-m">{{ r.org }}{% if r.target %} · {{ r.target }}{% endif %}</span>
    </a>
  {% endfor %}
  </div>
</div></section>
'''

ORGPAGE = r'''
<section class="page-head"><div class="wrap"><p class="crumb"><a href="{{ root }}field.html">강의현장</a> / 고객사</p><h1>{{ o.name }}</h1>
<p class="lede">{{ o.name }}에서 진행한 과정과 강의 후기입니다.</p></div></section>
<section class="section"><div class="wrap">
  <div class="table-scroll"><table class="agenda hist">
    <thead><tr><th>일정</th><th>과정</th><th>대상</th><th></th></tr></thead>
    <tbody>{% for r in o.reviews %}<tr>
      <td class="hr">{{ r.date|replace('-', '.') }}</td>
      <td class="mod">{{ r.course }}</td>
      <td class="note-s">{{ r.target }}{% if r.people %} · {{ r.people }}{% endif %}</td>
      <td><a href="{{ root }}field/{{ r.slug }}.html">후기 보기 →</a></td></tr>{% endfor %}</tbody>
  </table></div>
</div></section>
'''

REVIEW = r'''
<section class="page-head"><div class="wrap"><p class="crumb"><a href="{{ root }}field.html">강의현장</a> / 강의 후기</p><h1>{{ r.title }}</h1></div></section>
<section class="section"><div class="wrap rv-wrap">
  <figure class="rv-hero"><img src="{{ root }}assets/img/rv/{{ r.slug }}.jpg" alt="{{ r.course }} 표지"></figure>
  <div class="rv-info">
    <h2 class="rv-h">강의 개요</h2>
    <dl class="rv-dl">
      <div><dt>고객사</dt><dd>{{ r.org }}</dd></div>
      <div><dt>과정</dt><dd>{{ r.course }}</dd></div>
      {% for k in ['target','people','place'] if r[k] %}<div><dt>{{ {'target':'대상','people':'인원','place':'장소'}[k] }}</dt><dd>{{ r[k] }}</dd></div>{% endfor %}
      <div><dt>일정</dt><dd>{{ r.schedule or r.date|replace('-', '.') }}</dd></div>
      {% if r.hours %}<div><dt>시간</dt><dd>{{ r.hours }}</dd></div>{% endif %}
    </dl>
    {% if r.blog %}<p class="rv-blog">강의 내용과 교안 이미지, 현장 사진은 네이버 블로그에서 볼 수 있습니다.</p>
    <a class="btn primary" href="{{ r.blog }}" target="_blank" rel="noopener">블로그에서 강의 후기 보기 →</a>
    {% else %}<p class="rv-blog">강의 내용과 교안 이미지, 현장 사진은 네이버 블로그 '강의현장'에서 볼 수 있습니다.</p>
    <a class="btn primary" href="{{ p.blog }}" target="_blank" rel="noopener">블로그 강의현장 보기 →</a>{% endif %}
  </div>
</div></section>
'''

CONTACT = r'''
<section class="page-head"><div class="wrap"><p class="crumb">교육문의</p><h1>교육 문의 · 제안서 요청</h1>
<p class="lede">아래 내용을 남겨 주시면 1~2일 안에 맞춤 커리큘럼과 제안서를 보내 드립니다.</p></div></section>
<section class="section"><div class="wrap two-col">
  <div>
    <form class="form" id="req" novalidate>
      <div><label for="f-co">회사·기관명</label><input id="f-co" name="co" autocomplete="organization" required></div>
      <div><label for="f-name">담당자 성함 · 부서</label><input id="f-name" name="name" required></div>
      <div><label for="f-mail">회신 받을 이메일</label><input id="f-mail" name="mail" type="email" autocomplete="email" required></div>
      <div><label for="f-tel">연락처</label><input id="f-tel" name="tel" type="tel" autocomplete="tel"></div>
      <div><label for="f-course">관심 과정</label><select id="f-course" name="course"><option value="">선택하세요</option>{% for c in COURSES %}<option value="{{ c.slug }}">{{ c.title }}</option>{% endfor %}<option value="etc">기타 · 맞춤 과정</option></select></div>
      <div><label for="f-target">대상 · 인원</label><input id="f-target" name="target" placeholder="예: 신임팀장 25명"></div>
      <div><label for="f-when">희망 일정 · 시간</label><input id="f-when" name="when" placeholder="예: 12월 중, 8시간"></div>
      <div><label for="f-place">장소</label><input id="f-place" name="place" placeholder="예: 본사 교육장"></div>
      <div class="full"><label for="f-msg">요청 사항</label><textarea id="f-msg" name="msg" placeholder="교육 배경, 꼭 다뤘으면 하는 내용 등을 적어 주세요."></textarea></div>
      <div class="full check"><input id="f-prop" name="prop" type="checkbox" checked><label for="f-prop" style="margin:0;font-weight:500">표준 제안서(전체본)를 함께 받겠습니다</label></div>
      <div class="full"><button class="btn primary" type="submit">문의 내용 만들기</button></div>
    </form>
    <div id="result" hidden>
      <p style="margin-top:24px;font-weight:700">아래 내용을 <span class="sel">{{ p.email }}</span> 로 보내 주세요.</p>
      <p class="note-s">메일 프로그램이 자동으로 열리지 않으면 내용을 복사해 붙여 넣으시면 됩니다.</p>
      <div class="out" id="out"></div>
      <div class="cta-row"><button class="btn primary" type="button" id="copyOut">내용 복사</button><a class="btn ghost" id="mailto" href="#">메일 프로그램으로 열기</a></div>
    </div>
  </div>
  <aside class="side">
    <div class="box contact-list">
      <h3>바로 연락하기</h3>
      <div class="row"><span>이메일 <span class="sel">{{ p.email }}</span></span><button class="copy" type="button" data-copy="{{ p.email }}">복사</button></div>
      <div class="row"><span>전화 <span class="sel">{{ p.phone }}</span></span><button class="copy" type="button" data-copy="{{ p.phone }}">복사</button></div>
      <div class="row" style="border:0;padding:0"><a href="{{ p.blog }}" target="_blank" rel="noopener">네이버 블로그 →</a></div>
    </div>
    <div class="box"><h3>제안서 안내</h3><p class="note-s">각 과정 페이지의 커리큘럼이 표준 제안서 요약본입니다. 전체 제안서(세부 커리큘럼·교안 샘플·강사 프로필)는 요청해 주시면 메일로 보내 드립니다.</p></div>
  </aside>
</div></section>
<script>
(function(){
  var f=document.getElementById('req'), names={ {% for c in COURSES %}"{{ c.slug }}":"{{ c.title }}",{% endfor %} etc:"기타 · 맞춤 과정"};
  try{var q=new URLSearchParams(location.search).get('course'); if(q&&names[q]) f.course.value=q;}catch(e){}
  f.addEventListener('submit',function(ev){
    ev.preventDefault();
    if(!f.co.value.trim()||!f.name.value.trim()||!f.mail.value.trim()){ f.reportValidity&&f.reportValidity(); return; }
    var c=names[f.course.value]||'';
    var body=['[교육 문의] '+f.co.value,'','회사·기관: '+f.co.value,'담당자: '+f.name.value,'이메일: '+f.mail.value,'연락처: '+(f.tel.value||'-'),
      '관심 과정: '+(c||'-'),'대상·인원: '+(f.target.value||'-'),'희망 일정·시간: '+(f.when.value||'-'),'장소: '+(f.place.value||'-'),
      '표준 제안서 요청: '+(f.prop.checked?'예':'아니오'),'','요청 사항:',f.msg.value||'-'].join('\n');
    document.getElementById('out').textContent=body;
    document.getElementById('mailto').href='mailto:{{ p.email }}?subject='+encodeURIComponent('[교육 문의] '+f.co.value+(c?' - '+c:''))+'&body='+encodeURIComponent(body);
    document.getElementById('result').hidden=false;
  });
  function copy(t,btn){var done=function(){var o=btn.textContent;btn.textContent='복사됨';setTimeout(function(){btn.textContent=o},1500)};
    try{navigator.clipboard.writeText(t).then(done,function(){sel(t)})}catch(e){sel(t)}}
  function sel(t){var r=document.createRange(),n=document.getElementById('out');r.selectNodeContents(n);var s=getSelection();s.removeAllRanges();s.addRange(r)}
  document.getElementById('copyOut').addEventListener('click',function(){copy(document.getElementById('out').textContent,this)});
  Array.prototype.forEach.call(document.querySelectorAll('[data-copy]'),function(b){b.addEventListener('click',function(){copy(b.getAttribute('data-copy'),b)})});
})();
</script>
'''

def build():
    global FONT_FACE
    if os.path.exists(OUT): shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copytree(os.path.join(ROOT, 'assets'), os.path.join(OUT, 'assets'))
    for _ in range(2 if PREVIEW else 1):   # 미리보기는 글자 목록을 모은 뒤 폰트를 잘라 넣기 위해 두 번 만듭니다
        PAGES.clear()
        D = '허진호 강사 · 땡큐플러스 대표. 팀장 리더십, 중간관리자 리더십, 기획력, 보고서 작성, 업무관리, 문제해결, 소통과 협업, 조직활성화 기업교육.'
        render('index.html', '허진호 강사 | 리더십 · 업무성과 기업교육', D, 'home', INDEX)
        render('profile.html', '프로필 | 허진호 강사', '허진호 강사 경력·강의 분야·대표 강의 이력. ' + D, 'profile', PROFILE)
        render('programs.html', '과정 안내 | 허진호 강사', '허진호 강사의 리더십·업무성과·소통·조직활성화 과정 안내와 표준 커리큘럼.', 'programs', PROGRAMS)
        for c in COURSES:
            render(f'programs/{c["slug"]}.html', f'{c["title"]} 교육 과정 | 허진호 강사',
                   f'{c["title"]} 교육 — {c["subtitle"]}. 대상 {c["target"]}, {c["hours"]}. {c["summary"]}', 'programs', COURSE, c=c)
        render('videos.html', '리더의 한 장면 · 일잘러의 한 장면 | 허진호 강사', '허진호 강사의 영상 시리즈 리더의 한 장면, 일잘러의 한 장면.', 'videos', VIDEOS)
        render('field.html', '강의 후기 | 허진호 강사', '허진호 강사의 기업교육 강의 후기 — 고객사별 진행 과정.', 'field', FIELD)
        for o in ORGS:
            render(f'field/{o["slug"]}.html', f'{o["name"]} 교육 | 허진호 강사', f'허진호 강사가 {o["name"]}에서 진행한 과정: ' + ', '.join(o['courses']), 'field', ORGPAGE, o=o)
        for r in REVIEWS:
            render(f'field/{r["slug"]}.html', f'{r["course"]} 교육 후기 — {r["org"]} | 허진호 강사', f'{r["org"]} {r.get("target","")} 대상 {r["course"]} 교육 후기. 허진호 강사 강의현장.', 'field', REVIEW, r=r)
        render('contact.html', '교육 문의 | 허진호 강사', '허진호 강사 강의 섭외·교육 문의·표준 제안서 요청.', 'contact', CONTACT)
        if PREVIEW and not FONT_FACE:
            FONT_FACE = make_font()
    if not PREVIEW:
        today = datetime.date.today().isoformat()
        urls = ''.join(f'<url><loc>{P["site_url"]}/{"" if p == "index.html" else p}</loc><lastmod>{today}</lastmod></url>' for p in PAGES)
        open(os.path.join(OUT, 'sitemap.xml'), 'w').write(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>')
        open(os.path.join(OUT, 'robots.txt'), 'w').write(f'User-agent: *\nAllow: /\nSitemap: {P["site_url"]}/sitemap.xml\n')
        open(os.path.join(OUT, '.nojekyll'), 'w').write('')
    print(f'{len(PAGES)} pages -> {OUT}')

def make_font():
    """미리보기 전용: 페이지에 쓰인 글자만 남긴 Pretendard를 data URI로 넣습니다."""
    from fontTools import subset
    chars = set()
    for p in PAGES:
        chars |= set(re.sub(r'<[^>]+>', '', open(os.path.join(OUT, p), encoding='utf-8').read()))
    chars |= set('복사됨0123456789')
    src = os.environ.get('PRETENDARD', '/tmp/pf/public/variable/PretendardVariable.ttf')
    opts = subset.Options(); opts.flavor = 'woff'; opts.layout_features = ['*']
    font = subset.load_font(src, opts); s = subset.Subsetter(opts); s.populate(text=''.join(chars)); s.subset(font)
    tmp = os.path.join(OUT, '_font.woff'); subset.save_font(font, tmp, opts)
    b64 = base64.b64encode(open(tmp, 'rb').read()).decode(); os.remove(tmp)
    print('font subset', len(b64) // 1024, 'KB')
    return '@font-face{font-family:"Pretendard Variable";font-weight:45 920;font-display:swap;src:url(data:font/woff;base64,%s) format("woff")}' % b64

if __name__ == '__main__':
    build()
