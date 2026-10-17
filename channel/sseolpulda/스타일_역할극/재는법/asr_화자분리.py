import os, sys, json, subprocess, pathlib
KEY = pathlib.Path.home().joinpath(".volcano","keys","speechmatics").read_text(encoding="utf-8").strip()
from speechmatics.models import ConnectionSettings
from speechmatics.batch_client import BatchClient
out = pathlib.Path(sys.argv[1]); files = sys.argv[2:]
settings = ConnectionSettings(url="https://asr.api.speechmatics.com/v2", auth_token=KEY)
conf = {"type":"transcription","transcription_config":{"language":"ko","operating_point":"enhanced","diarization":"speaker","speaker_diarization_config":{"speaker_sensitivity":0.9}}}
with BatchClient(settings) as c:
    for f in files:
        vid = os.path.basename(f)[:11]; o = out/f"{vid}.json"
        if o.exists(): continue
        wav = out/f"{vid}.wav"
        subprocess.run(["ffmpeg","-v","error","-y","-i",f,"-ac","1","-ar","16000",str(wav)],check=True)
        job = c.submit_job(audio=str(wav), transcription_config=conf)
        r = c.wait_for_completion(job, transcription_format="json-v2")
        o.write_text(json.dumps(r,ensure_ascii=False),encoding="utf-8"); wav.unlink()
        ws=[x for x in r["results"] if x["type"]=="word"]
        print(vid, len(ws), sorted(set(x["alternatives"][0].get("speaker") for x in ws)))
