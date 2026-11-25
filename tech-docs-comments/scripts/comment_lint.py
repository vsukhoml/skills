#!/usr/bin/env python3
"""Lints staged Google Docs comments and replies for tech-docs-comments rules.

Usage:
  python3 comment_lint.py [--mode review|triage] [--markdown-converted] FILE...

Supported inputs:
  - JSON (.json): list of comment objects or {"comments": [...]}, each with:
      "text": comment or reply body (string, required unless resolve=true test)
      "action": "add" | "reply" | "suggest_reason" | "resolve" (optional)
      "mode": "review" | "triage" (optional override of --mode)
      "anchor": anchored document substring for "add" comments (optional)
      "paragraph_id": paragraph key for advisory pile-up checks (optional)
      "resolve": bool indicating thread resolution (optional)
      "assignee": email passed to --assignee (optional)
  - Markdown (.md): bulleted (- / * / 1.) or ###-headed staged comment cards.
"""

import argparse
from collections.abc import Sequence
import dataclasses
import json
import pathlib
import re
import sys

MAX_UTF8_BYTES = 2048
RECOMMENDED_WORDS = 45
SOFT_DETAIL_WORDS = 60
HARD_MAX_WORDS = 120
PREVIEW_CHARS = 100
MIN_ANCHOR_WORDS = 3
MAX_ANCHOR_WORDS = 10
MIN_ANCHOR_CHARS = 15
MAX_ANCHOR_CHARS = 80
RECOMMENDED_CARDS_PER_PARA = 2

_WORD_RE = re.compile(r"[A-Za-z0-9_]+(?:'[A-Za-z0-9_]+)?")
_REVIEW_PREFIX = re.compile(
    r'^(?:\[AI Review\]\s*)?'
    r'(?:Blocking|Question(?:\s*\(blocking\))?|Suggestion|Optional|Nit|FYI):',
)
_TRIAGE_SEVERITY_PREFIX = re.compile(
    r'^(?:Blocking|Question(?:\s*\(blocking\))?|Suggestion|Optional|Nit):',
    re.IGNORECASE,
)
_TRIAGE_OUTCOME_PREFIX = re.compile(
    r'^(?:[\U0001f44d\u2705]\s*)?(?:Done|Agreed|Updated|Tracked|Deferred|'
    r'Resolved|Fixed)\s*:',
    re.IGNORECASE,
)
_RESOLVED_OPENER = re.compile(
    r'^(?:[\U0001f44d\u2705]\s*)?resolved\b\s*[:,-]?',
    re.IGNORECASE,
)
_WHY_PREFIX = re.compile(r'^\s*why\s*:', re.IGNORECASE)
_BUNDLE_CUE = re.compile(
    r'(?:(?:^|[.!?]\s+)(?:Also|Additionally|Separately|Second(?:ly)?|'
    r'Another\s+(?:issue|point|question))\s*[,:]|'
    r'(?:^|\n)\s*2[.)]\s+\S)',
    re.IGNORECASE,
)
_FENCED_CODE = re.compile(r'```|~~~')
_RAW_MD_LINK = re.compile(r'\[[^\]\n]+\]\(https?://[^)\s]+\)')
_RAW_BACKTICK = re.compile(r'`[^`\n]+`')
_RAW_DOUBLE_BOLD = re.compile(r'\*\*[^*\n]+\*\*')
_EYES_EMOJI = re.compile(r'\U0001f440')
_LOOKING_STATUS = re.compile(
    r'^\s*(?:taking a look|looking into this|will take a look)\s*[.!]*\s*$',
    re.IGNORECASE,
)
_EMOJI_CHAR = re.compile(r'[\U0001f300-\U0001faff\u2600-\u27bf]')
_ALLOWED_EMOJI = frozenset({'\U0001f44d', '\u2705'})
_EMAIL_MENTION = re.compile(
    r'(?<![A-Za-z0-9._%+-])[+@]'
    r'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})'
)
_BARE_AT_MENTION = re.compile(
    r'(?<![A-Za-z0-9._%+-])@([A-Za-z][A-Za-z0-9_-]{1,30})(?!@[A-Za-z0-9.-])'
)
_CODE_ANNOTATIONS = frozenset({
    'override',
    'deprecated',
    'nullable',
    'nonnull',
    'param',
    'return',
    'returns',
    'throws',
    'property',
    'staticmethod',
    'classmethod',
    'dataclass',
    'test',
})
_ROLE_CUE = re.compile(
    r'(?:\bfyi\b\s*:?|\[\s*(?:assigned|fyi)\s*\]|\bassigned\s+to\b|'
    r'\bdri\b\s*:)',
    re.IGNORECASE,
)
_SYNC_PROPOSAL = re.compile(
    r'\b(?:15[-\s]min(?:ute)?\s+sync|'
    r'propos(?:e|ing)\s+a\s+(?:short\s+)?sync)\b',
    re.IGNORECASE,
)


@dataclasses.dataclass(frozen=True)
class Finding:
  """Represents a rule violation or advisory on a staged comment."""

  line: int
  rule: str
  message: str
  advisory: bool = False


@dataclasses.dataclass(frozen=True)
class StagedComment:
  """Normalized comment or reply item loaded from JSON or Markdown."""

  line: int
  text: str
  action: str = ''
  mode: str = ''
  anchor: str = ''
  paragraph_id: str = ''
  resolve: bool = False
  assignee: str = ''


def _count_words(text: str) -> int:
  """Counts word tokens in a comment body."""
  return len(_WORD_RE.findall(text))


def _has_frontloaded_summary(text: str) -> bool:
  """Checks whether the first 100 chars contain a complete summary clause."""
  head = text.strip()[:PREVIEW_CHARS]
  body = _REVIEW_PREFIX.sub('', head, count=1).strip()
  body = _TRIAGE_OUTCOME_PREFIX.sub('', body, count=1).strip()
  if not body:
    return False
  return bool(re.search(r'[.!?;—:]\s|\.$|[.!?]$', body))


def _check_emojis(text: str, line: int, out: list[Finding]) -> None:
  """Checks C10 emoji rules (no eyes, no text-duplicating or arbitrary emojis)."""
  if _EYES_EMOJI.search(text) or _LOOKING_STATUS.match(text):
    out.append(
        Finding(
            line,
            'C10',
            'intermediate "looking" status (👀): finish inspection and post '
            'the substantive comment or reply directly',
        )
    )
  bad_emojis = sorted(
      {ch for ch in _EMOJI_CHAR.findall(text) if ch not in _ALLOWED_EMOJI}
      - {'\U0001f440'}
  )
  if bad_emojis:
    joined = ' '.join(bad_emojis)
    out.append(
        Finding(
            line,
            'C10',
            f'non-standard emoji ({joined}): omit emojis in prose, or use '
            'standalone 👍 (Agreed) and ✅ (Done) only',
        )
    )
  used_allowed = sorted({ch for ch in text if ch in _ALLOWED_EMOJI})
  if used_allowed and _count_words(text) > 0:
    joined = ' '.join(used_allowed)
    out.append(
        Finding(
            line,
            'C10',
            f'emoji ({joined}) duplicates accompanying text: omit emojis when '
            'prose states the outcome (write "Done: ..." or "Agreed ...", '
            'reserving 👍 and ✅ for standalone replies)',
        )
    )


def _check_mentions(item: StagedComment, out: list[Finding]) -> None:
  """Checks C13 @-mention email format and multi-person role clarity."""
  text = item.text
  for match in _BARE_AT_MENTION.finditer(text):
    token = match.group(1)
    if token.lower() in _CODE_ANNOTATIONS:
      continue
    out.append(
        Finding(
            item.line,
            'C13',
            f'bare "@{token}" mention: use full email '
            f'(+{token}@example.com or @{token}@example.com)',
        )
    )
  emails = [m.group(1).lower() for m in _EMAIL_MENTION.finditer(text)]
  unique_emails = list(dict.fromkeys(emails))
  if len(unique_emails) >= 2 and not (
      item.assignee or _ROLE_CUE.search(text) or _SYNC_PROPOSAL.search(text)
  ):
    out.append(
        Finding(
            item.line,
            'C13',
            f'{len(unique_emails)} people mentioned without assignee or FYI '
            'labels: assign one DRI (--assignee) and mark others FYI',
        )
    )


def _check_anchor(anchor: str, line: int, out: list[Finding]) -> None:
  """Checks C8 anchor span length and single-paragraph containment."""
  if not anchor:
    return
  if '\n' in anchor:
    out.append(
        Finding(
            line,
            'C8',
            'anchor spans a newline: anchor inside one paragraph or cell',
        )
    )
  words = _count_words(anchor)
  chars = len(anchor.strip())
  if words < MIN_ANCHOR_WORDS or chars < MIN_ANCHOR_CHARS:
    out.append(
        Finding(
            line,
            'C8',
            f'anchor "{anchor}" is {words} words ({chars} chars): '
            'use a unique 3-to-10-word (15 to 80 char) phrase',
        )
    )
  elif words > MAX_ANCHOR_WORDS or chars > MAX_ANCHOR_CHARS:
    out.append(
        Finding(
            line,
            'C8',
            f'anchor is {words} words ({chars} chars): '
            'keep anchors to 3 to 10 words (15 to 80 chars)',
        )
    )


def _lint_item(
    item: StagedComment,
    default_mode: str,
    markdown_converted: bool,
) -> list[Finding]:
  """Checks one staged comment, reply, suggestion reason, or resolution."""
  out: list[Finding] = []
  mode = (item.mode or default_mode).lower()
  default_action = 'reply' if mode == 'triage' else 'add'
  action = (item.action or default_action).lower()
  text = item.text.strip()

  if item.resolve and not text:
    out.append(
        Finding(
            item.line,
            'C11',
            'silent thread resolution with empty reply: state the outcome '
            '(for example, "Done: updated Section 3.") before resolving',
        )
    )
    return out

  if action == 'suggest_reason' and not text:
    out.append(
        Finding(
            item.line,
            'C3',
            'Suggesting-mode edit lacks a brief reason comment on suggest.<ID>',
        )
    )
    return out

  utf8_len = len(item.text.encode('utf-8'))
  if utf8_len > MAX_UTF8_BYTES:
    out.append(
        Finding(
            item.line,
            'C6',
            f'comment payload is {utf8_len} UTF-8 bytes '
            f'(Google Docs API hard limit {MAX_UTF8_BYTES})',
        )
    )

  if '\n\n' in text:
    out.append(
        Finding(
            item.line,
            'C4',
            'blank line (\\n\\n) inside comment burns 20 px and triggers '
            'early 150 px collapse: write 1 paragraph or split into separate '
            'comments',
        )
    )

  if _FENCED_CODE.search(text):
    out.append(
        Finding(
            item.line,
            'C6',
            'fenced code block inside margin comment: move multi-line code '
            'to document prose or Suggesting mode',
        )
    )
  elif not markdown_converted:
    if _RAW_BACKTICK.search(text):
      out.append(
          Finding(
              item.line,
              'C6',
              'raw backtick code in comment: convert before upload '
              '(--markdown-converted) or use plain text / *bold*',
          )
      )
    if _RAW_MD_LINK.search(text):
      out.append(
          Finding(
              item.line,
              'C6',
              'Markdown [label](url) link in comment: use bare URL or convert '
              'before upload (--markdown-converted)',
          )
      )
    if _RAW_DOUBLE_BOLD.search(text):
      out.append(
          Finding(
              item.line,
              'C6',
              'Markdown **bold** in comment: Google Docs uses single *bold*, '
              'or convert before upload (--markdown-converted)',
          )
      )

  words = _count_words(text)
  if words > HARD_MAX_WORDS:
    out.append(
        Finding(
            item.line,
            'C4',
            f'comment is {words} words (recommended <= {RECOMMENDED_WORDS}, '
            f'hard cap {HARD_MAX_WORDS}): move detail to prose or split cards',
        )
    )
  elif words > RECOMMENDED_WORDS:
    if not _has_frontloaded_summary(text):
      out.append(
          Finding(
              item.line,
              'C4',
              f'comment of {words} words exceeds {RECOMMENDED_WORDS} words '
              f'without a complete summary clause in the first {PREVIEW_CHARS} '
              'characters (78 px collapsed preview)',
          )
      )
    elif words > SOFT_DETAIL_WORDS:
      out.append(
          Finding(
              item.line,
              'C4',
              f'comment is {words} words (recommended <= {RECOMMENDED_WORDS}): '
              'keep detail only if needed and verify separate points are '
              'not bundled',
              advisory=True,
          )
      )

  if _BUNDLE_CUE.search(text):
    out.append(
        Finding(
            item.line,
            'C5',
            'multi-point bundling cue ("Also," / numbered items) in one card: '
            'post loosely connected points as separate short comments',
        )
    )

  if action == 'suggest_reason':
    if _WHY_PREFIX.match(text):
      out.append(
          Finding(
              item.line,
              'C3',
              'Suggesting-mode reason starts with "Why:": state the reason '
              'directly without a "Why: " prefix',
          )
      )
  elif mode == 'review' and action == 'add':
    if not _REVIEW_PREFIX.match(text):
      out.append(
          Finding(
              item.line,
              'C7',
              'root Review comment lacks severity prefix (Blocking:, '
              'Question:, Suggestion:, Optional:, Nit:, or FYI:)',
          )
      )
    _check_anchor(item.anchor, item.line, out)
  elif mode == 'triage' and action in ('reply', 'resolve'):
    if _TRIAGE_SEVERITY_PREFIX.match(text):
      out.append(
          Finding(
              item.line,
              'C7',
              'Triage reply starts with reviewer severity prefix: start '
              'directly with the outcome ("Done: ...", "Updated ...", or '
              'factual trade-off answer)',
          )
      )

  if (
      (mode == 'triage' and action in ('reply', 'resolve'))
      or action == 'resolve'
  ) and _RESOLVED_OPENER.match(text):
    out.append(
        Finding(
            item.line,
            'C7',
            'reply opens with "Resolved": prefer "Done:" (or state the '
            'substantive outcome directly)',
        )
    )

  _check_emojis(text, item.line, out)
  _check_mentions(item, out)
  return out


def _parse_json_comments(content: str) -> list[StagedComment]:
  """Loads staged comments from a JSON array or {"comments": [...]} object."""
  data = json.loads(content)
  raw_items = data.get('comments', []) if isinstance(data, dict) else data
  if not isinstance(raw_items, list):
    raise ValueError('JSON root must be a list or {"comments": [...]} object')
  items: list[StagedComment] = []
  for idx, entry in enumerate(raw_items, start=1):
    if isinstance(entry, str):
      items.append(StagedComment(line=idx, text=entry))
      continue
    if not isinstance(entry, dict):
      raise ValueError(f'comment entry {idx} must be an object or string')
    items.append(
        StagedComment(
            line=int(entry.get('line', idx)),
            text=str(entry.get('text', '')),
            action=str(entry.get('action', '')),
            mode=str(entry.get('mode', '')),
            anchor=str(entry.get('anchor', '')),
            paragraph_id=str(entry.get('paragraph_id', '')),
            resolve=bool(entry.get('resolve', False)),
            assignee=str(entry.get('assignee', '')),
        )
    )
  return items


def _parse_markdown_comments(content: str) -> list[StagedComment]:
  """Extracts bulleted or ###-headed staged comments from a Markdown file."""
  items: list[StagedComment] = []
  lines = content.splitlines()
  in_fence = False
  in_h3_card = False
  current_line = 0
  current_buf: list[str] = []

  def _flush() -> None:
    nonlocal in_h3_card
    text = '\n'.join(current_buf).strip()
    if text:
      items.append(StagedComment(line=current_line, text=text))
    current_buf.clear()
    in_h3_card = False

  bullet_re = re.compile(r'^\s*(?:[-*+]|\d+[.)])\s+(.*)$')
  for idx, raw in enumerate(lines, start=1):
    stripped = raw.strip()
    if stripped.startswith('```') or stripped.startswith('~~~'):
      in_fence = not in_fence
      if current_buf or in_h3_card:
        current_buf.append(raw)
      continue
    if in_fence:
      if current_buf or in_h3_card:
        current_buf.append(raw)
      continue
    if stripped.startswith('### '):
      _flush()
      in_h3_card = True
      current_line = idx + 1
      continue
    if stripped.startswith('#'):
      _flush()
      continue
    match = bullet_re.match(raw)
    if match and not in_h3_card:
      _flush()
      current_line = idx
      current_buf.append(match.group(1))
    elif in_h3_card:
      if not current_buf and not stripped:
        current_line = idx + 1
      else:
        current_buf.append(stripped)
    elif current_buf:
      if not stripped:
        current_buf.append('')
      elif raw.startswith('  ') or raw.startswith('\t'):
        current_buf.append(stripped)
      else:
        _flush()
  _flush()
  return items


def lint_comments(
    items: Sequence[StagedComment],
    default_mode: str = 'review',
    markdown_converted: bool = False,
) -> list[Finding]:
  """Lints staged comment entries and checks paragraph pile-up advisories."""
  findings: list[Finding] = []
  para_counts: dict[str, list[int]] = {}
  for item in items:
    findings.extend(_lint_item(item, default_mode, markdown_converted))
    eff_mode = (item.mode or default_mode).lower()
    default_act = 'reply' if eff_mode == 'triage' else 'add'
    eff_act = (item.action or default_act).lower()
    if eff_mode == 'review' and eff_act == 'add' and item.paragraph_id:
      para_counts.setdefault(item.paragraph_id, []).append(item.line)

  for para_id, lines in para_counts.items():
    if len(lines) > RECOMMENDED_CARDS_PER_PARA:
      findings.append(
          Finding(
              lines[0],
              'C8',
              f'{len(lines)} Review comments target paragraph "{para_id}" '
              f'(recommended <= {RECOMMENDED_CARDS_PER_PARA}): check for '
              '>= 2/3 thread overlap without dropping important findings',
              advisory=True,
          )
      )
  return sorted(findings, key=lambda f: (f.line, f.advisory, f.rule))


def lint_file(
    path_arg: str,
    default_mode: str,
    markdown_converted: bool,
) -> tuple[str, list[Finding]]:
  """Reads and lints a JSON or Markdown staged-comments file."""
  if path_arg == '-':
    raw = sys.stdin.read()
    stripped = raw.lstrip()
    items = (
        _parse_json_comments(raw)
        if stripped.startswith(('[', '{'))
        else _parse_markdown_comments(raw)
    )
    return '<stdin>', lint_comments(items, default_mode, markdown_converted)

  path = pathlib.Path(path_arg)
  raw = path.read_text(encoding='utf-8')
  if path.suffix.lower() == '.json':
    items = _parse_json_comments(raw)
  else:
    items = _parse_markdown_comments(raw)
  return path_arg, lint_comments(items, default_mode, markdown_converted)


def main(argv: Sequence[str]) -> int:
  """Runs the comment_lint CLI and returns the exit status."""
  parser = argparse.ArgumentParser(
      description='Lint staged Google Docs comments for tech-docs-comments.',
  )
  parser.add_argument(
      '--mode',
      choices=('review', 'triage'),
      default='review',
      help='Default workflow mode when entries omit "mode" (default: review).',
  )
  parser.add_argument(
      '--markdown-converted',
      action='store_true',
      help='Allow Markdown inline syntax converted before Drive API upload.',
  )
  parser.add_argument(
      'files',
      nargs='*',
      help='Staged .json or .md comment files (or "-" for stdin).',
  )
  args = parser.parse_args(list(argv[1:]))
  if not args.files:
    parser.print_help()
    return 2

  exit_code = 0
  for path_arg in args.files:
    try:
      label, all_items = lint_file(
          path_arg,
          args.mode,
          args.markdown_converted,
      )
    except (OSError, ValueError, json.JSONDecodeError) as err:
      print(f'{path_arg}: cannot lint file: {err}', file=sys.stderr)
      return 2

    errors = [f for f in all_items if not f.advisory]
    advisories = [f for f in all_items if f.advisory]
    for finding in all_items:
      tag = f'{finding.rule} (advisory)' if finding.advisory else finding.rule
      print(f'{label}:{finding.line}: {tag}: {finding.message}')
    err_noun = 'finding' if len(errors) == 1 else 'findings'
    adv_noun = 'advisory' if len(advisories) == 1 else 'advisories'
    print(f'{label}: {len(errors)} {err_noun}, {len(advisories)} {adv_noun}')
    if errors:
      exit_code = 1
  return exit_code


if __name__ == '__main__':
  sys.exit(main(sys.argv))
