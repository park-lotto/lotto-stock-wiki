"""강의 영상을 10분 조각으로 나눠 제미니가 화면+소리를 보고 상세 기록을 만든다.
사용: py -I lecture_gemini.py <영상.mp4> <출력폴더>   (이미 끝난 조각은 건너뜀 — 다시 돌리면 이어서)
"""
import os, sys, time, json, subprocess, glob, itertools
sys.stdout.reconfigure(encoding="utf-8")
from google import genai
from google.genai import types

ENV = r"C:\Users\TheRose\Desktop\로또의 주식\.env"
MODELS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-flash"]  # 실패할 때마다 모델도 번갈아
SEG = 600  # 10분

PROMPT = """당신은 유료 강의를 '안 본 사람이 그대로 따라 할 수 있게' 기록하는 속기사다.
이 영상은 5시간 15분 강의 중 {idx}번째 조각이며 강의 전체 기준 {start} ~ {end} 구간이다.
요약하지 마라. 빠짐없이, 길어도 된다. 모든 시각은 강의 전체 기준 [HH:MM:SS]로 적어라.

## 1. 받아쓰기
강사가 한 말을 30초~1분 단위 시각과 함께 거의 그대로 적는다(군말·반복만 덜어 낸다). 수강생 질문·답도 포함.

## 2. 화면 시연 단계
화면에서 실제로 한 조작을 순서대로: 연 사이트/프로그램 이름·주소, 누른 메뉴·버튼, 입력한 값, 결과.
1. [시각] ... 형식의 번호 목록.

## 3. 화면에 보인 원문
화면에 띄운 프롬프트·지침서·코드·설정값·숫자·파일명·URL을 보이는 그대로 옮긴다(잘려 보이면 '(잘림)').

## 4. 팁·주의점·경험담
강사가 강조한 요령, 하지 말라는 것, 실패 사례, 수익·조회수 등 숫자, 추천 도구·요금.

## 5. 캡처할 만한 장면
나중에 이미지로 남길 가치가 있는 화면의 시각과 이유(최대 8개).

해당 내용이 없는 칸은 '없음'.
"""


def keys():
    out = []
    for line in open(ENV, encoding="utf-8"):
        if line.startswith("GEMINI") and "=" in line:
            v = line.split("=", 1)[1].strip().strip('"').strip("'")
            if len(v) > 20 and v not in out:
                out.append(v)
    return out


def hms(s):
    s = int(s); return f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}"


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def main(video, outdir):
    segdir = os.path.join(outdir, "segments"); os.makedirs(segdir, exist_ok=True)
    total = duration(video)
    n = int(total // SEG) + (1 if total % SEG > 5 else 0)
    ks = keys(); print(f"길이 {hms(total)} / 조각 {n} / 키 {len(ks)}개", flush=True)
    kc = itertools.cycle(ks)
    for i in range(n):
        md = os.path.join(outdir, f"part_{i+1:02d}.md")
        if os.path.exists(md) and os.path.getsize(md) > 500:
            continue
        seg = os.path.join(segdir, f"seg_{i+1:02d}.mp4")
        if not os.path.exists(seg):
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(i*SEG), "-i", video, "-t", str(SEG),
                            "-c", "copy", seg], check=True)
        prompt = PROMPT.format(idx=i+1, start=hms(i*SEG), end=hms(min((i+1)*SEG, total)))
        done = False
        for attempt in range(len(ks) * 2):
            k = next(kc); model = MODELS[attempt % len(MODELS)]
            try:
                c = genai.Client(api_key=k, http_options=types.HttpOptions(timeout=480000))  # 8분 넘게 응답 없으면 다른 키로
                f = c.files.upload(file=seg)
                while f.state.name == "PROCESSING":
                    time.sleep(5); f = c.files.get(name=f.name)
                if f.state.name != "ACTIVE":
                    raise RuntimeError(f"파일 상태 {f.state.name}")
                r = c.models.generate_content(model=model, contents=[f, prompt],
                                              config=types.GenerateContentConfig(max_output_tokens=65536, temperature=0.2))
                text = r.text or ""
                try: c.files.delete(name=f.name)
                except Exception: pass
                if len(text) < 500:
                    raise RuntimeError(f"응답 너무 짧음 {len(text)}자")
                open(md, "w", encoding="utf-8").write(f"# 조각 {i+1} ({hms(i*SEG)}~) · {model}\n\n{text}")
                print(f"[{i+1}/{n}] 완료 {len(text)}자 ({model}, 키 …{k[-4:]})", flush=True)
                done = True; break
            except Exception as e:
                print(f"[{i+1}/{n}] 실패(키 …{k[-4:]}, {model}): {str(e)[:150]}", flush=True)
                time.sleep(3)
        if not done:
            print(f"[{i+1}/{n}] 포기 - 다시 돌리면 이어서 합니다", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
