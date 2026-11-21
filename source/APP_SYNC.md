# 출강 도우미 앱 → 홈페이지 강의 이력 자동 반영 절차

앱: 「출강 도우미」 artifact (slug `3dbbc693-0fd3-42e5-a953-e70960323204`), DB 컬렉션 `lectures`

1. `db_list`(slug, collection `lectures`)로 강의 기록을 모두 읽어 `[{"id":..., "data":{...}}]` 형태의 JSON 파일로 저장한다.
1-1. 민감 정보 확인 (강사 요청: 민감하다고 생각되면 반드시 먼저 물어보고 올린다)
   - 이번에 홈페이지에 새로 올라가거나 바뀔 강의(마지막 날이 지났고 공개·확정인 강의 중 아직 올라가지 않았거나 고객사·과정명·대상이 홈페이지와 다른 것)의
     고객사·과정명·대상, 그리고 올릴 후기(review.status = 게시 요청)의 제목·태그·본문을 읽는다.
   - 민감한 예: 교육생을 낮추는 내부 평가 표현(저성과자, 부진자, 징계, 재교육 대상, 구조조정·전환배치 대상 등), 개인 이름·연락처·직급이 붙은 특정인,
     건강·사고·사건, 회사 내부 문제(노사 갈등, 사고 수습 등), 강사료·예산 금액, 고객사가 공개를 원하지 않는다고 적힌 내용, 참가 회사 목록 나열.
     판단이 애매하면 민감한 것으로 본다.
   - 단, 강사가 이미 확인한 것은 다시 묻지 않는다: site.approved_sig가 '고객사|과정명|대상'과 같으면 강의는 통과,
     review.approved_at이 review.updated보다 늦으면 후기는 통과.
   - 민감한 강의·후기는 이번 실행에서 보류한다: 2단계 실행 때 `--hold <강의 id들,쉼표로>` `--hold-review <후기 id들>`를 붙인다
     (이미 홈페이지에 올라간 내용은 그대로 두고 바꾸지 않음).
   - 보류한 문서마다 db_write merge로 강의는 `{"site": {"status": "확인 필요", "question": "무엇이 왜 민감한지 + 홈페이지에 어떻게 쓰면 좋을지 제안 한 줄", "at": "YYYY-MM-DD"}}`,
     후기는 `{"review": {"check": "같은 형식의 질문 한 줄"}}`를 기록하고, 마지막 알림에 "확인 필요: …"로 적는다. 고치지 말고 묻기만 한다.
2. `python3 source/sync_app.py <그 파일> [--hold …] [--hold-review …]` 실행 → 결과 JSON 확인
   - 강의 마지막 날이 오늘 이전 + 공개(public) + 진행 상태 '확정' (가예약·제안 중·취소는 올리지 않음) → `content/history.yml`에 추가·수정
   - 앱에서 지웠거나 비공개·취소로 바꾼 강의 → 홈페이지에서 내림
3. 결과의 `unclassified`에 출강처가 있으면 `source/clients_map.py` 끝의 '출강 도우미 앱으로 새로 들어온 출강처' 아래에
   `put('<기존 업종 이름>','<출강처>')` 한 줄을 추가하고 2단계를 다시 실행한다. (업종 이름은 파일 안의 기존 put 이름 중에서 고른다)
   - 강의 후기: 앱에서 '홈페이지에 올리기'를 누른 후기(review.status = 게시 요청/게시됨)를 `content/reviews/<날짜>-app-<id>.md`로 씀.
     후기를 내리거나 강의를 지우면 그 파일도 지움 → 결과의 reviews_written·reviews_removed·review_ids
   - 후기 사진: 결과의 `photos_needed`([{id, dest}])마다 `read_asset`(slug, id, max_bytes 4194304)으로 사진을 받고,
     결과에 나온 저장 파일 경로(Image source)로 `python3 source/sync_app.py --place <그 경로> <dest> <id>` 실행.
     모두 넣은 뒤 2단계를 한 번 더 실행해 photos_needed가 비었는지 확인. (사진이 없는 후기는 남색 표지를 자동으로 만듦)
4. added·updated·removed·reviews_written·reviews_removed가 모두 비어 있고 git status에 바뀐 파일이 없으면 여기서 끝(커밋하지 않음).
5. `bash source/deploy.sh` → 빌드 결과가 저장소 최상위로 옮겨짐
6. 커밋 메시지 `강의 이력 자동 반영: <고객사 과정명, ...>` 로 커밋하고 main에 푸시
7. `published_ids`의 각 문서에 `db_write` merge로 `{"site": {"status": "반영됨", "at": "YYYY-MM-DD"}}` 기록
   (이미 같은 값이면 쓰지 않음, 문서 version을 ifVersion으로)
   `review_ids`의 각 문서 중 review.status가 '게시 요청'인 것은 merge로
   `{"review": {"status": "게시됨", "published_at": "YYYY-MM-DD", "url": "https://edupert2020.github.io/field/<파일 이름에서 .md를 뺀 것>.html"}}` 기록
   (review의 다른 필드는 그대로 둠 — merge는 중첩 객체를 합침)
8. 반영한 내용을 사용자에게 한두 줄로 알린다.

주의: 고객사명·과정명은 앱에 입력된 그대로 쓴다. 지어내지 않는다.
월별 강의 건수처럼 비수기가 드러나는 표시는 만들지 않는다(연도별·고객사별만).
