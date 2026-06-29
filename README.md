# skills

> Claude Code가 특정 작업에서 자동으로 발동하는, 내가 만든 커스텀 스킬 모음입니다.
> 반복하는 글쓰기 · 학습 · 제작 과정을 규칙으로 굳혀 둔 것들입니다.

각 폴더의 `SKILL.md`가 스킬 본문입니다. 위쪽 frontmatter의 `description`이 발동 조건이고, 본문이 강제하는 절차입니다.

<br>

## 목록

| 스킬 | 하는 일 | 비고 |
|:--|:--|:--|
| [`algo-study`](algo-study/SKILL.md) | 백준 알고리즘을 답 없이 단계적으로 푸는 학습 러너 | 9단계 흐름 · 진도 파일로 이어가기 |
| [`mission-pre-study`](mission-pre-study/SKILL.md) | 우테코 사전학습 · 토론 활동 산출물 작성 | 자료가 명시한 형식 우선 |
| [`mission-retrospective`](mission-retrospective/SKILL.md) | 미션 · 프로젝트 회고 글 작성 | 인터뷰 → 구조 합의 → 꼭지별 |
| [`panda`](panda/SKILL.md) | 버전 · 체크리스트 기반 기능 개발 관리 | 요청 → 작업 → 검증 → 버전업 |
| [`skin-sheet-split`](skin-sheet-split/SKILL.md) | 캐릭터 8포즈 시트 → token-panda 스킨 분할 · 등록 | `split_sheet.py` 포함 |
| [`tech-learning-note`](tech-learning-note/SKILL.md) | 기술 노트 블로그 글 작성 | 공식 문서 + 본인 실측치 |

<br>

## 스킬이란

Claude Code의 [Agent Skill](https://docs.claude.com/en/docs/claude-code/skills)입니다. 폴더 안 `SKILL.md`의 `description`에 적힌 상황을 만나면 Claude가 알아서 그 절차를 불러와 따릅니다. 답을 더 잘 내게 하는 게 아니라, **내가 매번 시키던 방식을 한 번 규칙으로 박아두는** 용도입니다.

<br>

> 만든 사람 · [티뉴 (JohnPrk)](https://github.com/JohnPrk) · 개발 Claude Code
