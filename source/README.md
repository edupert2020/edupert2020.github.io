# 허진호 강사 홈페이지

- 내용 수정: `content/` 폴더의 파일만 고칩니다.
  - `profile.yml` 프로필·경력·연락처 / `programs.yml` 과정 목록·커리큘럼
  - `history.yml` 강의 이력 (`recent`에 최근 강의 추가) / `media.yml` 리더의 한 장면·강의영상
  - `reviews/*.md` 강의현장·후기 글
- 빌드: `python3 build.py` → `docs/` 폴더가 다시 만들어지고, GitHub Pages가 `docs/`를 공개합니다.
- 깃허브 주소가 정해지면 `profile.yml`의 `site_url`을 바꾸고 다시 빌드합니다.
