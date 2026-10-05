"""감정짤 밈팩 — 특별 묶음 두 개: (A) 페페 리액션 짤, (B) 누구나 아는 유명 리액션 밈(해외·국내).

    py tools/meme_pack/pepe_memes.py <작업폴더>            # 아래 두 표(PEPE·MEMES)에 적힌 것을 받는다. 이미 받은 것은 건너뛴다
    py tools/meme_pack/pepe_memes.py <작업폴더> --check    # 받지 않고 전수 검사(파일·ffprobe·길이·높이·움직임)
    py tools/meme_pack/pepe_memes.py <작업폴더> --sheets <폴더>   # 눈으로 볼 대조표(짤마다 처음·중간·끝 3장 + id·감정·제목)

결과: raw/pp_<id>.mp4 · raw/fm_<id>.mp4 + sheets/thumbs/<id>.jpg + extra_pepe.json("group":"페페") · extra_memes.json("group":"유명밈")

이 두 묶음은 검색어로 긁지 않는다 — 사람이(=대조표를 눈으로 보고) 고른 목록이 이 파일의 표 두 개다.
  PEPE  : Tenor 검색 결과 960개(검색어 73개)의 미리보기를 보고 고른 것. 스티커(투명 배경)는 흰 바탕에 얹어 굽는다.
  MEMES : 밈 이름 → 유튜브 원본/템플릿 영상에서 그 순간만 자른 것(없으면 Tenor mp4).
감정 목록의 주인은 search.py(EMOTIONS). Tenor 받기·판독은 tenor.py 함수를 그대로 쓴다(여기서 다시 적지 않는다).
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from search import EMOTIONS  # noqa: E402
from tenor import Blocked, get, probe, save, to_mp4  # noqa: E402

MIN_SEC, MAX_SEC, MIN_H = 1.0, 4.0, 200
LOOP_TO = 1.5        # 이보다 짧은 반복 짤(이모트)은 이 길이가 될 때까지 되풀이해 굽는다
CUT_TO = 3.0         # 4초 넘는 Tenor 짤은 앞에서 이만큼만 쓴다
MAX_DOWNLOADS = 600  # 한 번 실행에서 받는 파일 상한
STATIC_BELOW = 0.35  # 처음·중간·끝 프레임 차이(0~255 평균)가 이보다 작으면 정지 그림으로 본다

# (Tenor id, 감정, 스티커인가, 원본 주소, 받을 파일 주소)
PEPE = [
    ("27351069", "충격_입막", False, "https://tenor.com/view/peppo-gif-27351069",
     "https://media.tenor.com/sdlBnBGM1JAAAAPo/peppo.mp4"),
    ("15138438759410822982", "놀람", False, "https://tenor.com/view/pepe-the-frog-pepe-the-frog-nervous-shocked-gif-15138438759410822982",
     "https://media.tenor.com/0haJ2ESv70YAAAPo/pepe-the-frog.mp4"),
    ("12187647", "놀람", False, "https://tenor.com/view/poggers-pepe-gif-12187647",
     "https://media.tenor.com/bCWhbbjF8dwAAAPo/poggers-pepe.mp4"),
    ("19748313", "놀람", False, "https://tenor.com/view/twitch-creepy-monkaw-scared-gif-19748313",
     "https://media.tenor.com/5xlMhNAKu0oAAAPo/twitch-creepy.mp4"),
    ("26415224", "감탄_박수", False, "https://tenor.com/view/peepo-clap-gif-26415224",
     "https://media.tenor.com/2kUVEuO_VDkAAAPo/peepo-clap.mp4"),
    ("18531858", "기쁨_환호", False, "https://tenor.com/view/heydoubleu-studytogether-widepeepohappy-peepo-peepohappy-gif-18531858",
     "https://media.tenor.com/aXDs7_QLg98AAAPo/heydoubleu-studytogether.mp4"),
    ("22663665", "의심_황당", False, "https://tenor.com/view/pepe-peppo-gif-22663665",
     "https://media.tenor.com/WP4DYQAMkGYAAAPo/pepe-peppo.mp4"),
    ("27351072", "의심_황당", False, "https://tenor.com/view/peppo-gif-27351072",
     "https://media.tenor.com/Ci-CrNQGHpMAAAPo/peppo.mp4"),
    ("3507915379102834193", "충격_입막", False, "https://tenor.com/view/pepe-meme-wtf-wide-eyes-pepe-wtf-gif-3507915379102834193",
     "https://media.tenor.com/MK6ec5mN3hEAAAPo/pepe-meme.mp4"),
    ("17897173", "의심_황당", False, "https://tenor.com/view/pepe-hmm-pepe-the-frog-thinking-thoughts-gif-17897173",
     "https://media.tenor.com/IFgA1-FJI-YAAAPo/pepe-hmm.mp4"),
    ("3268828820814354684", "의심_황당", False, "https://tenor.com/view/reaction-meme-mood-awkward-hmm-gif-3268828820814354684",
     "https://media.tenor.com/LV02flgy2PwAAAPo/reaction-meme.mp4"),
    ("16391170", "끄덕_엄지", False, "https://tenor.com/view/uh-huh-yeah-yes-nod-pepe-the-frog-gif-16391170",
     "https://media.tenor.com/noNJGfVkHQUAAAPo/uh-huh-yeah.mp4"),
    ("16222429104977342189", "의심_황당", False, "https://tenor.com/view/reaction-meme-thinking-hmm-pepe-gif-16222429104977342189",
     "https://media.tenor.com/4SGlUiQh7u0AAAPo/reaction-meme.mp4"),
    ("9448555367471134656", "의심_황당", False, "https://tenor.com/view/thinking-pepe-think-pepe-the-frog-wojak-gif-9448555367471134656",
     "https://media.tenor.com/gyADC866N8AAAAPo/thinking-pepe.mp4"),
    ("3165979566685939361", "의심_황당", False, "https://tenor.com/view/sus-gif-3165979566685939361",
     "https://media.tenor.com/K-_RpE515qEAAAPo/sus.mp4"),
    ("13814247531370496419", "의심_황당", False, "https://tenor.com/view/thinking-pepe-think-pepe-the-frog-wojak-gif-13814247531370496419",
     "https://media.tenor.com/v7YQ8FKnwaMAAAPo/thinking-pepe.mp4"),
    ("14629696721899528776", "의심_황당", False, "https://tenor.com/view/pepe-smart-pepe-watch-think-pepe-you-smart-smart-watch-gif-14629696721899528776",
     "https://media.tenor.com/ywcfqDiEokgAAAPo/pepe-smart-pepe-watch.mp4"),
    ("4926111172958360518", "의심_황당", False, "https://tenor.com/view/reaction-meme-sleepy-bored-hmm-gif-4926111172958360518",
     "https://media.tenor.com/RF0QAxxEE8YAAAPo/reaction-meme.mp4"),
    ("13961898", "의심_황당", True, "https://tenor.com/view/pepe-kek-smirk-thinking-smile-gif-13961898",
     "https://media.tenor.com/kYy-nNXgmvkAAAAi/pepe-kek.gif"),
    ("17835791564975014794", "의심_황당", True, "https://tenor.com/view/hi-gif-17835791564975014794",
     "https://media.tenor.com/94V17iY-g4oAAAAi/hi.gif"),
    ("18565502", "의심_황당", True, "https://tenor.com/view/pepe-tea-arthas-%D0%BF%D0%B0%D0%BF%D0%B8%D1%87-%D1%81%D1%82%D0%B8%D0%BA%D0%B5%D1%80-gif-18565502",
     "https://media.tenor.com/2NRtE9OCeKUAAAAi/pepe-tea.gif"),
    ("16179668", "공포_움찔", False, "https://tenor.com/view/pepe-run-pepe-run-meme-frog-gif-16179668",
     "https://media.tenor.com/pOTyZ1XqqhIAAAPo/pepe-run-pepe.mp4"),
    ("22147341", "기쁨_환호", False, "https://tenor.com/view/ugryy-gif-22147341",
     "https://media.tenor.com/F1gCDOtCZIUAAAPo/ugryy.mp4"),
    ("16082868", "기쁨_환호", True, "https://tenor.com/view/pepe-the-frog-dancing-dancing-pepe-frog-moves-gif-16082868",
     "https://media.tenor.com/3kPGZrOLeiUAAAAi/pepe-the-frog-dancing.gif"),
    ("15714466844655423724", "기쁨_환호", True, "https://tenor.com/view/pepe-breakdance-gif-15714466844655423724",
     "https://media.tenor.com/2hUAVh5XEOwAAAAi/pepe-breakdance.gif"),
    ("20219576", "기쁨_환호", False, "https://tenor.com/view/clap-pepe-clap-clap-pepe-happy-pepe-pepe-happy-gif-20219576",
     "https://media.tenor.com/bIpDrwCobToAAAPo/clap-pepe-clap.mp4"),
    ("15697848", "기쁨_환호", True, "https://tenor.com/view/pepe-the-frog-dance-happy-dancing-transparent-gif-15697848",
     "https://media.tenor.com/B0BbyOHgHt4AAAAi/pepe-the-frog-dance.gif"),
    ("21019704", "기쁨_환호", True, "https://tenor.com/view/birthday-gif-21019704",
     "https://media.tenor.com/38zNlJsBFdYAAAAi/birthday.gif"),
    ("16761834542196815081", "기쁨_환호", False, "https://tenor.com/view/feels-good-man-feels-bad-man-feels-good-beniceman-be-nice-man-gif-16761834542196815081",
     "https://media.tenor.com/6J3_tUeDdOkAAAPo/feels-good-man-feels-bad-man.mp4"),
    ("1574278922215901624", "기쁨_환호", True, "https://tenor.com/view/pepe-rave-rave-pepe-pepe-dj-rave-dj-pepe-pepe-rave-dj-gif-1574278922215901624",
     "https://media.tenor.com/Fdj2VsAQSbgAAAAi/pepe-rave-rave-pepe.gif"),
    ("25802359", "감탄_박수", False, "https://tenor.com/view/pepe-proud-clap-gif-25802359",
     "https://media.tenor.com/Vj3Wqtb17ewAAAPo/pepe-proud-clap.mp4"),
    ("20345482", "감탄_박수", False, "https://tenor.com/view/feelsstrongman-motivating-happy-pepe-clap-gif-20345482",
     "https://media.tenor.com/N9m2r1E0sAMAAAPo/feelsstrongman-motivating.mp4"),
    ("16275904", "의심_황당", False, "https://tenor.com/view/pepe-clown-nose-pepe-the-frog-gif-16275904",
     "https://media.tenor.com/-bnpTFlQLKwAAAPo/pepe-clown.mp4"),
    ("25532712", "감탄_박수", True, "https://tenor.com/view/pepe-clap-gif-25532712",
     "https://media.tenor.com/PBr8LnIl59sAAAAi/pepe-clap.gif"),
    ("17819896437701153134", "웃음", False, "https://tenor.com/view/l-loser-pepe-pepe-the-frog-funny-gif-17819896437701153134",
     "https://media.tenor.com/90z9ZW9tEW4AAAPo/l-loser.mp4"),
    ("18166861", "웃음", True, "https://tenor.com/view/pepe-laughing-pepe-braces-pepe-crying-laughing-pepe-braces-crying-braces-pepe-gif-18166861",
     "https://media.tenor.com/ycLuQYbXL3gAAAAi/pepe-laughing-pepe-braces.gif"),
    ("26415225", "웃음", False, "https://tenor.com/view/peepo-giggle-gif-26415225",
     "https://media.tenor.com/VmAGGi_DdNYAAAPo/peepo-giggle.mp4"),
    ("22663667", "웃음", False, "https://tenor.com/view/pepe-peppo-lul-lol-gif-22663667",
     "https://media.tenor.com/9-52JAMIBQ4AAAPo/pepe-peppo.mp4"),
    ("18166841", "웃음", True, "https://tenor.com/view/pepe-laughing-laughing-pepe-pepe-crying-smiling-pepe-gif-18166841",
     "https://media.tenor.com/xipRYbPe6z8AAAAi/pepe-laughing-laughing-pepe.gif"),
    ("25444442", "웃음", False, "https://tenor.com/view/league-of-legends-lol-meme-pepe-gif-25444442",
     "https://media.tenor.com/pxzOB-4LIoAAAAPo/league-of-legends-lol.mp4"),
    ("6649488909184659110", "웃음", False, "https://tenor.com/view/pepe-laugh-funny-fun-funny-meme-gif-6649488909184659110",
     "https://media.tenor.com/XEe67rHZ7qYAAAPo/pepe-laugh.mp4"),
    ("9959624024171861027", "슬픔", True, "https://tenor.com/view/icon-60-gif-9959624024171861027",
     "https://media.tenor.com/ijexSBk11CMAAAAi/icon-60.gif"),
    ("13668806469495645945", "슬픔", False, "https://tenor.com/view/pepocry-pepe-pepe-the-frog-frog-cry-gif-13668806469495645945",
     "https://media.tenor.com/vbFbEEXZZvkAAAPo/pepocry-pepe.mp4"),
    ("22663734", "슬픔", False, "https://tenor.com/view/pepe-peppo-cry-gif-22663734",
     "https://media.tenor.com/gWs0s8QlsUgAAAPo/pepe-peppo.mp4"),
    ("14676092036832202948", "슬픔", True, "https://tenor.com/view/apu-apustaja-apu-apuapustaja-aputheworld-cute-gif-14676092036832202948",
     "https://media.tenor.com/y6vz80JSkMQAAAAi/apu-apustaja-apu.gif"),
    ("14666131635069271566", "슬픔", True, "https://tenor.com/view/pepe-gif-14666131635069271566",
     "https://media.tenor.com/y4iRBIFsPg4AAAAi/pepe.gif"),
    ("17607942", "슬픔", False, "https://tenor.com/view/pepe-cry-reading-pepe-the-frog-sad-gif-17607942",
     "https://media.tenor.com/Z2TdtasP_b0AAAPo/pepe-cry.mp4"),
    ("5069069", "슬픔", False, "https://tenor.com/view/feelsbadman-sadfrog-sad-cry-gif-5069069",
     "https://media.tenor.com/ccxrVfhNZcQAAAPo/feelsbadman-sadfrog.mp4"),
    ("19334433", "슬픔", False, "https://tenor.com/view/sad-gif-19334433",
     "https://media.tenor.com/vpKeL84c0AMAAAPo/sad.mp4"),
    ("4330591812078580489", "슬픔", False, "https://tenor.com/view/pepe-pepe-the-frog-pepe-sad-pepe-sadge-sadge-gif-4330591812078580489",
     "https://media.tenor.com/PBlaTwIoswkAAAPo/pepe-pepe-the-frog.mp4"),
    ("8493382194019209370", "슬픔", False, "https://tenor.com/view/pepe-gif-8493382194019209370",
     "https://media.tenor.com/dd6OGwgkkJoAAAPo/pepe.mp4"),
    ("26415215", "분노_짜증", False, "https://tenor.com/view/peepo-leave-gif-26415215",
     "https://media.tenor.com/w8VnsGC6qjUAAAPo/peepo-leave.mp4"),
    ("18421495", "분노_짜증", False, "https://tenor.com/view/reee-pepe-frog-angry-angery-gif-18421495",
     "https://media.tenor.com/_5NXbSz-xmgAAAPo/reee-pepe.mp4"),
    ("2368929984662384246", "분노_짜증", True, "https://tenor.com/view/pepe-box-fight-meme-angry-gif-2368929984662384246",
     "https://media.tenor.com/IOAhRRmSrnYAAAAi/pepe-box.gif"),
    ("5040879497295822046", "분노_짜증", False, "https://tenor.com/view/pepe-angry-dancing-pepe-angry-dancing-pepe-the-frog-gif-5040879497295822046",
     "https://media.tenor.com/RfTNMe_d_N4AAAPo/pepe-angry-dancing-pepe.mp4"),
    ("21562981", "거절_절레", False, "https://tenor.com/view/peepo-leave-leaving-pepe-peepo-frog-gif-21562981",
     "https://media.tenor.com/oLZPOi9Ew_kAAAPo/peepo-leave-leaving.mp4"),
    ("15154684", "당황_멘붕", False, "https://tenor.com/view/pepe-nervous-sweating-concerned-monkas-gif-15154684",
     "https://media.tenor.com/GmU85epf9D4AAAPo/pepe-nervous.mp4"),
    ("27351067", "당황_멘붕", False, "https://tenor.com/view/peppo-gif-27351067",
     "https://media.tenor.com/TayovEvaMFcAAAPo/peppo.mp4"),
    ("17384186", "당황_멘붕", False, "https://tenor.com/view/the-what-pepe-what-pepe-regret-ow-shit-oh-shit-gif-17384186",
     "https://media.tenor.com/1-utuRCvsvwAAAPo/the-what-pepe-what.mp4"),
    ("4474425", "슬픔", False, "https://tenor.com/view/pepe-sad-excited-disappointed-gif-4474425",
     "https://media.tenor.com/lu14yQNc5JMAAAPo/pepe-sad.mp4"),
    ("23978425", "당황_멘붕", False, "https://tenor.com/view/pepe-w-pepe-gif-23978425",
     "https://media.tenor.com/1HGEl8EyNUMAAAPo/pepe-w-pepe.mp4"),
    ("18862714", "거절_절레", False, "https://tenor.com/view/nope-twitch-gif-18862714",
     "https://media.tenor.com/bCgL4m3QlrEAAAPo/nope-twitch.mp4"),
    ("18792449", "당황_멘붕", False, "https://tenor.com/view/pepe-made-by-marble-awkward-smile-frog-meme-gif-18792449",
     "https://media.tenor.com/2H_QAOhJq60AAAPo/pepe-made-by-marble.mp4"),
    ("25215093", "공포_움찔", False, "https://tenor.com/view/pepe-cave-gif-25215093",
     "https://media.tenor.com/FkyAnJHMAYQAAAPo/pepe-cave.mp4"),
    ("22661284", "공포_움찔", False, "https://tenor.com/view/pepe-hiding-behind-wall-looking-over-wall-monk-w-ape-gang-gif-22661284",
     "https://media.tenor.com/UGM-k223SHEAAAPo/pepe-hiding-behind-wall.mp4"),
    ("5649994013283572886", "공포_움찔", False, "https://tenor.com/view/pepe-hidden-gm-pepe-gm-dumpster-pepe-naveer-sleeps-gm-hidden-hero-pepe-gif-5649994013283572886",
     "https://media.tenor.com/TmjPnsDZ3JYAAAPo/pepe-hidden-gm-pepe-gm-dumpster.mp4"),
    ("22663592", "공포_움찔", False, "https://tenor.com/view/peppo-pepe-gif-22663592",
     "https://media.tenor.com/tewSV2c7CUwAAAPo/peppo-pepe.mp4"),
    ("9655424992603585807", "공포_움찔", False, "https://tenor.com/view/clap-frog-meme-callhimclapped-pepe-the-frog-pepe-scared-gif-9655424992603585807",
     "https://media.tenor.com/hf7138eQvQ8AAAPo/clap-frog-meme.mp4"),
    ("160520238185526405", "공포_움찔", False, "https://tenor.com/view/newspaper-pepe-pepe-newspaper-pepe-pepe-hide-pepe-hide-newspaper-gif-160520238185526405",
     "https://media.tenor.com/AjpITmBPNIUAAAPo/newspaper-pepe-pepe-newspaper.mp4"),
    ("24418434", "공포_움찔", False, "https://tenor.com/view/monka-walk-away-monka-pepe-monka-s-monka-w-gif-24418434",
     "https://media.tenor.com/6pS6W91lRMAAAAPo/monka-walk-away-monka.mp4"),
    ("26415158", "거절_절레", False, "https://tenor.com/view/nopers-gif-26415158",
     "https://media.tenor.com/6wUCmNhxVzMAAAPo/nopers.mp4"),
    ("5088603", "끄덕_엄지", False, "https://tenor.com/view/yes-pepe-headnod-awesome-gif-5088603",
     "https://media.tenor.com/UG2hJNnwEeQAAAPo/yes-pepe.mp4"),
    ("18542513", "거절_절레", False, "https://tenor.com/view/frog-no-gif-18542513",
     "https://media.tenor.com/Od0cEtNiazsAAAPo/frog-no.mp4"),
    ("18394025", "거절_절레", False, "https://tenor.com/view/no-gif-18394025",
     "https://media.tenor.com/3ZFGhiSOONcAAAPo/no.mp4"),
    ("5925275", "끄덕_엄지", False, "https://tenor.com/view/pepe-nodding-pepe-the-frog-mmhm-pepea-gif-5925275",
     "https://media.tenor.com/4A5Tdhavg00AAAPo/pepe-nodding.mp4"),
    ("22458426", "끄덕_엄지", False, "https://tenor.com/view/ok-hand-pepe-ok-frog-pepe-the-frog-gif-22458426",
     "https://media.tenor.com/rCY3koHdiTwAAAPo/ok-hand-pepe.mp4"),
    ("947377454825282965", "웃음", True, "https://tenor.com/view/pepe-gif-947377454825282965",
     "https://media.tenor.com/DSXCxpcTHZUAAAAi/pepe.gif"),
    ("18805786", "끄덕_엄지", False, "https://tenor.com/view/pepe-wink-pepe-wink-gif-18805786",
     "https://media.tenor.com/W5Or9vSpgCAAAAPo/pepe-wink-pepe.mp4"),
    ("6068975347591079642", "끄덕_엄지", False, "https://tenor.com/view/meme-pepe-okay-ok-gif-6068975347591079642",
     "https://media.tenor.com/VDlU7H_E5toAAAPo/meme-pepe.mp4"),
    ("4883573", "놀람", False, "https://tenor.com/view/disappointed-pepe-frog-face-sad-gif-4883573",
     "https://media.tenor.com/g81KEK72a40AAAPo/disappointed-pepe.mp4"),
    ("13628086", "놀람", True, "https://tenor.com/view/coggers-shocked-pepe-spinning-happy-gif-13628086",
     "https://media.tenor.com/ma3mPGK_CdgAAAAi/coggers-shocked.gif"),
    ("10374658", "놀람", False, "https://tenor.com/view/pepe-gif-10374658",
     "https://media.tenor.com/FrA1cgH_I64AAAPo/pepe.mp4"),
    ("21813748", "놀람", False, "https://tenor.com/view/pog-pogchamp-pog-meme-thats-kinda-of-pog-gif-21813748",
     "https://media.tenor.com/Vbu3fKcwCGEAAAPo/pog-pogchamp.mp4"),
    ("3837207864234215889", "놀람", False, "https://tenor.com/view/meme-danker-meme-gif-3837207864234215889",
     "https://media.tenor.com/NUCAON0ECdEAAAPo/meme-danker-meme.mp4"),
    ("22663663", "충격_입막", False, "https://tenor.com/view/pepe-peppo-wow-gif-22663663",
     "https://media.tenor.com/1LYjAeHKULgAAAPo/pepe-peppo.mp4"),
    ("22663763", "의심_황당", False, "https://tenor.com/view/peppo-pepe-what-gif-22663763",
     "https://media.tenor.com/cpW-WuyjK_UAAAPo/peppo-pepe.mp4"),
    ("26220999", "분노_짜증", True, "https://tenor.com/view/pepe-angry-gif-26220999",
     "https://media.tenor.com/XUo11ho4uW8AAAAi/pepe-angry.gif"),
    ("22906311", "분노_짜증", False, "https://tenor.com/view/pepe-fire-riot-gif-22906311",
     "https://media.tenor.com/soFxGomZD_IAAAPo/pepe-fire-riot.mp4"),
    ("17124539", "분노_짜증", False, "https://tenor.com/view/%EC%BB%A4%ED%97%8C-punch-fast-beat-up-pepe-the-frog-gif-17124539",
     "https://media.tenor.com/y2z_8z2kxOkAAAPo/%EC%BB%A4%ED%97%8C-punch.mp4"),
    ("27516870", "분노_짜증", False, "https://tenor.com/view/peepo-min-yoongi-kim-taehyung-peepo-taegi-taegi-punch-gif-27516870",
     "https://media.tenor.com/nLjc9eJRY6EAAAPo/peepo-min-yoongi.mp4"),
    ("1902565290434953079", "감탄_박수", False, "https://tenor.com/view/pepe-pepe-wink-pepe-whale-lfg-stonks-gif-1902565290434953079",
     "https://media.tenor.com/GmdFDSpc_3cAAAPo/pepe-pepe-wink.mp4"),
    ("22663553", "분노_짜증", False, "https://tenor.com/view/pepe-peppo-gif-22663553",
     "https://media.tenor.com/gHj7eK_CabMAAAPo/pepe-peppo.mp4"),
    ("22663764", "거절_절레", False, "https://tenor.com/view/peppo-pepe-facepalm-face-gif-22663764",
     "https://media.tenor.com/-6KcxwabLyUAAAPo/peppo-pepe.mp4"),
    ("26084361", "분노_짜증", False, "https://tenor.com/view/valorant-pepe-riot-micad-valorancik-gif-26084361",
     "https://media.tenor.com/bptB2i_zDVEAAAPo/valorant-pepe.mp4"),
]

# (id, 밈 이름, 감정, 설명, 출처)
#   출처 = ("yt", 유튜브 id, 시작 초, 길이 초[, crop 필터])  또는  ("tenor", 보기 주소, 파일 주소[, 시작 초, 길이 초])
MEMES = [

]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stderr or "").strip()


def even():
    return "scale=trunc(iw/2)*2:trunc(ih/2)*2"


def flatten_white(src, dst):
    """투명 배경 gif → 흰 바탕 mp4. 너무 짧으면 되풀이하고 너무 길면 앞부분만."""
    p = probe(src)
    dur = p["dur"]
    if dur <= 0:
        raise ValueError("gif 길이 0")
    want = dur
    if dur < LOOP_TO:
        want = dur * math.ceil(LOOP_TO / dur)
    elif dur > MAX_SEC:
        want = CUT_TO
    rc, err = run(["ffmpeg", "-v", "error", "-y", "-ignore_loop", "0", "-i", src, "-t", f"{want:.3f}",
                   "-filter_complex",
                   f"color=white:s={p['w']}x{p['h']}:r=25[bg];[bg][0:v]overlay=shortest=0:format=auto,{even()},format=yuv420p[v]",
                   "-map", "[v]", "-t", f"{want:.3f}", "-an", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                   "-movflags", "+faststart", dst])
    if rc != 0 or not os.path.exists(dst):
        raise RuntimeError(f"ffmpeg(흰 바탕) 실패: {err[:160]}")


def cut(src, dst, start=None, dur=None, crop=None, loops=0):
    """구간을 잘라 H.264·yuv420p·짝수 크기·faststart 로 굽는다. 소리가 있으면 살린다."""
    p = probe(src)
    cmd = ["ffmpeg", "-v", "error", "-y"]
    if loops:
        cmd += ["-stream_loop", str(loops)]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", src]
    if dur is not None:
        cmd += ["-t", f"{dur:.3f}"]
    vf = (crop + "," if crop else "") + even()
    cmd += ["-map", "0:v:0", "-vf", vf, "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p"]
    cmd += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "128k"] if p["audio"] else ["-an"]
    rc, err = run(cmd + ["-movflags", "+faststart", dst])
    if rc != 0 or not os.path.exists(dst):
        raise RuntimeError(f"ffmpeg(자르기) 실패: {err[:160]}")


def tenor_mp4(src, dst, start=None, dur=None):
    """Tenor mp4 → 1~4초 mp4. 그대로 쓸 수 있으면 다시 굽지 않는다(tenor.to_mp4)."""
    p = probe(src)
    if start is not None or dur is not None:
        cut(src, dst, start, dur)
    elif p["dur"] < LOOP_TO:
        cut(src, dst, loops=math.ceil(LOOP_TO / p["dur"]) - 1)
    elif p["dur"] > MAX_SEC:
        cut(src, dst, 0, CUT_TO)
    else:
        to_mp4(src, dst)


def frames(path, n=3):
    """영상에서 처음·중간·끝 쪽 n장을 PIL 그림으로."""
    from PIL import Image
    import io
    d = probe(path)["dur"]
    out = []
    for i in range(n):
        t = d * (0.05 + 0.75 * i / max(1, n - 1))
        for tt in (t, t * 0.7, 0.0):  # 끝 쪽은 마지막 프레임 뒤일 수 있다 — 앞으로 당겨 다시 뽑는다
            r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{tt:.3f}", "-i", path, "-frames:v", "1", "-f", "image2pipe",
                                "-vcodec", "png", "-"], capture_output=True)
            if r.returncode == 0 and r.stdout:
                break
        else:
            raise RuntimeError(f"프레임 뽑기 실패 {path} @{t:.2f}")
        out.append(Image.open(io.BytesIO(r.stdout)).convert("RGB"))
    return out


def motion(path):
    """처음·중간·끝 프레임이 서로 얼마나 다른가(0~255 평균 차이의 최댓값). 정지 그림 거르기용."""
    from PIL import ImageChops, ImageStat
    fs = [f.convert("L").resize((96, 96)) for f in frames(path, 4)]
    return max(ImageStat.Stat(ImageChops.difference(fs[i], fs[j])).mean[0] for i in range(4) for j in range(i + 1, 4))


def thumb(mp4, jpg):
    d = probe(mp4)["dur"]
    rc, err = run(["ffmpeg", "-v", "error", "-y", "-ss", f"{d * 0.3:.2f}", "-i", mp4, "-frames:v", "1",
                   "-vf", "scale=-2:260", jpg])
    if rc != 0 or not os.path.exists(jpg):
        raise RuntimeError(f"썸네일 실패: {err[:160]}")


def slug_of(view_url):
    m = re.search(r"/view/(.*?)-?gif-\d+$", view_url)
    return (m.group(1) if m else "").replace("-", " ").strip()


class Job:
    def __init__(self, work):
        self.work = work
        self.raw = os.path.join(work, "raw")
        self.thumbs = os.path.join(work, "sheets", "thumbs")
        self.tmp = os.path.join(self.raw, "_pm_tmp")
        self.downloads = 0
        self.pruned = 0
        self.stats = {"받기 실패": 0, "변환 실패": 0, "정지 그림": 0, "짧음/김": 0, "작음(<200px)": 0}
        os.makedirs(os.path.join(self.tmp, "src"), exist_ok=True)
        os.makedirs(self.thumbs, exist_ok=True)

    def fetch(self, url, name):
        """파일 하나 받기(임시 폴더에 이미 있으면 다시 받지 않는다)."""
        dst = os.path.join(self.tmp, "src", name)
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            return dst
        if self.downloads >= MAX_DOWNLOADS:
            raise Blocked(f"받기 상한 {MAX_DOWNLOADS}개에 닿았다")
        data = get(url)
        self.downloads += 1
        with open(dst, "wb") as f:
            f.write(data)
        return dst

    def fetch_yt(self, vid):
        dst = os.path.join(self.tmp, "src", f"yt_{vid}.mp4")
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            return dst
        if self.downloads >= MAX_DOWNLOADS:
            raise Blocked(f"받기 상한 {MAX_DOWNLOADS}개에 닿았다")
        rc, err = run(["yt-dlp", "-q", "--no-warnings", "--sleep-requests", "0.4", "-f",
                       "bv*[height<=720]+ba/b[height<=720]/b", "--merge-output-format", "mp4", "-o", dst,
                       f"https://www.youtube.com/watch?v={vid}"])
        self.downloads += 1
        if rc != 0 or not os.path.exists(dst):
            if re.search(r"Sign in to confirm|HTTP Error 429|not a bot", err):
                raise Blocked(f"유튜브가 막았다: {err[:160]}")
            raise RuntimeError(f"yt-dlp 실패: {err[:200]}")
        return dst

    def finish(self, cid, dst, rows, row):
        """구운 mp4 를 재고(길이·높이·움직임) 썸네일을 만들어 목록에 넣는다. 탈락이면 지우고 False."""
        p = probe(dst)
        why = None
        if not (MIN_SEC <= p["dur"] <= MAX_SEC + 0.05):
            why = "짧음/김"
        elif p["h"] < MIN_H:
            why = "작음(<200px)"
        elif motion(dst) < STATIC_BELOW:
            why = "정지 그림"
        if why:
            self.stats[why] += 1
            print(f"[탈락·{why}] {cid}: {p['dur']:.2f}s {p['w']}x{p['h']}", file=sys.stderr)
            os.remove(dst)
            return False
        thumb(dst, os.path.join(self.thumbs, cid + ".jpg"))
        rows.append({"id": cid, **row, "duration": round(p["dur"], 2), "w": p["w"], "h": p["h"], "views": 0})
        return True


def have_ok(job, rows, cid):
    return (any(r["id"] == cid for r in rows) and os.path.exists(os.path.join(job.raw, cid + ".mp4"))
            and os.path.exists(os.path.join(job.thumbs, cid + ".jpg")))


def collect(job, table, out_name, make):
    """표의 줄마다: 이미 있으면 건너뛰고, 없으면 make(줄) 로 받아 굽는다. 줄마다 목록 파일을 다시 쓴다(중간에 끊겨도 남는다)."""
    out_path = os.path.join(job.work, out_name)
    rows = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else []
    new = skipped = 0
    want = {e["cid"]: e for e in table}
    for r in [r for r in rows if r["id"] not in want]:  # 표에서 뺀 짤은 파일까지 치운다(눈으로 보고 탈락시킨 것)
        for p in (os.path.join(job.raw, r["id"] + ".mp4"), os.path.join(job.thumbs, r["id"] + ".jpg")):
            if os.path.exists(p):
                os.remove(p)
        rows.remove(r)
        job.pruned += 1
    for r in rows:  # 감정은 표가 주인이다 — 표에서 감정을 옮기면 목록도 따라간다
        r["emotion"] = want[r["id"]]["emotion"]
    for entry in table:
        cid = entry["cid"]
        if have_ok(job, rows, cid):
            skipped += 1
            continue
        rows[:] = [r for r in rows if r["id"] != cid]  # 파일이 사라진 옛 줄은 버리고 다시 만든다
        dst = os.path.join(job.raw, cid + ".mp4")
        try:
            row = make(job, entry, dst)
            ok = job.finish(cid, dst, rows, row)
        except Blocked:
            save(rows, out_path)
            raise
        except Exception as e:
            kind = "받기 실패" if "yt-dlp" in str(e) or "HTTP" in repr(e) or "URLError" in repr(e) else "변환 실패"
            job.stats[kind] += 1
            print(f"[{kind}] {cid}: {e!r}"[:240], file=sys.stderr)
            if os.path.exists(dst):
                os.remove(dst)
            continue
        if ok:
            new += 1
            save(rows, out_path)
    save(rows, out_path)
    return rows, new, skipped


def make_pepe(job, e, dst):
    src = job.fetch(e["url"], f"{e['cid']}.{'gif' if e['sticker'] else 'mp4'}")
    if e["sticker"]:
        flatten_white(src, dst)
    else:
        tenor_mp4(src, dst)
    return {"title": f"Pepe — {slug_of(e['source']) or e['cid']}", "emotion": e["emotion"], "source": e["source"],
            "group": "페페", "sticker": e["sticker"]}


def make_meme(job, e, dst):
    s = e["src"]
    if s[0] == "yt":
        src = job.fetch_yt(s[1])
        cut(src, dst, s[2], s[3], s[4] if len(s) > 4 else None)
        source = f"https://www.youtube.com/watch?v={s[1]}&t={int(s[2])}s"
    else:
        src = job.fetch(s[2], f"{e['cid']}.mp4")
        tenor_mp4(src, dst, *(s[3:5] if len(s) > 3 else ()))
        source = s[1]
    return {"title": f"{e['name']} — {e['desc']}", "emotion": e["emotion"], "source": source, "group": "유명밈",
            "meme": e["name"], "from": s[0]}


def tables():
    pepe = [{"cid": f"pp_{t}", "emotion": emo, "sticker": st, "source": view, "url": url} for t, emo, st, view, url in PEPE]
    memes = [{"cid": f"fm_{k}", "name": n, "emotion": emo, "desc": d, "src": s} for k, n, emo, d, s in MEMES]
    ids = [e["cid"] for e in pepe + memes]
    bad = [i for i in ids if not re.fullmatch(r"[A-Za-z0-9_-]+", i)] + [e["cid"] for e in pepe + memes if e["emotion"] not in EMOTIONS]
    if bad or len(set(ids)) != len(ids):
        raise SystemExit(f"표가 잘못됐다 — id 꼴/감정/중복: {bad or [i for i in ids if ids.count(i) > 1]}")
    return pepe, memes


def check(work):
    """두 목록 전수 검사 — 줄마다 mp4·썸네일, ffprobe 형식·길이·높이, 움직임, 표에 있는 id 인가."""
    pepe, memes = tables()
    rc = 0
    for name, table, group in (("extra_pepe.json", pepe, "페페"), ("extra_memes.json", memes, "유명밈")):
        path = os.path.join(work, name)
        rows = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
        want = {e["cid"] for e in table}
        bad = []
        for r in rows:
            why = []
            mp4 = os.path.join(work, "raw", r["id"] + ".mp4")
            jpg = os.path.join(work, "sheets", "thumbs", r["id"] + ".jpg")
            if r["id"] not in want:
                why.append("표에 없는 id")
            if r.get("group") != group or r.get("emotion") not in EMOTIONS or r.get("views") != 0 or not r.get("title"):
                why.append("group/emotion/views/title")
            if not (os.path.exists(jpg) and os.path.getsize(jpg) > 0):
                why.append("썸네일 없음")
            if not os.path.exists(mp4):
                why.append("mp4 없음")
            else:
                try:
                    p = probe(mp4)
                    if not (MIN_SEC <= p["dur"] <= MAX_SEC + 0.05) or p["h"] < MIN_H:
                        why.append(f"길이/높이 {p['dur']:.2f}s {p['h']}px")
                    if p["codec"] != "h264" or p["pix"] != "yuv420p" or p["w"] % 2 or p["h"] % 2:
                        why.append(f"형식 {p['codec']} {p['pix']} {p['w']}x{p['h']}")
                    if (p["w"], p["h"]) != (r["w"], r["h"]) or abs(p["dur"] - r["duration"]) > 0.02:
                        why.append("JSON 과 파일 수치 다름")
                    m = motion(mp4)
                    if m < STATIC_BELOW:
                        why.append(f"정지 그림(움직임 {m:.2f})")
                except Exception as e:
                    why.append(f"판독 실패 {e!r}"[:80])
            if why:
                bad.append((r["id"], why))
        for cid, why in bad:
            print(f"[불량] {cid}: {why}")
        missing = sorted(want - {r["id"] for r in rows})
        hs = sorted(r["h"] for r in rows)
        print(f"{name}: {len(rows)}줄 · 불량 {len(bad)} · 표에는 있는데 목록에 없는 것 {len(missing)}{missing[:8] if missing else ''}"
              + (f" · 높이 중앙값 {hs[len(hs) // 2]}px · 480px 이상 {sum(1 for h in hs if h >= 480)}개" if hs else ""))
        for emo in EMOTIONS:
            rs = [r for r in rows if r["emotion"] == emo]
            extra = (f" (밈 {len({r.get('meme') for r in rs})}가지)" if group == "유명밈" else
                     f" (스티커 {sum(1 for r in rs if r.get('sticker'))})")
            print(f"  {emo}: {len(rs)}{extra}")
        if group == "유명밈":
            print(f"  밈 {len({r.get('meme') for r in rows})}가지 · 유튜브 {sum(1 for r in rows if r.get('from') == 'yt')}"
                  f" · Tenor {sum(1 for r in rows if r.get('from') == 'tenor')} · 소리 있는 것 "
                  f"{sum(1 for r in rows if probe(os.path.join(work, 'raw', r['id'] + '.mp4'))['audio'])}")
        else:
            print(f"  스티커(흰 바탕에 얹음) {sum(1 for r in rows if r.get('sticker'))}개")
        rc |= 1 if bad or missing else 0
    return rc


def sheets(work, out_dir):
    """눈으로 볼 대조표 — 짤마다 처음·중간·끝 3장 + id·감정·제목. 감정 순서대로."""
    from PIL import Image, ImageDraw, ImageFont
    os.makedirs(out_dir, exist_ok=True)
    font = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 13)
    FH, LAB, COLS, ROWS = 120, 34, 3, 6
    order = {e: i for i, e in enumerate(EMOTIONS)}
    for name, tag in (("extra_pepe.json", "pepe"), ("extra_memes.json", "memes")):
        path = os.path.join(work, name)
        rows = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
        rows.sort(key=lambda r: (order[r["emotion"]], r["title"]))
        CW = 3 * 160 + 6
        for s in range(0, len(rows), COLS * ROWS):
            sheet = Image.new("RGB", (COLS * CW, ROWS * (FH + LAB)), "#202020")
            d = ImageDraw.Draw(sheet)
            for j, r in enumerate(rows[s:s + COLS * ROWS]):
                x0, y0 = (j % COLS) * CW, (j // COLS) * (FH + LAB)
                x = x0
                for f in frames(os.path.join(work, "raw", r["id"] + ".mp4"), 3):
                    f.thumbnail((160, FH))
                    sheet.paste(f, (x, y0 + LAB))
                    x += 160
                d.text((x0 + 2, y0), f"{r['id']} [{r['emotion']}] {r['duration']}s {r['w']}x{r['h']}", fill="#ffe14d", font=font)
                d.text((x0 + 2, y0 + 16), r["title"][:60], fill="white", font=font)
            out = os.path.join(out_dir, f"{tag}_{s // (COLS * ROWS):02d}.jpg")
            sheet.save(out, quality=82)
            print(out)


def main():
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--check", action="store_true", help="받지 않고 전수 검사만")
    ap.add_argument("--sheets", metavar="폴더", help="대조표만 만든다")
    ap.add_argument("--keep-tmp", action="store_true", help="임시 폴더(raw/_pm_tmp)를 지우지 않는다")
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    if a.check:
        sys.exit(check(work))
    if a.sheets:
        sheets(work, os.path.abspath(a.sheets))
        return
    pepe, memes = tables()
    job = Job(work)
    blocked = None
    try:
        for label, table, out_name, make in (("페페", pepe, "extra_pepe.json", make_pepe),
                                             ("유명밈", memes, "extra_memes.json", make_meme)):
            rows, new, skipped = collect(job, table, out_name, make)
            print(f"{label}: 목록 {len(rows)}줄 · 이번에 새로 {new} · 이미 있어 건너뜀 {skipped} · 표 {len(table)}줄", flush=True)
    except Blocked as e:
        blocked = str(e)
    finally:
        if not a.keep_tmp:
            shutil.rmtree(job.tmp, ignore_errors=True)
    print(f"이번 실행: 받기 {job.downloads}개 · 표에서 빠져 치운 것 {job.pruned}개 · 탈락/실패 {job.stats}")
    if blocked:
        print(f"[중단] {blocked}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
