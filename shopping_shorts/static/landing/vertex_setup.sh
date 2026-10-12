#!/usr/bin/env bash
# 숏템메이커 — 구글 버텍스 API 자동 설정 (관제 096, 2026-10-03)
# 구글 클라우드 셸에서 한 줄로 실행한다:
#   curl -fsSL https://shoppingshorts.duckdns.org/landing/vertex_setup.sh | bash
# 설명서 ⑧의 2~4단계(API 사용 · 서비스 계정 · 역할 · 키 생성 차단 풀기 · 키 만들기)를 대신 한다.
# 1단계(무료 체험 가입 = 결제 계정)는 본인 확인이라 대신 못 한다 — 없으면 안내하고 멈춘다.
# 만든 것은 전부 이 스크립트 전용 프로젝트(라벨 shortsmaker=1) 안에만 둔다. 다른 프로젝트는 건드리지 않는다.
# 전체를 main 안에 넣어 맨 끝에서 부른다 — 받다 끊겨도 반쪽만 실행되지 않게.

main() {
  set -u
  local SA_NAME="shortsmaker" LABEL="shortsmaker=1"
  local B=$'\033[1m' C=$'\033[1;36m' G=$'\033[1;32m' R=$'\033[1;31m' Y=$'\033[1;33m' N=$'\033[0m'
  say()  { printf '\n%s▶ %s%s\n' "$C" "$*" "$N"; }
  ok()   { printf '  %s✔ %s%s\n' "$G" "$*" "$N"; }
  warn() { printf '  %s! %s%s\n' "$Y" "$*" "$N"; }
  die()  { printf '\n%s✘ %s%s\n\n' "$R" "$*" "$N"; return 1; }
  # retry <횟수> <간격초> <명령…> — 권한·생성 반영(구글 쪽 1~3분)을 기다린다
  retry() { local n=$1 s=$2 i; shift 2; for ((i=1;i<=n;i++)); do "$@" 2>/tmp/ss_err && return 0; sleep "$s"; done; return 1; }

  printf '\n%s숏템메이커 · 구글 버텍스 API 자동 설정%s\n' "$B" "$N"
  printf '2~3분 걸립니다. 중간에 「승인(Authorize)」 창이 뜨면 눌러 주세요.\n'

  # ── 0. 로그인 계정 ─────────────────────────────────────────
  local ACCOUNT
  ACCOUNT=$(gcloud config get-value account 2>/dev/null)
  [ -n "$ACCOUNT" ] || { die "구글 로그인 정보가 없습니다 — 클라우드 셸 화면에서 다시 실행해 주세요"; return 1; }
  ok "계정: $ACCOUNT"

  # ── 1. 결제 계정(무료 체험) ────────────────────────────────
  say "1/5 결제 계정(무료 체험 \$300) 확인"
  local BA
  BA=$(gcloud billing accounts list --filter=open=true --format='value(name.basename())' 2>/dev/null | head -1)
  if [ -z "$BA" ]; then
    die "결제 계정이 없습니다. 먼저 무료 체험(\$300)에 가입해 주세요:
     https://console.cloud.google.com/freetrial
     가입이 끝나면 이 명령을 다시 붙여넣으면 이어서 됩니다."; return 1
  fi
  ok "결제 계정: $BA"

  # ── 2. 전용 프로젝트 ───────────────────────────────────────
  say "2/5 숏템메이커 전용 프로젝트 준비"
  local PID
  PID=$(gcloud projects list --filter="labels.$LABEL lifecycleState=ACTIVE" --format='value(projectId)' 2>/dev/null | head -1)
  if [ -n "$PID" ]; then
    ok "이미 만든 프로젝트를 씁니다: $PID"
  else
    PID="shorts-$(date +%y%m%d)-$((RANDOM % 9000 + 1000))"
    if ! gcloud projects create "$PID" --name="shortsmaker" --labels="$LABEL" --quiet >/dev/null 2>/tmp/ss_err; then
      cat /tmp/ss_err
      die "프로젝트를 만들지 못했습니다(위 메시지). 프로젝트 개수 한도라면 안 쓰는 프로젝트를 지운 뒤 다시 실행해 주세요."; return 1
    fi
    ok "새 프로젝트: $PID"
  fi
  gcloud config set project "$PID" >/dev/null 2>&1
  local LINKED
  LINKED=$(gcloud billing projects describe "$PID" --format='value(billingEnabled)' 2>/dev/null)
  if [ "$LINKED" != "True" ]; then
    if ! gcloud billing projects link "$PID" --billing-account="$BA" >/dev/null 2>/tmp/ss_err; then
      cat /tmp/ss_err
      die "프로젝트에 결제 계정을 붙이지 못했습니다(위 메시지)."; return 1
    fi
  fi
  ok "결제 연결됨"

  # ── 3. API 사용 ─────────────────────────────────────────────
  say "3/5 Agent Platform(버텍스) API 사용 설정 — 1분쯤 걸립니다"
  if ! retry 3 10 gcloud services enable aiplatform.googleapis.com iam.googleapis.com \
         orgpolicy.googleapis.com cloudresourcemanager.googleapis.com --project="$PID"; then
    cat /tmp/ss_err; die "API를 켜지 못했습니다(위 메시지)."; return 1
  fi
  ok "API 켜짐"

  # ── 4. 서비스 계정 + 역할 ──────────────────────────────────
  say "4/5 서비스 계정과 역할(Agent Platform 사용자)"
  local SA="$SA_NAME@$PID.iam.gserviceaccount.com"
  if ! gcloud iam service-accounts describe "$SA" --project="$PID" >/dev/null 2>&1; then
    if ! retry 3 10 gcloud iam service-accounts create "$SA_NAME" --display-name="shortsmaker" --project="$PID" --quiet; then
      cat /tmp/ss_err; die "서비스 계정을 만들지 못했습니다(위 메시지)."; return 1
    fi
  fi
  ok "서비스 계정: $SA"
  if ! retry 6 10 gcloud projects add-iam-policy-binding "$PID" --member="serviceAccount:$SA" \
         --role="roles/aiplatform.user" --condition=None --quiet; then
    cat /tmp/ss_err; die "역할을 넣지 못했습니다(위 메시지)."; return 1
  fi
  ok "역할 넣음"

  # ── 5. 키 만들기 (막히면 이 프로젝트만 차단을 푼다) ─────────
  say "5/5 키 만들기"
  local KEY="$HOME/shortsmaker-key.json"
  rm -f "$KEY"
  mkkey() { gcloud iam service-accounts keys create "$KEY" --iam-account="$SA" --project="$PID" --quiet; }
  if ! mkkey >/dev/null 2>/tmp/ss_err; then
    if grep -qi 'disableServiceAccountKeyCreation' /tmp/ss_err; then
      warn "구글이 새 계정에 걸어 둔 「키 생성 차단」이 있어 이 프로젝트만 풉니다(1~3분)"
      local ORG
      ORG=$(gcloud projects get-ancestors "$PID" --format='value(id,type)' 2>/dev/null | awk '$2=="organization"{print $1}')
      if [ -n "$ORG" ]; then
        # 정책을 바꾸려면 조직 정책 관리자 역할이 있어야 한다(설명서의 「나에게 권한 주기」)
        gcloud organizations add-iam-policy-binding "$ORG" --member="user:$ACCOUNT" \
          --role="roles/orgpolicy.policyAdmin" --condition=None --quiet >/dev/null 2>&1 \
          && ok "나에게 조직 정책 관리자 권한 줌" || warn "권한 주기 실패 — 이미 있으면 괜찮습니다"
      fi
      local c f
      for c in iam.disableServiceAccountKeyCreation iam.managed.disableServiceAccountKeyCreation; do
        f="/tmp/ss_pol_$c.yaml"
        printf 'name: projects/%s/policies/%s\nspec:\n  rules:\n  - enforce: false\n' "$PID" "$c" > "$f"
        retry 12 15 gcloud org-policies set-policy "$f" --quiet \
          && ok "차단 해제: $c" || warn "$c 해제 안 됨(이 계정엔 없는 정책일 수 있음)"
      done
      printf '  키를 다시 만듭니다'
      local i made=0
      for ((i=1;i<=16;i++)); do
        if mkkey >/dev/null 2>/tmp/ss_err; then made=1; break; fi
        printf '.'; sleep 15
      done
      printf '\n'
      [ "$made" = 1 ] || { cat /tmp/ss_err; die "키를 만들지 못했습니다(위 메시지). 5분 뒤 같은 명령을 다시 붙여넣어 주세요."; return 1; }
    else
      cat /tmp/ss_err; die "키를 만들지 못했습니다(위 메시지)."; return 1
    fi
  fi
  ok "키 만듦"

  # ── 끝: 한 줄짜리 JSON으로 보여준다(복사가 쉽게) ────────────
  printf '\n%s━━━━━━━━ 아래 { 부터 } 까지 전부 복사하세요 ━━━━━━━━%s\n\n' "$G" "$N"
  python3 -c 'import json,sys;print(json.dumps(json.load(open(sys.argv[1])),separators=(",",":")))' "$KEY"
  printf '\n%s━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━%s\n' "$G" "$N"
  printf '숏템메이커 › 마이페이지 › 🔑 내 키 등록 › 🚀 구글 버텍스 API 에 붙여넣고 「확인하고 연결」을 누르세요.\n'
  printf '「권한이 없습니다」가 뜨면 역할이 반영되는 중입니다 — 5분 뒤 다시 눌러 주세요.\n'
  printf '이 키는 비밀번호와 같아요. 다른 곳에 올리지 마세요.\n\n'
}

main "$@"
