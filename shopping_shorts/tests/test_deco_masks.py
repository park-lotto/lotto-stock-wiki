# -*- coding: utf-8 -*-
"""꾸미기 가림막 — 안 지워진 자막·워터마크를 덮는 도형 (2026-08-28 고객 요청).

★왜: VMake가 못 지우는 것이 있다(08-27 확정 — 반투명 대형 워터마크는 eraser_watermark로도,
  두 번 태워도 안 지워진다). 고객이 스스로 낸 해법이 "가릴 수 있는 네모 도형"이었다.

★어디에 그리나: deco_frame이 만드는 **PNG 한 장**에 함께 그린다.
  그 PNG는 미리보기(API)와 렌더(mix_pipeline)가 **같은 파일**을 쓴다 —
  여기 그리면 화면과 결과가 구조적으로 안 갈린다(0순위-B).

★흐림 계열은 여기서 못 그린다: PNG는 '위에 얹는 그림'이라 뒤를 못 만진다.
  배경을 흐리게 하는 건 영상 필터라 렌더 쪽 일이다(2차).
"""
import pytest

from shopping_shorts import deco_frame as df


def _spec(masks):
    return {"preset": "news_coral", "bar_h": 0, "bottom_h": 0,
            "icons": False, "channel": "", "title": "", "masks": masks}


class Test정규화:
    def test_기본은_빈_목록(self):
        assert df.normalize({})["masks"] == []

    def test_범위를_자른다(self):
        m = df.normalize(_spec([{"l": -20, "t": 30, "w": 500, "h": 10}]))["masks"][0]
        assert 0 <= m["l"] <= 100 and 0 <= m["t"] <= 100
        assert m["l"] + m["w"] <= 100.001 and m["t"] + m["h"] <= 100.001

    def test_자리가_없으면_버린다(self):
        """★가장자리에 딱 붙은 막에 하한을 억지로 붙이면 화면 밖으로 삐져나간다."""
        assert df.normalize(_spec([{"l": 0, "t": 100, "w": 50, "h": 10}]))["masks"] == []
        assert df.normalize(_spec([{"l": 100, "t": 0, "w": 50, "h": 10}]))["masks"] == []

    def test_크기가_0이면_버린다(self):
        assert df.normalize(_spec([{"l": 10, "t": 10, "w": 0, "h": 5}]))["masks"] == []

    def test_모르는_모양은_사각으로(self):
        m = df.normalize(_spec([{"l": 1, "t": 1, "w": 5, "h": 5, "shape": "별"}]))["masks"][0]
        assert m["shape"] == "rect"

    def test_흐림도_이제_받는다(self):
        """2026-08-28: 렌더(ffmpeg)가 영역 블러를 먹인다 — 값은 살려서 넘겨야 한다.
        ★단 PNG에는 안 그린다(아래 test_흐림은_그림에_안_그린다)."""
        for fx in ("blur", "blurdark"):
            m = df.normalize(_spec([{"l": 1, "t": 1, "w": 5, "h": 5, "fx": fx}]))["masks"][0]
            assert m["fx"] == fx

    def test_모르는_효과는_단색(self):
        m = df.normalize(_spec([{"l": 1, "t": 1, "w": 5, "h": 5, "fx": "반짝"}]))["masks"][0]
        assert m["fx"] == "solid"

    def test_이상한_색은_검정(self):
        m = df.normalize(_spec([{"l": 1, "t": 1, "w": 5, "h": 5, "color": "red"}]))["masks"][0]
        assert m["color"] == "#000000"

    def test_개수_상한(self):
        many = [{"l": 1, "t": 1, "w": 5, "h": 5}] * 50
        assert len(df.normalize(_spec(many))["masks"]) <= df._MASK_MAX

    def test_dict가_아니면_버린다(self):
        assert df.normalize(_spec(["x", None, 3]))["masks"] == []


class Test실제로_그려진다:
    def _alpha_at(self, im, xp, yp):
        W, H = im.size
        return im.getpixel((int(W * xp), int(H * yp)))[3]

    def test_사각이_그_자리를_덮는다(self):
        im = df.render(_spec([{"l": 10, "t": 40, "w": 40, "h": 10,
                               "shape": "rect", "color": "#000000", "op": 100}]))
        assert self._alpha_at(im, 0.30, 0.45) == 255      # 안쪽
        assert self._alpha_at(im, 0.80, 0.45) == 0        # 바깥

    def test_원은_모서리가_비어_있다(self):
        """사각과 다른 모양이 실제로 나오는지 — 모양 선택이 먹는다는 증거."""
        im = df.render(_spec([{"l": 20, "t": 20, "w": 40, "h": 40,
                               "shape": "ellipse", "color": "#000000", "op": 100}]))
        assert self._alpha_at(im, 0.40, 0.40) == 255      # 가운데
        assert self._alpha_at(im, 0.205, 0.205) == 0      # 왼쪽 위 모서리

    def test_진하기가_반영된다(self):
        im = df.render(_spec([{"l": 10, "t": 40, "w": 40, "h": 10, "op": 50}]))
        a = self._alpha_at(im, 0.30, 0.45)
        assert 110 < a < 145

    def test_여러_개가_함께_얹힌다(self):
        im = df.render(_spec([
            {"l": 5, "t": 5, "w": 20, "h": 8, "color": "#000000"},
            {"l": 60, "t": 80, "w": 30, "h": 8, "color": "#ffffff"},
        ]))
        assert self._alpha_at(im, 0.15, 0.09) == 255
        assert self._alpha_at(im, 0.75, 0.84) == 255

    def test_가장자리_흐리기가_먹는다(self):
        """soft를 주면 경계 알파가 중간값이 된다 — 덮은 티가 덜 나게 하는 장치."""
        hard = df.render(_spec([{"l": 20, "t": 40, "w": 40, "h": 10, "soft": 0}]))
        soft = df.render(_spec([{"l": 20, "t": 40, "w": 40, "h": 10, "soft": 80}]))
        edge = (0.205, 0.405)
        assert self._alpha_at(hard, *edge) == 255
        assert self._alpha_at(soft, *edge) < 255

    def test_가림막이_띠보다_위다(self):
        """★띠·글자에 가려지면 원본 자막을 못 덮는다 — 그리는 순서가 계약이다."""
        spec = _spec([{"l": 0, "t": 0, "w": 100, "h": 5, "color": "#ff0000", "op": 100}])
        spec["bar_h"] = 190          # 상단 띠와 겹치게
        im = df.render(spec)
        px = im.getpixel((540, 40))
        assert px[0] > 200 and px[1] < 60, f"띠가 가림막을 덮었다: {px}"

    def test_캐시키가_가림막을_반영한다(self):
        """★안 반영하면 가림막을 바꿔도 옛 그림이 재사용된다(조용한 어긋남)."""
        a = df.cache_key(_spec([{"l": 1, "t": 1, "w": 9, "h": 9}]))
        b = df.cache_key(_spec([{"l": 1, "t": 1, "w": 9, "h": 20}]))
        assert a != b

    def test_가림막이_없으면_종전과_같은_그림(self):
        """기존 잡이 바이트 동일하게 나와야 한다 — 캐시가 통째로 무효화되면 안 된다."""
        base = {"preset": "news_coral", "bar_h": 190, "icons": True, "channel": "테스트"}
        assert df.cache_key(base) == df.cache_key(dict(base, masks=[]))
