#!/usr/bin/env python3
"""Checks Markdown, Mermaid, and DOT diagrams against tech-docs-diagrams rules.

Usage:
  diagram_lint.py FILE [FILE ...]   Check Markdown (.md) or diagram (.mmd/.dot)
                                    files. "-" reads Markdown from stdin.

Exit status: 0 for no findings, 1 for findings, 2 for an unreadable file.
Put "<!-- diagram-lint: off -->" and "<!-- diagram-lint: on -->" around verbatim
examples that intentionally show broken diagrams.
"""

from collections.abc import Sequence
import dataclasses
import pathlib
import re
import sys

MAX_PRIMARY_NODES = 9
MAX_SEQUENCE_ACTORS = 5
MAX_EDGES = 12
MAX_LABEL_WORDS = 5
MAX_SUBITEMS = 5
MAX_SEMANTIC_COLORS = 5
MAX_UNBRANCHED_LR_NODES = 4

_FENCE_OPEN = re.compile(r'^(\s*)(`{3,}|~{3,})\s*([\w+-]*).*$')
_LINT_OFF = re.compile(r'<!--\s*diagram-lint:\s*off\s*-->', re.IGNORECASE)
_LINT_ON = re.compile(r'<!--\s*diagram-lint:\s*on\s*-->', re.IGNORECASE)
_HTML_BR = re.compile(r'<br\s*/?>|\\n', re.IGNORECASE)
_HTML_TAG = re.compile(r'</?[A-Za-z][^>]*>')
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\u2019_/%.+-]*")

_BOX_DRAWING = re.compile(r'[\u2500-\u257f]')
_ASCII_BOX_CORNER = re.compile(r'\+-[+-]{3,}\+')
_RASTER_DIAGRAM_IMG = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)\)', re.IGNORECASE)
_DIAGRAM_IMG_HINT = re.compile(
    r'(?:diagram|arch|flow|sequence|topology|state|pipeline|graph)',
    re.IGNORECASE,
)
_RASTER_EXT = frozenset(('.png', '.jpg', '.jpeg', '.gif', '.webp'))

# Allowed prefixes/suffixes that do not count as regular prose label words:
# - Short bracketed domain/role prefix: "[HW] Key Store"
# - Short ordered step prefix: "1. Sign challenge" or "2) Verify token"
# - Trailing multiplicity marker: "Workers (1..N)", "Slots (0..*)", "Nodes (xN)"
_ROLE_PREFIX = re.compile(r'^\s*\[[A-Za-z0-9/_-]{1,6}\]\s*')
_STEP_PREFIX = re.compile(r'^\s*\d{1,2}[.)]\s*')
_BULLET_PREFIX = re.compile(r'^\s*(?:[\u2022\u2023\u25e6*]|-\s)\s*')
_MULTIPLICITY_SUFFIX = re.compile(
    r'\s*\((?:\d+\.\.(?:\d+|N|\*)|[x\u00d7]\s*[A-Za-z0-9]+|'
    r'multiple|0\.\.N|1\.\.N)\)\s*$',
    re.IGNORECASE,
)

_ALPHANUM_ID = re.compile(
    r'\b(?:REQ|INV|ASM|DEC|OPT|OQ|ITEM|MOD|SYS|COMP|ERR|STEP)[-_]\d+[A-Za-z]?\b'
    r'|^\s*[A-Z]{1,4}\d{1,3}\s*[:.-]\s+'
)
_COMMA_LIST = re.compile(r'[^,]+,\s+[^,]+,\s+[^,]+|[^,]+,\s+(?:and|or)\s+[^,]+')
_EMOJI = re.compile(r'[\U0001f300-\U0001faff\u2600-\u26ff\u2700-\u27bf]')
_MERMAID_ICON_ATTR = re.compile(r'@\{\s*icon\s*:', re.IGNORECASE)

_MERMAID_HEADER = re.compile(
    r'^\s*(flowchart|graph|sequenceDiagram|stateDiagram(?:-v2)?)\b'
    r'(?:\s+(TD|TB|BT|LR|RL))?',
    re.IGNORECASE,
)
_MERMAID_SUBGRAPH = re.compile(
    r'^\s*subgraph\s+(?:([A-Za-z0-9_.-]+)\s*(?:\[\s*"?([^"\]]*)"?\s*\])?'
    r'|"([^"]+)")?',
    re.IGNORECASE,
)
_MERMAID_PARTICIPANT = re.compile(
    r'^\s*(?:participant|actor)\s+([A-Za-z0-9_.-]+)(?:\s+as\s+(.+))?$',
    re.IGNORECASE,
)
_MERMAID_SEQ_MSG = re.compile(
    r'^\s*([A-Za-z0-9_.-]+)\s*(?:<<?--?>>?|--?>>?|--?[x)+-])\s*'
    r'([A-Za-z0-9_.-]+)\s*:\s*(.*)$'
)
_MERMAID_EDGE = re.compile(
    r'(-->|==>|-\.->|<-->|---|-\.-)' r'(?:\|\s*"?([^"|]*)"?\s*\|)?'
)
_MERMAID_INLINE_EDGE_LABEL = re.compile(
    r'(?:--\s*"?([^"\n-]+?)"?\s*-->|-\.\s*"?([^"\n.]+?)"?\s*\.->|'
    r'==\s*"?([^"\n=]+?)"?\s*==>)'
)
_MERMAID_NODE_DEF = re.compile(
    r'\b([A-Za-z_][A-Za-z0-9_.-]*)\s*'
    r'(?:'
    r'\[\[\s*"?([^"\]]*)"?\s*\]\]'
    r'|\[\(\s*"?([^"\)]*)"?\s*\)\]'
    r'|\(\[\s*"?([^"\]]*)"?\s*\]\)'
    r'|\(\(\(\s*"?([^"\)]*)"?\s*\)\)\)'
    r'|\(\(\s*"?([^"\)]*)"?\s*\)\)'
    r'|\{\{\s*"?([^"\}]*)"?\s*\}\}'
    r'|\[\s*"([^"]*)"\s*\]'
    r'|\[\s*([^\]"\n]+)\s*\]'
    r'|\(\s*"([^"]*)"\s*\)'
    r'|\{\s*"?([^"\}\n]+)"?\s*\}'
    r')'
)
_MERMAID_SKIP_KEYWORDS = frozenset((
    'flowchart',
    'graph',
    'subgraph',
    'end',
    'direction',
    'classdef',
    'class',
    'style',
    'linkstyle',
    'click',
    'accTitle',
    'accDescr',
))

_DOT_RANKDIR = re.compile(r'\brankdir\s*=\s*"?(LR|RL|TB|BT)"?', re.IGNORECASE)
_DOT_EDGE = re.compile(
    r'\b([A-Za-z_][A-Za-z0-9_]*)\s*-[->]\s*([A-Za-z_][A-Za-z0-9_]*)'
)
_DOT_LABEL = re.compile(r'\blabel\s*=\s*"((?:[^"\\]|\\.)*)"')
_DOT_NODE_STMT = re.compile(
    r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\[([^\]]*)\]\s*;?\s*$'
)
_DOT_RESERVED = frozenset(('node', 'edge', 'graph', 'digraph', 'subgraph'))

_FILL_COLOR = re.compile(
    r'(?:\bfill\s*:|\bfillcolor\s*=\s*"?)\s*(#[0-9A-Fa-f]{3,6}|[A-Za-z]+)',
    re.IGNORECASE,
)
_NEUTRAL_COLORS = frozenset((
    '#fff',
    '#ffffff',
    '#f8f9fa',
    '#f1f3f4',
    '#fafafa',
    '#eeeeee',
    'white',
    'none',
    'transparent',
    'lightgrey',
    'lightgray',
))
_RAW_RED_COLORS = frozenset((
    'red',
    '#f00',
    '#ff0000',
    '#ea4335',
    '#d93025',
    '#cc0000',
))
_RAW_GREEN_COLORS = frozenset((
    'green',
    '#0f0',
    '#00ff00',
    '#34a853',
    '#00aa00',
    '#008000',
))


@dataclasses.dataclass(frozen=True)
class Finding:
  """One diagram lint violation.

  Attributes:
    line: 1-based line number in the checked file.
    rule: Rule identifier such as D1 or D5.
    message: Actionable explanation of the violation.
  """

  line: int
  rule: str
  message: str


@dataclasses.dataclass(frozen=True)
class _CodeBlock:
  """One fenced code block extracted from a Markdown document.

  Attributes:
    line: 1-based starting line of the opening fence.
    lang: Lowercase info-string language tag.
    lines: Raw lines inside the code block.
  """

  line: int
  lang: str
  lines: tuple[str, ...]


def _clean_label_line(raw_line: str) -> str:
  """Strips HTML tags, role/step prefixes, and multiplicity suffixes."""
  text = _HTML_TAG.sub(' ', raw_line).strip().strip('"').strip()
  text = _BULLET_PREFIX.sub('', text)
  text = _ROLE_PREFIX.sub('', text)
  text = _STEP_PREFIX.sub('', text)
  text = _MULTIPLICITY_SUFFIX.sub('', text)
  return text.strip()


def _count_words(text: str) -> int:
  """Counts words in a cleaned diagram label."""
  return len(_WORD.findall(text))


def _check_label(
    raw_label: str,
    line_no: int,
    kind: str,
    is_mermaid: bool,
    findings: list[Finding],
) -> None:
  """Checks one node or edge label against D5 and D8."""
  stripped = raw_label.strip().strip('"')
  if not stripped or stripped == '...':
    return
  if _ALPHANUM_ID.search(stripped):
    findings.append(
        Finding(
            line_no,
            'D5',
            f'{kind} label "{stripped[:40]}" contains an alphanumeric ID: '
            'use a short plain name on the diagram and put IDs in the text '
            'below',
        )
    )
  parts = [p.strip() for p in _HTML_BR.split(stripped) if p.strip()]
  if len(parts) > 1 and kind == 'node':
    bullet_parts = parts[1:]
    if len(bullet_parts) > MAX_SUBITEMS:
      findings.append(
          Finding(
              line_no,
              'D8',
              f'box lists {len(bullet_parts)} sub-elements '
              f'(limit {MAX_SUBITEMS}): split into a child diagram or '
              'move details below',
          )
      )
    if is_mermaid and any(p.lstrip().startswith('- ') for p in bullet_parts):
      findings.append(
          Finding(
              line_no,
              'D8',
              'Mermaid node sub-item starts with "- ": use "• " or "1. " '
              'with <br/> so Mermaid parsers do not break',
          )
      )
  for part in parts:
    if kind == 'node' and _COMMA_LIST.search(part):
      findings.append(
          Finding(
              line_no,
              'D8',
              f'comma-separated list inside box label "{part[:45]}": '
              'use sub-boxes or a vertical bulleted/numbered list',
          )
      )
    cleaned = _clean_label_line(part)
    words = _count_words(cleaned)
    if words > MAX_LABEL_WORDS:
      findings.append(
          Finding(
              line_no,
              'D5',
              f'{kind} label "{part[:45]}" has {words} words '
              f'(limit {MAX_LABEL_WORDS}): use 1 to 3 words (max 5) and '
              'move details to a keyed list below',
          )
      )


def _check_colors(
    lines: Sequence[str], start_line: int, findings: list[Finding]
) -> None:
  """Checks semantic color count and red-green collisions (D10)."""
  semantic_colors: set[str] = set()
  has_raw_red = False
  has_raw_green = False
  first_color_line = start_line
  for offset, line in enumerate(lines):
    for match in _FILL_COLOR.finditer(line):
      color = match.group(1).lower()
      if color in _NEUTRAL_COLORS:
        continue
      if not semantic_colors:
        first_color_line = start_line + offset
      semantic_colors.add(color)
      if color in _RAW_RED_COLORS:
        has_raw_red = True
      if color in _RAW_GREEN_COLORS:
        has_raw_green = True
  if len(semantic_colors) > MAX_SEMANTIC_COLORS:
    findings.append(
        Finding(
            first_color_line,
            'D10',
            f'diagram uses {len(semantic_colors)} semantic fill colors '
            f'(limit {MAX_SEMANTIC_COLORS}): group into 3 to 5 categories',
        )
    )
  if has_raw_red and has_raw_green:
    findings.append(
        Finding(
            first_color_line,
            'D10',
            'pure red and pure green fills collide under deuteranopia/'
            'protanopia: shift green to teal (#E0F2F1/#00796B) and red to '
            'vermilion (#FCE8E6/#C5221F) with non-color cues',
        )
    )


def _lint_mermaid(
    lines: Sequence[str],
    start_line: int,
    inline_markdown: bool,
) -> list[Finding]:
  """Checks one Mermaid diagram block."""
  findings: list[Finding] = []
  kind = ''
  direction = ''
  subgraph_ids: set[str] = set()
  nodes: set[str] = set()
  participants: set[str] = set()
  out_degree: dict[str, int] = {}
  edge_count = 0

  for offset, raw in enumerate(lines):
    line_no = start_line + offset
    stripped = raw.strip()
    if not stripped or stripped.startswith('%%'):
      continue
    if inline_markdown and _MERMAID_ICON_ATTR.search(stripped):
      findings.append(
          Finding(
              line_no,
              'D9',
              'Mermaid "@{ icon: ... }" breaks in GitHub and many Markdown '
              'renderers: use shapes and colors inline, or render locally '
              'with alt-text source',
          )
      )
    if inline_markdown and _EMOJI.search(stripped):
      findings.append(
          Finding(
              line_no,
              'D9',
              'Unicode emoji in inline Mermaid renders inconsistently across '
              'headless renderers: use shapes, colors, or [TAG] prefixes',
          )
      )
    if not kind:
      header = _MERMAID_HEADER.match(stripped)
      if header:
        kind = header.group(1).lower()
        direction = (header.group(2) or '').upper()
      continue

    if kind == 'sequencediagram':
      part = _MERMAID_PARTICIPANT.match(stripped)
      if part:
        participants.add(part.group(1))
        if part.group(2):
          _check_label(part.group(2), line_no, 'node', True, findings)
        continue
      msg = _MERMAID_SEQ_MSG.match(stripped)
      if msg:
        participants.add(msg.group(1))
        participants.add(msg.group(2))
        edge_count += 1
        _check_label(msg.group(3), line_no, 'edge', True, findings)
      continue

    sub = _MERMAID_SUBGRAPH.match(stripped)
    if sub:
      if sub.group(1):
        subgraph_ids.add(sub.group(1))
      sub_label = sub.group(2) or sub.group(3) or ''
      if sub_label:
        _check_label(sub_label, line_no, 'subgraph', True, findings)
      continue

    first_word = stripped.split()[0].lower().rstrip(':')
    if first_word in _MERMAID_SKIP_KEYWORDS:
      continue

    for node_match in _MERMAID_NODE_DEF.finditer(stripped):
      node_id = node_match.group(1)
      if node_id.lower() not in _MERMAID_SKIP_KEYWORDS:
        nodes.add(node_id)
      label = next((g for g in node_match.groups()[1:] if g is not None), '')
      _check_label(label, line_no, 'node', True, findings)

    for inline_lbl in _MERMAID_INLINE_EDGE_LABEL.finditer(stripped):
      lbl = next((g for g in inline_lbl.groups() if g is not None), '')
      _check_label(lbl, line_no, 'edge', True, findings)

    edges_on_line = list(_MERMAID_EDGE.finditer(stripped))
    if edges_on_line:
      edge_count += len(edges_on_line)
      left_tokens = re.findall(
          r'\b([A-Za-z_][A-Za-z0-9_.-]*)\b',
          stripped[: edges_on_line[0].start()],
      )
      if left_tokens:
        src = left_tokens[0]
        if src.lower() not in _MERMAID_SKIP_KEYWORDS:
          nodes.add(src)
          out_degree[src] = out_degree.get(src, 0) + 1
      for idx, edge_match in enumerate(edges_on_line):
        if edge_match.group(2):
          _check_label(edge_match.group(2), line_no, 'edge', True, findings)
        seg_end = (
            edges_on_line[idx + 1].start()
            if idx + 1 < len(edges_on_line)
            else len(stripped)
        )
        right_tokens = re.findall(
            r'\b([A-Za-z_][A-Za-z0-9_.-]*)\b',
            stripped[edge_match.end() : seg_end],
        )
        if right_tokens:
          dst = right_tokens[0]
          if dst.lower() not in _MERMAID_SKIP_KEYWORDS:
            nodes.add(dst)

  primary_nodes = nodes - subgraph_ids
  if kind == 'sequencediagram' and len(participants) > MAX_SEQUENCE_ACTORS:
    findings.append(
        Finding(
            start_line,
            'D4',
            f'sequence diagram has {len(participants)} participants '
            f'(limit {MAX_SEQUENCE_ACTORS}): split by phase or subsystem',
        )
    )
  if kind in ('flowchart', 'graph'):
    if len(primary_nodes) > MAX_PRIMARY_NODES:
      findings.append(
          Finding(
              start_line,
              'D4',
              f'diagram has {len(primary_nodes)} primary boxes '
              f'(limit {MAX_PRIMARY_NODES}): add an overview diagram and '
              'split stages into child diagrams',
          )
      )
    has_branching = any(deg > 1 for deg in out_degree.values())
    if direction in ('LR', 'RL') and (
        len(primary_nodes) > MAX_UNBRANCHED_LR_NODES or has_branching
    ):
      findings.append(
          Finding(
              start_line,
              'D3',
              f'horizontal "{direction}" layout with {len(primary_nodes)} '
              'boxes or branching clips in portrait docs: use TD/TB instead',
          )
      )
  if edge_count > MAX_EDGES:
    findings.append(
        Finding(
            start_line,
            'D4',
            f'diagram has {edge_count} arrows/messages (limit {MAX_EDGES}): '
            'group shared targets or split into overview + sub-diagrams',
        )
    )
  _check_colors(lines, start_line, findings)
  return findings


def _lint_dot(lines: Sequence[str], start_line: int) -> list[Finding]:
  """Checks one Graphviz DOT diagram block."""
  findings: list[Finding] = []
  nodes: set[str] = set()
  out_degree: dict[str, int] = {}
  edge_count = 0
  rankdir = 'TB'

  for offset, raw in enumerate(lines):
    line_no = start_line + offset
    stripped = raw.strip()
    if not stripped or stripped.startswith('//') or stripped.startswith('#'):
      continue
    rd_match = _DOT_RANKDIR.search(stripped)
    if rd_match:
      rankdir = rd_match.group(1).upper()
    node_stmt = _DOT_NODE_STMT.match(stripped)
    if node_stmt and node_stmt.group(1).lower() not in _DOT_RESERVED:
      node_id = node_stmt.group(1)
      if not node_id.startswith('cluster_'):
        nodes.add(node_id)
      for lbl in _DOT_LABEL.finditer(node_stmt.group(2)):
        _check_label(lbl.group(1), line_no, 'node', False, findings)
      continue
    edge_matches = list(_DOT_EDGE.finditer(stripped))
    if edge_matches:
      edge_count += len(edge_matches)
      for em in edge_matches:
        src, dst = em.group(1), em.group(2)
        if not src.startswith('cluster_'):
          nodes.add(src)
          out_degree[src] = out_degree.get(src, 0) + 1
        if not dst.startswith('cluster_'):
          nodes.add(dst)
      for lbl in _DOT_LABEL.finditer(stripped):
        _check_label(lbl.group(1), line_no, 'edge', False, findings)

  if len(nodes) > MAX_PRIMARY_NODES:
    findings.append(
        Finding(
            start_line,
            'D4',
            f'DOT diagram has {len(nodes)} primary nodes '
            f'(limit {MAX_PRIMARY_NODES}): split into overview + sub-diagrams',
        )
    )
  if edge_count > MAX_EDGES:
    findings.append(
        Finding(
            start_line,
            'D4',
            f'DOT diagram has {edge_count} edges (limit {MAX_EDGES}): '
            'group shared targets or split into sub-diagrams',
        )
    )
  has_branching = any(deg > 1 for deg in out_degree.values())
  if rankdir in ('LR', 'RL') and (
      len(nodes) > MAX_UNBRANCHED_LR_NODES or has_branching
  ):
    findings.append(
        Finding(
            start_line,
            'D3',
            f'horizontal rankdir={rankdir} with {len(nodes)} nodes or '
            'branching clips in portrait docs: use rankdir=TB',
        )
    )
  _check_colors(lines, start_line, findings)
  return findings


def lint_markdown(text: str) -> list[Finding]:
  """Checks all diagrams and image embeds in a Markdown document."""
  findings: list[Finding] = []
  lines = text.splitlines()
  enabled = True
  in_fence = False
  fence_marker = ''
  fence_lang = ''
  fence_start = 1
  fence_lines: list[str] = []
  blocks: list[_CodeBlock] = []

  for idx, line in enumerate(lines, start=1):
    if not in_fence:
      if _LINT_OFF.search(line):
        enabled = False
        continue
      if _LINT_ON.search(line):
        enabled = True
        continue
      if not enabled:
        continue
      open_match = _FENCE_OPEN.match(line)
      if open_match:
        in_fence = True
        fence_marker = open_match.group(2)
        fence_lang = open_match.group(3).lower()
        fence_start = idx
        fence_lines = []
        continue
      for img_match in _RASTER_DIAGRAM_IMG.finditer(line):
        alt_text, target = img_match.group(1), img_match.group(2)
        ext = pathlib.Path(target.split('?', 1)[0]).suffix.lower()
        if ext in _RASTER_EXT and (
            _DIAGRAM_IMG_HINT.search(alt_text)
            or _DIAGRAM_IMG_HINT.search(target)
        ):
          findings.append(
              Finding(
                  idx,
                  'D1',
                  f'static raster diagram image "{target}": embed fenced '
                  'mermaid or dot source instead of a picture',
              )
          )
    else:
      stripped = line.strip()
      if stripped.startswith(fence_marker[0] * len(fence_marker)) and not (
          stripped.strip(fence_marker[0])
      ):
        if enabled:
          blocks.append(_CodeBlock(fence_start, fence_lang, tuple(fence_lines)))
        in_fence = False
      else:
        fence_lines.append(line)

  for block in blocks:
    joined = '\n'.join(block.lines)
    if block.lang in ('mermaid',):
      findings.extend(_lint_mermaid(block.lines, block.line + 1, True))
    elif block.lang in ('dot', 'graphviz'):
      findings.extend(_lint_dot(block.lines, block.line + 1))
    elif (
        _BOX_DRAWING.search(joined)
        or len(_ASCII_BOX_CORNER.findall(joined)) >= 2
    ):
      findings.append(
          Finding(
              block.line,
              'D1',
              'ASCII/Unicode box-drawing art in code block: use a fenced '
              'mermaid or dot diagram, or a table',
          )
      )
  return sorted(findings, key=lambda f: (f.line, f.rule))


def lint_file(path_arg: str) -> tuple[str, Sequence[Finding]]:
  """Lints one Markdown, Mermaid, or DOT file and returns its findings."""
  if path_arg == '-':
    return '<stdin>', lint_markdown(sys.stdin.read())
  path = pathlib.Path(path_arg)
  content = path.read_text(encoding='utf-8')
  suffix = path.suffix.lower()
  if suffix in ('.mmd', '.mermaid'):
    return path_arg, _lint_mermaid(content.splitlines(), 1, False)
  if suffix in ('.dot', '.gv'):
    return path_arg, _lint_dot(content.splitlines(), 1)
  return path_arg, lint_markdown(content)


def main(argv: Sequence[str]) -> int:
  """Runs the CLI entry point and returns the process exit code."""
  paths = [arg for arg in argv[1:] if not arg.startswith('-')] or (
      ['-'] if '-' in argv[1:] else []
  )
  if not paths or '-h' in argv[1:] or '--help' in argv[1:]:
    print(__doc__.strip())
    return 0 if ('-h' in argv[1:] or '--help' in argv[1:]) else 2
  exit_code = 0
  for path_arg in paths:
    try:
      label, findings = lint_file(path_arg)
    except OSError as err:
      print(f'{path_arg}: cannot read file: {err}', file=sys.stderr)
      return 2
    for finding in findings:
      print(f'{label}:{finding.line}: {finding.rule}: {finding.message}')
    noun = 'finding' if len(findings) == 1 else 'findings'
    print(f'{label}: {len(findings)} {noun}')
    if findings:
      exit_code = 1
  return exit_code


if __name__ == '__main__':
  sys.exit(main(sys.argv))
