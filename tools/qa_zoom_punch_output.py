"""Compare the media area of punch and pop renders produced by the QA renderer."""
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
work=Path(__file__).resolve().parents[1]/'.tmp/scene-style-qa'
box=(200,1000,900,1650)
def delta(a,b):
    first=Image.open(work/a).convert('RGB').crop(box)
    second=Image.open(work/b).convert('RGB').crop(box)
    return sum(ImageStat.Stat(ImageChops.difference(first,second)).mean)/3
punch=delta('punch-early.png','punch-settled.png')
pop=delta('motion-0.1.png','motion-0.65.png')
assert punch>5, f'Punch did not move the video: {punch}'
assert pop<.5, f'Pop unexpectedly moved the video: {pop}'
print({'punch_media_delta':punch,'pop_media_delta':pop})
