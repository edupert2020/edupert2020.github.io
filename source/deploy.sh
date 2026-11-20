#!/bin/bash
# 빌드 결과(source/docs)를 저장소 최상위로 옮겨 GitHub Pages에 공개될 상태로 만듭니다.
# 사용: bash source/deploy.sh   (커밋·푸시는 따로)
set -e
cd "$(dirname "$0")"
python3 build.py
cd ..
# 최상위의 이전 빌드 결과를 지우고(저장소 관리 파일·source는 남김) 새 결과로 바꿈
find . -mindepth 1 -maxdepth 1 ! -name '.git' ! -name 'source' ! -name '.gitignore' -exec rm -rf {} +
cp -a source/docs/. .
rm -rf source/docs source/__pycache__
echo "deployed"
