#!/usr/bin/env bash
# harden-build/scripts/check-elf.sh — READ-ONLY ELF binary hardening verifier.
#
# Inspects ELF executables and shared libraries using only GNU binutils `readelf`
# (no checksec/python dependency). Distinguishes static Go/Rust/C binaries from
# dynamically linked C/C++/Rust/CGO binaries and Python/Node native `.so` wheels
# so static CGO_ENABLED=0 builds are not false-flagged for missing libc symbols.
#
# Usage:
#   check-elf.sh [--strict] [--require-cfi] [--] FILE_OR_DIR [...]
#
# Options:
#   --strict       Exit 1 on hard defects: executable stack (RWE), RWX segment,
#                  dynamically linked non-PIE executable, missing/partial RELRO
#                  on dynamically linked or static-pie ELF files, or linked dev
#                  sanitizer runtimes (ASan/TSan/MSan/UBSan).
#   --require-cfi  With --strict, also require hardware CFI notes (x86_64 IBT+SHSTK
#                  or aarch64 BTI+PAC) on non-Go ELF files.

set -u
export LC_ALL=C

STRICT=0
REQ_CFI=0
TARGETS=()

usage() {
  sed -n '2,/^$/s/^# \{0,1\}//p' "$0"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --strict) STRICT=1 ;;
    --require-cfi) REQ_CFI=1 ;;
    -h | --help) usage; exit 0 ;;
    --) shift; TARGETS+=("$@"); break ;;
    -*) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
    *) TARGETS+=("$1") ;;
  esac
  shift
done

if [ "${#TARGETS[@]}" -eq 0 ]; then
  usage >&2
  exit 2
fi

if ! command -v readelf >/dev/null 2>&1; then
  echo "error: readelf (binutils) is required" >&2
  exit 2
fi

is_elf() {
  local f="$1" magic
  [ -f "$f" ] && [ -r "$f" ] || return 1
  magic=$(od -An -tx1 -N4 "$f" 2>/dev/null | tr -d ' \n')
  [ "$magic" = "7f454c46" ]
}

FAILS=0
COUNT=0

printf '%-34s %-10s %-10s %-8s %-6s %-8s %-11s %-12s %s\n' \
  "BINARY" "KIND" "PIE" "RELRO" "NX" "CANARY" "HW-CFI" "META" "ISSUES"
printf '%-34s %-10s %-10s %-8s %-6s %-8s %-11s %-12s %s\n' \
  "----------------------------------" "----------" "----------" "--------" "------" "--------" "-----------" "------------" "------"

check_one() {
  local f="$1"
  local hdr phdrs dyn notes secs syms
  hdr=$(readelf -h "$f" 2>/dev/null) || return 0
  phdrs=$(readelf -lW "$f" 2>/dev/null)
  dyn=$(readelf -d "$f" 2>/dev/null)
  notes=$(readelf -n "$f" 2>/dev/null)
  secs=$(readelf -SW "$f" 2>/dev/null)
  syms=$(readelf -sW "$f" 2>/dev/null)

  COUNT=$((COUNT + 1))

  local etype machine has_interp=0 has_dyn=0 is_go=0 has_auditable=0
  etype=$(printf '%s\n' "$hdr" | awk '/^\s*Type:/{print $2; exit}')
  machine=$(printf '%s\n' "$hdr" | awk -F: '/^\s*Machine:/{gsub(/^[ \t]+/,"",$2); print $2; exit}')
  printf '%s\n' "$phdrs" | grep -q '^\s*INTERP\b' && has_interp=1
  printf '%s\n' "$phdrs" | grep -q '^\s*DYNAMIC\b' && has_dyn=1
  printf '%s\n' "$secs" | grep -qE '\.go\.buildinfo|\.gopclntab' && is_go=1
  printf '%s\n' "$secs" | grep -q '\.dep-v0' && has_auditable=1

  local kind="dyn-exe" pie="NO-PIE"
  if [ "$etype" = "EXEC" ]; then
    if [ "$has_interp" -eq 0 ]; then
      kind="static"
      pie="static"
    else
      kind="dyn-exe"
      pie="NO-PIE"
    fi
  elif [ "$etype" = "DYN" ]; then
    if [ "$has_interp" -eq 1 ]; then
      kind="dyn-exe"
      pie="PIE"
    elif printf '%s\n' "$dyn" | grep -qE '\(FLAGS_1\).*\bPIE\b'; then
      if printf '%s\n' "$dyn" | grep -q '(NEEDED)'; then
        kind="dyn-exe"
        pie="PIE"
      else
        kind="static-pie"
        pie="STATIC-PIE"
      fi
    else
      kind="shared-lib"
      pie="DSO"
    fi
  else
    kind="$etype"
    pie="$etype"
  fi
  [ "$is_go" -eq 1 ] && [ "$kind" = "static" ] && kind="go-static"
  [ "$is_go" -eq 1 ] && [ "$kind" = "dyn-exe" ] && kind="go-cgo"

  # RELRO
  local relro="N/A"
  if [ "$has_dyn" -eq 1 ] && [ "$kind" != "static" ]; then
    if printf '%s\n' "$phdrs" | grep -q '^\s*GNU_RELRO\b'; then
      if printf '%s\n' "$dyn" | grep -qE '\bBIND_NOW\b|\(FLAGS_1\).*\bNOW\b'; then
        relro="FULL"
      else
        relro="PARTIAL"
      fi
    else
      relro="NONE"
    fi
  fi

  # NX stack & W+X segments
  local nx="NX" rwx=0
  if printf '%s\n' "$phdrs" | awk '$1=="GNU_STACK"{print}' | grep -q 'E'; then
    nx="EXEC!"
  fi
  if printf '%s\n' "$phdrs" | awk '$1=="LOAD"{print}' | grep -qE 'RWE|W E'; then
    rwx=1
    nx="RWX!"
  fi

  # Canary & Fortify
  local canary="-" meta="-"
  if [ "$is_go" -eq 1 ] && [ "$kind" = "go-static" ]; then
    canary="go-rt"
  elif printf '%s\n' "$syms" | grep -qE '__stack_chk_fail|__stack_chk_guard'; then
    canary="yes"
  elif [ "$has_dyn" -eq 1 ]; then
    canary="no"
  fi

  local mlist=()
  printf '%s\n' "$syms" | grep -qE '__[a-z0-9_]+_chk(@|$| )' && mlist+=("fortify")
  printf '%s\n' "$syms" | grep -qE '__cfi_check|__cfi_slowpath|\.cfi($| )' && mlist+=("clang-cfi")
  [ "$is_go" -eq 1 ] && printf '%s\n' "$secs" | grep -q '\.go\.buildinfo' && mlist+=("buildinfo")
  [ "$has_auditable" -eq 1 ] && mlist+=("auditable")
  if printf '%s\n' "$syms" | grep -qE '__asan_|__tsan_|__msan_|__ubsan_handle_'; then
    mlist+=("SANITIZER!")
  fi
  [ "${#mlist[@]}" -gt 0 ] && meta=$(IFS=,; echo "${mlist[*]}")

  # Hardware CFI notes (x86_64 CET: IBT, SHSTK; AArch64: BTI, PAC)
  local hwcfi="-"
  case "$machine" in
    *X86-64*)
      local ibt=0 shstk=0
      printf '%s\n' "$notes" | grep -q '\bIBT\b' && ibt=1
      printf '%s\n' "$notes" | grep -q '\bSHSTK\b' && shstk=1
      if [ "$ibt" -eq 1 ] && [ "$shstk" -eq 1 ]; then hwcfi="ibt+shstk"
      elif [ "$ibt" -eq 1 ]; then hwcfi="ibt-only"
      elif [ "$shstk" -eq 1 ]; then hwcfi="shstk-only"
      else hwcfi="none"; fi
      ;;
    *AArch64*)
      local bti=0 pac=0
      printf '%s\n' "$notes" | grep -q '\bBTI\b' && bti=1
      printf '%s\n' "$notes" | grep -q '\bPAC\b' && pac=1
      if [ "$bti" -eq 1 ] && [ "$pac" -eq 1 ]; then hwcfi="bti+pac"
      elif [ "$bti" -eq 1 ]; then hwcfi="bti-only"
      elif [ "$pac" -eq 1 ]; then hwcfi="pac-only"
      else hwcfi="none"; fi
      ;;
  esac

  # Evaluate issues
  local issues=()
  [ "$nx" = "EXEC!" ] && issues+=("executable-stack")
  [ "$rwx" -eq 1 ] && issues+=("rwx-segment")
  [ "$pie" = "NO-PIE" ] && issues+=("no-pie")
  if [ "$kind" = "dyn-exe" ] || [ "$kind" = "go-cgo" ] || [ "$kind" = "shared-lib" ] || [ "$kind" = "static-pie" ]; then
    [ "$relro" = "NONE" ] && issues+=("no-relro")
    [ "$relro" = "PARTIAL" ] && issues+=("partial-relro")
  fi
  if printf '%s' "$meta" | grep -q 'SANITIZER!'; then
    issues+=("dev-sanitizer-in-binary")
  fi
  if [ "$REQ_CFI" -eq 1 ] && [ "$is_go" -eq 0 ]; then
    case "$hwcfi" in
      ibt+shstk | bti+pac | -) ;;
      *) issues+=("missing-hw-cfi($hwcfi)") ;;
    esac
  fi

  local issue_str="ok"
  if [ "${#issues[@]}" -gt 0 ]; then
    issue_str=$(IFS=,; echo "${issues[*]}")
    FAILS=$((FAILS + 1))
  fi

  local disp="$f"
  [ "${#disp}" -gt 34 ] && disp="...${disp: -31}"
  printf '%-34s %-10s %-10s %-8s %-6s %-8s %-11s %-12s %s\n' \
    "$disp" "$kind" "$pie" "$relro" "$nx" "$canary" "$hwcfi" "$meta" "$issue_str"
}

for t in "${TARGETS[@]}"; do
  if [ -d "$t" ]; then
    while IFS= read -r -d '' cand; do
      is_elf "$cand" && check_one "$cand"
    done < <(find -H "$t" -type f -print0 2>/dev/null | sort -z)
  elif is_elf "$t"; then
    check_one "$t"
  elif [ ! -e "$t" ]; then
    echo "error: path not found: $t" >&2
    exit 2
  fi
done

if [ "$COUNT" -eq 0 ]; then
  echo "no ELF files found in targets" >&2
  exit 2
fi

if [ "$STRICT" -eq 1 ] && [ "$FAILS" -gt 0 ]; then
  printf '\nFAILED (--strict): %d of %d ELF file(s) had hardening gaps.\n' "$FAILS" "$COUNT" >&2
  exit 1
fi
exit 0
