"""qa_scene_controls + qa_scene_style_render의 실제 MP4 프레임 회귀 검사."""
from pathlib import Path
from PIL import Image, ImageChops, ImageStat

work = Path(__file__).resolve().parents[1] / '.tmp/scene-style-qa'
early = Image.open(work / 'motion-0.1.png').convert('RGB')
late = Image.open(work / 'motion-0.65.png').convert('RGB')
# 정지된 소스 영상 위에서 제목과 화살표 영역을 별도로 확인한다.
# 미세한 비디오 압축 차이로 정지 모션이 통과하지 않도록 평균 차이 5 이상.
for name, box in [('title', (0, 280, 1080, 800)), ('shape', (400, 880, 650, 985))]:
    mean = sum(ImageStat.Stat(ImageChops.difference(early.crop(box), late.crop(box))).mean) / 3
    assert mean > 5, f'{name} 애니메이션 정지: 픽셀 차이 {mean}'
    print(f'{name}: 실제 MP4 시간별 픽셀 차이 {mean:.2f}')
