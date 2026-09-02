# 미디어gzip

- 2026-09-02 미리보기 검은화면·정지의 진짜 뿌리=GZipMiddleware가 mp4까지 압축(Content-Length 사라지고 chunked → <video>가 readyState 0). Range 요청은 206이라 gzip이 안 붙어 혼자 시험하면 멀쩡해 보였다. _NoCompressMedia로 미디어만 비켜가게 함(JSON 압축은 유지). 브라우저로 직접 재현·확인.
