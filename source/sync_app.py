#!/usr/bin/env python3
"""출강 도우미 앱의 강의 기록을 history.yml에 반영합니다.

  python3 sync_app.py lectures.json [--today YYYY-MM-DD]

lectures.json: 앱 DB 'lectures' 컬렉션을 [{id, data}, ...] 형태로 내려받은 것.
- 강의 날짜(종료일)가 오늘 이전이고, 공개(public)이며, 취소되지 않은 강의만 반영합니다.
- 같은 강의는 app_id로 찾아 고칩니다(수정·삭제·비공개 전환도 반영).
- 반영 결과를 JSON으로 출력합니다: {"added": [...], "updated": [...], "removed": [...], "published_ids": [...]}
"""
import json, os, re, sys, datetime, yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(ROOT, 'content', 'history.yml')

# 과정명 → 홈페이지 프로그램 slug (앞에서부터 먼저 맞는 것)
PROGRAM_KEYS = [
    ('AI', '리더', 'ai-leadership'),
    ('AI', None, 'ai-planning'),
    ('기획보고서', None, 'planning-report'),
    ('보고서', None, 'planning-report'),
    ('기안', None, 'official-document'),
    ('공문서', None, 'official-document'),
    ('기획', None, 'planning'),
    ('업무관리', None, 'work-management'),
    ('스마트', None, 'work-management'),
    ('시간관리', None, 'work-management'),
    ('문제해결', None, 'problem-solving'),
    ('소통', None, 'communication-collaboration'),
    ('협업', None, 'communication-collaboration'),
    ('팀장', None, 'team-leader-leadership'),
    ('중간관리자', None, 'bridge-leadership'),
    ('브릿지', None, 'bridge-leadership'),
    ('조직활성화', None, 'org-activation'),
    ('변화관리', None, 'org-activation'),
    ('사내강사', None, 'in-house-instructor'),
    ('강사양성', None, 'in-house-instructor'),
]


def guess_program(course):
    c = str(course or '')
    for a, b, slug in PROGRAM_KEYS:
        if a in c and (b is None or b in c):
            return slug
    return ''


def to_entry(lid, d):
    target = ' '.join(x for x in [str(d.get('target') or '').strip(),
                                  (f"{d['people']}명" if d.get('people') else '')] if x)
    return {
        'date': str(d.get('date')),
        'org': str(d.get('org') or '').strip(),
        'course': str(d.get('course') or '').strip(),
        'target': target,
        'sessions': int(d.get('sessions') or 1),
        'program': d.get('program') or guess_program(d.get('course')),
        'status': '',
        'confirm': False,
        'app_id': lid,
    }


def main():
    src = sys.argv[1]
    today = datetime.date.today().isoformat()
    if '--today' in sys.argv:
        today = sys.argv[sys.argv.index('--today') + 1]
    rows = json.load(open(src, encoding='utf-8'))
    hist = yaml.safe_load(open(HIST, encoding='utf-8'))
    recent = hist.get('recent') or []
    by_id = {h.get('app_id'): h for h in recent if h.get('app_id')}
    out = {'added': [], 'updated': [], 'removed': [], 'published_ids': []}
    seen = set()

    for r in rows:
        lid, d = r['id'], r['data']
        end = str(d.get('end_date') or d.get('date') or '')
        ok = (d.get('org') and d.get('course') and end and end < today
              and d.get('public', True) and d.get('state') != '취소')
        if not ok:
            continue
        seen.add(lid)
        e = to_entry(lid, d)
        if lid in by_id:
            h = by_id[lid]
            if any(h.get(k) != v for k, v in e.items()):
                h.update(e); out['updated'].append(f"{e['date']} {e['org']} {e['course']}")
        else:
            # 앱 도입 전에 손으로 넣어 둔 같은 강의(날짜·기관 같음)가 있으면 그것을 이어받음
            twin = next((h for h in recent if not h.get('app_id') and str(h.get('date')) == e['date']
                         and str(h.get('org')).strip() == e['org']), None)
            if twin:
                twin.update(e); out['updated'].append(f"{e['date']} {e['org']} {e['course']}")
            else:
                recent.append(e); out['added'].append(f"{e['date']} {e['org']} {e['course']}")
        out['published_ids'].append(lid)

    # 앱에서 지웠거나 비공개·취소로 바꾼 강의는 홈페이지에서도 내림
    alive = {r['id'] for r in rows}
    keep = []
    for h in recent:
        aid = h.get('app_id')
        if aid and (aid not in alive or aid not in seen):
            out['removed'].append(f"{h['date']} {h['org']} {h['course']}")
            continue
        keep.append(h)
    keep.sort(key=lambda h: str(h.get('date')), reverse=True)
    # 업종 분류표(clients_map.py)에 없는 출강처 → '주요 출강처' 표에 안 나오므로 알려 줌
    sys.path.insert(0, ROOT)
    from clients_map import ALIAS, S, EXCLUDE
    norm = lambda o: re.sub(r'\s+', ' ', re.sub(r'^\(주\)|\(주\)$|㈜|주식회사', '', str(o))).strip()
    out['unclassified'] = sorted({ALIAS.get(norm(h['org']), norm(h['org'])) for h in keep if h.get('app_id')}
                                 - set(S) - set(EXCLUDE))
    hist['recent'] = keep
    with open(HIST, 'w', encoding='utf-8') as f:
        yaml.safe_dump(hist, f, allow_unicode=True, sort_keys=False)
    sync_reviews(rows, out)
    print(json.dumps(out, ensure_ascii=False))


def review_path(lid, d):
    safe = re.sub(r'[^A-Za-z0-9-]', '', lid)[-12:] or 'x'
    return os.path.join(ROOT, 'content', 'reviews', f"{d.get('date')}-app-{safe}.md")


def sync_reviews(rows, out):
    """앱에서 '홈페이지에 올리기'를 누른 강의 후기를 content/reviews/ 에 씀.
    review.status: 초안 | 게시 요청 | 게시됨  (게시 요청·게시됨이면 파일을 최신 내용으로 유지, 그 밖이면 내림)"""
    out.update({'reviews_written': [], 'reviews_removed': [], 'review_ids': []})
    rdir = os.path.join(ROOT, 'content', 'reviews')
    want = {}
    for r in rows:
        lid, d = r['id'], r['data']
        rv = d.get('review') or {}
        if rv.get('status') in ('게시 요청', '게시됨') and rv.get('body') and d.get('public', True) and d.get('state') != '취소':
            want[lid] = (d, rv)
    # 앱에서 내린 후기 파일 삭제 (app_id로 찾음)
    for f in os.listdir(rdir):
        if '-app-' not in f:
            continue
        fp = os.path.join(rdir, f)
        m = re.match(r'^---\n(.*?)\n---\n', open(fp, encoding='utf-8').read(), re.S)
        aid = (yaml.safe_load(m.group(1)) or {}).get('app_id') if m else None
        if aid not in want or fp != review_path(aid, want[aid][0]):
            os.remove(fp); out['reviews_removed'].append(f)
    for lid, (d, rv) in want.items():
        days = '' if not d.get('end_date') or d['end_date'] == d['date'] else '~' + '.'.join(str(int(x)) for x in d['end_date'].split('-')[1:]) + '.'
        meta = {
            'title': rv.get('title') or f"{d['course']} — {d['org']}",
            'date': str(d['date']), 'org': d['org'], 'course': d['course'],
            'target': d.get('target') or '', 'people': f"{d['people']}명" if d.get('people') else '',
            'hours': rv.get('hours') or '', 'place': d.get('venue') or '',
            'schedule': '.'.join(str(int(x)) for x in str(d['date']).split('-')) + '.' + days,
            'program': d.get('program') or guess_program(d.get('course')),
            'tags': [t for t in (rv.get('tags') or []) if t], 'photo': '', 'src': '', 'blog': rv.get('blog') or '',
            'app_id': lid,
        }
        text = '---\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + '---\n' + rv['body'].strip() + '\n'
        fp = review_path(lid, d)
        old = open(fp, encoding='utf-8').read() if os.path.exists(fp) else None
        if old != text:
            open(fp, 'w', encoding='utf-8').write(text); out['reviews_written'].append(os.path.basename(fp))
        out['review_ids'].append(lid)


if __name__ == '__main__':
    main()
