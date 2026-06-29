---
name: skin-sheet-split
description: 캐릭터 8 포즈 시트(Gemini 등으로 만든 "3+3+2" 레이아웃 한 장)를 token-panda 스킨 PNG 8 장으로 자동 분할·정렬해서 src/skins/<id>/ 에 넣고 src/skins.ts 에 등록하는 스킬. 흰 배경/투명 배경 둘 다 처리하고, 누끼 흰 테두리 제거(디프린지) + panda-v3/cat-v1 과 같은 비율(640×640, 발끝 Y=630, 서있는 높이 ~590)로 정렬한다. "이 시트 8등분해서 스킨 넣어줘", "포즈 시트 분할", "캐릭터 누끼 따서 스킨 추가", "판다/고양이 다시 넣어줘(시트에서)", "8등분해서 넣어줘" 같은 표현이나, 사용자가 8 포즈 캐릭터 시트 + 새 스킨 의도를 같이 줄 때 발동. 단순 이미지 자르기·일반 누끼 작업에는 쓰지 않는다(이건 token-panda 스킨 규격 전용).
---

# 캐릭터 8 포즈 시트 → 스킨 분할 스킬 (skin-sheet-split)

## 존재 이유

token-panda 의 스킨(panda-v3 / cat-v1 / hamster-v2 …)은 전부 **같은 8 포즈
시트 한 장**에서 8 개 PNG 로 잘라낸 것이다. 사용자가 손으로 누끼를 따면
(1) 캐릭터마다 크기·발끝 위치가 제각각이라 스킨끼리 비율이 안 맞고,
(2) 흰 배경 잔재로 누끼 테두리가 희게 뜬다("선이 뭉개짐"). 이 스킬은 그
분할·정렬·디프린지를 한 번에 결정론적으로 처리한다. 같은 시트는 항상 같은
바이트가 나온다.

## 전제 도구

`python3` + `Pillow` + `scipy`. 이미 token-panda 환경(`node_modules.nosync`
와 무관, 시스템 python)에 깔려 있음. 없으면 `pip install pillow scipy`.

## 입력으로 받을 것 (작업 시작 전에 사용자에게 확인)

1. **시트 이미지 경로** — 보통 `~/Downloads/Gemini_Generated_Image_*.png`.
   여러 후보가 있으면 Read 로 직접 보고 "3+3+2 8 포즈"인 걸 고른다.
2. **스킨 id** (= 폴더명). 컨벤션: `<동물>-v<N>`. 같은 캐릭터를 다시 뽑으면
   버전을 올린다(예: hamster-v1 잘림 → hamster-v2). 사용자에게 v 번호 확인.
3. **표시 이름** (선택) — 예 "Hamster v2". 없으면 id 에서 유추.
4. **배경** — 기본 `auto` (알파 전부 불투명이면 white, 아니면 transparent).
   Gemini "흰 배경"은 white, "투명 배경"은 transparent. 애매하면 auto.

## 포즈 → 파일명 → state 매핑 (불변)

시트는 **읽기 순서(행 우선, 행 안에서 좌→우)** 로 다음과 같이 고정 매핑된다.
이 순서는 panda-v3 개별 파일로 검증된 것이며, 모든 스킨이 동일하다.

| 위치 | 포즈 | 파일명 |
|---|---|---|
| 1 (1행1열) | 윙크 + 노란 별 | `cheerful` |
| 2 (1행2열) | 기본 미소(양눈 뜬 활기) | `idle` |
| 3 (1행3열) | 식은땀 1 방울(약간 걱정) | `tired` |
| 4 (2행1열) | 식은땀 2~3 방울 + 손 모음 | `weary` |
| 5 (2행2열) | 하품(눈 감고 입 벌림) | `sleepy` |
| 6 (2행3열) | 옆으로 누워 자기 | `sleep` |
| 7 (3행1열) | X 눈 + 혀 | `dead` |
| 8 (3행2열) | 앉은 포즈 | `sit` |

`src/skins.ts` 의 9-state → 파일 매핑 (표준, 2026-05-26 hamster-v2 정정 이후):

```
full → cheerful  high → idle  good → sit
mid  → tired     low  → weary     tired → sleepy
sleepy → sleep   dead → dead      disconnected → dead
```

**의미 흐름**: 잔량이 가장 많을 때 가장 활기찬 표정(`full=cheerful`, 윙크+별)
→ 정면 활기(`high=idle`) → 편안한 앉음(`good=sit`) → 점점 지친 톤. 8 포즈가
잔량 그라데이션에 1:1 로 매핑된다 (포즈 하나도 안 버려짐).

**레거시 매핑 (panda-v3 / cat-v1 / penguin-v1 / penguin-v2 가 쓰고 있음)**:
```
full → idle  high → cheerful  good → cheerful  (sit 안 씀)
```
새 스킨을 등록할 때는 **표준 매핑**을 쓴다. 레거시 스킨은 사용자가 손대지
말라고 명시할 때까지 그대로 둔다 (시각적으로 큰 문제 없음).

## 파이프라인 (split_sheet.py 가 하는 일)

1. **배경 제거**
   - white: neutral-white(채널 min>238 & max-min≤8)만 골라 *테두리부터*
     connected-component 로 잡아 제거. warm cream 배는 본체에 enclosed 라
     테두리와 안 이어져서 보존된다. (단순 임계 누끼면 배에 구멍 남)
   - transparent: 기존 알파를 그대로 fg 로.
2. **라벨 텍스트 제외** — Gemini 시트에 "Playful Wink" 같은 영문 라벨이 박혀
   오면, 분리된 *어두운* 컴포넌트(픽셀별 max 채널 평균 < `TEXT_BRIGHTNESS_MAX`
   =110)를 텍스트로 보고 버린다. 별(노랑)·식은땀(파랑)은 밝아서 통과. 캐릭터의
   검은 눈/X눈은 본체에 붙어 있어 분리 컴포넌트가 아니므로 안전.
3. **8 분할** — `ndimage.label` 후, 텍스트를 뺀 컴포넌트 중 **면적 상위 8 개를
   캐릭터(본체)** 로 잡는다(캐릭터는 항상 부속보다 훨씬 큼 — 별이 임계를 살짝
   넘겨도 안전). 나머지(별·식은땀)는 부속. 노이즈 하한만 total×0.00004.
5. **부속 병합** — 별/식은땀을 centroid 가 가장 가까운 본체에 배정해 같이 크롭.
6. **읽기 순서 정렬** — centroid Y 로 행을 묶고(gap = H×0.12), 행 안에서 X 정렬.
   `rows=[3,3,2]` 가 안 나오면 레이아웃이 다른 것이니 확인 (아래 *4+4 정정*).
7. **엣지 디프린지** — 알파를 `ring`(기본 2)px 침식해 깨끗한 interior 정의 →
   `distance_transform_edt` 로 오염 링 RGB 를 가장 가까운 본체 색으로 치환.
   알파(투명도)는 그대로라 어떤 배경에서도 흰 선이 안 보인다. **배경을 구워
   넣지 않는다** — 데스크탑 펫은 투명이어야 함.
8. **비율 정렬 스케일** — 부속 없는 기본 포즈 `idle` 높이를
   `TARGET_STAND_H=590` 에 맞추는 전역 스케일 `s` 산출. 전 포즈에 같은 `s`
   적용(포즈 간 상대 비율 유지). premult-alpha LANCZOS 리샘플(헤일로 방지).
   cheerful 은 별이 머리 위로 솟아 bbox 가 커서 기준에서 뺀다 — idle 단독이
   다른 스킨과 가장 일관된 "기본 캐릭터 높이".
9. **배치** — 640×640 캔버스에 알파 가중 centroid X→320, 발끝(최하단 알파)
   → `FEET_Y=630`. panda-v3/cat-v1 과 동일 규격이라 스킨끼리 크기·발끝 일치.
10. 8 장(`cheerful…sit.png`) 저장 + 각 포즈 topY/botY/clip 리포트.

상수(`CANVAS=640`, `FEET_Y=630`, `TARGET_STAND_H=590`)는 token-panda 스킨
규격이라 바꾸지 않는다. 바꾸면 기존 스킨과 비율이 어긋난다.

## 실행

프로젝트 루트(`/Users/john_park/Desktop/token-panda-v2`)에서:

```bash
python3 ~/.claude/skills/skin-sheet-split/split_sheet.py \
  --src ~/Downloads/<시트>.png \
  --skin-id <animal>-v<N> --name "<표시 이름>"
# 기본 출력: src/skins/<skin-id>/  (--out 으로 변경 가능, --bg / --ring 옵션)
```

- 리포트의 모든 포즈가 `ok`(clip 아님)인지 확인. `CLIP!` 이 뜨면 그 포즈가
  캔버스 위로 넘친 것 → 거의 안 생기지만, 생기면 `TARGET_STAND_H` 가 아닌
  *그 포즈 자체*가 비정상적으로 큰 경우라 시트/매핑 재확인.
- `본체가 8 개가 아님` 에러면 컴포넌트 목록이 출력된다. 흰 배경이 아주
  지저분하거나(임계 조정) 캐릭터가 서로 붙은 경우. `--bg` 모드부터 점검.

### 4+4 레이아웃 정정 (Gemini 시트가 자주 이렇게 나옴)

리포트 첫 줄에 `rows=[4, 4] (기대 [3,3,2])` 가 뜨면, Gemini 가 시트를 *3행 →
2행 4열* 로 뱉은 케이스. 위 매핑표(3+3+2 가정)와 비교했을 때 정확히 **3-사이클
순환 어긋남**이 발생한다:

| 저장된 파일명 | 실제 포즈 | 진짜 이름 |
|---|---|---|
| `weary.png`  | 1행 4열 = 누운 자세 | `sleep` |
| `sleepy.png` | 2행 1열 = 식은땀+손모음 | `weary` |
| `sleep.png`  | 2행 2열 = 하품 | `sleepy` |
| `cheerful` / `idle` / `tired` / `dead` / `sit` | 변동 없음 | (그대로) |

`dead` 와 `sit` 은 마지막 행에 있을 때나 4+4 의 2행 3·4열에 있을 때나 위치가
바뀌어도 의미가 안 바뀐다(둘 다 마지막 두 장). `cheerful/idle/tired` 도 1행
1·2·3 열로 고정. **`weary/sleepy/sleep` 셋만 사이클**.

정정 (프로젝트 루트에서):

```bash
cd src/skins/<skin-id> && \
  mv weary.png __tmp.png && \
  mv sleepy.png weary.png && \
  mv sleep.png sleepy.png && \
  mv __tmp.png sleep.png
```

정정 후 Read 로 8 장 모두 직접 보고 매핑이 일치하는지 재확인. 특히 `sleep.png`
가 누운 포즈, `weary.png` 가 손모음+눈물, `sleepy.png` 가 하품인지 검증.

**언제 정정해야 하는가**: 리포트의 첫 줄이 `[3,3,2]` 면 정정 X, `[4,4]` 면
정정 O. 다른 패턴(`[2,3,3]` 등)이면 시트 자체가 비정상이니 사용자에게 확인.

## 검증 (분할 직후, 등록 전)

- 잘린 PNG 8 장을 Read 로 직접 본다 (배경 깨끗·배 안 파임·부속 포함·발끝 정렬).
- 흰 테두리 확인은 어두운 배경 합성으로: 임시 파이썬으로 `idle`/`cheerful`을
  dark gray(예 40,38,36)에 알파 합성해 저장 후 Read → 흰 헤일로 없어야 함.

## src/skins.ts 등록

import 블록(파일명 **8 개 — sit 포함**)과 SKINS 엔트리 추가. 새 스킨은 표준
매핑(`full=cheerful, high=idle, good=sit`)으로 등록:

```ts
import <id>Idle from "./skins/<id>/idle.png";
import <id>Cheerful from "./skins/<id>/cheerful.png";
import <id>Tired from "./skins/<id>/tired.png";
import <id>Weary from "./skins/<id>/weary.png";
import <id>Sleepy from "./skins/<id>/sleepy.png";
import <id>Sleep from "./skins/<id>/sleep.png";
import <id>Dead from "./skins/<id>/dead.png";
import <id>Sit from "./skins/<id>/sit.png";
// ...
  {
    id: "<id>", name: "<표시 이름>",
    frames: {
      full: <id>Cheerful, high: <id>Idle, good: <id>Sit,
      mid: <id>Tired, low: <id>Weary, tired: <id>Sleepy,
      sleepy: <id>Sleep, dead: <id>Dead, disconnected: <id>Dead,
    },
    actions: {},
  },
```

- 같은 캐릭터의 **옛 버전 폴더는 삭제**(panda 가 v1/v2 버리고 v3 만 남긴 패턴).
  깨진 버전을 selectable 로 남기면 select 목록만 지저분해진다.
- `DEFAULT_SKIN_ID` 는 건드리지 않는다(기본 panda-v3). 옛 저장값은 `findSkin`
  fallback 으로 흡수.

## 검증 게이트 + 미리보기

- `node_modules/.bin/tsc -b` (typecheck) + `node_modules/.bin/vitest run`.
  (이 프로젝트는 `node_modules` 가 `node_modules.nosync` 심링크여야 동작.)
- `node_modules/.bin/vite --port 5180 --strictPort` → `http://localhost:5180/skin-grid.html`
  에서 새 스킨 토글. 새로고침하면 select 에 새 스킨 반영. 배경 체크무늬의
  어두운 칸에서 흰 테두리 사라진 걸로 디프린지 확인.

## panda 워크플로우와의 관계

스킨 추가/재처리는 token-panda 의 [소] 작업이므로, panda 스킬의 사이클
(features.md 등록 → 작업 → "잘 됐냐" 검증 → 버전업)을 그대로 탄다. 이 스킬은
그 안에서 *분할·정렬·디프린지·등록* 의 결정론적 절차만 담당한다. 검증 질문과
버전 카운트는 panda 스킬이 관리.

## 안 하는 것

- 배경색을 PNG 에 굽지 않는다(투명 유지). 흰 테두리는 디프린지로 해결.
- 8 포즈 시트가 아닌 임의 이미지 자르기에는 쓰지 않는다.
- 상수(640/630/590)는 임의로 바꾸지 않는다 (기존 스킨과 비율 어긋남).
- 새 스킨은 항상 **표준 매핑** (`full=cheerful, high=idle, good=sit`) 으로
  등록. 레거시 스킨(panda-v3/cat-v1/penguin-v1/penguin-v2) 의 매핑을 사용자
  지시 없이 표준으로 정정하지 않는다 (사용자가 원치 않을 수 있음).
