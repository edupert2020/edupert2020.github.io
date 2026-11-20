# 출강 도우미 앱 → 홈페이지 강의 이력 자동 반영 절차

앱: 「출강 도우미」 artifact (slug `3dbbc693-0fd3-42e5-a953-e70960323204`), DB 컬렉션 `lectures`

1. `db_list`(slug, collection `lectures`)로 강의 기록을 모두 읽어 `[{"id":..., "data":{...}}]` 형태의 JSON 파일로 저장한다.
2. `python3 source/sync_app.py <그 파일>` 실행 → 결과 JSON 확인
   - 강의 마지막 날이 오늘 이전 + 공개(public) + 취소 아님 → `content/history.yml`에 추가·수정
   - 앱에서 지웠거나 비공개·취소로 바꾼 강의 → 홈페이지에서 내림
3. 결과의 `unclassified`에 출강처가 있으면 `source/clients_map.py` 끝의 '출강 도우미 앱으로 새로 들어온 출강처' 아래에
   `put('<기존 업종 이름>','<출강처>')` 한 줄을 추가하고 2단계를 다시 실행한다. (업종 이름은 파일 안의 기존 put 이름 중에서 고른다)
   - 강의 후기: 앱에서 '홈페이지에 올리기'를 누른 후기(review.status = 게시 요청/게시됨)를 `content/reviews/<날짜>-app-<id>.md`로 씀.
     후기를 내리거나 강의를 지우면 그 파일도 지움 → 결과의 reviews_written·reviews_removed·review_ids
4. added·updated·removed·reviews_written·reviews_removed가 모두 비어 있으면 여기서 끝(커밋하지 않음).
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
