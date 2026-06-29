#!/usr/bin/env python3
"""
캐릭터 8 포즈 시트 → token-panda 스킨 PNG 8 장 분할기.

Gemini 등으로 만든 "3+3+2" 레이아웃 8 포즈 시트(흰 배경 또는 투명 배경)를
받아서, 각 캐릭터를 panda-v3 / cat-v1 과 동일한 규격으로 잘라낸다:

  - 640×640 RGBA, 발끝 Y=630, 서있는 포즈 높이 ~590 (전 스킨 비율 정렬)
  - 좌우 중심 = 알파 가중 centroid → X=320
  - 흰 누끼 테두리 제거(엣지 디프린지) — 투명도는 유지

읽기 순서(행 우선, 행 안에서 좌→우)로 다음 파일명에 매핑:
  1 cheerful  (윙크+별)      2 idle (기본 미소)     3 tired (식은땀 1)
  4 weary     (식은땀+손모음) 5 sleepy(하품)         6 sleep (누워 자기)
  7 dead      (X눈+혀)        8 sit  (앉음)

사용:
  python3 split_sheet.py --src <sheet.png> --skin-id hamster-v2 \
      [--name "Hamster v2"] [--bg auto|white|transparent] [--out src/skins/<id>]

배경 모드:
  auto         (기본) 알파가 전부 불투명이면 white, 아니면 transparent 로 판단
  white        흰 배경. neutral-white(채널 min>WHITE_MIN & max-min<=WHITE_TOL)
               를 테두리부터 flood-fill 로 제거 (warm cream 배는 enclosed 라 보존)
  transparent  이미 투명 배경. 기존 알파를 그대로 fg 로 사용

분할 결과가 8 개 본체가 아니면 중단하고 컴포넌트 정보를 출력한다 (임계 튜닝용).
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.ndimage import binary_erosion, distance_transform_edt, gaussian_filter

# --- token-panda 규격 상수 (스킨 간 비율 정렬의 기준) ---
CANVAS = 640
FEET_Y = 630
TARGET_STAND_H = 590  # cheerful/idle/tired 평균 높이를 여기 맞춤

# --- 배경 판정 임계 (흰 배경) ---
WHITE_MIN = 238  # 채널 최소값이 이보다 크고
WHITE_TOL = 8    # 채널 최대-최소 차가 이하이면 "neutral white" (cream 은 warm 이라 제외)

# 분리된 어두운 컴포넌트 = 라벨 텍스트로 보고 제외 (별=노랑/식은땀=파랑은 밝아서 통과).
# 픽셀별 max 채널의 평균이 이 값보다 작으면 텍스트로 판단.
TEXT_BRIGHTNESS_MAX = 110

# 출하 캔버스 기준 알파 페더 강도(px). 소스 엣지가 날카롭고(특히 어두운 외곽선이
# 있는 캐릭터) 축소율이 1.0 에 가까우면 하드 마스크가 계단현상으로 보인다 →
# 알파를 살짝 가우시안 블러해 안티앨리어싱. 디컨탬으로 전 픽셀이 본체색이라
# 검은 헤일로 없이 실루엣만 부드러워진다.
FEATHER_SIGMA = 1.2

NAMES = ["cheerful", "idle", "tired", "weary", "sleepy", "sleep", "dead", "sit"]


def build_foreground(a, bg_mode):
    """RGBA 배열에서 fg 불린 마스크를 만들고 a 의 알파를 0/255 로 갱신."""
    H, W = a.shape[:2]
    alpha = a[:, :, 3]
    if bg_mode == "auto":
        bg_mode = "white" if (alpha.min() >= 250) else "transparent"
    if bg_mode == "transparent":
        fg = alpha > 16
    else:  # white
        rgb = a[:, :, :3].astype(np.int16)
        mn, mx = rgb.min(2), rgb.max(2)
        white = (mn > WHITE_MIN) & ((mx - mn) <= WHITE_TOL)
        lbl, _ = ndimage.label(white)
        border = (set(lbl[0, :]) | set(lbl[-1, :]) | set(lbl[:, 0]) | set(lbl[:, -1]))
        border.discard(0)
        fg = ~np.isin(lbl, list(border))
    a[:, :, 3] = np.where(fg, 255, 0).astype(np.uint8)
    return fg, bg_mode


def order_reading(main_info, row_gap):
    """centroid 기준 행 우선 → 행 내 좌→우 정렬."""
    ms = sorted(main_info, key=lambda m: m[1])
    rows = [[ms[0]]]
    for m in ms[1:]:
        if m[1] - rows[-1][-1][1] <= row_gap:
            rows[-1].append(m)
        else:
            rows.append([m])
    ordered = []
    for r in rows:
        ordered.extend(sorted(r, key=lambda m: m[2]))
    return ordered, [len(r) for r in rows]


def decontaminate(crop, ring=2):
    """누끼 테두리의 흰 오염 픽셀 RGB 를 본체 색으로 치환 (알파 유지)."""
    al = crop[:, :, 3] > 0
    interior = binary_erosion(al, iterations=ring)
    if interior.sum() < 50:  # 너무 작은 부속은 침식 생략
        interior = al
    inds = distance_transform_edt(~interior, return_distances=False, return_indices=True)
    out = crop.copy()
    for c in range(3):
        out[:, :, c] = crop[inds[0], inds[1], c]
    out[:, :, 3] = crop[:, :, 3]
    return out


def feather_alpha(crop, sigma):
    """알파만 가우시안 블러해 하드 마스크 엣지에 안티앨리어싱을 넣는다.
    디컨탬 후라 전 픽셀 RGB 가 본체색이므로 검은/흰 헤일로 없이 실루엣만 부드러워짐."""
    if sigma <= 0:
        return crop
    o = crop.copy()
    o[:, :, 3] = gaussian_filter(crop[:, :, 3].astype(np.float64), sigma).clip(0, 255).astype(np.uint8)
    return o


def premult_resize(crop, s):
    """premultiplied-alpha LANCZOS 리샘플 (엣지 헤일로 방지)."""
    f = crop.astype(np.float64)
    al = f[:, :, 3:4] / 255.0
    img = np.dstack([f[:, :, :3] * al, f[:, :, 3]]).astype(np.uint8)
    nh = max(1, round(crop.shape[0] * s))
    nw = max(1, round(crop.shape[1] * s))
    r = np.array(Image.fromarray(img, "RGBA").resize((nw, nh), Image.LANCZOS)).astype(np.float64)
    A = r[:, :, 3:4] / 255.0
    out = np.zeros_like(r)
    nz = A[:, :, 0] > 0
    out[:, :, :3][nz] = np.clip(r[:, :, :3][nz] / A[nz], 0, 255)
    out[:, :, 3] = r[:, :, 3]
    return out.astype(np.uint8)


def place(crop):
    """640×640 캔버스에 centroidX→320, 발끝→FEET_Y 로 배치."""
    al = crop[:, :, 3].astype(float)
    cx = (al.sum(0) * np.arange(crop.shape[1])).sum() / al.sum()
    ys, _ = np.where(crop[:, :, 3] > 10)
    by = ys.max()
    dx = int(round(CANVAS / 2 - cx))
    dy = int(round(FEET_Y - by))
    canvas = np.zeros((CANVAS, CANVAS, 4), np.uint8)
    ch, cw = crop.shape[:2]
    sx0, sy0 = max(0, dx), max(0, dy)
    cx0, cy0 = max(0, -dx), max(0, -dy)
    w = min(cw - cx0, CANVAS - sx0)
    h = min(ch - cy0, CANVAS - sy0)
    canvas[sy0:sy0 + h, sx0:sx0 + w] = crop[cy0:cy0 + h, cx0:cx0 + w]
    return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="8 포즈 시트 PNG 경로")
    ap.add_argument("--skin-id", required=True, help="스킨 id (= 폴더명), 예: hamster-v2")
    ap.add_argument("--name", default=None, help="표시 이름 (기록용)")
    ap.add_argument("--bg", default="auto", choices=["auto", "white", "transparent"])
    ap.add_argument("--out", default=None, help="출력 폴더 (기본 src/skins/<skin-id>)")
    ap.add_argument("--ring", type=int, default=2, help="디프린지 침식 px")
    ap.add_argument("--feather", type=float, default=FEATHER_SIGMA,
                    help="알파 페더(안티앨리어싱) 강도, 출하 px. 0 이면 끔")
    args = ap.parse_args()

    out = args.out or os.path.join("src", "skins", args.skin_id)
    os.makedirs(out, exist_ok=True)

    a = np.array(Image.open(args.src).convert("RGBA"))
    H, W = a.shape[:2]
    total = H * W
    fg, bg_mode = build_foreground(a, args.bg)
    print(f"src {W}x{H}  bg-mode={bg_mode}")

    flbl, fn = ndimage.label(fg)
    areas = ndimage.sum(np.ones(fg.shape), flbl, range(1, fn + 1))
    small_lo = total * 0.00004     # 노이즈 하한
    cand = [(i + 1, areas[i]) for i in range(fn) if areas[i] > small_lo]

    def mean_max_channel(lid):
        return float(a[flbl == lid][:, :3].max(axis=1).mean())

    # 어두운 분리 컴포넌트 = 라벨 텍스트 → 제외 (별=노랑/식은땀=파랑은 밝아 통과)
    texts = [lid for lid, _ in cand if mean_max_channel(lid) < TEXT_BRIGHTNESS_MAX]
    non_text = [(lid, ar) for lid, ar in cand if lid not in texts]
    if texts:
        print(f"라벨 텍스트로 판단해 제외: {len(texts)} 개 컴포넌트")

    # 캐릭터 8 마리 = (텍스트 제외) 가장 큰 8 개. 나머지(별/식은땀)는 부속.
    non_text.sort(key=lambda t: t[1], reverse=True)
    mains = [lid for lid, _ in non_text[:8]]
    smalls = [lid for lid, _ in non_text[8:]]

    def cen(lid):
        ys, xs = np.where(flbl == lid)
        return ys.mean(), xs.mean()

    main_info = [(lid, *cen(lid)) for lid in mains]
    if len(main_info) != 8:
        print(f"!! 본체가 8 개가 아님: {len(main_info)} 개 (non-text 후보={len(non_text)})", file=sys.stderr)
        for lid, ar in sorted(non_text, key=lambda t: t[1], reverse=True):
            cy, cx = cen(lid)
            print(f"   label {lid}: centroid=({cy:.0f},{cx:.0f}) area={int(ar)}", file=sys.stderr)
        print("캐릭터가 서로 붙었거나 조각났을 수 있음. --bg 모드부터 점검.", file=sys.stderr)
        sys.exit(2)

    # 부속을 가장 가까운 본체에 배정
    small_assign = {lid: [] for lid in mains}
    for sid in smalls:
        sy, sx = cen(sid)
        nearest = min(main_info, key=lambda m: (m[1] - sy) ** 2 + (m[2] - sx) ** 2)
        small_assign[nearest[0]].append(sid)

    ordered, row_sizes = order_reading(main_info, row_gap=H * 0.12)
    print(f"rows={row_sizes} (기대 [3,3,2])")

    # raw 크롭 + 디프린지
    raw = {}
    for (lid, _, _), name in zip(ordered, NAMES):
        mask = (flbl == lid)
        for sid in small_assign[lid]:
            mask |= (flbl == sid)
        ys, xs = np.where(mask)
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        crop = a[y0:y1 + 1, x0:x1 + 1].copy()
        crop[~mask[y0:y1 + 1, x0:x1 + 1], 3] = 0
        raw[name] = decontaminate(crop, ring=args.ring)

    # 전역 스케일 = 부속 없는 기본 포즈(idle) 높이를 TARGET_STAND_H 에 맞춤.
    # cheerful 은 별이 머리 위로 솟아 bbox 가 커지므로 기준에서 제외 — idle 단독이
    # 다른 스킨과 가장 일관된 "기본 캐릭터 높이"다.
    stand_h = raw["idle"].shape[0]
    scale = TARGET_STAND_H / stand_h
    print(f"idle raw H={stand_h:.1f} -> SCALE={scale:.4f}")

    # 페더는 소스 해상도에서 적용 → 출하 px 기준 강도(args.feather)가 되도록 1/scale 보정
    src_sigma = args.feather / scale if scale > 0 else args.feather
    for name in NAMES:
        canvas = place(premult_resize(feather_alpha(raw[name], src_sigma), scale))
        Image.fromarray(canvas).save(os.path.join(out, name + ".png"))
        yy, _ = np.where(canvas[:, :, 3] > 10)
        clip = "CLIP!" if yy.min() <= 0 else "ok"
        print(f"  {name:9s} topY={yy.min():3d} botY={yy.max():3d} H={yy.max()-yy.min()+1:3d} {clip}")

    label = args.name or args.skin_id
    print(f"\n완료 -> {out}  (skin '{label}')")
    print("다음: src/skins.ts 에 import + SKINS 엔트리 추가 (SKILL.md '등록' 절 참고)")


if __name__ == "__main__":
    main()
