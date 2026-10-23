import requests,re,urllib.parse as up
H={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36','Accept-Language':'ko-KR,ko;q=0.9','Accept':'text/html,application/xhtml+xml,*/*'}
U={
 '공식홈':'https://www.skybay.co.kr/',
 '공식홈2':'http://skybay.co.kr/',
 '아고다':'https://www.agoda.com/ko-kr/skybay-hotel-gyeongpo/hotel/gangneung-si-kr.html',
 '부킹닷컴':'https://www.booking.com/hotel/kr/skybay-gyeongpo.ko.html',
 '익스피디아':'https://www.expedia.co.kr/Gangneung-Hotels-Skybay-Hotel-Gyeongpo.h21230386.Hotel-Information',
 '호텔스닷컴':'https://kr.hotels.com/ho680372352/',
 '트립어드바이저검색':'https://www.tripadvisor.co.kr/Search?q=%EC%8A%A4%EC%B9%B4%EC%9D%B4%EB%B2%A0%EC%9D%B4%20%EA%B2%BD%ED%8F%AC',
 '마이리얼트립검색':'https://www.myrealtrip.com/accommodations/search?keyword=%EC%8A%A4%EC%B9%B4%EC%9D%B4%EB%B2%A0%EC%9D%B4',
 '야놀자검색':'https://nol.yanolja.com/search?keyword=%EC%8A%A4%EC%B9%B4%EC%9D%B4%EB%B2%A0%EC%9D%B4%20%EA%B2%BD%ED%8F%AC',
 '네이버검색':'https://search.naver.com/search.naver?query=%EC%8A%A4%EC%B9%B4%EC%9D%B4%EB%B2%A0%EC%9D%B4%EA%B2%BD%ED%8F%AC',
 '구글이미지':'https://www.google.com/search?q=skybay+gyeongpo&tbm=isch',
 '빙이미지':'https://www.bing.com/images/search?q=%EC%8A%A4%EC%B9%B4%EC%9D%B4%EB%B2%A0%EC%9D%B4+%EA%B2%BD%ED%8F%AC',
 '인스타태그':'https://www.instagram.com/explore/tags/%EC%8A%A4%EC%B9%B4%EC%9D%B4%EB%B2%A0%EC%9D%B4%EA%B2%BD%ED%8F%AC/',
}
for k,u in U.items():
    try:
        r=requests.get(u,headers=H,timeout=20,allow_redirects=True); t=r.text
        imgs=set(re.findall(r'https?://[^"\'\s\)<>]+?\.(?:jpg|jpeg|webp|png)',t))
        print(f'{k:10s} {r.status_code} 최종:{r.url[:70]} 글자{len(t)} 그림주소{len(imgs)}')
    except Exception as e: print(k,'실패',str(e)[:80])
