#!/usr/bin/env python3
"""Collects Google Docs review-round deltas, staleness stages, and lint checks.

Usage:
  python3 review_round_collect.py collect [--lookback-days 3] [--output OUT]
  python3 review_round_collect.py ack --doc URL_OR_ID [--refresh-live]
  [--defer-thread ID]
  python3 review_round_collect.py watchlist --add URL_OR_ID [--deadline DATE]

Authentication (read-only Google Drive v3, Docs v1, and Calendar v3 REST APIs):
  1. GOOGLE_OAUTH_ACCESS_TOKEN (or GOOGLE_ACCESS_TOKEN) environment variable
  2. --token-cmd SHELL_CMD (or GOOGLE_OAUTH_TOKEN_CMD environment variable)
  3. Automatic fallback to `gcloud auth application-default print-access-token`
     or `gcloud auth print-access-token`

Subcommands:
  collect    Discovers active Google Docs (watchlist.json + 2-3 day heuristics +
             45-day open-thread carryover), exports tabs, computes cumulative
             diffs since the last ack (auto-acking clean self-only edits),
             checks reply sentiment, deferred-thread wakeups, and multi-stage
             idle time (with >1-week OOO subtraction and business-day floors),
             and runs doc_lint.py, diagram_lint.py, and anchor checks on
             authored documents.
  ack        Advances ack_<tab_id>.md from local digest_<tab_id>.md (or live
             tabs with --refresh-live), records per-thread deferrals
             (--defer-thread), and preserves post-digest collaborator replies.
  watchlist  Adds, mutes, removes, or lists entries in watchlist.json.
"""

import argparse
from collections.abc import Callable, Mapping, Sequence
import dataclasses
import datetime
import difflib
import hashlib
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile
import time
import types
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

JsonDict = dict[str, Any]
HttpFetcher = Callable[[str, Mapping[str, str]], tuple[int, str]]

DEFAULT_LOOKBACK_DAYS = 3
OOO_MIN_EXCLUDED_DAYS = 7.0
POST_ACTIVITY_MIN_OFFSET_DAYS = 1.0
LEGACY_BACKLOG_DAYS = 60.0
RECENT_MENTION_DAYS = 14.0
CARRYOVER_HORIZON_DAYS = 45.0
DEFAULT_DEFER_DAYS = 7.0
COLLABORATOR_MAX_ALL_TABS = 5

_DEFAULT_HTTP_TIMEOUT_S = 60
_RETRY_BACKOFF_S = 5.0
_FENCE_NO_LANG_MSG = 'Code fence lacks a language tag'

_DRIVE_API = 'https://www.googleapis.com/drive/v3'
_DOCS_API = 'https://docs.googleapis.com/v1'
_CAL_API = 'https://www.googleapis.com/calendar/v3'

_DOC_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{9,127}$')
_TAB_ID_RE = re.compile(r'^t\.[A-Za-z0-9_-]+$')
_COMMENT_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$')
_URL_DOC_ID_RE = re.compile(r'/document/d/([A-Za-z0-9][A-Za-z0-9_-]{9,127})')
_EMAIL_MENTION_RE = re.compile(
    r'(?<![A-Za-z0-9._%+-])[+@]'
    r'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})'
)
_DONE_REPLY_RE = re.compile(
    r'^(?:[\U0001f44d\u2705]\s*)?(?:done|updated|added|fixed|resolved)\b',
    re.IGNORECASE,
)
_DISAGREE_OR_CHANGE_CUE_RE = re.compile(
    r'\b(?:but|however|although|though|except|unless|instead|whereas|disagree|'
    r"not\s+sure|don't\s+think|do\s+not\s+think|prefer|should|need\s+to|"
    r'needs\s+to|must|please|could\s+we|can\s+we|would\s+be\s+better|'
    r"let's|lets|what\s+if|still\s+need|wait|hold\s+off|blocking|suggestion|"
    r'nit|caveat|todo|tbd|open\s+question)\b',
    re.IGNORECASE,
)
_AGREEMENT_CUE_RE = re.compile(
    r'(?:^[\U0001f44d\u2705]\s*(?:$|[A-Za-z])|'
    r'\b(?:thanks|thank\s+you|thx|ty|lgtm|looks\s+good|sounds\s+good|sg|sgtm|'
    r'makes\s+sense|agreed|i\s+agree|concur|works\s+for\s+me|wfm|'
    r'fine\s+by\s+me|fine\s+with\s+me|good\s+point|fair\s+point|fair\s+enough|'
    r'good\s+catch|nice\s+catch|ack|acknowledged|got\s+it|understood|'
    r'no\s+(?:objections?|concerns?|issues?)|ok|okay|all\s+good|ship\s+it|'
    r'clear\s+now|that\s+answers|answers\s+my)\b)',
    re.IGNORECASE,
)
_OOO_SUMMARY_RE = re.compile(
    r'^(?:ooo\b|out\s+of\s+office\b|pto\b|vacation\b|annual\s+leave\b)',
    re.IGNORECASE,
)
_RATE_LIMIT_RE = re.compile(
    r'(?:RATE_LIMIT_EXCEEDED|rateLimitExceeded|Quota\s+exceeded|\b429\b)',
    re.IGNORECASE,
)
_MONOSPACE_FONTS = frozenset((
    'roboto mono',
    'courier new',
    'consolas',
    'source code pro',
    'jetbrains mono',
    'fira code',
    'menlo',
    'monospace',
))
_DEFAULT_EXCLUDE_TITLE_REGEXES = (
    r' - Notes by Gemini$',
    r' - Transcript$',
)
_CONVERTED_GDOC_MIME = 'application/vnd.google-apps.document'
_DOC_MIME_TYPES = frozenset((
    _CONVERTED_GDOC_MIME,
    'text/markdown',
    'text/x-markdown',
))
_VALID_THREAD_CATEGORIES = frozenset((
    'complex_fix',
    'disagreement',
    'unanswered',
    'needs_author_triage',
    'verify_owner_reply',
    'ready_to_resolve',
))
_STAGE_RANK = (
    ('none', 0),
    ('warn_1', 1),
    ('warn_2', 2),
    ('warn_3', 3),
    ('action_due', 4),
)
_STAGE_RANK_MAP = types.MappingProxyType(dict(_STAGE_RANK))


@dataclasses.dataclass(frozen=True)
class DocTarget:
  """Represents a validated Google Doc target for collection or ack."""

  doc_id: str
  url: str
  resource_key: str = ''
  source: str = 'cli'
  reasons: tuple[str, ...] = ()
  role: str = 'author'
  deadline: str = ''
  mime_type: str = _CONVERTED_GDOC_MIME
  approvers: tuple[JsonDict, ...] = ()


@dataclasses.dataclass(frozen=True)
class WarningEval:
  """Holds the evaluated staleness warning stage and next transition metadata."""

  category: str
  stage: str
  label: str
  expected_followup: str
  net_idle_days: float
  excluded_ooo_days: float
  next_stage: str
  next_stage_in_days: float
  next_stage_date: str
  net_business_days: float = 0.0


def default_state_dir() -> pathlib.Path:
  """Returns the local review-round state directory."""
  override = os.environ.get('TECH_DOCS_REVIEW_STATE_DIR', '').strip()
  if override:
    return pathlib.Path(override).expanduser()
  xdg = os.environ.get('XDG_CACHE_HOME', '').strip()
  base = pathlib.Path(xdg).expanduser() if xdg else pathlib.Path.home() / '.cache'
  return base / 'tech-docs-review-round'


def resolve_access_token(token_cmd: str = '') -> str:
  """Resolves an OAuth 2.0 bearer token from env, --token-cmd, or gcloud."""
  for env_key in ('GOOGLE_OAUTH_ACCESS_TOKEN', 'GOOGLE_ACCESS_TOKEN'):
    val = os.environ.get(env_key, '').strip()
    if val:
      return val

  cmd_str = token_cmd.strip() or os.environ.get(
      'GOOGLE_OAUTH_TOKEN_CMD', ''
  ).strip()
  candidates: list[list[str]] = []
  if cmd_str:
    candidates.append(shlex.split(cmd_str))
  else:
    candidates.extend([
        ['gcloud', 'auth', 'application-default', 'print-access-token'],
        ['gcloud', 'auth', 'print-access-token'],
    ])

  for argv in candidates:
    try:
      proc = subprocess.run(
          argv,
          check=False,
          capture_output=True,
          text=True,
          timeout=15,
      )
    except (OSError, subprocess.SubprocessError):
      continue
    token = proc.stdout.strip()
    if proc.returncode == 0 and token:
      return token
  return ''


def _default_http_fetcher(
    url: str, headers: Mapping[str, str]
) -> tuple[int, str]:
  """Executes a read-only HTTPS GET with 1 backoff retry on 429/5xx/timeout."""
  if not url.startswith('https://'):
    raise ValueError(f'Refusing non-HTTPS URL: {url!r}')
  for attempt in range(2):
    req = urllib.request.Request(url, headers=dict(headers), method='GET')
    try:
      with urllib.request.urlopen(req, timeout=_DEFAULT_HTTP_TIMEOUT_S) as resp:
        status = int(getattr(resp, 'status', 200))
        body = resp.read().decode('utf-8', errors='replace')
        return status, body
    except urllib.error.HTTPError as err:
      err_body = err.read().decode('utf-8', errors='replace')
      if attempt == 0 and (
          err.code in (429, 500, 502, 503, 504)
          or _RATE_LIMIT_RE.search(err_body)
      ):
        time.sleep(_RETRY_BACKOFF_S)
        continue
      return int(err.code), err_body
    except (urllib.error.URLError, TimeoutError) as err:
      if attempt == 0:
        time.sleep(_RETRY_BACKOFF_S)
        continue
      return 599, str(err)
  return 599, 'HTTP retry exhausted'


def parse_doc_spec(spec: str) -> tuple[str, str, str]:
  """Extracts (doc_id, resource_key, canonical_url) from a URL or bare ID."""
  cleaned = spec.strip()
  if _DOC_ID_RE.match(cleaned):
    url = f'https://docs.google.com/document/d/{cleaned}/edit'
    return cleaned, '', url
  parsed = urllib.parse.urlparse(cleaned)
  match = _URL_DOC_ID_RE.search(parsed.path)
  if not match:
    raise ValueError(f'Invalid Google Doc URL or ID: {spec!r}')
  doc_id = match.group(1)
  query = urllib.parse.parse_qs(parsed.query)
  rkeys = query.get('resourcekey') or query.get('resourceKey') or []
  rkey = rkeys[0] if rkeys else ''
  base_url = f'https://docs.google.com/document/d/{doc_id}/edit'
  if rkey:
    safe_rkey = urllib.parse.quote(rkey, safe='-_')
    return doc_id, rkey, f'{base_url}?resourcekey={safe_rkey}'
  return doc_id, '', base_url


def parse_utc(ts: str) -> datetime.datetime | None:
  """Parses an RFC3339 or YYYY-MM-DD timestamp into timezone-aware UTC."""
  if not ts:
    return None
  raw = ts.strip()
  if raw.endswith('Z'):
    raw = raw[:-1] + '+00:00'
  try:
    dt = datetime.datetime.fromisoformat(raw)
  except ValueError:
    try:
      day = datetime.date.fromisoformat(raw[:10])
      return datetime.datetime(
          day.year, day.month, day.day, tzinfo=datetime.timezone.utc
      )
    except ValueError:
      return None
  if dt.tzinfo is None:
    return dt.replace(tzinfo=datetime.timezone.utc)
  return dt.astimezone(datetime.timezone.utc)


def format_utc(dt: datetime.datetime) -> str:
  """Formats a datetime as an ISO-8601 UTC string ending with Z."""
  utc_dt = dt.astimezone(datetime.timezone.utc).replace(microsecond=0)
  return utc_dt.isoformat().replace('+00:00', 'Z')


def _sha256_text(text: str) -> str:
  """Returns the hex SHA-256 digest of UTF-8 text."""
  return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _safe_tab_filename(prefix: str, tab_id: str) -> str:
  """Returns a safe snapshot filename for a validated or sanitized tab ID."""
  clean = re.sub(r'[^A-Za-z0-9._-]', '_', tab_id)
  return f'{prefix}_{clean}.md'


def classify_reply_sentiment(text: str) -> str:
  """Classifies a reply as done_fix, pure_agreement, question, or disagreement."""
  cleaned = text.strip()
  if not cleaned:
    return 'disagreement_or_change'
  if _DONE_REPLY_RE.search(cleaned):
    return 'done_fix'
  if '?' in cleaned:
    return 'question_or_followup'
  if _DISAGREE_OR_CHANGE_CUE_RE.search(cleaned):
    return 'disagreement_or_change'
  if _AGREEMENT_CUE_RE.search(cleaned):
    return 'pure_agreement'
  return 'disagreement_or_change'


def load_watchlist(path: pathlib.Path) -> JsonDict:
  """Loads watchlist.json or returns an initialized default dictionary."""
  if not path.exists():
    return {
        'documents': [],
        'muted_doc_ids': [],
        'exclude_title_regexes': list(_DEFAULT_EXCLUDE_TITLE_REGEXES),
    }
  data = json.loads(path.read_text(encoding='utf-8'))
  data.setdefault('documents', [])
  data.setdefault('muted_doc_ids', [])
  data.setdefault('exclude_title_regexes', list(_DEFAULT_EXCLUDE_TITLE_REGEXES))
  return data


def save_watchlist(path: pathlib.Path, data: Mapping[str, Any]) -> None:
  """Writes watchlist.json with deterministic indentation."""
  path.parent.mkdir(parents=True, exist_ok=True)
  rendered = json.dumps(dict(data), indent=2, sort_keys=False) + '\n'
  path.write_text(rendered, encoding='utf-8')


def _is_widely_shared(permissions: Sequence[Mapping[str, Any]]) -> bool:
  """Returns True when Drive permissions share broadly or to >=3 peers."""
  non_owner_users = 0
  for perm in permissions:
    ptype = str(perm.get('type', '')).lower()
    role = str(perm.get('role', '')).lower()
    if ptype in ('domain', 'group', 'anyone'):
      return True
    if ptype == 'user' and role != 'owner':
      non_owner_users += 1
  return non_owner_users >= 3


def _title_excluded(title: str, patterns: Sequence[str]) -> bool:
  """Returns True when a document title matches any exclusion regex."""
  for pat in patterns:
    try:
      if re.search(pat, title):
        return True
    except re.error:
      continue
  return False


def _is_monospace_style(style: Mapping[str, Any]) -> bool:
  """Returns True when a Google Docs textStyle uses a monospace font."""
  weighted = style.get('weightedFontFamily') or {}
  family = str(
      weighted.get('fontFamily') or style.get('fontFamily') or ''
  ).strip().lower()
  return family in _MONOSPACE_FONTS


def _format_para_runs(elements: Sequence[Any]) -> tuple[str, bool]:
  """Renders paragraph textRuns to Markdown and reports all-monospace status."""
  chunks: list[str] = []
  non_ws_runs = 0
  mono_runs = 0
  for pe in elements:
    if not isinstance(pe, dict):
      continue
    tr = pe.get('textRun')
    if not isinstance(tr, dict):
      continue
    raw = str(tr.get('content', '')).replace('\x0b', ' ')
    if raw.endswith('\n'):
      raw = raw[:-1]
    if not raw:
      continue
    style = tr.get('textStyle') or {}
    is_mono = _is_monospace_style(style)
    if raw.strip():
      non_ws_runs += 1
      if is_mono:
        mono_runs += 1
    link_url = str((style.get('link') or {}).get('url', '')).strip()
    piece = raw
    if is_mono and '`' not in piece and piece.strip():
      piece = f'`{piece}`'
    elif style.get('bold') and piece.strip():
      lead = piece[: len(piece) - len(piece.lstrip())]
      tail = piece[len(piece.rstrip()) :]
      core = piece.strip()
      piece = f'{lead}**{core}**{tail}'
    elif style.get('italic') and piece.strip():
      lead = piece[: len(piece) - len(piece.lstrip())]
      tail = piece[len(piece.rstrip()) :]
      core = piece.strip()
      piece = f'{lead}*{core}*{tail}'
    if link_url and piece.strip() and not piece.strip().startswith('['):
      piece = f'[{piece.strip()}]({link_url})'
    chunks.append(piece)
  all_mono = non_ws_runs > 0 and mono_runs == non_ws_runs
  return ''.join(chunks), all_mono


def _extract_plain_text(elements: Sequence[Any]) -> str:
  """Extracts plain text from Docs structural elements for anchor checks."""
  parts: list[str] = []
  for elem in elements:
    if not isinstance(elem, dict):
      continue
    if 'paragraph' in elem:
      for pe in (elem['paragraph'] or {}).get('elements') or []:
        if isinstance(pe, dict) and isinstance(pe.get('textRun'), dict):
          parts.append(str(pe['textRun'].get('content', '')))
    elif 'table' in elem:
      for row in (elem['table'] or {}).get('tableRows') or []:
        for cell in (row or {}).get('tableCells') or []:
          parts.append(_extract_plain_text((cell or {}).get('content') or []))
  return ''.join(parts)


def _doc_body_to_markdown(
    elements: Sequence[Any],
    lists_meta: Mapping[str, Any],
) -> str:
  """Converts a Google Docs body content array into deterministic Markdown."""
  blocks: list[str] = []
  code_acc: list[str] = []
  list_counters: dict[tuple[str, int], int] = {}

  def flush_code() -> None:
    if code_acc:
      blocks.append('```\n' + '\n'.join(code_acc) + '\n```')
      code_acc.clear()

  heading_map = {
      'TITLE': '#',
      'HEADING_1': '#',
      'HEADING_2': '##',
      'HEADING_3': '###',
      'HEADING_4': '####',
      'HEADING_5': '#####',
      'HEADING_6': '######',
  }

  for elem in elements:
    if not isinstance(elem, dict):
      continue
    if 'paragraph' in elem:
      para = elem['paragraph'] or {}
      p_elems = para.get('elements') or []
      p_style = para.get('paragraphStyle') or {}
      named = str(p_style.get('namedStyleType', 'NORMAL_TEXT'))
      bullet = para.get('bullet')
      raw_plain = ''.join(
          str((pe.get('textRun') or {}).get('content', ''))
          for pe in p_elems
          if isinstance(pe, dict)
      ).rstrip('\n')
      rendered, all_mono = _format_para_runs(p_elems)

      if (
          all_mono
          and named == 'NORMAL_TEXT'
          and not bullet
          and raw_plain.strip()
      ):
        code_acc.append(raw_plain)
        continue
      flush_code()

      if not rendered.strip():
        continue
      if named in heading_map:
        clean_h = re.sub(r'^\*\*(.*)\*\*$', r'\1', rendered.strip())
        blocks.append(f'{heading_map[named]} {clean_h}')
      elif isinstance(bullet, dict):
        list_id = str(bullet.get('listId', ''))
        nesting = int(bullet.get('nestingLevel', 0))
        indent = '  ' * nesting
        glyph_meta = (
            ((lists_meta.get(list_id) or {}).get('listProperties') or {}).get(
                'nestingLevels'
            )
            or []
        )
        is_ordered = False
        if nesting < len(glyph_meta) and isinstance(glyph_meta[nesting], dict):
          gtype = str(glyph_meta[nesting].get('glyphType', ''))
          is_ordered = gtype not in ('', 'GLYPH_TYPE_UNSPECIFIED')
        key = (list_id, nesting)
        if is_ordered:
          list_counters[key] = list_counters.get(key, 0) + 1
          blocks.append(f'{indent}{list_counters[key]}. {rendered.strip()}')
        else:
          blocks.append(f'{indent}- {rendered.strip()}')
      else:
        list_counters.clear()
        blocks.append(rendered.strip())
    elif 'table' in elem:
      flush_code()
      list_counters.clear()
      rows_md: list[list[str]] = []
      for row in (elem['table'] or {}).get('tableRows') or []:
        cells_md: list[str] = []
        for cell in (row or {}).get('tableCells') or []:
          cell_parts: list[str] = []
          for celem in (cell or {}).get('content') or []:
            if isinstance(celem, dict) and 'paragraph' in celem:
              txt, _ = _format_para_runs(
                  (celem['paragraph'] or {}).get('elements') or []
              )
              if txt.strip():
                cell_parts.append(txt.strip())
          joined = ' '.join(cell_parts).replace('|', '\\|')
          cells_md.append(joined)
        if cells_md:
          rows_md.append(cells_md)
      if rows_md:
        width = max(len(r) for r in rows_md)
        padded = [r + [''] * (width - len(r)) for r in rows_md]
        header = '| ' + ' | '.join(padded[0]) + ' |'
        sep = '| ' + ' | '.join(['---'] * width) + ' |'
        body = ['| ' + ' | '.join(r) + ' |' for r in padded[1:]]
        blocks.append('\n'.join([header, sep, *body]))

  flush_code()
  return '\n\n'.join(blocks) + ('\n' if blocks else '')


class _WorkspaceCollector:
  """Fetches and caches read-only Google Docs, Drive, and Calendar metadata."""

  def __init__(
      self,
      fetcher: HttpFetcher,
      access_token: str,
      now: datetime.datetime,
  ) -> None:
    """Initializes the collector with an HTTP fetcher, token, and clock."""
    self._fetcher = fetcher
    self._token = access_token
    self._now = now
    self._revisions_cache: dict[str, list[JsonDict]] = {}
    self._comments_cache: dict[str, list[JsonDict]] = {}
    self._permissions_cache: dict[str, list[JsonDict]] = {}
    self._file_meta_cache: dict[str, JsonDict] = {}
    self._docs_cache: dict[tuple[str, str], JsonDict] = {}
    self._ooo_cache: dict[str, tuple[list[tuple[float, float]], bool]] = {}

  def _headers(self, doc_id: str = '', rkey: str = '') -> dict[str, str]:
    """Builds Authorization and optional Drive resource-key headers."""
    hdrs: dict[str, str] = {'Accept': 'application/json'}
    if self._token:
      hdrs['Authorization'] = f'Bearer {self._token}'
    if doc_id and rkey:
      hdrs['X-Goog-Drive-Resource-Keys'] = f'{doc_id}/{rkey}'
    return hdrs

  def _get_json(
      self, url: str, doc_id: str = '', rkey: str = ''
  ) -> Any | None:
    """Executes a GET request and parses JSON on HTTP 200."""
    status, body = self._fetcher(url, self._headers(doc_id, rkey))
    if status != 200 or not body.strip():
      return None
    try:
      return json.loads(body)
    except json.JSONDecodeError:
      return None

  def _get_file_meta(self, doc_id: str, rkey: str = '') -> JsonDict:
    """Returns cached Drive file metadata (name, mimeType, webViewLink)."""
    if doc_id not in self._file_meta_cache:
      params = urllib.parse.urlencode({
          'supportsAllDrives': 'true',
          'fields': 'id,name,mimeType,webViewLink',
      })
      url = f'{_DRIVE_API}/files/{urllib.parse.quote(doc_id)}?{params}'
      raw = self._get_json(url, doc_id, rkey)
      self._file_meta_cache[doc_id] = raw if isinstance(raw, dict) else {}
    return self._file_meta_cache[doc_id]

  def get_revisions(self, doc_id: str, rkey: str = '') -> list[JsonDict]:
    """Returns cached Drive revision items for doc_id."""
    if doc_id not in self._revisions_cache:
      params = urllib.parse.urlencode({
          'pageSize': '200',
          'fields': (
              'revisions(id,modifiedTime,'
              'lastModifyingUser(displayName,emailAddress,me))'
          ),
      })
      url = (
          f'{_DRIVE_API}/files/{urllib.parse.quote(doc_id)}/revisions?{params}'
      )
      raw = self._get_json(url, doc_id, rkey)
      revs = raw.get('revisions') if isinstance(raw, dict) else None
      self._revisions_cache[doc_id] = revs if isinstance(revs, list) else []
    return self._revisions_cache[doc_id]

  def get_comments(self, doc_id: str, rkey: str = '') -> list[JsonDict]:
    """Returns cached full comment threads (open and resolved) for doc_id."""
    if doc_id not in self._comments_cache:
      items: list[JsonDict] = []
      page_token = ''
      fields = (
          'nextPageToken,comments(id,createdTime,modifiedTime,resolved,'
          'content,quotedFileContent,anchor,'
          'author(displayName,emailAddress,me),assigneeEmailAddress,'
          'replies(id,createdTime,action,content,'
          'author(displayName,emailAddress,me),assigneeEmailAddress))'
      )
      for _ in range(10):
        q: dict[str, str] = {
            'includeDeleted': 'false',
            'pageSize': '100',
            'fields': fields,
        }
        if page_token:
          q['pageToken'] = page_token
        params = urllib.parse.urlencode(q)
        url = (
            f'{_DRIVE_API}/files/{urllib.parse.quote(doc_id)}/comments?{params}'
        )
        raw = self._get_json(url, doc_id, rkey)
        if not isinstance(raw, dict):
          break
        batch = raw.get('comments')
        if isinstance(batch, list):
          items.extend(c for c in batch if isinstance(c, dict))
        page_token = str(raw.get('nextPageToken') or '').strip()
        if not page_token:
          break
      self._comments_cache[doc_id] = items
    return self._comments_cache[doc_id]

  def get_permissions(self, doc_id: str, rkey: str = '') -> list[JsonDict]:
    """Returns cached Drive permissions list for doc_id."""
    if doc_id not in self._permissions_cache:
      params = urllib.parse.urlencode({
          'supportsAllDrives': 'true',
          'fields': 'permissions(id,type,role,displayName,emailAddress)',
      })
      url = (
          f'{_DRIVE_API}/files/{urllib.parse.quote(doc_id)}'
          f'/permissions?{params}'
      )
      raw = self._get_json(url, doc_id, rkey)
      perms = raw.get('permissions') if isinstance(raw, dict) else None
      self._permissions_cache[doc_id] = perms if isinstance(perms, list) else []
    return self._permissions_cache[doc_id]

  def get_url(self, doc_id: str, rkey: str = '', fallback: str = '') -> str:
    """Resolves the canonical UI link (preserving resourcekey)."""
    meta = self._get_file_meta(doc_id, rkey)
    web_link = str(meta.get('webViewLink') or '').strip()
    if web_link:
      _, parsed_rk, norm_url = parse_doc_spec(web_link)
      if rkey and not parsed_rk:
        _, _, norm_url = parse_doc_spec(
            f'https://docs.google.com/document/d/{doc_id}/edit?resourcekey={rkey}'
        )
      return norm_url
    return fallback or f'https://docs.google.com/document/d/{doc_id}/edit'

  def _get_doc_json(
      self, doc_id: str, rkey: str, suggestions_mode: str
  ) -> JsonDict:
    """Fetches and caches Google Docs v1 JSON with includeTabsContent=true."""
    key = (doc_id, suggestions_mode)
    if key not in self._docs_cache:
      params = urllib.parse.urlencode({
          'includeTabsContent': 'true',
          'suggestionsViewMode': suggestions_mode,
      })
      url = f'{_DOCS_API}/documents/{urllib.parse.quote(doc_id)}?{params}'
      raw = self._get_json(url, doc_id, rkey)
      self._docs_cache[key] = raw if isinstance(raw, dict) else {}
    return self._docs_cache[key]

  def get_suggestions_doc(self, doc_id: str, rkey: str = '') -> JsonDict:
    """Returns raw Docs JSON in SUGGESTIONS_INLINE mode."""
    return self._get_doc_json(doc_id, rkey, 'SUGGESTIONS_INLINE')

  def get_clean_doc(self, doc_id: str, rkey: str = '') -> JsonDict:
    """Returns raw Docs JSON in PREVIEW_WITHOUT_SUGGESTIONS mode."""
    return self._get_doc_json(doc_id, rkey, 'PREVIEW_WITHOUT_SUGGESTIONS')

  def _iter_doc_tabs(self, doc: Mapping[str, Any]) -> list[JsonDict]:
    """Flattens top-level and child tabs from a Docs v1 document payload."""
    out: list[JsonDict] = []

    def walk(tabs: Sequence[Any], level: int) -> None:
      for idx, tab in enumerate(tabs):
        if not isinstance(tab, dict):
          continue
        props = tab.get('tabProperties') or {}
        tid = str(props.get('tabId', ''))
        if _TAB_ID_RE.match(tid):
          out.append({
              'tabId': tid,
              'title': str(props.get('title') or tid),
              'index': int(props.get('index', idx)),
              'nestingLevel': int(props.get('nestingLevel', level)),
              'documentTab': tab.get('documentTab') or {},
          })
        walk(tab.get('childTabs') or [], level + 1)

    raw_tabs = doc.get('tabs')
    if isinstance(raw_tabs, list) and raw_tabs:
      walk(raw_tabs, 0)
    if out:
      return out
    return [{
        'tabId': 't.0',
        'title': str(doc.get('title') or 'Main'),
        'index': 0,
        'nestingLevel': 0,
        'documentTab': {
            'body': doc.get('body') or {},
            'lists': doc.get('lists') or {},
        },
    }]

  def get_tabs(self, doc_id: str, rkey: str = '') -> list[JsonDict]:
    """Returns document tabs metadata, falling back to default tab t.0."""
    doc = self.get_clean_doc(doc_id, rkey) or self.get_suggestions_doc(
        doc_id, rkey
    )
    return [
        {
            'tabId': t['tabId'],
            'title': t['title'],
            'index': t['index'],
            'nestingLevel': t['nestingLevel'],
        }
        for t in self._iter_doc_tabs(doc)
    ]

  def pull_tab_markdown(
      self,
      doc_id: str,
      tab_id: str,
      rkey: str = '',
      mime_type: str = _CONVERTED_GDOC_MIME,
  ) -> str | None:
    """Exports a single tab to clean Markdown without unaccepted suggestions."""
    if mime_type in ('text/markdown', 'text/x-markdown'):
      params = urllib.parse.urlencode({
          'alt': 'media',
          'supportsAllDrives': 'true',
      })
      url = f'{_DRIVE_API}/files/{urllib.parse.quote(doc_id)}?{params}'
      status, body = self._fetcher(url, self._headers(doc_id, rkey))
      return body if status == 200 else None

    doc = self.get_clean_doc(doc_id, rkey)
    if not doc:
      return None
    for tab in self._iter_doc_tabs(doc):
      if tab['tabId'] == tab_id:
        dtab = tab.get('documentTab') or {}
        elems = (dtab.get('body') or {}).get('content') or []
        lists_meta = dtab.get('lists') or doc.get('lists') or {}
        return _doc_body_to_markdown(elems, lists_meta)
    return None

  def get_anchor_health(self, doc_id: str, rkey: str = '') -> JsonDict:
    """Checks whether open comment quotedFileContent phrases remain in tabs."""
    doc = self.get_clean_doc(doc_id, rkey)
    comments = self.get_comments(doc_id, rkey)
    tab_texts: list[tuple[str, str]] = []
    for tab in self._iter_doc_tabs(doc):
      dtab = tab.get('documentTab') or {}
      elems = (dtab.get('body') or {}).get('content') or []
      plain = _extract_plain_text(elems)
      norm = re.sub(r'\s+', ' ', plain)
      tab_texts.append((str(tab['tabId']), norm))

    out_comments: list[JsonDict] = []
    orphaned = 0
    for thread in comments:
      if not isinstance(thread, dict) or bool(thread.get('resolved')):
        continue
      cid = str(thread.get('id', ''))
      quote = str((thread.get('quotedFileContent') or {}).get('value') or '')
      norm_q = re.sub(r'\s+', ' ', quote).strip()
      matched_tab = 't.0'
      if not norm_q:
        status = 'unanchored'
      else:
        status = 'orphaned'
        for tid, t_norm in tab_texts:
          if norm_q in t_norm:
            status = 'intact'
            matched_tab = tid
            break
        if status == 'orphaned' and tab_texts:
          orphaned += 1
      out_comments.append({
          'commentId': cid,
          'tabId': matched_tab,
          'anchorStatus': status,
          'quote': quote,
      })

    return {
        'allIntact': orphaned == 0,
        'orphanedCount': orphaned,
        'brokenCount': 0,
        'comments': out_comments,
    }

  def get_ooo_intervals(
      self,
      email: str,
      earliest: datetime.datetime,
      org_domain: str = '',
  ) -> tuple[Sequence[tuple[float, float]], bool]:
    """Returns merged OOO (start_epoch, end_epoch) spans for a peer calendar."""
    norm = email.strip().lower()
    if '@' not in norm:
      return (), False
    if org_domain and norm.split('@', 1)[1] != org_domain.lower():
      return (), False
    if norm not in self._ooo_cache:
      start_dt = min(earliest, self._now - datetime.timedelta(days=30))
      params = urllib.parse.urlencode({
          'timeMin': format_utc(start_dt),
          'timeMax': format_utc(self._now + datetime.timedelta(days=1)),
          'singleEvents': 'true',
          'maxResults': '100',
      })
      cal_id = urllib.parse.quote(norm, safe='')
      url = f'{_CAL_API}/calendars/{cal_id}/events?{params}'
      raw = self._get_json(url)
      items = raw.get('items') if isinstance(raw, dict) else None
      if not isinstance(items, list):
        self._ooo_cache[norm] = ([], False)
      else:
        spans: list[tuple[float, float]] = []
        for ev in items:
          if not isinstance(ev, dict):
            continue
          if str(ev.get('status', '')).lower() == 'cancelled':
            continue
          etype = str(ev.get('eventType', ''))
          summary = str(ev.get('summary', '')).strip()
          if etype != 'outOfOffice' and not _OOO_SUMMARY_RE.search(summary):
            continue
          start_obj = ev.get('start') or {}
          end_obj = ev.get('end') or {}
          s_dt = parse_utc(
              str(start_obj.get('dateTime') or start_obj.get('date') or '')
          )
          e_dt = parse_utc(
              str(end_obj.get('dateTime') or end_obj.get('date') or '')
          )
          if s_dt and e_dt and e_dt > s_dt:
            spans.append((s_dt.timestamp(), e_dt.timestamp()))
        self._ooo_cache[norm] = (_merge_intervals(spans), True)
    spans, ok = self._ooo_cache[norm]
    return spans, ok

  def discover_targets(
      self,
      watchlist: Mapping[str, Any],
      cli_docs: Sequence[str],
      lookback_days: int,
      auto_discover: bool,
      state_dir: pathlib.Path | None = None,
  ) -> list[DocTarget]:
    """Resolves watchlist, explicit CLI docs, 3-day docs, and carryover."""
    targets: dict[str, DocTarget] = {}
    muted = {str(x).strip() for x in watchlist.get('muted_doc_ids', []) if x}
    exclude_pats = [
        str(p) for p in watchlist.get('exclude_title_regexes', []) if p
    ]

    for spec in cli_docs:
      doc_id, rkey, url = parse_doc_spec(spec)
      targets[doc_id] = DocTarget(
          doc_id=doc_id,
          url=url,
          resource_key=rkey,
          source='cli',
          reasons=('explicit_cli',),
      )

    for entry in watchlist.get('documents', []):
      if not isinstance(entry, dict) or not entry.get('active', True):
        if isinstance(entry, dict) and entry.get('doc_id'):
          muted.add(str(entry['doc_id']))
        continue
      raw_spec = str(entry.get('url') or entry.get('doc_id') or '').strip()
      if not raw_spec:
        continue
      try:
        doc_id, rkey, url = parse_doc_spec(raw_spec)
      except ValueError:
        continue
      if doc_id in muted and doc_id not in targets:
        continue
      raw_approvers = entry.get('approvers')
      approvers_tup = (
          tuple(a for a in raw_approvers if isinstance(a, dict))
          if isinstance(raw_approvers, list)
          else ()
      )
      if doc_id not in targets:
        targets[doc_id] = DocTarget(
            doc_id=doc_id,
            url=url,
            resource_key=rkey,
            source='watchlist',
            reasons=('watchlist',),
            role=str(entry.get('role', 'author')),
            deadline=str(entry.get('deadline', '')),
            approvers=approvers_tup,
        )

    if not auto_discover:
      return list(targets.values())

    cutoff = self._now - datetime.timedelta(days=max(1, lookback_days))
    cutoff_iso = format_utc(cutoff)
    mime_clause = (
        "(mimeType = 'application/vnd.google-apps.document' or "
        "mimeType = 'text/markdown')"
    )

    owned_q = (
        f"'me' in owners and trashed = false and {mime_clause} and "
        f"modifiedTime >= '{cutoff_iso}'"
    )
    owned_params = urllib.parse.urlencode({
        'q': owned_q,
        'pageSize': '50',
        'supportsAllDrives': 'true',
        'includeItemsFromAllDrives': 'true',
        'fields': (
            'files(id,name,mimeType,createdTime,modifiedTime,webViewLink,'
            'permissions(type,role))'
        ),
    })
    owned_raw = self._get_json(f'{_DRIVE_API}/files?{owned_params}')
    owned_files = owned_raw.get('files') if isinstance(owned_raw, dict) else []
    if isinstance(owned_files, list):
      for item in owned_files:
        if not isinstance(item, dict):
          continue
        doc_id = str(item.get('id', '')).strip()
        title = str(item.get('name', ''))
        mime = str(item.get('mimeType', '')) or _CONVERTED_GDOC_MIME
        if (
            not _DOC_ID_RE.match(doc_id)
            or doc_id in targets
            or doc_id in muted
            or mime not in _DOC_MIME_TYPES
            or _title_excluded(title, exclude_pats)
        ):
          continue
        reasons: list[str] = []
        created_dt = parse_utc(str(item.get('createdTime', '')))
        mod_dt = parse_utc(str(item.get('modifiedTime', '')))
        if created_dt and created_dt >= cutoff:
          reasons.append('created_by_me')
        if mod_dt and mod_dt >= cutoff:
          reasons.append('revised_recently')
        perms = item.get('permissions')
        if isinstance(perms, list) and _is_widely_shared(perms):
          reasons.append('widely_shared')
        if reasons:
          raw_link = str(item.get('webViewLink', '')).strip()
          _, rkey, url = parse_doc_spec(raw_link or doc_id)
          targets[doc_id] = DocTarget(
              doc_id=doc_id,
              url=url,
              resource_key=rkey,
              source='auto_discovered',
              reasons=tuple(reasons),
              role='author',
              mime_type=mime,
          )

    collab_q = (
        f"not 'me' in owners and trashed = false and {mime_clause} and "
        f"modifiedTime >= '{cutoff_iso}'"
    )
    collab_params = urllib.parse.urlencode({
        'q': collab_q,
        'orderBy': 'modifiedByMeTime desc,modifiedTime desc',
        'pageSize': '40',
        'supportsAllDrives': 'true',
        'includeItemsFromAllDrives': 'true',
        'fields': 'files(id,name,mimeType,modifiedTime,webViewLink)',
    })
    collab_raw = self._get_json(f'{_DRIVE_API}/files?{collab_params}')
    collab_files = (
        collab_raw.get('files') if isinstance(collab_raw, dict) else []
    )
    if isinstance(collab_files, list):
      for item in collab_files:
        if not isinstance(item, dict):
          continue
        doc_id = str(item.get('id', '')).strip()
        title = str(item.get('name', ''))
        mime = str(item.get('mimeType', ''))
        mod_dt = parse_utc(str(item.get('modifiedTime', '')))
        if (
            not _DOC_ID_RE.match(doc_id)
            or doc_id in targets
            or doc_id in muted
            or mime not in _DOC_MIME_TYPES
            or not mod_dt
            or mod_dt < cutoff
            or _title_excluded(title, exclude_pats)
        ):
          continue
        reasons = self._check_collaborator_activity(doc_id, cutoff)
        if reasons:
          raw_link = str(item.get('webViewLink', '')).strip()
          _, rkey, url = parse_doc_spec(raw_link or doc_id)
          targets[doc_id] = DocTarget(
              doc_id=doc_id,
              url=url,
              resource_key=rkey,
              source='auto_discovered',
              reasons=tuple(reasons),
              role='collaborator',
              mime_type=mime,
          )

    if state_dir is not None and state_dir.exists():
      horizon_sec = CARRYOVER_HORIZON_DAYS * 86400.0
      for child in sorted(state_dir.iterdir()):
        if not child.is_dir() or not _DOC_ID_RE.match(child.name):
          continue
        doc_id = child.name
        if doc_id in targets or doc_id in muted:
          continue
        st_path = child / 'state.json'
        if not st_path.exists():
          continue
        try:
          st = json.loads(st_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
          continue
        if not isinstance(st, dict):
          continue
        title = str(st.get('title', ''))
        if _title_excluded(title, exclude_pats):
          continue
        if 'open_threads_count' in st:
          open_cnt = int(st.get('open_threads_count') or 0)
        else:
          open_cnt = len(
              ((st.get('last_digest') or {}).get('stage_ranks')) or {}
          )
        if open_cnt <= 0:
          continue
        ref_dt = parse_utc(
            str(st.get('last_digest_utc') or st.get('last_ack_utc') or '')
        )
        if ref_dt is None or (self._now - ref_dt).total_seconds() > horizon_sec:
          continue
        raw_url = str(st.get('url') or doc_id)
        try:
          _, rkey, url = parse_doc_spec(raw_url)
        except ValueError:
          continue
        targets[doc_id] = DocTarget(
            doc_id=doc_id,
            url=url,
            resource_key=rkey,
            source='state_carryover',
            reasons=('open_threads_carryover',),
            role=str(st.get('role') or 'author'),
            mime_type=str(st.get('mime_type') or _CONVERTED_GDOC_MIME),
        )

    return list(targets.values())

  def _check_collaborator_activity(
      self, doc_id: str, cutoff: datetime.datetime
  ) -> list[str]:
    """Checks whether the user edited or collaborated on doc_id since cutoff."""
    reasons: list[str] = []
    for rev in self.get_revisions(doc_id):
      user = rev.get('lastModifyingUser') or {}
      rev_dt = parse_utc(str(rev.get('modifiedTime', '')))
      if user.get('me') and rev_dt and rev_dt >= cutoff:
        reasons.append('revised_by_me')
        break

    comments = self.get_comments(doc_id)
    my_recent_msgs = 0
    open_participation = False
    for thread in comments:
      resolved = bool(thread.get('resolved'))
      root_author = thread.get('author') or {}
      root_dt = parse_utc(str(thread.get('createdTime', '')))
      if root_author.get('me'):
        if root_dt and root_dt >= cutoff:
          my_recent_msgs += 1
        if not resolved:
          open_participation = True
      for reply in thread.get('replies') or []:
        rep_author = reply.get('author') or {}
        rep_dt = parse_utc(str(reply.get('createdTime', '')))
        if rep_author.get('me'):
          if rep_dt and rep_dt >= cutoff:
            my_recent_msgs += 1
          if not resolved:
            open_participation = True
    if my_recent_msgs > 0 or open_participation:
      reasons.append('collaborated_on')
    return reasons


def _merge_intervals(
    spans: Sequence[tuple[float, float]],
) -> list[tuple[float, float]]:
  """Merges overlapping or contiguous (start_epoch, end_epoch) intervals."""
  if not spans:
    return []
  ordered = sorted(spans, key=lambda s: (s[0], s[1]))
  merged: list[tuple[float, float]] = [ordered[0]]
  for start_s, end_s in ordered[1:]:
    prev_start, prev_end = merged[-1]
    if start_s <= prev_end + 3600.0:
      merged[-1] = (prev_start, max(prev_end, end_s))
    else:
      merged.append((start_s, end_s))
  return merged


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> datetime.date:
  """Returns the n-th (1-based) occurrence of weekday (0=Mon) in year/month."""
  first = datetime.date(year, month, 1)
  offset = (weekday - first.weekday()) % 7
  return first + datetime.timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> datetime.date:
  """Returns the last occurrence of weekday (0=Mon) in year/month."""
  if month == 12:
    nxt = datetime.date(year + 1, 1, 1)
  else:
    nxt = datetime.date(year, month + 1, 1)
  last = nxt - datetime.timedelta(days=1)
  offset = (last.weekday() - weekday) % 7
  return last - datetime.timedelta(days=offset)


def _observed_holiday(day: datetime.date) -> datetime.date:
  """Maps Saturday fixed holidays to Friday and Sunday holidays to Monday."""
  if day.weekday() == 5:
    return day - datetime.timedelta(days=1)
  if day.weekday() == 6:
    return day + datetime.timedelta(days=1)
  return day


_HOLIDAY_CACHE: dict[int, frozenset[datetime.date]] = {}


def _us_holidays(year: int) -> frozenset[datetime.date]:
  """Returns standard US holiday dates for year."""
  if year not in _HOLIDAY_CACHE:
    thanksgiving = _nth_weekday(year, 11, 3, 4)
    days = {
        _observed_holiday(datetime.date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _last_weekday(year, 5, 0),
        _observed_holiday(datetime.date(year, 6, 19)),
        _observed_holiday(datetime.date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),
        thanksgiving,
        thanksgiving + datetime.timedelta(days=1),
        datetime.date(year, 12, 24),
        _observed_holiday(datetime.date(year, 12, 25)),
        datetime.date(year, 12, 31),
    }
    _HOLIDAY_CACHE[year] = frozenset(days)
  return _HOLIDAY_CACHE[year]


def compute_net_idle_days(
    since: datetime.datetime,
    now: datetime.datetime,
    ooo_spans: Sequence[tuple[float, float]],
) -> tuple[float, float]:
  """Computes (net_idle_days, excluded_ooo_days) subtracting >7d OOO blocks."""
  if now <= since:
    return 0.0, 0.0
  s_ep = since.timestamp()
  n_ep = now.timestamp()
  raw_days = (n_ep - s_ep) / 86400.0
  excluded = 0.0
  for o_start, o_end in ooo_spans:
    block_days = (o_end - o_start) / 86400.0
    if block_days <= OOO_MIN_EXCLUDED_DAYS:
      continue
    overlap_start = max(s_ep, o_start)
    overlap_end = min(n_ep, o_end)
    if overlap_end > overlap_start:
      excluded += (overlap_end - overlap_start) / 86400.0
  net = max(0.0, raw_days - excluded)
  return round(net, 2), round(excluded, 2)


def compute_net_business_days(
    since: datetime.datetime,
    now: datetime.datetime,
    ooo_spans: Sequence[tuple[float, float]],
) -> float:
  """Computes net business days excluding weekends, US holidays, and >7d OOO."""
  if now <= since:
    return 0.0
  since_utc = since.astimezone(datetime.timezone.utc)
  now_utc = now.astimezone(datetime.timezone.utc)
  s_ep = since_utc.timestamp()
  n_ep = now_utc.timestamp()
  long_ooo = [
      (o_s, o_e)
      for o_s, o_e in ooo_spans
      if (o_e - o_s) / 86400.0 > OOO_MIN_EXCLUDED_DAYS
  ]
  total_sec = 0.0
  cur_day = since_utc.date()
  end_day = now_utc.date()
  while cur_day <= end_day:
    if cur_day.weekday() < 5 and cur_day not in _us_holidays(cur_day.year):
      day_start = datetime.datetime(
          cur_day.year,
          cur_day.month,
          cur_day.day,
          tzinfo=datetime.timezone.utc,
      ).timestamp()
      day_end = day_start + 86400.0
      seg_s = max(s_ep, day_start)
      seg_e = min(n_ep, day_end)
      if seg_e > seg_s:
        active = seg_e - seg_s
        for o_s, o_e in long_ooo:
          ov_s = max(seg_s, o_s)
          ov_e = min(seg_e, o_e)
          if ov_e > ov_s:
            active -= ov_e - ov_s
        total_sec += max(0.0, active)
    cur_day += datetime.timedelta(days=1)
  return round(total_sec / 86400.0, 2)


def evaluate_warning_schedule(
    category: str,
    net_days: float,
    excluded_ooo_days: float,
    now: datetime.datetime,
    deadline: str = '',
    net_business_days: float | None = None,
) -> WarningEval:
  """Evaluates continuous multi-stage staleness intervals with weekday floor."""
  bus_days = (
      round(net_days * 5.0 / 7.0, 2)
      if net_business_days is None
      else net_business_days
  )
  if category == 'ready_to_resolve':
    return WarningEval(
        category=category,
        stage='action_due',
        label='Ready to resolve (agreement with no pending changes)',
        expected_followup='Resolve satisfied thread with brief outcome (C11).',
        net_idle_days=net_days,
        excluded_ooo_days=excluded_ooo_days,
        next_stage='',
        next_stage_in_days=0.0,
        next_stage_date='',
        net_business_days=bus_days,
    )

  if category in ('complex_fix', 'post_activity'):
    suffix = ' post-activity' if category == 'post_activity' else ' idle'
    schedule = (
        (
            2.0,
            1.5,
            'warn_1',
            f'1st warning (2 to <4 d{suffix})',
            'Optional check-in ping or monitor toward 7 d C11 closure.',
        ),
        (
            4.0,
            3.0,
            'warn_2',
            f'2nd warning (4 to <7 d{suffix})',
            'Ping commenter to confirm fix or reconcile before 7 d C11 close.',
        ),
        (
            7.0,
            5.0,
            'action_due',
            f'Action day (>= 7 d{suffix}, >= 5 business d)',
            'Resolve stale thread with outcome per C11 (omit idle days).',
        ),
    )
  elif category == 'verify_owner_reply':
    schedule = (
        (
            2.0,
            1.5,
            'warn_1',
            '1st warning (2 to <4 d awaiting verification)',
            'Check owner reply against current prose and resolve or follow up.',
        ),
        (
            4.0,
            3.0,
            'warn_2',
            '2nd warning (4 to <7 d awaiting verification)',
            'Verify fix and resolve thread or reply with remaining gap.',
        ),
        (
            7.0,
            5.0,
            'action_due',
            'Action day (>= 7 d awaiting verification, >= 5 business d)',
            'Verify owner reply and close satisfied thread per C11.',
        ),
    )
  elif category == 'disagreement':
    schedule = (
        (
            4.0,
            3.0,
            'warn_1',
            '1st warning (4 to <8 d idle)',
            'Check whether commenter wants a 15-min sync (C12) or OQ entry.',
        ),
        (
            8.0,
            5.0,
            'warn_2',
            '2nd warning (8 to <14 d idle)',
            'Ping commenter or log remaining trade-off in Open Questions.',
        ),
        (
            14.0,
            10.0,
            'warn_3',
            '3rd warning (14 to <21 d idle)',
            'Final check-in before 21 d C11 stale-disagreement closure.',
        ),
        (
            21.0,
            14.0,
            'action_due',
            'Action day (>= 21 d idle, >= 14 business d)',
            'Resolve stale disagreement per C11 (omit idle days in comment).',
        ),
    )
  else:
    schedule = (
        (
            2.0,
            1.5,
            'warn_1',
            '1st warning (2 to <4 d unanswered)',
            'Prepare gentle +email follow-up or default assumption in prose.',
        ),
        (
            4.0,
            3.0,
            'warn_2',
            '2nd warning (4 to <6 d unanswered)',
            'Ping +email with default or decouple to Open Questions.',
        ),
        (
            6.0,
            4.0,
            'action_due',
            'Action day (>= 6 d unanswered, >= 4 business d)',
            'Escalate: ping +email, move to Open Questions, or propose sync.',
        ),
    )

  if deadline:
    due_dt = parse_utc(deadline)
    if due_dt and now.date() >= due_dt.date():
      return WarningEval(
          category=category,
          stage='action_due',
          label=f'Action day (deadline {deadline[:10]} reached)',
          expected_followup='Send deadline-aware follow-up ping or decouple.',
          net_idle_days=net_days,
          excluded_ooo_days=excluded_ooo_days,
          next_stage='',
          next_stage_in_days=0.0,
          next_stage_date='',
          net_business_days=bus_days,
      )

  stage = 'none'
  label = 'Active (< first warning window)'
  followup = ''
  next_stage = schedule[0][2]
  next_cal_thresh = schedule[0][0]
  next_bus_thresh = schedule[0][1]

  for idx, (cal_t, bus_t, s_name, s_label, s_follow) in enumerate(schedule):
    if net_days >= cal_t and bus_days >= bus_t:
      stage = s_name
      label = s_label
      followup = s_follow
      if idx + 1 < len(schedule):
        next_cal_thresh = schedule[idx + 1][0]
        next_bus_thresh = schedule[idx + 1][1]
        next_stage = schedule[idx + 1][2]
      else:
        next_cal_thresh = 0.0
        next_bus_thresh = 0.0
        next_stage = ''
    else:
      next_cal_thresh = cal_t
      next_bus_thresh = bus_t
      next_stage = s_name
      break

  if next_stage:
    cal_rem = max(0.0, next_cal_thresh - net_days)
    bus_rem = max(0.0, next_bus_thresh - bus_days)
    rem = round(max(cal_rem, bus_rem), 2)
    proj = (now + datetime.timedelta(days=rem)).date().isoformat()
  else:
    rem = 0.0
    proj = ''

  return WarningEval(
      category=category,
      stage=stage,
      label=label,
      expected_followup=followup,
      net_idle_days=net_days,
      excluded_ooo_days=excluded_ooo_days,
      next_stage=next_stage,
      next_stage_in_days=rem,
      next_stage_date=proj,
      net_business_days=bus_days,
  )


def extract_pending_suggestions(
    suggestions_doc: Mapping[str, Any],
    comments: Sequence[Mapping[str, Any]],
) -> list[JsonDict]:
  """Extracts pending Suggesting-mode edits across single- or multi-tab JSON."""
  by_id: dict[str, JsonDict] = {}
  comment_by_id = {
      str(c.get('id', '')): c for c in comments if isinstance(c, dict)
  }

  def walk_elements(elements: Sequence[Any], tab_id: str) -> None:
    for elem in elements:
      if not isinstance(elem, dict):
        continue
      if 'paragraph' in elem:
        para = elem['paragraph']
        p_elems = para.get('elements') or []
        full_para = ''.join(
            str((pe.get('textRun') or {}).get('content', ''))
            for pe in p_elems
            if isinstance(pe, dict)
        ).strip()
        for pe in p_elems:
          if not isinstance(pe, dict):
            continue
          tr = pe.get('textRun')
          if not isinstance(tr, dict):
            continue
          text = str(tr.get('content', ''))
          for sid in tr.get('suggestedInsertionIds') or []:
            rec = by_id.setdefault(
                str(sid),
                {
                    'suggestion_id': str(sid),
                    'tab_id': tab_id,
                    'inserted_text': '',
                    'deleted_text': '',
                    'paragraph_context': full_para[:240],
                },
            )
            rec['inserted_text'] += text
          for sid in tr.get('suggestedDeletionIds') or []:
            rec = by_id.setdefault(
                str(sid),
                {
                    'suggestion_id': str(sid),
                    'tab_id': tab_id,
                    'inserted_text': '',
                    'deleted_text': '',
                    'paragraph_context': full_para[:240],
                },
            )
            rec['deleted_text'] += text
      elif 'table' in elem:
        for row in (elem['table'] or {}).get('tableRows') or []:
          for cell in (row or {}).get('tableCells') or []:
            walk_elements((cell or {}).get('content') or [], tab_id)

  def walk_tabs(tabs: Sequence[Any]) -> None:
    for tab in tabs:
      if not isinstance(tab, dict):
        continue
      props = tab.get('tabProperties') or {}
      tid = str(props.get('tabId', 't.0'))
      doc_tab = tab.get('documentTab') or {}
      body = (doc_tab.get('body') or {}).get('content') or []
      walk_elements(body, tid)
      walk_tabs(tab.get('childTabs') or [])

  tabs = suggestions_doc.get('tabs')
  if isinstance(tabs, list) and tabs:
    walk_tabs(tabs)
  else:
    body = (suggestions_doc.get('body') or {}).get('content') or []
    walk_elements(body, 't.0')

  results: list[JsonDict] = []
  for sid, rec in sorted(by_id.items()):
    thread = comment_by_id.get(sid) or comment_by_id.get(f'suggest.{sid}')
    if thread:
      author = (thread.get('author') or {}).get('displayName', '')
      rec['author'] = author
      rec['reason_comment'] = str(thread.get('content', ''))
      rec['created_time'] = str(thread.get('createdTime', ''))
      rec['replies_count'] = len(thread.get('replies') or [])
    results.append(rec)
  return results


def _build_directory(
    permissions: Sequence[Mapping[str, Any]],
    revisions: Sequence[Mapping[str, Any]],
    comments: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, str], str, str]:
  """Maps display names to emails and resolves (my_email, doc_owner_email)."""
  name_to_email: dict[str, str] = {}
  my_email = os.environ.get('GOOGLE_USER_EMAIL', '').strip().lower()
  owner_email = ''
  for perm in permissions:
    name = str(perm.get('displayName', '')).strip().lower()
    email = str(perm.get('emailAddress', '')).strip().lower()
    role = str(perm.get('role', '')).strip().lower()
    if name and email:
      name_to_email[name] = email
    if role == 'owner' and email and not owner_email:
      owner_email = email
  for rev in revisions:
    user = rev.get('lastModifyingUser') or {}
    name = str(user.get('displayName', '')).strip().lower()
    email = str(user.get('emailAddress', '')).strip().lower()
    if name and email:
      name_to_email[name] = email
    if user.get('me') and email:
      my_email = email
  for thread in comments:
    author = thread.get('author') or {}
    name = str(author.get('displayName', '')).strip().lower()
    email = str(author.get('emailAddress', '')).strip().lower()
    if name and email:
      name_to_email[name] = email
    if author.get('me') and email:
      my_email = email
    for reply in thread.get('replies') or []:
      if not isinstance(reply, dict):
        continue
      r_author = reply.get('author') or {}
      r_name = str(r_author.get('displayName', '')).strip().lower()
      r_email = str(r_author.get('emailAddress', '')).strip().lower()
      if r_name and r_email:
        name_to_email[r_name] = r_email
      if r_author.get('me') and r_email:
        my_email = r_email
  return name_to_email, my_email, owner_email


def _text_mentions_me(text: str, my_email: str) -> bool:
  """Returns True when text mentions my_email or +/@localpart."""
  if not text or not my_email:
    return False
  emails = [m.lower() for m in _EMAIL_MENTION_RE.findall(text)]
  if my_email in emails:
    return True
  if '@' in my_email:
    local = my_email.split('@', 1)[0]
    pat = rf'(?<![A-Za-z0-9._%+-])[+@]{re.escape(local)}\b'
    if re.search(pat, text, re.IGNORECASE):
      return True
  return False


def _thread_involves_me(
    thread: Mapping[str, Any],
    replies: Sequence[Mapping[str, Any]],
    root_email: str,
    my_email: str,
) -> bool:
  """Returns True when the user opened, replied to, or is mentioned in thread."""
  root_author = thread.get('author') or {}
  if root_author.get('me') or (my_email and root_email == my_email):
    return True
  assignee = str(thread.get('assigneeEmailAddress', '')).strip().lower()
  if my_email and assignee == my_email:
    return True
  if _text_mentions_me(str(thread.get('content', '')), my_email):
    return True
  for reply in replies:
    rep_author = reply.get('author') or {}
    rep_email = str(rep_author.get('emailAddress', '')).strip().lower()
    if rep_author.get('me') or (my_email and rep_email == my_email):
      return True
    rep_assignee = str(reply.get('assigneeEmailAddress', '')).strip().lower()
    if my_email and rep_assignee == my_email:
      return True
    if _text_mentions_me(str(reply.get('content', '')), my_email):
      return True
  return False


def _has_recent_me_mention(
    thread: Mapping[str, Any],
    replies: Sequence[Mapping[str, Any]],
    my_email: str,
    now: datetime.datetime,
) -> bool:
  """Returns True if thread or a reply within RECENT_MENTION_DAYS pings me."""
  if not my_email:
    return False
  cutoff = now - datetime.timedelta(days=RECENT_MENTION_DAYS)
  root_dt = parse_utc(str(thread.get('createdTime', '')))
  if (
      root_dt
      and root_dt >= cutoff
      and _text_mentions_me(str(thread.get('content', '')), my_email)
  ):
    return True
  for reply in replies:
    rep_dt = parse_utc(str(reply.get('createdTime', '')))
    if (
        rep_dt
        and rep_dt >= cutoff
        and _text_mentions_me(str(reply.get('content', '')), my_email)
    ):
      return True
  return False


def _resolve_counterparty(
    root_is_me: bool,
    root_name: str,
    root_email: str,
    msg_replies: Sequence[Mapping[str, Any]],
    other_mentions: Sequence[str],
    name_to_email: Mapping[str, str],
    my_email: str,
    owner_email: str,
) -> tuple[str, str]:
  """Resolves (counterparty_email, counterparty_label) without self-matching."""
  if other_mentions:
    return other_mentions[0], other_mentions[0]
  if not root_is_me:
    return root_email, root_email or root_name
  for reply in reversed(msg_replies):
    r_author = reply.get('author') or {}
    if r_author.get('me'):
      continue
    r_name = str(r_author.get('displayName', '')).strip()
    r_email = str(
        r_author.get('emailAddress', '')
    ).strip().lower() or name_to_email.get(r_name.lower(), '')
    if my_email and r_email == my_email:
      continue
    if r_email or r_name:
      return r_email, r_email or r_name
  if owner_email and owner_email != my_email:
    return owner_email, owner_email
  return '', 'doc_owner'


def _latest_user_doc_activity(
    author_name: str,
    author_email: str,
    exclude_comment_id: str,
    revisions: Sequence[Mapping[str, Any]],
    comments: Sequence[Mapping[str, Any]],
) -> datetime.datetime | None:
  """Returns the latest revision or comment timestamp by author elsewhere."""
  norm_name = author_name.strip().lower()
  norm_email = author_email.strip().lower()
  latest: datetime.datetime | None = None

  def matches(user: Mapping[str, Any]) -> bool:
    u_email = str(user.get('emailAddress', '')).strip().lower()
    u_name = str(user.get('displayName', '')).strip().lower()
    if norm_email and u_email and norm_email == u_email:
      return True
    return bool(norm_name and u_name and norm_name == u_name)

  def bump(ts: str) -> None:
    nonlocal latest
    dt = parse_utc(ts)
    if dt and (latest is None or dt > latest):
      latest = dt

  for rev in revisions:
    user = rev.get('lastModifyingUser') or {}
    if matches(user):
      bump(str(rev.get('modifiedTime', '')))

  for thread in comments:
    if str(thread.get('id', '')) == exclude_comment_id:
      continue
    if matches(thread.get('author') or {}):
      bump(str(thread.get('createdTime', '')))
    for reply in thread.get('replies') or []:
      if matches(reply.get('author') or {}):
        bump(str(reply.get('createdTime', '')))

  return latest


def _find_sibling_script(
    skills_root: pathlib.Path,
    dir_candidates: Sequence[str],
    script_name: str,
) -> pathlib.Path | None:
  """Resolves a sibling skill script across hyphen or underscore layouts."""
  for dname in dir_candidates:
    candidate = skills_root / dname / 'scripts' / script_name
    if candidate.exists():
      return candidate
  return None


def _run_bundled_linters(
    skills_root: pathlib.Path,
    tab_files: Mapping[str, pathlib.Path],
    suppress_missing_fence_lang: bool,
) -> JsonDict:
  """Runs sibling doc_lint.py and diagram_lint.py across exported tabs."""
  doc_lint = _find_sibling_script(
      skills_root, ('writing-tech-docs', 'writing_tech_docs'), 'doc_lint.py'
  )
  diag_lint = _find_sibling_script(
      skills_root,
      ('tech-docs-diagrams', 'tech_docs_diagrams'),
      'diagram_lint.py',
  )
  out: JsonDict = {'doc_lint': {}, 'diagram_lint': {}}
  for tab_id, md_path in tab_files.items():
    if doc_lint is not None:
      proc = subprocess.run(
          [sys.executable, str(doc_lint), str(md_path)],
          check=False,
          capture_output=True,
          text=True,
      )
      lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
      if suppress_missing_fence_lang:
        lines = [ln for ln in lines if _FENCE_NO_LANG_MSG not in ln]
      rc = 0 if not lines else proc.returncode
      out['doc_lint'][tab_id] = {
          'returncode': rc,
          'lines': lines[:60],
      }
    if diag_lint is not None:
      proc = subprocess.run(
          [sys.executable, str(diag_lint), str(md_path)],
          check=False,
          capture_output=True,
          text=True,
      )
      lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
      out['diagram_lint'][tab_id] = {
          'returncode': proc.returncode,
          'lines': lines[:40],
      }
  return out


def _cleanup_old_digest_files(
    doc_dir: pathlib.Path, valid_digest_names: set[str]
) -> None:
  """Deletes superseded digest_*.md files so only the latest digest remains."""
  if not doc_dir.exists():
    return
  for child in doc_dir.iterdir():
    if (
        child.is_file()
        and child.name.startswith('digest_')
        and child.name.endswith('.md')
        and child.name not in valid_digest_names
    ):
      child.unlink()


def collect_document(
    ws: _WorkspaceCollector,
    target: DocTarget,
    state_dir: pathlib.Path,
    skills_root: pathlib.Path,
    now: datetime.datetime,
    lookback_days: int,
    force_full: bool,
) -> JsonDict:
  """Collects cumulative review-round state, diffs, staleness, and linters."""
  doc_dir = state_dir / target.doc_id
  doc_dir.mkdir(parents=True, exist_ok=True)
  state_path = doc_dir / 'state.json'
  prior_state: JsonDict = (
      json.loads(state_path.read_text(encoding='utf-8'))
      if state_path.exists()
      else {}
  )
  first_run = not bool(prior_state.get('last_ack_utc'))
  last_ack_utc = str(prior_state.get('last_ack_utc') or '')
  last_digest_utc = str(prior_state.get('last_digest_utc') or '')
  ack_dt = parse_utc(last_ack_utc) or (
      now - datetime.timedelta(days=max(1, lookback_days))
  )
  thread_overrides: dict[str, str] = dict(
      prior_state.get('thread_categories') or {}
  )
  deferred_map: dict[str, JsonDict] = {
      str(k): dict(v)
      for k, v in (prior_state.get('deferred_threads') or {}).items()
      if isinstance(v, dict)
  }
  is_collaborator = target.role == 'collaborator'

  canonical_url = ws.get_url(target.doc_id, target.resource_key, target.url)
  tabs = ws.get_tabs(target.doc_id, target.resource_key)
  comments = ws.get_comments(target.doc_id, target.resource_key)
  revisions = ws.get_revisions(target.doc_id, target.resource_key)
  permissions = ws.get_permissions(target.doc_id, target.resource_key)
  anchors = ws.get_anchor_health(target.doc_id, target.resource_key)
  suggestions_doc = ws.get_suggestions_doc(target.doc_id, target.resource_key)
  clean_doc = ws.get_clean_doc(target.doc_id, target.resource_key)
  title = str(
      suggestions_doc.get('title')
      or clean_doc.get('title')
      or prior_state.get('title')
      or target.doc_id
  )

  anchor_by_comment: dict[str, JsonDict] = {}
  for ac in anchors.get('comments') or []:
    if isinstance(ac, dict) and ac.get('commentId'):
      anchor_by_comment[str(ac['commentId'])] = ac

  name_to_email, my_email, owner_email = _build_directory(
      permissions, revisions, comments
  )
  org_domain = my_email.split('@', 1)[1] if '@' in my_email else ''
  suggestions = extract_pending_suggestions(suggestions_doc, comments)

  ack_seen_replies: dict[str, list[str]] = dict(
      prior_state.get('ack_thread_replies') or {}
  )
  open_threads: list[JsonDict] = []
  newly_resolved: list[JsonDict] = []
  staleness_alerts: list[JsonDict] = []
  upcoming_events: list[JsonDict] = []
  legacy_ids: list[str] = []
  active_deferred_ids: list[str] = []
  legacy_max_days = 0.0
  uninvolved_skipped = 0
  commenter_open_counts: dict[str, int] = {}
  current_stage_map: dict[str, int] = {}
  relevant_tab_ids: set[str] = {
      str(s.get('tab_id', 't.0')) for s in suggestions
  }

  for thread in comments:
    cid = str(thread.get('id', ''))
    if not cid or not _COMMENT_ID_RE.match(cid):
      continue
    resolved = bool(thread.get('resolved'))
    replies = [r for r in thread.get('replies') or [] if isinstance(r, dict)]
    root_author = thread.get('author') or {}
    root_name = str(root_author.get('displayName', '')).strip()
    root_email = str(
        root_author.get('emailAddress', '')
    ).strip().lower() or name_to_email.get(root_name.lower(), '')
    involves_me = _thread_involves_me(thread, replies, root_email, my_email)

    if is_collaborator and not involves_me:
      if not resolved:
        uninvolved_skipped += 1
      continue

    reply_ids = [str(r.get('id', '')) for r in replies if r.get('id')]
    prev_reply_ids = set(ack_seen_replies.get(cid, []))
    created_dt = parse_utc(str(thread.get('createdTime', '')))
    is_new_thread = cid not in ack_seen_replies and (
        first_run or (created_dt is not None and created_dt >= ack_dt)
    )
    new_reply_ids = [rid for rid in reply_ids if rid not in prev_reply_ids]

    if resolved:
      deferred_map.pop(cid, None)
      if cid in ack_seen_replies or (
          replies
          and (parse_utc(str(replies[-1].get('createdTime', ''))) or ack_dt)
          >= ack_dt
          and not first_run
      ):
        last_rep_txt = str((replies[-1] if replies else {}).get('content', ''))
        newly_resolved.append({
            'comment_id': cid,
            'author': root_name,
            'content': str(thread.get('content', ''))[:240],
            'last_reply': last_rep_txt[:240],
        })
      continue

    if root_email:
      commenter_open_counts[root_email] = (
          commenter_open_counts.get(root_email, 0) + 1
      )

    ac_info = anchor_by_comment.get(cid, {})
    tab_id = str(ac_info.get('tabId', 't.0'))
    relevant_tab_ids.add(tab_id)

    root_is_me = bool(root_author.get('me')) or (
        bool(my_email) and root_email == my_email
    )
    msg_replies = [r for r in replies if r.get('content') or r.get('action')]
    last_actor = (
        (msg_replies[-1].get('author') or {}) if msg_replies else root_author
    )
    last_is_me = bool(last_actor.get('me')) or (
        bool(my_email)
        and str(last_actor.get('emailAddress', '')).lower() == my_email
    )
    last_ts_str = str(
        (msg_replies[-1] if msg_replies else thread).get('createdTime', '')
    )
    last_dt = parse_utc(last_ts_str) or now
    last_text = str(
        (msg_replies[-1] if msg_replies else thread).get('content', '')
    )
    any_me_reply = any(
        bool((r.get('author') or {}).get('me'))
        or (
            bool(my_email)
            and str((r.get('author') or {}).get('emailAddress', '')).lower()
            == my_email
        )
        for r in msg_replies
    )

    mentions = _EMAIL_MENTION_RE.findall(
        last_text + ' ' + str(thread.get('content', ''))
    )
    other_mentions = [m.lower() for m in mentions if m.lower() != my_email]
    counterparty_email, counterparty_label = _resolve_counterparty(
        root_is_me=root_is_me,
        root_name=root_name,
        root_email=root_email,
        msg_replies=msg_replies,
        other_mentions=other_mentions,
        name_to_email=name_to_email,
        my_email=my_email,
        owner_email=owner_email,
    )

    reply_sentiment = classify_reply_sentiment(last_text) if last_is_me else ''
    override = thread_overrides.get(cid, '')
    if override in _VALID_THREAD_CATEGORIES:
      base_cat = override
    elif last_is_me:
      if reply_sentiment == 'done_fix':
        base_cat = 'complex_fix'
      elif reply_sentiment == 'pure_agreement':
        base_cat = 'ready_to_resolve'
      elif root_is_me and reply_sentiment == 'question_or_followup':
        base_cat = 'unanswered'
      else:
        base_cat = 'disagreement'
    elif root_is_me:
      base_cat = 'verify_owner_reply'
    elif other_mentions and any_me_reply:
      base_cat = 'unanswered'
    else:
      base_cat = 'needs_author_triage'

    disco_url = (
        f'{canonical_url}&disco={cid}'
        if '?' in canonical_url
        else f'{canonical_url}?disco={cid}'
    )

    raw_idle_days = max(0.0, (now.timestamp() - last_dt.timestamp()) / 86400.0)
    has_unacked_activity = (not first_run) and (
        is_new_thread or bool(new_reply_ids)
    )
    is_legacy = (
        raw_idle_days > LEGACY_BACKLOG_DAYS
        and not has_unacked_activity
        and not _has_recent_me_mention(thread, replies, my_email, now)
    )

    is_deferred = False
    deferred_until_utc = ''
    defer_woke_reason = ''
    if cid in deferred_map:
      d_info = deferred_map[cid]
      cur_last_rid = reply_ids[-1] if reply_ids else ''
      until_dt = parse_utc(str(d_info.get('until_utc', '')))
      if cur_last_rid != str(d_info.get('last_reply_id', '')):
        deferred_map.pop(cid, None)
        defer_woke_reason = 'new_reply'
      elif until_dt is None or now >= until_dt:
        deferred_map.pop(cid, None)
        defer_woke_reason = 'defer_expired'
      else:
        is_deferred = True
        deferred_until_utc = str(d_info.get('until_utc', ''))
        active_deferred_ids.append(cid)
        rem_d = max(0.0, round((until_dt - now).total_seconds() / 86400.0, 2))
        upcoming_events.append({
            'comment_id': cid,
            'counterparty': counterparty_label,
            'category': 'deferred_by_user',
            'next_stage': 'defer_expiry',
            'next_stage_in_days': rem_d,
            'next_stage_date': until_dt.date().isoformat(),
        })

    best_eval: WarningEval | None = None
    post_act_str = ''
    cal_ok = False
    if is_legacy:
      legacy_ids.append(cid)
      legacy_max_days = max(legacy_max_days, round(raw_idle_days, 1))
      current_stage_map[cid] = 0
    elif is_deferred:
      current_stage_map[cid] = 0
    elif base_cat != 'needs_author_triage':
      ooo_spans, cal_ok = (
          ws.get_ooo_intervals(counterparty_email, last_dt, org_domain)
          if counterparty_email
          else ((), False)
      )
      net_days, excl_ooo = compute_net_idle_days(last_dt, now, ooo_spans)
      bus_days = compute_net_business_days(last_dt, now, ooo_spans)
      due = target.deadline if base_cat == 'unanswered' else ''
      best_eval = evaluate_warning_schedule(
          base_cat,
          net_days,
          excl_ooo,
          now,
          due,
          net_business_days=bus_days,
      )
      if (
          last_is_me
          and not root_is_me
          and base_cat in ('complex_fix', 'disagreement')
      ):
        act_dt = _latest_user_doc_activity(
            root_name, root_email, cid, revisions, comments
        )
        if (
            act_dt
            and (act_dt - last_dt).total_seconds()
            >= POST_ACTIVITY_MIN_OFFSET_DAYS * 86400.0
        ):
          post_act_str = format_utc(act_dt)
          pa_net, pa_ooo = compute_net_idle_days(act_dt, now, ooo_spans)
          pa_bus = compute_net_business_days(act_dt, now, ooo_spans)
          pa_eval = evaluate_warning_schedule(
              'post_activity',
              pa_net,
              pa_ooo,
              now,
              net_business_days=pa_bus,
          )
          if _STAGE_RANK_MAP[pa_eval.stage] > _STAGE_RANK_MAP[best_eval.stage]:
            best_eval = pa_eval
      stage_name = best_eval.stage if best_eval else 'none'
      current_stage_map[cid] = _STAGE_RANK_MAP[stage_name]
    else:
      current_stage_map[cid] = 0

    cal_note = '' if cal_ok else 'external_or_unverified_ooo'
    rec: JsonDict = {
        'comment_id': cid,
        'disco_url': disco_url,
        'tab_id': tab_id,
        'anchor_status': str(ac_info.get('anchorStatus', 'unknown')),
        'quote': str(
            ac_info.get('quote')
            or (thread.get('quotedFileContent') or {}).get('value')
            or ''
        )[:200],
        'author_name': root_name,
        'author_email': root_email,
        'counterparty_email': counterparty_email,
        'counterparty_label': counterparty_label,
        'content': str(thread.get('content', '')),
        'replies': [
            {
                'id': str(r.get('id', '')),
                'author': str((r.get('author') or {}).get('displayName', '')),
                'me': bool((r.get('author') or {}).get('me')),
                'created_time': str(r.get('createdTime', '')),
                'action': str(r.get('action', '')),
                'content': str(r.get('content', '')),
            }
            for r in replies
        ],
        'is_new_since_ack': is_new_thread,
        'new_reply_ids_since_ack': new_reply_ids,
        'triage_category': base_cat,
        'reply_sentiment': reply_sentiment,
        'is_legacy_backlog': is_legacy,
        'is_deferred': is_deferred,
        'deferred_until_utc': deferred_until_utc,
        'defer_woke_reason': defer_woke_reason,
        'post_reply_author_doc_activity_utc': post_act_str,
        'calendar_checked': cal_ok,
        'calendar_note': cal_note if base_cat != 'needs_author_triage' else '',
    }
    if best_eval and not is_legacy and not is_deferred:
      eval_dict = dataclasses.asdict(best_eval)
      rec['staleness'] = eval_dict
      if best_eval.stage != 'none':
        staleness_alerts.append({
            'comment_id': cid,
            'disco_url': disco_url,
            'counterparty': counterparty_label,
            'calendar_checked': cal_ok,
            'calendar_note': cal_note,
            **eval_dict,
        })
      elif best_eval.next_stage:
        upcoming_events.append({
            'comment_id': cid,
            'counterparty': counterparty_label,
            'category': best_eval.category,
            'next_stage': best_eval.next_stage,
            'next_stage_in_days': best_eval.next_stage_in_days,
            'next_stage_date': best_eval.next_stage_date,
        })
    open_threads.append(rec)

  # Check optional watchlist-configured approvers with 0 open comments.
  if not is_collaborator:
    for approver in target.approvers:
      if approver.get('me'):
        continue
      status = str(approver.get('status', '')).lower()
      if 'approv' in status or 'lgtm' in status:
        continue
      a_email = str(approver.get('emailAddress') or '').strip().lower()
      if a_email and commenter_open_counts.get(a_email, 0) > 0:
        continue
      ooo_spans, ap_cal_ok = (
          ws.get_ooo_intervals(a_email, ack_dt, org_domain)
          if a_email
          else ((), False)
      )
      net_days, excl_ooo = compute_net_idle_days(ack_dt, now, ooo_spans)
      ap_bus = compute_net_business_days(ack_dt, now, ooo_spans)
      ap_eval = evaluate_warning_schedule(
          'pending_approver',
          net_days,
          excl_ooo,
          now,
          target.deadline,
          net_business_days=ap_bus,
      )
      key = f'approver:{a_email or approver.get("displayName", "unknown")}'
      current_stage_map[key] = _STAGE_RANK_MAP[ap_eval.stage]
      if ap_eval.stage != 'none':
        staleness_alerts.append({
            'comment_id': key,
            'disco_url': canonical_url,
            'counterparty': a_email,
            'calendar_checked': ap_cal_ok,
            'calendar_note': '' if ap_cal_ok else 'external_or_unverified_ooo',
            **dataclasses.asdict(ap_eval),
        })

  if is_collaborator:
    relevant_orphans = sum(
        1 for t in open_threads if t['anchor_status'] in ('orphaned', 'broken')
    )
    anchor_summary = {
        'all_intact': relevant_orphans == 0,
        'orphaned_count': sum(
            1 for t in open_threads if t['anchor_status'] == 'orphaned'
        ),
        'broken_count': sum(
            1 for t in open_threads if t['anchor_status'] == 'broken'
        ),
    }
  else:
    anchor_summary = {
        'all_intact': bool(anchors.get('allIntact', True)),
        'orphaned_count': int(anchors.get('orphanedCount', 0)),
        'broken_count': int(anchors.get('brokenCount', 0)),
    }
  cur_broken_anchors = (
      anchor_summary['orphaned_count'] + anchor_summary['broken_count']
  )
  active_open_cnt = sum(1 for t in open_threads if not t['is_legacy_backlog'])

  current_tabs: dict[str, str] = {}
  restrict_tabs = is_collaborator and len(tabs) > COLLABORATOR_MAX_ALL_TABS
  for tab in tabs:
    tid = str(tab['tabId'])
    if restrict_tabs and tid not in relevant_tab_ids:
      continue
    md = ws.pull_tab_markdown(
        target.doc_id, tid, target.resource_key, target.mime_type
    )
    if md is not None:
      current_tabs[tid] = md

  recent_revisions: list[JsonDict] = []
  last_digest_dt = parse_utc(last_digest_utc)
  revs_since_digest: list[JsonDict] = []
  for rev in revisions:
    rev_dt = parse_utc(str(rev.get('modifiedTime', '')))
    user = rev.get('lastModifyingUser') or {}
    rec_rev = {
        'id': str(rev.get('id', '')),
        'modified_time': str(rev.get('modifiedTime', '')),
        'editor_name': str(user.get('displayName', '')),
        'editor_email': str(user.get('emailAddress', '')),
        'me': bool(user.get('me')),
    }
    if rev_dt and rev_dt >= ack_dt:
      recent_revisions.append(rec_rev)
    if rev_dt and last_digest_dt and rev_dt > last_digest_dt:
      revs_since_digest.append(rec_rev)

  prev_digest_meta: JsonDict = dict(prior_state.get('last_digest') or {})
  prev_tab_hashes: dict[str, str] = dict(
      prev_digest_meta.get('tab_hashes') or {}
  )
  cur_tab_hashes = {tid: _sha256_text(txt) for tid, txt in current_tabs.items()}
  changed_tab_ids = {
      tid for tid, h in cur_tab_hashes.items() if prev_tab_hashes.get(tid) != h
  }
  relevant_comment_ids = {t['comment_id'] for t in open_threads}
  cur_comment_fp = _sha256_text(
      json.dumps(
          [
              (
                  str(c.get('id', '')),
                  bool(c.get('resolved')),
                  len(c.get('replies') or []),
              )
              for c in comments
              if not is_collaborator
              or str(c.get('id', '')) in relevant_comment_ids
          ],
          sort_keys=True,
      )
  )
  cur_sugg_fp = _sha256_text(
      json.dumps([s['suggestion_id'] for s in suggestions], sort_keys=True)
  )
  raw_ranks = prev_digest_meta.get('stage_ranks') or {}
  prev_stages: dict[str, int] = {str(k): int(v) for k, v in raw_ranks.items()}
  stage_advanced = any(
      rank > prev_stages.get(cid, 0) for cid, rank in current_stage_map.items()
  )
  cur_deferred_sorted = sorted(active_deferred_ids)
  prev_deferred_sorted = sorted(
      str(x) for x in prev_digest_meta.get('deferred_ids') or []
  )
  deferral_changed = cur_deferred_sorted != prev_deferred_sorted

  non_tab_changed = (
      first_run
      or force_full
      or cur_comment_fp != prev_digest_meta.get('comment_fp', '')
      or cur_sugg_fp != prev_digest_meta.get('suggestion_fp', '')
      or stage_advanced
      or deferral_changed
  )

  upcoming_events.sort(key=lambda e: (e['next_stage_in_days'], e['comment_id']))
  next_event = upcoming_events[0] if upcoming_events else None
  now_str = format_utc(now)

  if changed_tab_ids and not non_tab_changed:
    check_revs = revs_since_digest or recent_revisions
    is_self_only = (
        bool(check_revs)
        and all(r['me'] for r in recent_revisions)
        and all(r['me'] for r in check_revs)
    )
    prev_broken = int(prev_digest_meta.get('broken_anchors', 0))
    severed_anchor = cur_broken_anchors > prev_broken
    unreplied_on_edited = any(
        t['tab_id'] in changed_tab_ids
        and not t['is_legacy_backlog']
        and not t['is_deferred']
        and not t['replies']
        for t in open_threads
    )
    if is_self_only and not severed_anchor and not unreplied_on_edited:
      valid_digests: set[str] = set()
      for tid, md in current_tabs.items():
        (doc_dir / _safe_tab_filename('ack', tid)).write_text(
            md, encoding='utf-8'
        )
        dfile = doc_dir / _safe_tab_filename('digest', tid)
        dfile.write_text(md, encoding='utf-8')
        valid_digests.add(dfile.name)
      _cleanup_old_digest_files(doc_dir, valid_digests)
      auto_state: JsonDict = {
          'doc_id': target.doc_id,
          'title': title,
          'url': canonical_url,
          'role': target.role,
          'mime_type': target.mime_type,
          'open_threads_count': active_open_cnt,
          'last_ack_utc': now_str,
          'last_digest_utc': now_str,
          'ack_thread_replies': ack_seen_replies,
          'thread_categories': thread_overrides,
          'deferred_threads': deferred_map,
          'last_digest': {
              'tab_hashes': cur_tab_hashes,
              'comment_fp': cur_comment_fp,
              'suggestion_fp': cur_sugg_fp,
              'stage_ranks': current_stage_map,
              'deferred_ids': cur_deferred_sorted,
              'broken_anchors': cur_broken_anchors,
          },
      }
      state_path.write_text(
          json.dumps(auto_state, indent=2, sort_keys=False) + '\n',
          encoding='utf-8',
      )
      return {
          'doc_id': target.doc_id,
          'title': title,
          'url': canonical_url,
          'role': target.role,
          'source': target.source,
          'reasons': list(target.reasons),
          'deadline': target.deadline,
          'status': 'quiet',
          'self_edits_auto_acked': True,
          'quiet_since_utc': now_str,
          'last_ack_utc': now_str,
          'unacked_digest_pending': False,
          'open_threads_count': active_open_cnt,
          'deferred_open_threads_count': len(active_deferred_ids),
          'active_staleness_alerts_count': len(staleness_alerts),
          'next_staleness_event': next_event,
      }

  changed_since_digest = bool(changed_tab_ids) or non_tab_changed

  if not changed_since_digest:
    return {
        'doc_id': target.doc_id,
        'title': title,
        'url': canonical_url,
        'role': target.role,
        'source': target.source,
        'reasons': list(target.reasons),
        'deadline': target.deadline,
        'status': 'quiet',
        'self_edits_auto_acked': False,
        'quiet_since_utc': last_digest_utc,
        'last_ack_utc': last_ack_utc,
        'unacked_digest_pending': bool(
            last_ack_utc and last_digest_utc and last_ack_utc < last_digest_utc
        ),
        'open_threads_count': active_open_cnt,
        'deferred_open_threads_count': len(active_deferred_ids),
        'active_staleness_alerts_count': len(staleness_alerts),
        'next_staleness_event': next_event,
    }

  tab_diffs: list[JsonDict] = []
  valid_digest_files: set[str] = set()
  with tempfile.TemporaryDirectory() as tmp:
    lint_paths: dict[str, pathlib.Path] = {}
    for tab in tabs:
      tid = str(tab['tabId'])
      if tid not in current_tabs:
        continue
      cur_md = current_tabs[tid]
      ack_file = doc_dir / _safe_tab_filename('ack', tid)
      digest_file = doc_dir / _safe_tab_filename('digest', tid)
      valid_digest_files.add(digest_file.name)
      if first_run or not ack_file.exists():
        ack_file.write_text(cur_md, encoding='utf-8')
        base_md = cur_md
      else:
        base_md = ack_file.read_text(encoding='utf-8')
      digest_file.write_text(cur_md, encoding='utf-8')
      diff_lines = list(
          difflib.unified_diff(
              base_md.splitlines(),
              cur_md.splitlines(),
              fromfile=f'ack/{tid} ({tab.get("title", tid)})',
              tofile=f'current/{tid} ({tab.get("title", tid)})',
              lineterm='',
          )
      )
      if diff_lines:
        tab_diffs.append({
            'tab_id': tid,
            'tab_title': str(tab.get('title', tid)),
            'changed_lines': sum(
                1
                for ln in diff_lines
                if (ln.startswith('+') and not ln.startswith('+++'))
                or (ln.startswith('-') and not ln.startswith('---'))
            ),
            'unified_diff': '\n'.join(diff_lines[:400]),
        })
      tmp_md = pathlib.Path(tmp) / _safe_tab_filename('lint', tid)
      tmp_md.write_text(cur_md, encoding='utf-8')
      lint_paths[tid] = tmp_md

    if is_collaborator:
      linters: JsonDict = {
          'doc_lint': {},
          'diagram_lint': {},
          'skipped_for_role': 'collaborator',
      }
    else:
      linters = _run_bundled_linters(
          skills_root,
          lint_paths,
          suppress_missing_fence_lang=(
              target.mime_type == _CONVERTED_GDOC_MIME
          ),
      )

  _cleanup_old_digest_files(doc_dir, valid_digest_files)

  if first_run:
    last_ack_utc = now_str
    ack_seen_replies = {
        str(c.get('id', '')): [
            str(r.get('id', ''))
            for r in c.get('replies') or []
            if isinstance(r, dict) and r.get('id')
        ]
        for c in comments
        if isinstance(c, dict) and c.get('id')
    }

  updated_state: JsonDict = {
      'doc_id': target.doc_id,
      'title': title,
      'url': canonical_url,
      'role': target.role,
      'mime_type': target.mime_type,
      'open_threads_count': active_open_cnt,
      'last_ack_utc': last_ack_utc,
      'last_digest_utc': now_str,
      'ack_thread_replies': ack_seen_replies,
      'thread_categories': thread_overrides,
      'deferred_threads': deferred_map,
      'last_digest': {
          'tab_hashes': cur_tab_hashes,
          'comment_fp': cur_comment_fp,
          'suggestion_fp': cur_sugg_fp,
          'stage_ranks': current_stage_map,
          'deferred_ids': cur_deferred_sorted,
          'broken_anchors': cur_broken_anchors,
      },
  }
  state_path.write_text(
      json.dumps(updated_state, indent=2, sort_keys=False) + '\n',
      encoding='utf-8',
  )

  return {
      'doc_id': target.doc_id,
      'title': title,
      'url': canonical_url,
      'role': target.role,
      'source': target.source,
      'reasons': list(target.reasons),
      'deadline': target.deadline,
      'status': 'active_digest',
      'first_run_bootstrap': first_run,
      'cumulative_since_ack_utc': last_ack_utc,
      'digest_generated_utc': now_str,
      'summary_counts': {
          'open_threads': len(open_threads),
          'active_open_threads': active_open_cnt,
          'deferred_open_threads': len(active_deferred_ids),
          'uninvolved_open_threads_skipped': uninvolved_skipped,
          'legacy_backlog_threads_collapsed': len(legacy_ids),
          'new_threads_since_ack': sum(
              1 for t in open_threads if t['is_new_since_ack']
          ),
          'threads_with_new_replies': sum(
              1 for t in open_threads if t['new_reply_ids_since_ack']
          ),
          'newly_resolved_threads': len(newly_resolved),
          'pending_suggestions': len(suggestions),
          'tabs_with_prose_diffs': len(tab_diffs),
          'collaborator_revisions_since_ack': sum(
              1 for r in recent_revisions if not r['me']
          ),
          'staleness_alerts': len(staleness_alerts),
          'broken_or_orphaned_anchors': cur_broken_anchors,
      },
      'legacy_backlog': {
          'count': len(legacy_ids),
          'max_idle_days': legacy_max_days,
          'comment_ids': legacy_ids,
      },
      'deferred_threads': {
          cid: deferred_map[cid] for cid in cur_deferred_sorted
      },
      'revisions_since_ack': recent_revisions,
      'tab_diffs_since_ack': tab_diffs,
      'pending_suggestions': suggestions,
      'open_threads': open_threads,
      'newly_resolved_threads': newly_resolved,
      'staleness_alerts': staleness_alerts,
      'next_staleness_event': next_event,
      'anchor_health': anchor_summary,
      'linters': linters,
  }


def _filter_ack_replies(
    comments: Sequence[Mapping[str, Any]],
    cutoff_utc: str,
    refresh_live: bool,
) -> dict[str, list[str]]:
  """Builds ack_thread_replies while keeping post-digest collaborator replies."""
  cutoff_dt = parse_utc(cutoff_utc) if not refresh_live else None
  ack_replies: dict[str, list[str]] = {}
  for comment in comments:
    if not isinstance(comment, dict) or not comment.get('id'):
      continue
    cid = str(comment['id'])
    c_dt = parse_utc(str(comment.get('createdTime', '')))
    c_me = bool((comment.get('author') or {}).get('me'))
    if cutoff_dt and c_dt and c_dt > cutoff_dt and not c_me:
      continue
    rids: list[str] = []
    for reply in comment.get('replies') or []:
      if not isinstance(reply, dict) or not reply.get('id'):
        continue
      r_dt = parse_utc(str(reply.get('createdTime', '')))
      r_me = bool((reply.get('author') or {}).get('me'))
      if cutoff_dt and r_dt and r_dt > cutoff_dt and not r_me:
        continue
      rids.append(str(reply['id']))
    ack_replies[cid] = rids
  return ack_replies


def _count_active_open_threads(
    comments: Sequence[Mapping[str, Any]],
    role: str,
    my_email: str,
    now: datetime.datetime,
) -> int:
  """Counts non-resolved, non-legacy open threads (scoped by role)."""
  count = 0
  for thread in comments:
    if not isinstance(thread, dict) or bool(thread.get('resolved')):
      continue
    replies = [r for r in thread.get('replies') or [] if isinstance(r, dict)]
    root_author = thread.get('author') or {}
    root_email = str(root_author.get('emailAddress', '')).strip().lower()
    if role == 'collaborator' and not _thread_involves_me(
        thread, replies, root_email, my_email
    ):
      continue
    msg_replies = [r for r in replies if r.get('content') or r.get('action')]
    last_ts = str(
        (msg_replies[-1] if msg_replies else thread).get('createdTime', '')
    )
    last_dt = parse_utc(last_ts) or now
    raw_idle = max(0.0, (now.timestamp() - last_dt.timestamp()) / 86400.0)
    if raw_idle > LEGACY_BACKLOG_DAYS and not _has_recent_me_mention(
        thread, replies, my_email, now
    ):
      continue
    count += 1
  return count


def acknowledge_document(
    ws: _WorkspaceCollector,
    doc_spec: str,
    state_dir: pathlib.Path,
    thread_sets: Sequence[str],
    now: datetime.datetime,
    refresh_live: bool = False,
    defer_threads: Sequence[str] = (),
    defer_days: float = DEFAULT_DEFER_DAYS,
    clear_defers: Sequence[str] = (),
    role_override: str = '',
) -> JsonDict:
  """Promotes local digest_<tab>.md to ack_<tab>.md and updates deferrals."""
  doc_id, rkey, fallback_url = parse_doc_spec(doc_spec)
  doc_dir = state_dir / doc_id
  doc_dir.mkdir(parents=True, exist_ok=True)
  state_path = doc_dir / 'state.json'
  prior: JsonDict = (
      json.loads(state_path.read_text(encoding='utf-8'))
      if state_path.exists()
      else {}
  )
  overrides: dict[str, str] = dict(prior.get('thread_categories') or {})
  for item in thread_sets:
    if '=' not in item:
      raise ValueError(f'Expected COMMENT_ID=CATEGORY, got {item!r}')
    cid, cat = item.split('=', 1)
    cid = cid.strip()
    cat = cat.strip()
    if not _COMMENT_ID_RE.match(cid) or cat not in _VALID_THREAD_CATEGORIES:
      raise ValueError(f'Invalid --set-thread {item!r}')
    overrides[cid] = cat

  prior_digest_utc = str(prior.get('last_digest_utc') or '')
  prior_digest_meta: JsonDict = dict(prior.get('last_digest') or {})
  local_digests = sorted(doc_dir.glob('digest_*.md'))
  comments = ws.get_comments(doc_id, rkey)
  _, my_email, _ = _build_directory((), (), comments)
  eff_role = str(role_override or prior.get('role') or 'author')
  eff_mime = str(prior.get('mime_type') or _CONVERTED_GDOC_MIME)

  tab_hashes: dict[str, str] = {}
  valid_digests: set[str] = set()
  now_str = format_utc(now)

  if local_digests and not refresh_live:
    canonical_url = str(prior.get('url') or fallback_url)
    for dfile in local_digests:
      tid = dfile.name[len('digest_') : -len('.md')]
      md = dfile.read_text(encoding='utf-8')
      (doc_dir / _safe_tab_filename('ack', tid)).write_text(
          md, encoding='utf-8'
      )
      valid_digests.add(dfile.name)
      tab_hashes[tid] = _sha256_text(md)
    sugg_fp = str(prior_digest_meta.get('suggestion_fp') or '')
    ack_utc = prior_digest_utc or now_str
    digest_utc = prior_digest_utc or now_str
  else:
    canonical_url = ws.get_url(doc_id, rkey, fallback_url)
    tabs = ws.get_tabs(doc_id, rkey)
    suggestions = extract_pending_suggestions(
        ws.get_suggestions_doc(doc_id, rkey), comments
    )
    for tab in tabs:
      tid = str(tab['tabId'])
      md = ws.pull_tab_markdown(doc_id, tid, rkey, eff_mime)
      if md is None:
        continue
      (doc_dir / _safe_tab_filename('ack', tid)).write_text(
          md, encoding='utf-8'
      )
      dfile = doc_dir / _safe_tab_filename('digest', tid)
      dfile.write_text(md, encoding='utf-8')
      valid_digests.add(dfile.name)
      tab_hashes[tid] = _sha256_text(md)
    sugg_fp = _sha256_text(
        json.dumps([s['suggestion_id'] for s in suggestions], sort_keys=True)
    )
    ack_utc = now_str
    digest_utc = now_str

  _cleanup_old_digest_files(doc_dir, valid_digests)

  ack_replies = _filter_ack_replies(
      comments, prior_digest_utc, refresh_live=refresh_live
  )
  known_ids = {
      str(c.get('id', ''))
      for c in comments
      if isinstance(c, dict) and c.get('id')
  }
  resolved_ids = {
      str(c.get('id', ''))
      for c in comments
      if isinstance(c, dict) and c.get('id') and bool(c.get('resolved'))
  }

  def _norm_cid(raw_cid: str) -> str:
    cleaned = raw_cid.strip()
    if cleaned not in known_ids and f'doco.{cleaned}' in known_ids:
      return f'doco.{cleaned}'
    return cleaned

  deferred_map: dict[str, JsonDict] = {
      str(k): dict(v)
      for k, v in (prior.get('deferred_threads') or {}).items()
      if isinstance(v, dict) and str(k) not in resolved_ids
  }
  for raw_clear in clear_defers:
    deferred_map.pop(_norm_cid(raw_clear), None)

  until_str = format_utc(now + datetime.timedelta(days=max(0.1, defer_days)))
  for raw_defer in defer_threads:
    cid = _norm_cid(raw_defer)
    if not _COMMENT_ID_RE.match(cid):
      raise ValueError(f'Invalid --defer-thread {raw_defer!r}')
    rids = ack_replies.get(cid, [])
    deferred_map[cid] = {
        'deferred_at_utc': now_str,
        'until_utc': until_str,
        'last_reply_id': rids[-1] if rids else '',
    }

  active_deferred_sorted = sorted(
      cid
      for cid, info in deferred_map.items()
      if (parse_utc(str(info.get('until_utc', ''))) or now) > now
  )
  open_cnt = _count_active_open_threads(comments, eff_role, my_email, now)
  relevant_cids: set[str] | None = None
  if eff_role == 'collaborator':
    relevant_cids = {
        str(c.get('id', ''))
        for c in comments
        if isinstance(c, dict)
        and _thread_involves_me(
            c,
            [r for r in c.get('replies') or [] if isinstance(r, dict)],
            str((c.get('author') or {}).get('emailAddress', ''))
            .strip()
            .lower(),
            my_email,
        )
    }

  comment_fp = _sha256_text(
      json.dumps(
          [
              (
                  str(c.get('id', '')),
                  bool(c.get('resolved')),
                  len(ack_replies.get(str(c.get('id', '')), [])),
              )
              for c in comments
              if isinstance(c, dict)
              and str(c.get('id', '')) in ack_replies
              and (
                  relevant_cids is None or str(c.get('id', '')) in relevant_cids
              )
          ],
          sort_keys=True,
      )
  )
  prev_ranks = dict(prior_digest_meta.get('stage_ranks') or {})
  for d_cid in active_deferred_sorted:
    prev_ranks[d_cid] = 0
  prev_broken = int(prior_digest_meta.get('broken_anchors', 0))
  new_state: JsonDict = {
      'doc_id': doc_id,
      'title': str(prior.get('title') or doc_id),
      'url': canonical_url,
      'role': eff_role,
      'mime_type': eff_mime,
      'open_threads_count': open_cnt,
      'last_ack_utc': ack_utc,
      'last_digest_utc': digest_utc,
      'ack_thread_replies': ack_replies,
      'thread_categories': overrides,
      'deferred_threads': deferred_map,
      'last_digest': {
          'tab_hashes': tab_hashes,
          'comment_fp': comment_fp,
          'suggestion_fp': sugg_fp,
          'stage_ranks': prev_ranks,
          'deferred_ids': active_deferred_sorted,
          'broken_anchors': prev_broken,
      },
  }
  state_path.write_text(
      json.dumps(new_state, indent=2, sort_keys=False) + '\n', encoding='utf-8'
  )
  return {
      'doc_id': doc_id,
      'url': canonical_url,
      'role': eff_role,
      'open_threads_count': open_cnt,
      'acked_utc': ack_utc,
      'refresh_live': refresh_live,
      'tabs_acked': sorted(tab_hashes),
      'thread_categories': overrides,
      'deferred_threads': deferred_map,
  }


def update_watchlist_cmd(
    path: pathlib.Path,
    add_spec: str,
    mute_spec: str,
    remove_spec: str,
    role: str,
    deadline: str,
) -> JsonDict:
  """Mutates or lists watchlist.json entries."""
  wl = load_watchlist(path)
  docs: list[JsonDict] = list(wl.get('documents') or [])
  muted: list[str] = [str(x) for x in wl.get('muted_doc_ids') or []]

  if add_spec:
    doc_id, _, url = parse_doc_spec(add_spec)
    muted = [m for m in muted if m != doc_id]
    updated = False
    for entry in docs:
      if entry.get('doc_id') == doc_id:
        entry['url'] = url
        entry['role'] = role or entry.get('role', 'author')
        if deadline:
          entry['deadline'] = deadline
        entry['active'] = True
        updated = True
        break
    if not updated:
      docs.append({
          'doc_id': doc_id,
          'url': url,
          'role': role or 'author',
          'deadline': deadline,
          'active': True,
      })
  if mute_spec:
    doc_id, _, _ = parse_doc_spec(mute_spec)
    if doc_id not in muted:
      muted.append(doc_id)
    for entry in docs:
      if entry.get('doc_id') == doc_id:
        entry['active'] = False
  if remove_spec:
    doc_id, _, _ = parse_doc_spec(remove_spec)
    docs = [e for e in docs if e.get('doc_id') != doc_id]
    muted = [m for m in muted if m != doc_id]

  wl['documents'] = docs
  wl['muted_doc_ids'] = muted
  if add_spec or mute_spec or remove_spec:
    save_watchlist(path, wl)
  return wl


def run_cli_args(
    argv: Sequence[str],
    fetcher: HttpFetcher = _default_http_fetcher,
    access_token: str | None = None,
) -> JsonDict:
  """Parses CLI arguments and executes collect, ack, or watchlist."""
  parser = argparse.ArgumentParser(description=__doc__)
  sub = parser.add_subparsers(dest='subcommand')

  p_col = sub.add_parser('collect', help='Collect review-round deltas.')
  p_col.add_argument('--state-dir', default='', help='Local state directory.')
  p_col.add_argument('--watchlist', default='', help='Path to watchlist.json.')
  p_col.add_argument('--doc', action='append', default=[], help='Doc URL/ID.')
  p_col.add_argument('--lookback-days', type=int, default=DEFAULT_LOOKBACK_DAYS)
  p_col.add_argument('--no-auto-discover', action='store_true')
  p_col.add_argument('--full', action='store_true')
  p_col.add_argument(
      '--token-cmd',
      default='',
      help='Shell command printing an OAuth 2.0 access token.',
  )
  p_col.add_argument('--now', default='', help='Override UTC clock (testing).')
  p_col.add_argument('--output', default='', help='Write JSON report to path.')

  p_ack = sub.add_parser('ack', help='Advance ack baseline after a round.')
  p_ack.add_argument('--state-dir', default='', help='Local state directory.')
  p_ack.add_argument('--doc', required=True, help='Google Doc URL or ID.')
  p_ack.add_argument('--set-thread', action='append', default=[])
  p_ack.add_argument('--defer-thread', action='append', default=[])
  p_ack.add_argument('--defer-days', type=float, default=DEFAULT_DEFER_DAYS)
  p_ack.add_argument('--clear-defer', action='append', default=[])
  p_ack.add_argument('--role', default='', help='Optional role override.')
  p_ack.add_argument(
      '--refresh-live',
      action='store_true',
      help='Re-pull live tabs instead of promoting local digest_*.md files.',
  )
  p_ack.add_argument(
      '--token-cmd',
      default='',
      help='Shell command printing an OAuth 2.0 access token.',
  )
  p_ack.add_argument('--now', default='', help='Override UTC clock (testing).')

  p_wl = sub.add_parser('watchlist', help='Manage watchlist.json.')
  p_wl.add_argument('--state-dir', default='', help='Local state directory.')
  p_wl.add_argument('--watchlist', default='', help='Path to watchlist.json.')
  p_wl.add_argument('--add', default='', help='Add or activate doc URL/ID.')
  p_wl.add_argument('--mute', default='', help='Mute doc URL/ID.')
  p_wl.add_argument('--remove', default='', help='Remove doc URL/ID.')
  p_wl.add_argument('--role', default='author', help='author or collaborator.')
  p_wl.add_argument('--deadline', default='', help='YYYY-MM-DD deadline.')
  p_wl.add_argument('--list', action='store_true', help='List watchlist.')

  args_list = list(argv)
  if not args_list or args_list[0].startswith('-'):
    args_list = ['collect', *args_list]
  ns = parser.parse_args(args_list)

  sdir = (
      pathlib.Path(ns.state_dir).expanduser()
      if ns.state_dir
      else default_state_dir()
  )

  if ns.subcommand == 'watchlist':
    wl_path = (
        pathlib.Path(ns.watchlist).expanduser()
        if ns.watchlist
        else sdir / 'watchlist.json'
    )
    res = update_watchlist_cmd(
        wl_path, ns.add, ns.mute, ns.remove, ns.role, ns.deadline
    )
    print(json.dumps(res, indent=2))
    return res

  token = (
      resolve_access_token(getattr(ns, 'token_cmd', ''))
      if access_token is None
      else access_token
  )
  now_dt = parse_utc(ns.now) or datetime.datetime.now(datetime.timezone.utc)
  ws = _WorkspaceCollector(fetcher=fetcher, access_token=token, now=now_dt)

  if ns.subcommand == 'ack':
    res = acknowledge_document(
        ws,
        ns.doc,
        sdir,
        ns.set_thread,
        now_dt,
        refresh_live=ns.refresh_live,
        defer_threads=ns.defer_thread,
        defer_days=ns.defer_days,
        clear_defers=ns.clear_defer,
        role_override=ns.role,
    )
    print(json.dumps(res, indent=2))
    return res

  wl_path = (
      pathlib.Path(ns.watchlist).expanduser()
      if ns.watchlist
      else sdir / 'watchlist.json'
  )
  wl = load_watchlist(wl_path)
  targets = ws.discover_targets(
      watchlist=wl,
      cli_docs=ns.doc,
      lookback_days=ns.lookback_days,
      auto_discover=not ns.no_auto_discover,
      state_dir=sdir,
  )
  skills_root = pathlib.Path(__file__).resolve().parents[2]
  docs_out: list[JsonDict] = []
  for tgt in targets:
    try:
      docs_out.append(
          collect_document(
              ws=ws,
              target=tgt,
              state_dir=sdir,
              skills_root=skills_root,
              now=now_dt,
              lookback_days=ns.lookback_days,
              force_full=ns.full,
          )
      )
    except (subprocess.SubprocessError, OSError, ValueError) as err:
      docs_out.append({
          'doc_id': tgt.doc_id,
          'title': tgt.doc_id,
          'url': tgt.url,
          'role': tgt.role,
          'source': tgt.source,
          'reasons': list(tgt.reasons),
          'status': 'error',
          'error': str(err),
      })

  report: JsonDict = {
      'generated_utc': format_utc(now_dt),
      'state_dir': str(sdir),
      'lookback_days': ns.lookback_days,
      'documents_total': len(docs_out),
      'documents_active': sum(
          1 for d in docs_out if d['status'] == 'active_digest'
      ),
      'documents_quiet': sum(1 for d in docs_out if d['status'] == 'quiet'),
      'documents_error': sum(1 for d in docs_out if d['status'] == 'error'),
      'documents': docs_out,
  }
  rendered = json.dumps(report, indent=2, sort_keys=False) + '\n'
  if ns.output:
    out_file = pathlib.Path(ns.output).expanduser()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(rendered, encoding='utf-8')
  print(rendered, end='')
  return report


def main() -> int:
  """Entry point for CLI execution."""
  try:
    run_cli_args(sys.argv[1:])
  except ValueError as err:
    print(f'error: {err}', file=sys.stderr)
    return 2
  return 0


if __name__ == '__main__':
  sys.exit(main())
