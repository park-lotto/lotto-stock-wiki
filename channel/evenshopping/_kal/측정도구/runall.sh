S=/c/숏템_칼카피/evenshopping
for id in ABjQ0YCZoes LHembw8EUU0 tcaIPaGWLrE kC8fkx1Ve3Q 1kfqEB2b1xM Y2YXuAE4J00; do
  w=$S/work/$id; mkdir -p $w
  [ -f $w/m.json ] || PYTHONUTF8=1 py -I measure.py "C:/숏템_칼카피/evenshopping/src/$id.mp4" "C:/숏템_칼카피/evenshopping/work/$id/m.json"
  PYTHONUTF8=1 py -I cutsheet.py "C:/숏템_칼카피/evenshopping/src/$id.mp4" "C:/숏템_칼카피/evenshopping/work/$id/m.json" "C:/숏템_칼카피/evenshopping/work/$id/cuts.jpg"
  PYTHONUTF8=1 py -I capsheet.py "C:/숏템_칼카피/evenshopping/src/$id.mp4" "C:/숏템_칼카피/evenshopping/work/$id/m.json" "C:/숏템_칼카피/evenshopping/work/$id/caps.jpg" "C:/숏템_칼카피/evenshopping/work/$id/capm.json"
  ffmpeg -v error -y -i $S/src/$id.mp4 -vf "fps=2,scale=180:320,tile=10x8" -frames:v 1 $w/sheet2fps.jpg
done
echo ALLDONE
