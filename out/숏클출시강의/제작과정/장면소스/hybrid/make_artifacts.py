import json, sys, pathlib
sys.path.insert(0, r"C:/Users/TheRose/.claude/toolbox/library/OpenMontage")
W = pathlib.Path(r"C:/Users/TheRose/숏템자료/모션그래픽엔진/work/2026-10-29_openmontage/hybrid")
A = W/"artifacts"; A.mkdir(exist_ok=True)
def w(n,d): (A/f"{n}.json").write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf8")
w("brief",{"version":"1.0","title":"이 쇼츠, 말 한 줄로 나왔습니다","hook":"결말(완성 쇼츠)을 먼저 보여주고 되감기","key_points":["완성 쇼츠 먼저","어떻게요?","말 한 줄 입력 -> 4단계 진행","말 한 줄이면 됩니다"],"tone":"차분","style":"clean-professional(ink/cream/orange/teal custom)","target_platform":"generic","target_duration_seconds":25,
 "metadata":{"anchor_medium":"screen_recording(source=finished vertical short)","source_inventory":["해외화장품_코팩_완성본.mp4 1080x1920 28s"],"support_layers":["headline text","question card","typing prompt UI","progress chip","brand tag"],"deliverable_mix":["16:9 hero 1920x1080"],"missing_capabilities":[],"fallback_policy":"no paid API; no narration"}})
secs=[("s1","이 쇼츠, 말 한 줄로 나왔습니다",0,4),("s2","어떻게요?",4,7),("s3","해외 화장품 쇼츠 만들어줘 / 원본 찾는 중… / 대본 쓰는 중… / 장면 맞추는 중… / 완성 ✓",7,18),("s4","말 한 줄이면 됩니다 / 숏클메이커",18,25)]
w("script",{"version":"1.0","title":"hybrid sample","total_duration_seconds":25,"sections":[{"id":i,"text":t,"start_seconds":a,"end_seconds":b} for i,t,a,b in secs],"metadata":{"anchor_sections":["s1","s4"],"support_sections":["s2","s3"],"narration_sections":[],"required_support_assets":["Pretendard fonts"]}})
w("scene_plan",{"version":"1.0","scenes":[
 {"id":"s1","type":"screen_recording","description":"phone frame (source, 506x900) + 3-line headline","start_seconds":0,"end_seconds":4},
 {"id":"s2","type":"text_card","description":"cream question card","start_seconds":4,"end_seconds":7},
 {"id":"s3","type":"screen_recording","description":"prompt box typing -> send -> progress chip x4","start_seconds":7,"end_seconds":18},
 {"id":"s4","type":"screen_recording","description":"phone replay + closing line + brand","start_seconds":18,"end_seconds":25}],
 "metadata":{"overlay_density_limits":"<=2 moving things per frame","safe_zones":"16:9 only","anchor_rules":"source visible in s1,s4"}})
w("asset_manifest",{"version":"1.0","assets":[
 {"id":"src","type":"video","path":"assets/source_kopack.mp4","source_tool":"user_provided","scene_id":"s1"},
 {"id":"font_bold","type":"font","path":"assets/fonts/Pretendard-Bold.otf","source_tool":"user_provided","scene_id":"s3"},
 {"id":"font_xbold","type":"font","path":"assets/fonts/Pretendard-ExtraBold.otf","source_tool":"user_provided","scene_id":"s1"},
 {"id":"font_semi","type":"font","path":"assets/fonts/Pretendard-SemiBold.otf","source_tool":"user_provided","scene_id":"s2"},
 {"id":"font_reg","type":"font","path":"assets/fonts/Pretendard-Regular.otf","source_tool":"user_provided","scene_id":"s2"}]})
w("edit_decisions",{"version":"1.0","render_runtime":"remotion","composition_mode":"atelier",
 "cuts":[{"id":"c1","source":"src","in_seconds":0,"out_seconds":4},{"id":"c2","source":"src","in_seconds":0,"out_seconds":7}],
 "bespoke":{"entry":"src/index.tsx","composition_id":"HybridKopack","public_dir":"assets","crf":18,"art_direction":"ink #0b0a11 / cream #f3ece0 / orange #f0902a / teal #2ee6c9; Pretendard; ease-out only; signature device = phone frame in bookend beats"},
 "metadata":{"layer_order":["source phone","text","ui"],"overlay_windows":{}}})
def opts(sel,items): return [{"option_id":k,"label":k,"score":(0.9 if k==sel else 0.4),"reason":r,**({} if k==sel else {"rejected_because":r})} for k,r in items]
w("decision_log",{"version":"1.0","project_id":"hybrid-kopack","decisions":[
 {"decision_id":"d1","stage":"idea","category":"render_runtime_selection","subject":"Composition runtime","options_considered":opts("remotion",[("remotion","source video via OffthreadVideo + React typing UI in one pass"),("hyperframes","no HTML/GSAP-native need here"),("ffmpeg","cannot do typing UI")]),"selected":"remotion","reason":"brief pre-approved by user; both runtimes available","confidence":0.8},
 {"decision_id":"d2","stage":"idea","category":"composition_mode","subject":"Authoring mode","options_considered":opts("atelier",[("atelier","typing UI + phone frame are not in stock cut.type catalog"),("templated","stock scene types do not cover it")]),"selected":"atelier","reason":"bespoke UI beats","confidence":0.85}]})
