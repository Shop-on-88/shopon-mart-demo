#!/usr/bin/env bash
# 한국관광공사 사진 출처를 인증키 없이 조회할 수 있는지 점검한다.
mkdir -p tools/probe
UA="Mozilla/5.0 (jagalmadang-site)"
curl -sL -A "$UA" -o tools/probe/gallery-search.html -w "gallery %{http_code} %{url_effective}\n" "https://phoko.visitkorea.or.kr/media/mediaList.kto?keyword=%EC%B6%95%EC%84%9C%EC%82%AC"
curl -sL -A "$UA" -o tools/probe/photo-search.html -w "photo %{http_code} %{url_effective}\n" "https://photo.visitkorea.or.kr/"
curl -sL -A "$UA" -o tools/probe/tourapi.txt -w "tourapi %{http_code}\n" "https://apis.data.go.kr/B551011/PhotoGalleryService1/gallerySearchList1?MobileOS=ETC&MobileApp=test&_type=json&keyword=%EC%B6%95%EC%84%9C%EC%82%AC"
curl -sL -A "$UA" -o tools/probe/visitkorea.html -w "visitkorea %{http_code} %{url_effective}\n" "https://korean.visitkorea.or.kr/search/search_list.do?keyword=%EC%B6%95%EC%84%9C%EC%82%AC"
ls -la tools/probe
