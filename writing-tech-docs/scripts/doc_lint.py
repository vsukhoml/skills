#!/usr/bin/env python3
"""Checks Markdown documents against the measurable writing rules.

Usage:
  doc_lint.py FILE [FILE ...]            Check documents. "-" reads stdin.
  doc_lint.py --compare ORIG REVISED     Check preservation limits and rules.
  doc_lint.py --words                    Print the word list with the advice.

Options:
  --profile decision|docs   Rule set. "decision" (default) is for design
                            documents and proposals. "docs" is for developer
                            and operator documentation.
  --link-root DIR           Directory that relative links start from. Give it
                            if the checked file is a copy in another directory.
  --allow-restructure       With --compare, allow requested heading and
                            section-order restructuring while checking code
                            blocks, identifiers, links, and numbers.
  --strict                  Count open items as findings for the exit status.

Exit status: 0 for no findings, 1 for findings, 2 for a file that cannot be
read. Open items (OPEN) and modal advisories (R28 advisory) do not change the
exit status unless --strict is given.

The script measures only what a program can measure: lengths, counts,
preserved tokens, and known words. A clean result does not prove that a
document is clear. The script has checks for these rules: R1, R2, R3, R4, R8,
R9, R10, R11 (image alternative text only; diagram topology and relation rules
are manual), R12 to R20, R24 (loaded comparison words only; category bias is
manual), and R25 to R32. It has no check for R5, R6, R7, R21, R22, and R23.

The script does not check words in code blocks, in inline code, or in double
quotes. For code blocks, it checks the lead-in sentence, line count, language
tag, line width, tab characters, and typographic quotes or dashes. It reports
each open item of the form "[Open: question]" and does not check the text of the
question. A status in parentheses, for example "(measured, release 4.1)", does
not count toward the length of a sentence. The profile "docs" does not require
a table caption, accepts a table directly below a heading, raises the cell limit
to 30 words, and has no limit for code names in a sentence. To skip a region,
put it between the HTML comments
"<!-- doc-lint: off -->" and "<!-- doc-lint: on -->".
"""

import argparse
import collections
import dataclasses
import math
import pathlib
import re
import sys
import urllib.parse

MAX_SENTENCE_WORDS = 25
MAX_PARAGRAPH_SENTENCES = 5
MAX_SECTION_WORDS = 400
MAX_LIST_ITEMS = 7
MAX_TABLE_COLUMNS = 5
MAX_CELL_WORDS = 15
MAX_CELL_WORDS_DOCS = 30
MAX_CODE_LINES = 25
MAX_CODE_WIDTH = 80
MAX_HEADING_LEVEL = 3
MAX_BOLD_SHARE = 0.10
MAX_BOLD_WORDS = 6
MAX_LEAD_IN_WORDS = 8
MIN_BODY_TO_HEADING_RATIO = 3
MAX_CODE_NAMES = 2
MAX_PASSIVE_SHARE = 0.20
MIN_PASSIVE_SENTENCES = 5
WORDS_ON_A_PAGE = 400

# Each entry is (rule, forms, advice). "|" separates the forms of a phrase.
WORDS = (
    # R8: open placeholders.
    (
        'R8',
        'TBD|TODO|FIXME|to be determined|to be decided',
        'resolve it, or state what is deferred and where it is tracked',
    ),
    # R14: vague verbs and nouns that hide a verb.
    ('R14', 'handle|handles|handled|handling', 'name the real action'),
    (
        'R14',
        'takes care of|take care of|deals with|deal with',
        'name the real action',
    ),
    ('R14', 'streamline|streamlines|empower|empowers', 'name the real action'),
    (
        'R14',
        'perform|performs|performed|conduct|conducts|conducted',
        'use the verb of the action: "validate", not "perform validation"',
    ),
    # R16: praise without a number.
    ('R16', 'fast|quick|quickly|rapid|rapidly', 'give a number with a unit'),
    ('R16', 'faster|slower|quicker', 'give a number with a unit'),
    (
        'R16',
        'scalable|lightweight|performant|efficient|flexible|powerful',
        'give a number with a unit, or delete',
    ),
    (
        'R16',
        'seamless|seamlessly|robust|elegant|comprehensive',
        'state the measurable property, or delete',
    ),
    (
        'R16',
        'simple|simply|easy|easily|trivial|trivially|straightforward',
        'delete, or state the number of steps',
    ),
    (
        'R16',
        'minimal|significant|significantly|very|extremely|highly',
        'give the quantity',
    ),
    ('R16', 'state-of-the-art|cutting-edge|best-in-class', 'delete'),
    ('R16', 'obviously|clearly|of course|needless to say', 'delete'),
    # R16: filler.
    (
        'R16',
        'it is worth noting that|it should be noted that|note that',
        'delete and state the fact',
    ),
    (
        'R16',
        'please note|it is important to|basically|essentially|actually',
        'delete and state the fact',
    ),
    ('R16', 'in order to', 'write "to"'),
    ('R16', 'due to the fact that', 'write "because"'),
    ('R16', 'in the event that', 'write "if"'),
    ('R16', 'a number of|a few|couple of|roughly', 'write the number'),
    ('R16', 'just', 'delete'),
    ('R16', 'cheap|cheaply|expensive', 'give the cost with a unit'),
    (
        'R16',
        'maybe|kind of|sort of|more or less',
        'give the value, or write "about" with the status "estimated"',
    ),
    ('R16', 'in terms of|with regard to|with respect to', 'write "for"'),
    (
        'R4',
        'as mentioned|as noted|as described above|as stated',
        'point to the section by name',
    ),
    (
        'R4',
        'in conclusion|to conclude|to summarize|in summary',
        'do not repeat the summary at the end, state the next action or stop',
    ),
    # R24: exaggerated pros or cons in option comparisons.
    (
        'R24',
        (
            'prohibitive|prohibitively|untenable|unacceptable|superior|inferior'
            '|compelling|attractive|ideal|flawed'
        ),
        (
            'state the factual trade-off or quantity without exaggerating pros'
            ' or cons'
        ),
    ),
    # R25: uncommon words.
    (
        'R25',
        'utilize|utilizes|utilized|utilise|leverage|leverages|leveraged',
        'write "use"',
    ),
    ('R25', 'facilitate|facilitates', 'write "help" or "make possible"'),
    ('R25', 'commence|commences|initiate|initiates', 'write "start"'),
    ('R25', 'prior to', 'write "before"'),
    ('R25', 'subsequent to|subsequently', 'write "after" or "then"'),
    ('R25', 'ascertain', 'write "find"'),
    ('R25', 'numerous|plethora|myriad', 'write "many"'),
    ('R25', 'functionality', 'write "function" or "feature"'),
    ('R25', 'methodology', 'write "method"'),
    (
        'R25',
        'aforementioned|thereof|therein|herein|whereby|henceforth',
        'name the thing again',
    ),
    ('R25', 'hence|thus', 'write "therefore"'),
    ('R25', 'albeit|notwithstanding', 'write "although"'),
    ('R25', 'whilst|amongst', 'write "while" or "among"'),
    ('R25', 'in lieu of', 'write "instead of"'),
    # R26: Latin abbreviations.
    ('R26', 'e.g.|e.g', 'write "for example"'),
    ('R26', 'i.e.|i.e', 'write "that is"'),
    ('R26', 'etc.|etc', 'name the items'),
    ('R26', 'viz.|n.b.|cf.', 'write the English words'),
    # R26: idioms.
    ('R26', 'out of the box', 'write "by default"'),
    ('R26', 'under the hood', 'write "internally"'),
    ('R26', 'on the fly', 'write "during operation"'),
    ('R26', 'rule of thumb', 'write "general rule"'),
    ('R26', 'in a nutshell', 'state the conclusion'),
    ('R26', 'from scratch', 'write "from an empty state"'),
    ('R26', 'sanity check', 'write "basic check"'),
    ('R26', 'happy path', 'write "normal case"'),
    ('R26', 'deep dive|dive into|drill down', 'write "detailed analysis"'),
    ('R26', 'pain point|pain points', 'write "problem"'),
    ('R26', 'nice to have', 'write "optional", or state the priority'),
    ('R26', 'non-starter', 'write "not acceptable", with the reason'),
    ('R26', 'push back|pushes back|pushed back', 'write "disagree"'),
    ('R26', 'must-have', 'write "required"'),
    ('R26', 'red flag|red flags', 'write "warning sign"'),
    ('R26', 'big picture', 'write "overview"'),
    ('R26', 'ballpark', 'write "approximate"'),
    ('R26', 'going forward', 'give the date or the version'),
    ('R26', 'boils down to|boil down to', 'write "means"'),
    (
        'R26',
        'low-hanging fruit|no-brainer|silver bullet|game changer',
        'state the fact literally',
    ),
    (
        'R26',
        'heavy lifting|moving parts|bulletproof|rock solid',
        'state the fact literally',
    ),
    (
        'R26',
        'at the end of the day|on the same page|touch base',
        'state the fact literally',
    ),
    ('R26', 'gotcha|gotchas', 'write "hidden problem"'),
    # R26: phrasal verbs.
    ('R26', 'set up|sets up|setting up', 'write "configure" or "install"'),
    (
        'R26',
        'carry out|carries out|carried out|carrying out',
        'write "do", or use the verb of the action',
    ),
    (
        'R26',
        'figure out|figures out|figured out|find out|finds out',
        'write "find" or "determine"',
    ),
    ('R26', 'get rid of|gets rid of|getting rid of', 'write "remove"'),
    ('R26', 'kick off|kicks off|kicked off|spin up|spins up', 'write "start"'),
    ('R26', 'wrap up|wraps up|wrapped up', 'write "finish"'),
    (
        'R26',
        'come up with|comes up with|came up with',
        'write "create" or "propose"',
    ),
    ('R26', 'look into|looks into|looked into|looking into', 'write "examine"'),
    ('R26', 'run into|runs into|ran into', 'write "find" or "meet"'),
    (
        'R26',
        'end up|ends up|ended up|turn out|turns out|turned out',
        'state the result',
    ),
    ('R26', 'point out|points out|pointed out', 'write "show" or "state"'),
    ('R26', 'rule out|rules out|ruled out', 'write "exclude"'),
    ('R26', 'leave out|leaves out|left out', 'write "omit"'),
    ('R26', 'tear down|tears down|phase out|phases out', 'write "remove"'),
    ('R26', 'iron out|flesh out', 'write "fix" or "add detail to"'),
    ('R26', 'make use of|makes use of', 'write "use"'),
    ('R26', 'give rise to|gives rise to', 'write "cause"'),
    (
        'R26',
        'take into account|takes into account|keep in mind',
        'write "consider"',
    ),
    # R27: constructions that hide the grammar.
    ('R27', 'and/or', 'write "A, or B, or both"'),
    (
        'R27',
        'not uncommon|not unusual|not unlikely|not unreasonable',
        'write a positive statement',
    ),
    (
        'R27',
        'not impossible|not insignificant|not unrelated|not without',
        'write a positive statement',
    ),
    # R28: subjective advice phrases, loopholes, and relative dates.
    (
        'R28',
        (
            'we recommend|we suggest|we advise|we would recommend|it is'
            ' recommended|it is advisable|it is better to|best practice|best'
            ' practices'
        ),
        (
            'write a conditional imperative ("If X, do Y"), or state the'
            ' decision with its criterion'
        ),
    ),
    (
        'R28',
        (
            'if possible|where possible|when possible|as appropriate|where'
            ' appropriate|when necessary|if necessary|if applicable|where'
            ' applicable|ideally|normally|typically'
        ),
        'state the exact condition or remove the loophole',
    ),
    (
        'R28',
        'recently|soon|shortly|in the near future|asap',
        'give the date or the version',
    ),
    (
        'R28',
        'currently|historically|nowadays|at present|at the moment|for now',
        'give the date or the version',
    ),
    ('R28', 'next week|next month|next quarter|next year', 'give the date'),
    (
        'R28',
        'first quarter|second quarter|third quarter|fourth quarter',
        'give the months',
    ),
    ('R28', 'last week|last month|last quarter|last year', 'give the date'),
    (
        'R28',
        'this week|this month|this quarter|yesterday|tomorrow',
        'give the date',
    ),
    # R25: inflated synthetic verbs.
    (
        'R25',
        'delve|delves|delved|delving|unpack|unpacks|unpacking',
        'write "examine" or "explain"',
    ),
    (
        'R25',
        (
            'embark|embarks|unleash|unleashes|elevate|elevates|'
            'supercharge|supercharges'
        ),
        'use a common literal verb',
    ),
    (
        'R25',
        (
            'spearhead|spearheads|bolster|bolsters|foster|fosters|'
            'encompass|encompasses|underpin|underpins'
        ),
        'use a common literal verb',
    ),
    # R29: comments about the document instead of the system.
    (
        'R29',
        (
            'in this document|this document describes|let us explore|let us'
            ' examine|let us unpack'
        ),
        'delete comments about the document and state the content',
    ),
    # R30: synthetic stagecraft, puffery, and self-labeling commentary.
    (
        'R30',
        (
            'here is the thing|let us be clear|make no mistake|at its core|the'
            ' reality is|the truth is|when it comes to'
        ),
        'delete the setup and state the claim',
    ),
    (
        'R30',
        (
            'to be honest|to be transparent|in full disclosure|worth'
            ' noting|worth mentioning'
        ),
        'delete the announcement and state the fact',
    ),
    (
        'R30',
        (
            'notably|interestingly|importantly|crucially|surprisingly|'
            'undoubtedly|genuinely|truly|frankly'
        ),
        'delete and let the fact carry the weight',
    ),
    (
        'R30',
        (
            'pivotal|watershed|groundbreaking|transformative|unprecedented|'
            'paramount|game-changing'
        ),
        'state the measurable effect, or delete',
    ),
    (
        'R30',
        (
            'meticulous|meticulously|intricate|intricacies|multifaceted|'
            'holistic|holistically|ever-evolving|actionable|impactful'
        ),
        'state the exact property, or delete',
    ),
    (
        'R30',
        (
            'tapestry|beacon|realm|paradigm|synergy|synergies|'
            'cornerstone|testament to'
        ),
        'use a literal technical noun',
    ),
    (
        'R30',
        'plays a vital role|plays a crucial role|plays a key role',
        'state the exact action',
    ),
    # R31: anonymous authority without a primary source.
    (
        'R31',
        (
            'experts agree|experts believe|studies show|research'
            ' suggests|widely regarded|industry leaders'
        ),
        'name the primary source, or delete the claim',
    ),
    # R32: inflated copulas and moral adjectives on technical nouns.
    (
        'R32',
        'serves as|serve as|served as|boasts|boast|stands as',
        'write "is" or "has"',
    ),
    (
        'R32',
        (
            'honest metric|honest shape|honest number|honest signal|truthful'
            ' metric'
        ),
        'state the exact technical property',
    ),
)

# Checks that use a pattern and not the word list. Printed by --words.
PATTERN_NOTES = (
    (
        'R1',
        (
            'leaf heading >= 1/3 of section words, or sibling sections mostly'
            ' 1-2 sentences'
        ),
        'use a list or merge short sections into their parent',
    ),
    (
        'OPEN',
        '[Open: question]',
        'answer the open item or move it to an open-questions section',
    ),
    (
        'R10',
        'table of (optional ID, item name, prose explanation), or empty cell',
        'use a list/sections, or write 0, None, N/A, or Not measured',
    ),
    (
        'R11',
        (
            'image without alternative text (run diagram_lint.py for diagram'
            ' rules)'
        ),
        'add alternative text and explain image labels in body text',
    ),
    (
        'R12',
        'table or code block without lead-in',
        'add an introductory sentence above',
    ),
    ('R13', 'semicolon', 'write two sentences'),
    ('R13', 'dash between clauses', 'write two sentences'),
    ('R19', 'raw link address', 'attach the link to a descriptive noun'),
    (
        'R19',
        'indented or untagged code block',
        'use triple backticks with a language tag',
    ),
    (
        'R19',
        f'code line over {MAX_CODE_WIDTH} characters',
        'wrap at 72 to 80 characters for Google Docs',
    ),
    (
        'R19',
        'tab or smart quote in code block',
        'use spaces and straight ASCII characters',
    ),
    (
        'R20',
        'informational Note/Tip callout in decision doc, or consecutive boxes',
        'fold notes into prose and reserve callouts for hazards/invariants',
    ),
    ('R26', "contraction (don't, it's)", 'write the full words'),
    ('R27', '"-ing" clause after a comma', 'start a new sentence'),
    (
        'R27',
        '2 or more negations in a conditional sentence',
        'rewrite as a positive front-loaded condition',
    ),
    ('R17', 'heading in title case', 'use sentence case'),
    ('R17', 'dash or "&" in a heading', 'write a short topic label'),
    ('R26', '"~" before a number', 'write "about"'),
    ('R26', '"&" or "+" between words', 'write "and"'),
    ('R26', '"vs." and "w/"', 'write "compared with" and "with"'),
    (
        'R26',
        '2 or more slashes between words in a table cell',
        'write "and" or "or", or move the detail to the page of the item',
    ),
    (
        'R14',
        'agentless obligation passive (must/cannot/will be <participle>)',
        'name the actor that owns the obligation',
    ),
    (
        'R14',
        'passive verb with its actor after "by"',
        'make the actor the subject',
    ),
    (
        'R14',
        f'more than {round(100 * MAX_PASSIVE_SHARE)}% of the sentences passive',
        'name the actor and use the active voice',
    ),
    ('R27', 'This/That/These/Those + verb', 'put a noun after the pronoun'),
    ('R27', '3 or more "it" in one sentence', 'repeat the nouns'),
    (
        'R28 (advisory)',
        'should / may / could / would (outside declared normative spec words)',
        'prefer a conditional imperative ("If X, do Y") or fixed-meaning verb',
    ),
    ('R28', 'date with slashes', 'write year-month-day'),
    ('R28', 'relative period (last 30 days)', 'give the dates'),
    ('R28', 'quarter of a year (Q1 to Q4)', 'give the months'),
    ('R30', 'rhetorical hook question', 'state the claim directly'),
    (
        'R31',
        'draft placeholder, chat citation, or AI URL tracker',
        'supply the primary fact or strip the artifact',
    ),
    (
        'R32',
        'trailing commentary participle (highlighting, underscoring)',
        'delete the commentary or state the concrete effect',
    ),
)

SHOUT_WORDS = frozenset((
    'NOTE',
    'WARNING',
    'IMPORTANT',
    'CAUTION',
    'NEVER',
    'ALWAYS',
    'NOT',
    'MUST',
    'ONLY',
    'CRITICAL',
    'MANDATORY',
    'DANGER',
    'ATTENTION',
    'STOP',
))

_FENCE = re.compile(r'^\s*(`{3,}(?=[^`]*$)|~{3,})(.*)$')
_SMART_CODE_CHARS = re.compile(r'[\u2018\u2019\u201c\u201d\u2013\u2014\u2026]')
_PROSE_CODE_LANGS = frozenset(('text', 'plaintext', 'txt', 'markdown', 'md'))
_DIAGRAM_CODE_LANGS = frozenset(('mermaid', 'dot', 'graphviz'))
_TAB_OK_LANGS = frozenset(('makefile', 'make'))
_YAML_KEY = re.compile(r'^[A-Za-z0-9_.-]+\s*:')
_THEMATIC_BREAK = re.compile(
    r'^\s*(?:-\s*){3,}$|^\s*(?:\*\s*){3,}$|^\s*(?:_\s*){3,}$'
)
_LINT_OFF = re.compile(r'^\s*<!--\s*doc-lint:\s*off\s*-->\s*$')
_LINT_ON = re.compile(r'^\s*<!--\s*doc-lint:\s*on\s*-->\s*$')
_QUOTE_PREFIX = re.compile(r'^\s*(?:>\s?)+')
_HEADING = re.compile(r'^(#{1,6})\s+(.*?)\s*#*\s*$')
_HEADING_ID = re.compile(r'^(?:[A-Z]{1,6}-\d+[A-Za-z]?):?\s*')
_APPENDIX_TITLE = re.compile(r'^appendi(?:x|ces)\b', re.IGNORECASE)
_NOT_APPLICABLE = re.compile(r'^\s*(?:not\s+applicable|n/a)\b', re.IGNORECASE)
_LIST_ITEM = re.compile(r'^(\s*)([-*+]|\d+[.)])\s+(.*)$')
_TABLE_RULE = re.compile(r'^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$')
_CELL_SPLIT = re.compile(r'(?<!\\)\|')
_CAPTION = re.compile(r'^\s*[*_][^*_\s]')
_CAPTION_BLOCK = re.compile(
    r'^\s*(?:(?:\*[^*]+\*\s*)+|(?:_[^_]+_\s*)+)$', re.DOTALL
)
_CAPTION_LABEL = re.compile(
    r'^\s*[*_]+\s*(?:table|figure)\b', re.IGNORECASE
)
_LEAD_IN = re.compile(
    r'^\s*(?:\*\*[^*\n]{1,100}:?\*\*|<u>[^<\n]{1,100}:?</u>):?\s*'
)
_ID_HEADER = re.compile(
    r'^(?:#|no\.?|num(?:ber)?|id|index|item|idx|step|ref)$', re.IGNORECASE
)
_ID_CELL = re.compile(r'^(?:#?\d+[.)]?|[A-Za-z]{1,6}[-_.]?\d+[A-Za-z]?)$')
_ALERT_TAG = re.compile(r'^\s*\[!\w+\]')
_INFO_CALLOUT = re.compile(
    r'^\s*(?:\[!(?:NOTE|TIP)\]|\*{0,2}(?:Note|Tip)\s*:)',
    re.IGNORECASE,
)
_CALLOUT = re.compile(
    r'^\s*(?:\[!\w+\]|\*{0,2}(?:Note|Warning|Caution|Important|Tip)\s*:)',
    re.IGNORECASE,
)

_COMMENT = re.compile(r'<!--.*?-->', re.DOTALL)
_IMAGE = re.compile(r'!\[([^\]]*)\]\((?:[^()]|\([^()]*\))*\)', re.DOTALL)
_LINK = re.compile(r'\[([^\]]+)\]\((?:[^()]|\([^()]*\))*\)', re.DOTALL)
_REF_LINK = re.compile(r'\[([^\]]+)\]\[[^\]]*\]', re.DOTALL)
_AUTOLINK = re.compile(r'<https?://[^>\s]+>')
_INLINE_CODE = re.compile(r'(`+)(?!`).+?(?<!`)\1(?!`)', re.DOTALL)
_BOLD = re.compile(r'\*\*(.+?)\*\*', re.DOTALL)
_EMPHASIS = re.compile(r'\*+|(?<!\w)_+|_+(?!\w)')
_QUOTED = re.compile(r'"[^"]{0,200}"|\u201c[^\u201d]{0,200}\u201d')

_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\u2019_/%.+-]*")
_ABBREVIATION = re.compile(
    r'\b(?:e\.g|i\.e|etc|vs|cf|fig|sec|eq|no|vol|ch|pp|ref|approx|al)\.',
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(
    r'(?<=[.!?])["\u201d)\]]*\s+(?=["\u201c(\[]?[A-Z0-9])'
)
_BARE_PRONOUN = re.compile(
    r'^(This|That|These|Those)\s+(is|are|was|were|means|allows|causes|makes|'
    r'will|can|requires|ensures|happens|leads|results|helps|prevents|'
    r'enables|gives|lets|shows|has|have|had|must|might|does|did|should|'
    r'would|could|may)\b'
)
_IT = re.compile(r'\bit\b', re.IGNORECASE)
_OPEN_ITEM = re.compile(r'\[Open:\s*([^\]]*)\]', re.IGNORECASE)
_SUMMARY_TITLE = re.compile(
    r'summary|tl;dr|overview|objective|abstract', re.IGNORECASE
)
MAX_IT_IN_SENTENCE = 2

_HERE_LINK = re.compile(
    r'\[\s*(?:here|this|link|this link|click here|this page)\s*\]\(',
    re.IGNORECASE,
)
_RAW_URL = re.compile(r'https?://[^\s)>\]]+')
_SEMICOLON = re.compile(r';')
_DASH = re.compile(r'\u2014|\s\u2013\s|\s--\s')
_CONTRACTION = re.compile(
    r"\b(?:\w+n['\u2019]t|\w+['\u2019](?:ll|re|ve|m|d)|"
    r'(?:it|that|there|what|let|here|who|he|she|how|where|when|why)'
    r"['\u2019]s)\b",
    re.IGNORECASE,
)
_ING_CLAUSE = re.compile(
    r',\s+(causing|making|allowing|resulting|leading|ensuring|enabling|'
    r'preventing|reducing|increasing|leaving|forcing|requiring|meaning|'
    r'creating|producing)\b'
)
_COMMENTARY_ING = re.compile(
    r',\s+(highlighting|underscoring|showcasing|reflecting|demonstrating|'
    r'illustrating|signaling|reinforcing|emphasizing)\b'
)
_RHETORICAL_HOOK = re.compile(
    r'\b(?:why does this matter|what does this mean|the catch|the kicker|'
    r'plot twist)\?',
    re.IGNORECASE,
)
_PLACEHOLDER = re.compile(
    r'\[(?:Insert|Add|Your|Enter|Describe|Specify)\s+[^\]]+\]|\b20\d\d-XX-XX\b',
    re.IGNORECASE,
)
_CHAT_CITATION = re.compile(
    r'\bciteturn\d+\w*\b|contentReference\[oaicite|\boai_citation\b'
)
_AI_UTM = re.compile(
    r'(?:[?&])(utm_source=(?:chatgpt\.com|openai(?:\.com)?|copilot\.com|'
    r'claude\.ai|perplexity\.ai|gemini\.google\.com|grok\.com)|'
    r'referrer=grok\.com)(?=[&#)\s]|$)',
    re.IGNORECASE,
)
_AI_UTM_PARAM = re.compile(
    r'^(?:utm_source=(?:chatgpt\.com|openai(?:\.com)?|copilot\.com|claude\.ai|'
    r'perplexity\.ai|gemini\.google\.com|grok\.com)|referrer=grok\.com)$',
    re.IGNORECASE,
)
_STRUCTURAL_NUM = re.compile(
    r'\b(?:(?:Table|Figure|Section|Step|Option)\s+\d+|'
    r'(?:SPEC|DESIGN|ADR|PLAN|REQ|INV|ASM|DEC|OPT|OQ|ITEM)-\d+[A-Za-z]?)\b',
    re.IGNORECASE,
)
_NUMBER_TOKEN = re.compile(
    r'\b\d+(?:[, ]\d{3})*(?:\.\d+)?%?\b'
)
_NUMBER_WORDS = {
    'two': '2',
    'three': '3',
    'four': '4',
    'five': '5',
    'six': '6',
    'seven': '7',
    'eight': '8',
    'nine': '9',
    'ten': '10',
}
_NUMBER_WORD_RE = re.compile(
    r'\b(' + '|'.join(_NUMBER_WORDS) + r')\b', re.IGNORECASE
)
_LINK_TARGET = re.compile(
    r'\[[^\]]*\]\(((?:[^()\s]|\([^()\s]*\))+)(?:[^()]|\([^()]*\))*\)'
)
_SMART_QUOTE_MAP = str.maketrans({
    '\u2018': "'",
    '\u2019': "'",
    '\u201c': '"',
    '\u201d': '"',
    '\u2013': '-',
    '\u2014': '-',
    '\u2026': '...',
})
# Standard terms that contain a word from the list. The word check skips them.
_TERM_EXCEPTIONS = re.compile(
    r'\b(?:(?:file|socket|window|object|device|resource|opaque)\s+handles?|'
    r'minimal\s+(?:base\s+)?images?|minimal\s+reproducers?|'
    r'fast\s+path|fast-forward|quick\s*start|quickstart|'
    r'significant\s+(?:digits?|bits?|figures?)|simple\s+past|'
    r'highly\s+available|just-in-time)\b',
    re.IGNORECASE,
)
# A quantity directly after a word such as "fast" answers the advice.
_QUANTITY_AFTER = re.compile(r'^\s*[:,(]\s*(?:[A-Za-z]+\s+){0,3}[<>=~]?\s*\d')
_QUANTITY_BEFORE = re.compile(r'\d[\w.%]*\s+(?:times\s+)?$')
_NEEDS_QUANTITY = ('give a number', 'give the quantity', 'give the cost')
_STATUS_NOTE = re.compile(
    r'\((?:measured|calculated|estimated|derived|verified in source|cited|'
    r'reported|assumed|not measured|not verified|not known)\b[^()]*\)',
    re.IGNORECASE,
)
_TILDE_NUMBER = re.compile(r'(?<![\w/.])~\s?\d')
_RELATIVE_PERIOD = re.compile(
    r'\b(?:last|past|previous|next)\s+\d+\s+'
    r'(?:minutes?|hours?|days?|weeks?|months?|quarters?|years?)\b',
    re.IGNORECASE,
)
_RANGE_SIDE_BEFORE = re.compile(r'(?:CODE|\d[\w.%]*)\s*$')
_RANGE_SIDE_AFTER = re.compile(r'^\s*(?:CODE|\d)')
_PARTICIPLE = (
    r'(?:\w{2,}ed|built|made|sent|kept|held|read|run|done|lost|found|shown|'
    r'known|given|taken|written|chosen|hidden|sold|told|paid|left|cut|split|'
    r'spent|put|set|drawn|thrown|broken|stolen|frozen|driven|overwritten)'
)
_PASSIVE = re.compile(
    r'\b(?:is|are|was|were|be|been|being|gets|get|got)\s+'
    r'(?:(?:not|also|never|always|only|then|still|first|\w+ly)\s+){0,2}'
    r'(' + _PARTICIPLE + r')\b',
    re.IGNORECASE,
)
_OBLIGATION_PASSIVE = re.compile(
    r'\b(?:must|cannot|will)\s+(?:not\s+)?be\s+'
    r'(?:(?:also|never|always|only|then|still|first|\w+ly)\s+){0,2}'
    r'(' + _PARTICIPLE + r')\b',
    re.IGNORECASE,
)
_DOUBLE_NEG_COND = re.compile(
    r'\b(?:(?:not|never)\b[^.?!]{0,120}\bunless|'
    r'unless\b[^.?!]{0,120}\b(?:not|never)|'
    r'if\b[^.?!]{0,120}\b(?:not|never)\b[^.?!]{0,120}\b(?:not|never|unless))\b',
    re.IGNORECASE,
)
_NEG_SAFE = re.compile(
    r'\b(?:or\s+not|not\s+(?:measured|verified|known|applicable))\b',
    re.IGNORECASE,
)
# Participles that describe a state. They are adjectives, not passive verbs.
_STATE_WORDS = frozenset((
    'based', 'located', 'required', 'needed', 'allowed', 'permitted',
    'supported', 'deprecated', 'enabled', 'disabled', 'expected', 'intended',
    'related', 'associated', 'connected', 'limited', 'interested', 'installed',
    'finished', 'unchanged', 'named', 'called', 'reserved', 'fixed', 'closed',
    'locked', 'unlocked', 'unused', 'detailed', 'advanced', 'embedded',
    'left', 'set', 'done', 'known', 'hidden', 'lost', 'need', 'exceed',
    'proceed', 'succeed', 'speed', 'feed', 'indeed',
))
_BY_ACTOR = re.compile(
    r'^[^.;:]{0,60}?\bby\s+(?:the|a|an|each|this|that|these|our|its|CODE|'
    r'[A-Z]\w+)\b'
)
_AMPERSAND = re.compile(r'(?<=[\w)])\s+&\s+(?=[\w(])')
_PLUS_WORD = re.compile(r'(?<=[A-Za-z)])\s+\+\s+(?=[A-Za-z(])')
_VERSUS = re.compile(r'(?<![\w-])vs\.?(?![\w-])', re.IGNORECASE)
_WITH_SLASH = re.compile(r'(?<![\w/])w/(?=\s|\w)', re.IGNORECASE)
# A slash between two words hides "and" or "or". Standard pairs stay.
_SLASH_PAIR = re.compile(
    r'(?<![\w/.:-])[A-Za-z][\w-]*(?:/[A-Za-z][\w-]*)+(?![\w/])'
)
_SLASH_OK = frozenset((
    'i/o', 'tcp/ip', 'ci/cd', 'a/b', 'and/or', 'client/server', 'read/write',
    'input/output', 'n/a', 'os/2', 'gnu/linux', 'pl/sql', 'request/response',
    'publish/subscribe', 'pub/sub', 'on/off', 'true/false', 'yes/no',
    'pass/fail', 'key/value', 'code',
))
MAX_CELL_SLASH_PAIRS = 1
_HEADING_SYMBOL = re.compile(r'\u2014|\s\u2013\s|\s--\s|\s&\s')
_SHOULD_MODAL = re.compile(r'(?<![\w-])should(?![\w-])', re.IGNORECASE)
_MAY_MODAL = re.compile(r'(?<![\w-])(?:may|MAY)(?![\w-])')
_COULD_MODAL = re.compile(r'(?<![\w-])could(?![\w-])', re.IGNORECASE)
_WOULD_MODAL = re.compile(r'(?<![\w-])would(?![\w-])', re.IGNORECASE)
_NORMATIVE_HEADING = re.compile(
    r'^(?:normative\s+(?:key\s*words?|terms?|language)|'
    r'requirements?\s+language|conventions(?:\s+and\s+terminology)?)$',
    re.IGNORECASE,
)
_NORMATIVE_LEAD = re.compile(
    r'^(?:[-*+]\s+)?\*{0,2}(?:normative|conformance|requirement)s?\s+'
    r'(?:key\s*words?|terms?|levels?|language)\*{0,2}\s*:\*{0,2}',
    re.IGNORECASE,
)
_NORMATIVE_SCOPE = re.compile(
    r'\b(?:this\s+(?:document|spec(?:ification)?|standard)|herein)\b',
    re.IGNORECASE,
)
_NORMATIVE_DECL = re.compile(
    r'\b(?:rfc\s*(?:2119|8174)|bcp\s*14|'
    r'normative\s+(?:key\s*words?|terms?|language|requirement|conformance)|'
    r'(?:key\s*words?|terms?)\b[^.]{0,140}\bare\s+'
    r'(?:to\s+be\s+interpreted|normative))\b',
    re.IGNORECASE,
)
_NORMATIVE_WORDS = re.compile(
    r'\bmust\b.*\b(?:should|may)\b|\b(?:should|may)\b.*\bmust\b',
    re.IGNORECASE,
)
_NORMATIVE_NOT_BEFORE = re.compile(r'\b(?:MUST|SHALL|SHOULD)\s+$')
_NORMATIVE_NOT_AFTER = re.compile(r'^\s+RECOMMENDED\b')
_SLASH_DATE = re.compile(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b')
_QUARTER = re.compile(r'\bQ[1-4]\b')
_CAPITAL_WORD = re.compile(r'\b[A-Z]{3,}\b')
_MD_NON_IMG_LINK = re.compile(
    r'(?<!!)\[([^\]]+)\]\(((?:[^()]|\([^()]*\))+)\)'
)
_HTML_ID = re.compile(r'\bid=["\']([^"\']+)["\']')
_EXTERNAL_SCHEME = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.-]*:')
_SHELL_LANGS = frozenset(('bash', 'sh', 'shell', 'zsh'))
_SHELL_PROMPT = re.compile(r'^\$\s+\S')


@dataclasses.dataclass(frozen=True, order=True, slots=True)
class Finding:
  """One rule violation or advisory at one line."""

  line: int
  rule: str
  message: str
  advisory: bool = False


@dataclasses.dataclass(slots=True)
class Block:
  """A structural unit of a Markdown document."""

  kind: str  # 'heading', 'text', 'item', 'table', or 'code'.
  line: int
  lines: list[str]
  indent: int = 0
  size: int = 0  # Heading level, or number of lines in a code block.
  ordered: bool = False  # True for an item of a numbered list.
  info: str = ''  # Info string on a fenced code block.
  unclosed: bool = False  # True for an unclosed fenced code block.


def _phrase_regex(forms: str) -> re.Pattern[str]:
  """Returns a regex that matches each form as a complete word or phrase."""
  alternatives = []
  for form in forms.split('|'):
    words = (re.escape(word) for word in form.split(' '))
    alternatives.append(r'\s+'.join(words))
  pattern = r'(?<![\w-])(?:%s)(?![\w-])' % '|'.join(alternatives)
  return re.compile(pattern, re.IGNORECASE)


_WORD_RULES = tuple(
    (rule, _phrase_regex(forms), advice) for rule, forms, advice in WORDS
)


def _same_lines(replacement: str, original: str) -> str:
  """Pads a replacement so that it keeps the line count of the original."""
  missing = original.count('\n') - replacement.count('\n')
  return replacement + '\n' * max(missing, 0)


def _mask_literals(text: str) -> str:
  """Replaces HTML comments, inline code, and double-quoted spans."""
  text = _COMMENT.sub(lambda m: _same_lines('', m.group(0)), text)
  text = _INLINE_CODE.sub(lambda m: _same_lines(' CODE ', m.group(0)), text)
  return _QUOTED.sub(lambda m: _same_lines(' QUOTE ', m.group(0)), text)


def _clean_inline(text: str) -> str:
  """Removes Markdown markup from prose and keeps the line structure."""
  text = _COMMENT.sub(lambda m: _same_lines('', m.group(0)), text)
  text = _INLINE_CODE.sub(lambda m: _same_lines(' CODE ', m.group(0)), text)
  text = _IMAGE.sub(lambda m: _same_lines(m.group(1), m.group(0)), text)
  text = _LINK.sub(lambda m: _same_lines(m.group(1), m.group(0)), text)
  text = _REF_LINK.sub(lambda m: _same_lines(m.group(1), m.group(0)), text)
  text = _AUTOLINK.sub(' LINK ', text)
  return _EMPHASIS.sub('', text)


def _count_words(text: str) -> int:
  return len(_WORD.findall(text))


def _line_of(text: str, offset: int, first_line: int) -> int:
  return first_line + text.count('\n', 0, offset)


def _sentences(text: str) -> list[tuple[int, str]]:
  """Splits prose into sentences. Returns (offset, sentence) pairs."""
  guarded = _ABBREVIATION.sub(lambda m: m.group(0).replace('.', '\u2024'), text)
  starts = [0] + [m.end() for m in _SENTENCE_END.finditer(guarded)]
  ends = starts[1:] + [len(guarded)]
  pairs = []
  for start, end in zip(starts, ends):
    sentence = text[start:end].strip()
    if sentence:
      pairs.append((start, sentence))
  return pairs


def _excerpt(text: str, limit: int = 6) -> str:
  words = text.split()
  tail = ' ...' if len(words) > limit else ''
  return ' '.join(words[:limit]) + tail


def _context(text: str, start: int, end: int) -> str:
  """Returns the match with the 2 words before it and the 2 words after it."""
  head = text[max(0, start - 40) : start]
  tail = text[end : end + 40]
  before = ' '.join(head.split()[-2:])
  after = ' '.join(tail.split()[:2])
  if before and head[-1:].isspace():
    before += ' '
  if after and tail[:1].isspace():
    after = ' ' + after
  return before + ' '.join(text[start:end].split()) + after


def _has_front_matter(lines: list[str]) -> bool:
  """Returns True if lines start with a closed YAML front-matter block."""
  if len(lines) < 2 or lines[0].strip() != '---':
    return False
  if lines[1].strip() in ('---', '...'):
    return True
  saw_key = False
  for line in lines[1:]:
    stripped = line.strip()
    if stripped in ('---', '...'):
      return saw_key
    if not stripped or stripped.startswith('#'):
      continue
    if _YAML_KEY.match(line):
      saw_key = True
    elif not saw_key and not line[:1].isspace():
      return False
  return False


def _split_table_cells(line: str) -> list[str]:
  """Splits a Markdown table row on unescaped pipes outside inline code."""
  stripped = line.strip()
  if stripped.startswith('|'):
    stripped = stripped[1:]
  if stripped.endswith('|') and not stripped.endswith('\\|'):
    stripped = stripped[:-1]
  code_spans = [m.span() for m in _INLINE_CODE.finditer(stripped)]
  cells: list[str] = []
  start = 0
  for match in _CELL_SPLIT.finditer(stripped):
    pos = match.start()
    if any(cs <= pos < ce for cs, ce in code_spans):
      continue
    cells.append(stripped[start:pos].strip())
    start = match.end()
  cells.append(stripped[start:].strip())
  return cells


def parse_blocks(
    lines: list[str], respect_lint_off: bool = True
) -> list[Block]:
  """Splits the lines of a Markdown document into blocks."""
  blocks: list[Block] = []
  current: Block | None = None
  fence = ''
  fence_base_indent = 0
  code_block: Block | None = None
  list_indents: list[int] = []
  saw_blank = False
  checking = True
  front_matter = _has_front_matter(lines)
  index = 0
  while index < len(lines):
    number = index + 1
    raw = lines[index]
    index += 1
    if front_matter:
      front_matter = not (number > 1 and raw.strip() in ('---', '...'))
      continue
    text = _QUOTE_PREFIX.sub('', raw)
    stripped = text.strip()
    expanded = text.expandtabs(4)
    line_indent = len(expanded) - len(expanded.lstrip(' '))
    fence_match = _FENCE.match(text)
    if fence and code_block is not None:
      closes = (
          fence_match is not None
          and line_indent <= fence_base_indent + 3
          and fence_match.group(1).startswith(fence)
          and not fence_match.group(2).strip()
      )
      if closes:
        fence = ''
        fence_base_indent = 0
        if checking:
          blocks.append(code_block)
        code_block = None
      else:
        stripped_indent = 0
        while (
            stripped_indent < code_block.indent
            and stripped_indent < len(text)
            and text[stripped_indent] == ' '
        ):
          stripped_indent += 1
        code_block.lines.append(text[stripped_indent:])
        code_block.size += 1
      saw_blank = False
      continue
    if not stripped:
      current = None
      saw_blank = True
      continue
    if _LINT_OFF.match(stripped):
      if respect_lint_off:
        checking = False
      current = None
      continue
    if _LINT_ON.match(stripped):
      if respect_lint_off:
        checking = True
      current = None
      continue
    if saw_blank:
      list_indents = [w for w in list_indents if w <= line_indent]
      saw_blank = False
    enclosing_indent = max(
        (w for w in list_indents if w <= line_indent), default=0
    )
    if fence_match and line_indent <= enclosing_indent + 3:
      list_indents = [w for w in list_indents if w <= line_indent]
      fence = fence_match.group(1)
      fence_base_indent = enclosing_indent
      code_block = Block(
          'code',
          number,
          [],
          indent=line_indent,
          info=fence_match.group(2).strip(),
      )
      current = None
      continue
    if not checking:
      continue
    heading = _HEADING.match(text)
    if heading:
      list_indents.clear()
      blocks.append(
          Block(
              'heading', number, [heading.group(2)], size=len(heading.group(1))
          )
      )
      current = None
      continue
    following = ''
    if index < len(lines):
      following = _QUOTE_PREFIX.sub('', lines[index])
    if '|' in text and '|' in following and _TABLE_RULE.match(following):
      list_indents = [w for w in list_indents if w <= line_indent]
      rows = [text]
      index += 1
      while index < len(lines):
        row = _QUOTE_PREFIX.sub('', lines[index])
        if not row.strip() or not ('|' in row or row.lstrip().startswith(':')):
          break
        rows.append(row)
        index += 1
      blocks.append(Block('table', number, rows, indent=line_indent))
      current = None
      continue
    if _THEMATIC_BREAK.match(text):
      list_indents = [w for w in list_indents if w <= line_indent]
      current = None
      continue
    item = _LIST_ITEM.match(text)
    if item:
      item_indent = len(item.group(1).expandtabs(4))
      content_indent = len(text[: item.start(3)].expandtabs(4))
      list_indents = [w for w in list_indents if w <= item_indent]
      list_indents.append(content_indent)
      current = Block(
          'item',
          number,
          [item.group(3)],
          indent=item_indent,
          ordered=item.group(2)[0].isdigit(),
      )
      blocks.append(current)
      continue
    if current is None:
      current = Block('text', number, [], indent=line_indent)
      blocks.append(current)
    current.lines.append(text)
  if fence and code_block is not None and checking:
    code_block.unclosed = True
    blocks.append(code_block)
  return blocks


def _github_slugs(title: str) -> tuple[str, ...]:
  """Returns GitHub-style anchor slug forms for a Markdown heading."""
  cleaned = re.sub(r'\s+#+\s*$', '', title.strip())
  cleaned = re.sub(r'<[^>]+>', '', cleaned)
  cleaned = _IMAGE.sub(r'\1', cleaned)
  cleaned = _LINK.sub(r'\1', cleaned)
  cleaned = cleaned.replace('`', '').lower().strip()
  cleaned = re.sub(r'[^\w\s-]', '', cleaned, flags=re.UNICODE)
  raw_slug = re.sub(r'\s', '-', cleaned).strip('-')
  collapsed = re.sub(r'-+', '-', raw_slug)
  if raw_slug == collapsed:
    return (raw_slug,) if raw_slug else ()
  return tuple(s for s in (raw_slug, collapsed) if s)


def _document_anchors(text: str) -> frozenset[str]:
  """Extracts heading anchor slugs and explicit HTML id attributes."""
  anchors: set[str] = set()
  counts: dict[str, int] = {}
  for html_id in _HTML_ID.findall(_mask_literals(text)):
    anchors.add(html_id)
  for block in parse_blocks(text.splitlines(), respect_lint_off=False):
    if block.kind != 'heading':
      continue
    for slug in _github_slugs(block.lines[0]):
      seen = counts.get(slug, 0)
      counts[slug] = seen + 1
      anchors.add(slug if seen == 0 else f'{slug}-{seen}')
  return frozenset(anchors)


def _table_rows(
    lines: list[str], first_line: int
) -> list[tuple[int, list[str]]]:
  """Returns (line_number, cells) for each table row, merging continuations."""
  rows: list[tuple[int, list[str]]] = []
  for offset, line in enumerate(lines):
    # The block has no entry for the separator rule line below the header.
    number = first_line + offset + (1 if offset else 0)
    stripped = line.strip()
    if stripped.startswith(':'):
      cells = re.split(r'\s+:(?:\s+|$)', stripped.lstrip(':').strip())
      for column, cell in enumerate(cells):
        if rows and column < len(rows[-1][1]):
          rows[-1][1][column] += ' ' + cell.strip()
      continue
    rows.append((number, _split_table_cells(line)))
  return rows


def _is_block_caption(block: Block | None, preceding: Block | None) -> bool:
  """Returns True if block captions a preceding table or code block."""
  if (
      block is None
      or block.kind != 'text'
      or preceding is None
      or preceding.kind not in ('table', 'code')
  ):
    return False
  masked = _mask_literals('\n'.join(block.lines))
  return bool(
      _CAPTION_BLOCK.match(masked) or _CAPTION_LABEL.match(block.lines[0])
  )


class _Linter:
  """Collects the findings for one document."""

  def __init__(
      self, base_dir: pathlib.Path | None = None, profile: str = 'decision'
  ) -> None:
    self.findings: list[Finding] = []
    self.words = 0
    self._base_dir = base_dir
    self._docs = profile == 'docs'
    self._cell_limit = MAX_CELL_WORDS_DOCS if self._docs else MAX_CELL_WORDS
    self._self_anchors: frozenset[str] = frozenset()
    self._anchor_cache: dict[pathlib.Path, frozenset[str]] = {}
    self._bold_characters = 0
    self._characters = 0
    self._callouts = 0
    self._section_line = 1
    self._section_words = 0
    self._appendix_level = 0
    self._previous_heading_level = 0
    self._list_runs: dict[int, list[int]] = {}
    # (line, is_title_case, is_strong) for each heading of 2 or more words.
    self._heading_cases: list[tuple[int, bool, bool]] = []
    self._sentences = 0
    self._passive_lines: list[int] = []
    self._prev_was_callout = False
    self._normative_style = ''

  def _check_links_and_images(self, masked: str, first_line: int) -> None:
    """Checks image alt text and local link paths and heading anchors."""
    for match in _IMAGE.finditer(masked):
      if not match.group(1).strip():
        self._add(
            _line_of(masked, match.start(), first_line),
            'R11',
            'image without alternative text',
        )
    for match in _MD_NON_IMG_LINK.finditer(masked):
      raw_target = match.group(2).strip()
      if raw_target.startswith('<') and '>' in raw_target:
        raw_target = raw_target[1 : raw_target.index('>')]
      else:
        raw_target = raw_target.split()[0] if raw_target else ''
      if not raw_target or _EXTERNAL_SCHEME.match(raw_target):
        continue
      line_no = _line_of(masked, match.start(), first_line)
      path_part, sep, frag_part = raw_target.partition('#')
      rel_path = urllib.parse.unquote(path_part)
      fragment = urllib.parse.unquote(frag_part) if sep else ''
      if not rel_path:
        if fragment and fragment not in self._self_anchors:
          self._add(
              line_no, 'R19', f'missing heading anchor "#{fragment}"'
          )
        continue
      if self._base_dir is None:
        continue
      target_file = (self._base_dir / rel_path).resolve()
      if not target_file.exists():
        self._add(line_no, 'R19', f'broken local link "{raw_target}"')
        continue
      if (
          fragment
          and target_file.is_file()
          and target_file.suffix.lower() == '.md'
      ):
        anchors = self._anchor_cache.get(target_file)
        if anchors is None:
          try:
            anchors = _document_anchors(target_file.read_text(encoding='utf-8'))
          except OSError:
            anchors = frozenset()
          self._anchor_cache[target_file] = anchors
        if fragment not in anchors:
          self._add(
              line_no,
              'R19',
              f'missing heading anchor "#{fragment}" in "{rel_path}"',
          )

  def _add(
      self, line: int, rule: str, message: str, advisory: bool = False
  ) -> None:
    self.findings.append(Finding(line, rule, message, advisory=advisory))

  def _take_open_items(
      self, raw: str, first_line: int, report: bool = True
  ) -> str:
    """Reports each open item and removes its text from the prose."""
    code_spans = [match.span() for match in _INLINE_CODE.finditer(raw)]

    def replace(match: re.Match[str]) -> str:
      if any(start <= match.start() < end for start, end in code_spans):
        return match.group(0)
      if report:
        self._add(
            _line_of(raw, match.start(), first_line),
            'OPEN',
            f'open item "{_excerpt(match.group(1))}": the author answers it '
            'or moves it to an open-questions section',
        )
      return _same_lines(' OPEN ', match.group(0))

    return _OPEN_ITEM.sub(replace, raw)

  def _check_words(self, cleaned: str, first_line: int) -> None:
    """Checks prose without markup against the word list and patterns."""
    text = _QUOTED.sub(lambda m: _same_lines(' QUOTE ', m.group(0)), cleaned)
    listed = _TERM_EXCEPTIONS.sub(
        lambda m: _same_lines(' TERM ', m.group(0)).ljust(len(m.group(0))), text
    )
    flat = ' '.join(cleaned.split())
    is_norm_decl = bool(
        self._normative_style
        and (
            _NORMATIVE_DECL.search(flat)
            or _NORMATIVE_LEAD.match(flat)
            or _NORMATIVE_WORDS.search(flat)
        )
    )
    for rule, regex, advice in _WORD_RULES:
      if self._docs and rule == 'R24':
        continue
      for match in regex.finditer(listed):
        if advice.startswith(_NEEDS_QUANTITY) and (
            _QUANTITY_AFTER.match(listed[match.end() :])
            or _QUANTITY_BEFORE.search(listed[: match.start()])
        ):
          continue
        found = ' '.join(match.group(0).split())
        if (
            is_norm_decl
            and rule == 'R29'
            and found.lower() in ('in this document', 'this document describes')
        ):
          continue
        context = _context(text, match.start(), match.end())
        self._add(
            _line_of(text, match.start(), first_line),
            rule,
            f'"{found}" in "{context}": {advice}',
        )
    modal_checks = (
        (
            _SHOULD_MODAL,
            'should',
            'SHOULD',
            (
                'prefer a conditional imperative ("If X, do Y"), "must", or '
                '"we expect"'
            ),
        ),
        (
            _MAY_MODAL,
            'may',
            'MAY',
            'prefer a conditional imperative ("If X, do Y"), "can", or "might"',
        ),
        (
            _COULD_MODAL,
            '',
            '',
            'prefer a conditional imperative ("If X, do Y"), "can", or "might"',
        ),
        (
            _WOULD_MODAL,
            '',
            '',
            (
                'prefer an explicit conditional ("If X, do Y" or '
                '"If X occurs, Y occurs")'
            ),
        ),
    )
    for m_regex, lower_kw, upper_kw, m_advice in modal_checks:
      for match in m_regex.finditer(listed):
        tok = match.group(0)
        if self._normative_style == 'upper' and upper_kw and tok == upper_kw:
          continue
        if self._normative_style == 'lower' and lower_kw and tok == lower_kw:
          continue
        context = _context(text, match.start(), match.end())
        self._add(
            _line_of(text, match.start(), first_line),
            'R28',
            f'"{tok}" in "{context}": {m_advice}',
            advisory=True,
        )
    patterns = (
        (_SEMICOLON, 'R13', 'semicolon', 'write two sentences'),
        (_DASH, 'R13', 'dash between clauses', 'write two sentences'),
        (_CONTRACTION, 'R26', 'contraction', 'write the full words'),
        (
            _ING_CLAUSE,
            'R27',
            '"-ing" clause after a comma',
            'start a new sentence with a subject',
        ),
        (
            _COMMENTARY_ING,
            'R32',
            'trailing commentary clause',
            'delete it, or state the concrete effect in a new sentence',
        ),
        (
            _RHETORICAL_HOOK,
            'R30',
            'rhetorical hook question',
            'delete the hook and state the claim directly',
        ),
        (
            _CHAT_CITATION,
            'R31',
            'chat citation markup',
            'remove the markup and cite the primary source',
        ),
        (_SLASH_DATE, 'R28', 'date', 'write year-month-day'),
        (_RELATIVE_PERIOD, 'R28', 'relative period', 'give the dates'),
        (_TILDE_NUMBER, 'R26', '"~" before a number', 'write "about"'),
        (_AMPERSAND, 'R26', '"&" as a word', 'write "and"'),
        (_PLUS_WORD, 'R26', '"+" as a word', 'write "and"'),
        (_VERSUS, 'R26', '"vs."', 'write "compared with" or "against"'),
        (_WITH_SLASH, 'R26', '"w/"', 'write "with"'),
        (_QUARTER, 'R28', 'quarter of a year', 'give the months'),
        (
            _RAW_URL,
            'R19',
            'raw address',
            'attach the link to a descriptive noun',
        ),
    )
    for regex, rule, label, advice in patterns:
      for match in regex.finditer(text):
        if (
            regex is _DASH
            and _RANGE_SIDE_BEFORE.search(text[: match.start()])
            and _RANGE_SIDE_AFTER.match(text[match.end() :])
        ):
          continue  # A range such as "R1 - R32", not a clause break.
        context = _context(text, match.start(), match.end())
        self._add(
            _line_of(text, match.start(), first_line),
            rule,
            f'{label} in "{context}": {advice}',
        )
    for match in _CAPITAL_WORD.finditer(text):
      word = match.group(0)
      if word not in SHOUT_WORDS:
        continue
      if self._normative_style == 'upper':
        if word == 'MUST':
          continue
        if word == 'NOT' and (
            _NORMATIVE_NOT_BEFORE.search(text[: match.start()])
            or _NORMATIVE_NOT_AFTER.match(text[match.end() :])
        ):
          continue
      self._add(
          _line_of(text, match.start(), first_line),
          'R20',
          f'"{word}" in capital letters: use sentence case',
      )

  def _check_prose(self, block: Block) -> None:
    """Checks one paragraph, list item, or callout block."""
    raw = self._take_open_items('\n'.join(block.lines), block.line)
    masked = _mask_literals(raw)
    lead_in_span = _LEAD_IN.match(raw) if block.kind == 'item' else None
    for match in _BOLD.finditer(masked):
      cleaned_bold = _clean_inline(match.group(1))
      self._bold_characters += len(cleaned_bold)
      bold_limit = (
          MAX_LEAD_IN_WORDS
          if lead_in_span and match.start() < lead_in_span.end()
          else MAX_BOLD_WORDS
      )
      if _count_words(cleaned_bold) > bold_limit:
        self._add(
            _line_of(masked, match.start(), block.line),
            'R18',
            f'bold text of more than {bold_limit} words: '
            f'"{_excerpt(match.group(1))}"',
        )
    if _HERE_LINK.search(masked):
      self._add(block.line, 'R19', 'link text does not describe the target')
    self._check_links_and_images(masked, block.line)
    for match in _AI_UTM.finditer(masked):
      self._add(
          _line_of(masked, match.start(), block.line),
          'R31',
          f'AI-tool tracking parameter "{match.group(1)}": '
          'remove it from the link',
      )
    for match in _PLACEHOLDER.finditer(masked):
      self._add(
          _line_of(masked, match.start(), block.line),
          'R31',
          f'draft placeholder "{match.group(0)}": '
          'supply the fact or use [Open: question]',
      )
    is_callout = bool(_CALLOUT.match(raw))
    if is_callout:
      is_info = bool(_INFO_CALLOUT.match(raw))
      if not self._docs or is_info:
        self._callouts += 1
      if not self._docs and is_info:
        self._add(
            block.line,
            'R20',
            'informational Note/Tip callout in decision document: '
            'fold into prose or delete',
        )
      if self._prev_was_callout:
        self._add(
            block.line,
            'R20',
            'consecutive callout boxes: merge or convert notes to prose',
        )
      raw = _ALERT_TAG.sub('', raw)
    self._prev_was_callout = is_callout
    cleaned = _clean_inline(raw)
    self._characters += len(cleaned)
    count = _count_words(cleaned)
    self.words += count
    self._section_words += count
    self._check_words(cleaned, block.line)

    body = cleaned
    if block.kind == 'item':
      lead_in = _LEAD_IN.match(raw)
      if lead_in:
        body = _clean_inline(
            _same_lines('', lead_in.group(0)) + raw[lead_in.end() :]
        )
    sentences = _sentences(body)
    for offset, sentence in sentences:
      line = _line_of(body, offset, block.line)
      length = _count_words(_STATUS_NOTE.sub(' ', sentence))
      if length > MAX_SENTENCE_WORDS:
        self._add(
            line,
            'R13',
            f'sentence of {length} words (limit {MAX_SENTENCE_WORDS}): '
            f'"{_excerpt(sentence)}"',
        )
      self._sentences += 1
      unquoted = _QUOTED.sub(' QUOTE ', sentence)
      passives = [
          m
          for m in _PASSIVE.finditer(unquoted)
          if m.group(1).lower() not in _STATE_WORDS
      ]
      if passives:
        self._passive_lines.append(line)
      for match in passives:
        if _BY_ACTOR.match(unquoted[match.end() :]):
          self._add(
              line,
              'R14',
              f'passive verb with its actor after "by" in '
              f'"{_context(sentence, match.start(), match.end())}": '
              'make the actor the subject',
          )
      for match in _OBLIGATION_PASSIVE.finditer(unquoted):
        if match.group(1).lower() in _STATE_WORDS or _BY_ACTOR.match(
            unquoted[match.end() :]
        ):
          continue
        self._add(
            line,
            'R14',
            'agentless passive obligation in '
            f'"{_context(sentence, match.start(), match.end())}": '
            'name the actor that owns the obligation',
        )
      neg_check = _NEG_SAFE.sub(' ', unquoted)
      if _DOUBLE_NEG_COND.search(neg_check):
        self._add(
            line,
            'R27',
            '2 or more negations in a conditional sentence: '
            f'rewrite positively ("{_excerpt(sentence)}")',
        )
      if (
          not self._docs
          and not self._appendix_level
          and sentence.count('CODE') > MAX_CODE_NAMES
      ):
        self._add(
            line,
            'R15',
            f'more than {MAX_CODE_NAMES} code names in one sentence: '
            f'"{_excerpt(sentence)}"',
        )
      if _BARE_PRONOUN.match(sentence):
        self._add(
            line, 'R27', f'no noun after the pronoun: "{_excerpt(sentence, 3)}"'
        )
      if len(_IT.findall(sentence)) > MAX_IT_IN_SENTENCE:
        self._add(
            line,
            'R27',
            f'more than {MAX_IT_IN_SENTENCE} "it" in one sentence, repeat the'
            f' nouns: "{_excerpt(sentence)}"',
        )
    if (
        block.kind == 'text'
        and block.indent == 0
        and len(sentences) > MAX_PARAGRAPH_SENTENCES
    ):
      self._add(
          block.line,
          'R13',
          f'paragraph of {len(sentences)} sentences '
          f'(limit {MAX_PARAGRAPH_SENTENCES})',
      )

  def _check_table(
      self,
      block: Block,
      previous: Block | None,
      following: Block | None,
      before_previous: Block | None = None,
  ) -> None:
    """Checks one Markdown table, its lead-in frame, and its caption."""
    below_heading = previous is not None and previous.kind == 'heading'
    if (
        previous is None
        or previous.kind in ('heading', 'table', 'code')
        or _is_block_caption(previous, before_previous)
    ) and not (self._docs and below_heading):
      self._add(
          block.line, 'R12', 'table without an introductory sentence above'
      )
    sanitized_lines: list[str] = []
    for offset, line in enumerate(block.lines):
      number = block.line + offset + (1 if offset else 0)
      sanitized_lines.append(self._take_open_items(line, number))
    rows = _table_rows(sanitized_lines, block.line)
    columns = max(len(cells) for _, cells in rows)
    if columns > MAX_TABLE_COLUMNS:
      self._add(
          block.line,
          'R10',
          f'table of {columns} columns (limit {MAX_TABLE_COLUMNS})',
      )
    if not self._docs and not self._appendix_level:
      self._check_key_description_table(block.line, rows, columns)
    cell_limit = (
        MAX_CELL_WORDS_DOCS if self._appendix_level else self._cell_limit
    )
    for row_idx, (row_line, cells) in enumerate(rows):
      if row_idx > 0 and len(cells) < columns:
        self._add(
            row_line,
            'R10',
            'empty table cell: write 0, None, N/A, or Not measured',
        )
      for cell in cells:
        if row_idx > 0 and not cell.strip():
          self._add(
              row_line,
              'R10',
              'empty table cell: write 0, None, N/A, or Not measured',
          )
          continue
        masked_cell = _mask_literals(cell)
        if row_idx > 0:
          for match in _BOLD.finditer(masked_cell):
            self._bold_characters += len(_clean_inline(match.group(1)))
        if _HERE_LINK.search(masked_cell):
          self._add(row_line, 'R19', 'link text does not describe the target')
        self._check_links_and_images(masked_cell, row_line)
        for match in _AI_UTM.finditer(masked_cell):
          self._add(
              row_line,
              'R31',
              f'AI-tool tracking parameter "{match.group(1)}": '
              'remove it from the link',
          )
        for match in _PLACEHOLDER.finditer(masked_cell):
          self._add(
              row_line,
              'R31',
              f'draft placeholder "{match.group(0)}": '
              'supply the fact or use [Open: question]',
          )
        cleaned_cell = _clean_inline(cell)
        self._characters += len(cleaned_cell)
        length = _count_words(cleaned_cell)
        if length > cell_limit:
          self._add(
              row_line,
              'R10',
              f'table cell of {length} words (limit {cell_limit}): '
              f'"{_excerpt(cell)}"',
          )
        self._check_words(cleaned_cell, row_line)
        pairs = [
            m.group(0)
            for m in _SLASH_PAIR.finditer(_RAW_URL.sub(' ', cleaned_cell))
            if m.group(0).lower() not in _SLASH_OK
        ]
        if len(pairs) > MAX_CELL_SLASH_PAIRS:
          self._add(
              row_line,
              'R26',
              f'{len(pairs)} groups of words with slashes in one cell '
              f'("{pairs[0]}", "{pairs[1]}"): write "and" or "or", or move '
              'the detail to the page of the item',
          )
    has_caption = (
        following is not None
        and following.kind == 'text'
        and _CAPTION.match(following.lines[0])
    )
    if not has_caption and not self._docs:
      self._add(block.line, 'R12', 'table without a caption in italics below')

  def _check_key_description_table(
      self,
      table_line: int,
      rows: list[tuple[int, list[str]]],
      columns: int,
  ) -> None:
    """Flags 2- or 3-col (optional ID, name, prose explanation) tables."""
    if columns not in (2, 3) or len(rows) < 3:
      return
    data_rows = [cells for _, cells in rows[1:] if len(cells) == columns]
    if len(data_rows) < 2:
      return
    if columns == 3:
      header_id = _clean_inline(rows[0][1][0]).strip()
      col0_cells = [_clean_inline(c[0]).strip() for c in data_rows]
      if any(_count_words(val) > 2 or len(val) > 12 for val in col0_cells):
        return
      if not (
          _ID_HEADER.match(header_id)
          or all(_ID_CELL.match(val) for val in col0_cells if val)
      ):
        return
    name_col = 0 if columns == 2 else 1
    if any(_count_words(_clean_inline(c[name_col])) > 8 for c in data_rows):
      return
    long_rows = 0
    for cells in data_rows:
      cleaned_desc = _clean_inline(cells[-1])
      words = _count_words(cleaned_desc)
      sents = len(_sentences(cleaned_desc))
      if words > MAX_CELL_WORDS or (sents >= 2 and words >= 12):
        long_rows += 1
    if long_rows * 2 >= len(data_rows):
      self._add(
          table_line,
          'R10',
          'table of (optional ID, item name, prose explanation): '
          'use a list or short sections instead',
      )

  def _check_section_density(self, blocks: list[Block]) -> None:
    """Checks leaf heading-to-body ratio and majority-short sibling sections."""
    headings = [(idx, b) for idx, b in enumerate(blocks) if b.kind == 'heading']
    parent_stack: list[tuple[int, int]] = []
    sibling_groups: dict[tuple[int, int], list[tuple[int, bool]]] = {}
    for i, (pos, hb) in enumerate(headings):
      while parent_stack and parent_stack[-1][1] >= hb.size:
        parent_stack.pop()
      parent_pos = parent_stack[-1][0] if parent_stack else -1
      parent_stack.append((pos, hb.size))
      if hb.size < 2:
        continue
      next_pos = headings[i + 1][0] if i + 1 < len(headings) else len(blocks)
      has_child = i + 1 < len(headings) and headings[i + 1][1].size > hb.size
      if has_child:
        continue
      sec_blocks = blocks[pos + 1 : next_pos]
      first_txt = (
          _clean_inline('\n'.join(sec_blocks[0].lines)).strip()
          if sec_blocks and sec_blocks[0].kind == 'text'
          else ''
      )
      sents = sum(
          len(_sentences(_clean_inline('\n'.join(b.lines))))
          for b in sec_blocks
          if b.kind in ('text', 'item')
      )
      if sents <= 2 and _NOT_APPLICABLE.match(first_txt):
        continue
      h_words = _count_words(_clean_inline(hb.lines[0]).strip())
      c_words = sum(
          _count_words(_clean_inline('\n'.join(b.lines))) for b in sec_blocks
      )
      if h_words > 0 and c_words < MIN_BODY_TO_HEADING_RATIO * h_words:
        self._add(
            hb.line,
            'R1',
            f'section heading ({h_words} words) is less than '
            f'{MIN_BODY_TO_HEADING_RATIO} times shorter than its '
            f'{c_words}-word body: use a list or merge into parent',
        )
      has_struct = any(
          b.kind in ('table', 'code') or _IMAGE.search('\n'.join(b.lines))
          for b in sec_blocks
      )
      list_items = sum(1 for b in sec_blocks if b.kind == 'item')
      is_brief = not has_struct and list_items < 3 and sents <= 2
      sibling_groups.setdefault((parent_pos, hb.size), []).append(
          (hb.line, is_brief)
      )
    for group in sibling_groups.values():
      if len(group) < 3:
        continue
      brief_lines = [line for line, brief in group if brief]
      if len(brief_lines) * 2 > len(group):
        self._add(
            brief_lines[0],
            'R1',
            f'{len(brief_lines)} of {len(group)} sibling sections have at most '
            '2 sentences: use a list instead of short sections',
        )

  def _check_code(
      self,
      block: Block,
      previous: Block | None,
      before_previous: Block | None = None,
  ) -> None:
    """Checks one fenced code block for framing, size, and Docs safety."""
    if block.unclosed:
      self._add(block.line, 'R19', 'unclosed fenced code block')
    if (
        previous is None
        or previous.kind in ('heading', 'table', 'code')
        or _is_block_caption(previous, before_previous)
    ):
      self._add(
          block.line, 'R12', 'code block without an introductory sentence above'
      )
    lang = block.info.split()[0].lower() if block.info else ''
    is_diagram = lang in _DIAGRAM_CODE_LANGS
    if (
        block.size > MAX_CODE_LINES
        and not self._appendix_level
        and not is_diagram
    ):
      self._add(
          block.line,
          'R3',
          f'code block of {block.size} lines '
          f'(limit {MAX_CODE_LINES}): move it to an appendix',
      )
    if not lang:
      self._add(
          block.line,
          'R19',
          'code block without a language tag (for example "go", "rust", "sh")',
      )
    if block.size == 0:
      self._add(block.line, 'R19', 'empty code block')
      return
    non_comment = [
        ln.strip()
        for ln in block.lines
        if ln.strip() and not ln.strip().startswith('#')
    ]
    if (
        lang in _SHELL_LANGS
        and non_comment
        and all(_SHELL_PROMPT.match(ln) for ln in non_comment)
    ):
      self._add(
          block.line + 1,
          'R19',
          'shell prompt "$" in command block: omit "$" so readers can copy it',
      )
    reported_tab = False
    reported_smart = False
    for offset, code_line in enumerate(block.lines):
      line_number = block.line + 1 + offset
      if (
          not reported_tab
          and '\t' in code_line
          and lang not in _TAB_OK_LANGS
      ):
        self._add(
            line_number,
            'R19',
            'tab character in code block: indent with spaces for Google Docs',
        )
        reported_tab = True
      if (
          not reported_smart
          and lang not in _PROSE_CODE_LANGS
          and _SMART_CODE_CHARS.search(code_line)
      ):
        self._add(
            line_number,
            'R19',
            'typographic quote, dash, or ellipsis in code block: '
            'use straight ASCII characters',
        )
        reported_smart = True
      width = len(code_line.expandtabs(4))
      if width > MAX_CODE_WIDTH and not is_diagram:
        self._add(
            line_number,
            'R19',
            f'code line of {width} characters (limit {MAX_CODE_WIDTH}): '
            'wrap at 72 to 80 characters for Google Docs',
        )

  def _check_heading(self, block: Block) -> None:
    """Checks one heading and closes the preceding section."""
    self._close_section()
    self._section_line = block.line
    title = _clean_inline(block.lines[0]).strip()
    if self._appendix_level and block.size <= self._appendix_level:
      self._appendix_level = 0
    if _APPENDIX_TITLE.match(title) and not self._appendix_level:
      self._appendix_level = block.size
    if (
        self._previous_heading_level
        and block.size > self._previous_heading_level + 1
    ):
      self._add(
          block.line,
          'R17',
          f'heading level skips from {self._previous_heading_level} '
          f'to {block.size}',
      )
    self._previous_heading_level = block.size
    if block.size > MAX_HEADING_LEVEL:
      self._add(
          block.line,
          'R17',
          f'heading level {block.size} (limit {MAX_HEADING_LEVEL})',
      )
    if title.endswith(':'):
      self._add(block.line, 'R17', 'heading that ends with a colon')
    bare_title = _HEADING_ID.sub('', title)
    letters = [c for c in bare_title if c.isalpha()]
    alpha_words = [
        w for w in bare_title.split() if any(c.isalpha() for c in w)
    ]
    is_shout = (
        len(letters) > 3
        and all(c.isupper() for c in letters)
        and (
            len(alpha_words) >= 2
            or len(letters) > 6
            or bare_title.upper() in SHOUT_WORDS
        )
    )
    if is_shout:
      self._add(block.line, 'R20', 'heading in capital letters')
    if _HEADING_SYMBOL.search(bare_title):
      self._add(
          block.line,
          'R17',
          'dash or "&" in a heading: write a short topic label',
      )
    later = [w.strip('()[],.:') for w in alpha_words[1:] if w != 'CODE']
    # An acronym or a name such as "GitHub" does not show the case style.
    later = [
        w for w in later
        if len(w) >= 3 and not w.isupper() and w[1:] == w[1:].lower()
    ]
    if later and not is_shout:
      capitals = sum(1 for w in later if w[0].isupper())
      title_case = capitals >= 0.8 * len(later)
      self._heading_cases.append(
          (block.line, title_case, title_case and capitals >= 3)
      )

  def _close_section(self) -> None:
    if self._section_words > MAX_SECTION_WORDS:
      self._add(
          self._section_line,
          'R1',
          f'section of {self._section_words} words (limit {MAX_SECTION_WORDS})',
      )
    self._section_words = 0

  def _close_lists(self, deeper_than: int = -1) -> None:
    for indent in [i for i in self._list_runs if i > deeper_than]:
      line, items, _ = self._list_runs.pop(indent)
      if items > MAX_LIST_ITEMS:
        self._add(line, 'R9', f'list of {items} items (limit {MAX_LIST_ITEMS})')

  def run(self, text: str) -> None:
    """Checks one document."""
    self._self_anchors = _document_anchors(text)
    blocks = parse_blocks(text.splitlines())
    self._normative_style = _detect_normative_style(blocks)
    if (
        len(blocks) > 1
        and (
            (blocks[0].kind == 'heading' and blocks[0].size == 1)
            or (
                blocks[0].kind == 'text'
                and len(blocks[0].lines) == 1
                and not blocks[0]
                .lines[0]
                .rstrip()
                .endswith(('.', '!', '?', ':'))
            )
        )
        and blocks[1].kind == 'heading'
        and not _SUMMARY_TITLE.search(blocks[1].lines[0])
    ):
      self._add(
          blocks[1].line,
          'R2',
          'no opening summary between the title and the first section',
      )
    for position, block in enumerate(blocks):
      if block.kind == 'item':
        self._close_lists(deeper_than=block.indent)
        run = self._list_runs.get(block.indent)
        if run and run[2] != block.ordered:
          self._close_lists(deeper_than=block.indent - 1)
          run = None
        if run is None:
          run = self._list_runs[block.indent] = [block.line, 0, block.ordered]
        run[1] += 1
      elif not (block.kind in ('text', 'code', 'table') and block.indent > 0):
        self._close_lists()
      if block.kind == 'heading':
        self._prev_was_callout = False
        self._check_heading(block)
      elif block.kind == 'code':
        self._prev_was_callout = False
        previous = blocks[position - 1] if position > 0 else None
        before_prev = blocks[position - 2] if position > 1 else None
        self._check_code(block, previous, before_prev)
      elif block.kind == 'table':
        self._prev_was_callout = False
        previous = blocks[position - 1] if position > 0 else None
        before_prev = blocks[position - 2] if position > 1 else None
        following = blocks[position + 1] if position + 1 < len(blocks) else None
        self._check_table(block, previous, following, before_prev)
      elif block.kind == 'text' and not self._list_runs and block.indent >= 4:
        self._add(
            block.line,
            'R19',
            'indented code block: use triple backticks with a language tag',
        )
      else:
        self._check_prose(block)
    self._close_lists()
    self._close_section()
    self._check_section_density(blocks)
    passive = len(self._passive_lines)
    if (
        passive >= MIN_PASSIVE_SENTENCES
        and passive > MAX_PASSIVE_SHARE * self._sentences
    ):
      lines = ', '.join(str(n) for n in self._passive_lines[:8])
      more = ', ...' if passive > 8 else ''
      self._add(
          1,
          'R14',
          f'{passive} of {self._sentences} sentences are passive (limit '
          f'{round(100 * MAX_PASSIVE_SHARE)}%): name the actor and use the '
          f'active voice. Lines: {lines}{more}',
      )
    weak = sum(1 for _, title_case, _ in self._heading_cases if title_case)
    by_style = weak >= 3 and weak >= 0.6 * len(self._heading_cases)
    for line, title_case, strong in self._heading_cases:
      if strong or (title_case and by_style):
        self._add(line, 'R17', 'heading in title case: use sentence case')
    if (
        self._characters
        and self._bold_characters / self._characters > MAX_BOLD_SHARE
    ):
      share = round(100 * self._bold_characters / self._characters)
      self._add(
          1,
          'R18',
          f'{share}% of the text is bold '
          f'(limit {round(100 * MAX_BOLD_SHARE)}%)',
      )
    allowed = max(1, math.ceil(self.words / WORDS_ON_A_PAGE))
    if self._callouts > allowed:
      self._add(
          1,
          'R20',
          f'{self._callouts} callouts (limit one on a page, '
          f'{allowed} for this length)',
      )
    self.findings.sort(
        key=lambda f: (
            f.line,
            f.advisory,
            int(f.rule[1:]) if f.rule[1:].isdigit() else 0,
            f.rule,
            f.message,
        )
    )


def _detect_normative_style(blocks: list[Block]) -> str:
  """Returns 'upper', 'lower', or '' if a spec declares normative keywords."""
  non_code = [b for b in blocks if b.kind != 'code']
  for idx, block in enumerate(non_code):
    if block.kind == 'heading':
      title = _clean_inline(block.lines[0]).strip()
      if not _NORMATIVE_HEADING.match(title) or idx + 1 >= len(non_code):
        continue
      window = ' '.join(' '.join(non_code[idx + 1].lines).split())
    else:
      window = ' '.join(' '.join(block.lines).split())
      if not (
          _NORMATIVE_LEAD.match(window)
          or (
              _NORMATIVE_SCOPE.search(window) and _NORMATIVE_DECL.search(window)
          )
      ):
        continue
    has_upper = bool(re.search(r'\b(?:MUST|SHOULD)\b', window))
    has_lower = bool(
        re.search(r'\blowercase\b', window, re.IGNORECASE)
        or (
            re.search(r'\bmust\b', window)
            and re.search(r'\b(?:should|may)\b', window)
            and not has_upper
        )
    )
    if has_lower:
      return 'lower'
    return 'upper'
  return ''


def lint(
    text: str,
    base_dir: pathlib.Path | None = None,
    profile: str = 'decision',
) -> tuple[list[Finding], int]:
  """Returns the findings and the number of prose words of a document."""
  linter = _Linter(base_dir=base_dir, profile=profile)
  linter.run(text)
  return linter.findings, linter.words


def _normalize_url(url: str) -> str:
  """Strips AI-referrer tracking query parameters from a URL."""
  q_pos = url.find('?')
  if q_pos == -1:
    return url
  frag_pos = url.find('#')
  if frag_pos != -1 and frag_pos < q_pos:
    return url
  q_end = len(url) if frag_pos == -1 else frag_pos
  params = [
      p
      for p in url[q_pos + 1 : q_end].split('&')
      if p and not _AI_UTM_PARAM.match(p)
  ]
  suffix = url[q_end:]
  if not params:
    return url[:q_pos] + suffix
  return f'{url[:q_pos]}?{"&".join(params)}{suffix}'


def _normalize_code_block(block: Block) -> tuple[str, ...]:
  """Normalizes allowed Revise-mode character fixes inside a code block."""
  lang = block.info.split()[0].lower() if block.info else ''
  out: list[str] = []
  for raw_line in block.lines:
    fixed = raw_line.translate(_SMART_QUOTE_MAP)
    if lang not in _TAB_OK_LANGS:
      fixed = fixed.expandtabs(2)
    stripped = ' '.join(fixed.split())
    if stripped:
      out.append(stripped)
  return tuple(out)


def _split_code_and_prose(blocks: list[Block]) -> tuple[list[Block], str]:
  """Separates code blocks (including top-level indent>=4) from prose text."""
  codes: list[Block] = []
  prose_parts: list[str] = []
  in_list = False
  prev_was_indented_code = False
  for block in blocks:
    if block.kind == 'item':
      in_list = True
    elif not (block.kind in ('text', 'code', 'table') and block.indent > 0):
      in_list = False
    if block.kind == 'code':
      codes.append(block)
      prev_was_indented_code = False
    elif block.kind == 'text' and not in_list and block.indent >= 4:
      if prev_was_indented_code and codes:
        codes[-1] = Block(
            'code',
            codes[-1].line,
            [*codes[-1].lines, '', *block.lines],
            indent=codes[-1].indent,
        )
      else:
        codes.append(
            Block('code', block.line, list(block.lines), indent=block.indent)
        )
      prev_was_indented_code = True
    else:
      prose_parts.append(_OPEN_ITEM.sub(' ', '\n'.join(block.lines)))
      prev_was_indented_code = False
  return codes, '\n'.join(prose_parts)


def _prose_without_code(blocks: list[Block]) -> str:
  """Returns non-code blocks joined with open-item markers removed."""
  _, prose = _split_code_and_prose(blocks)
  return prose


def _extract_numbers(prose_no_inline_code: str) -> collections.Counter[str]:
  """Extracts normalized numbers and number words 2..10 from prose."""
  masked = _STRUCTURAL_NUM.sub(' ', prose_no_inline_code)
  counts: collections.Counter[str] = collections.Counter()
  for match in _NUMBER_TOKEN.finditer(masked):
    tok = match.group(0).replace(',', '').replace(' ', '')
    pct = '%' if tok.endswith('%') else ''
    core = tok[:-1] if pct else tok
    if '.' in core:
      whole, frac = core.split('.', 1)
      norm = f"{whole.lstrip('0') or '0'}.{frac}{pct}"
    else:
      norm = f"{core.lstrip('0') or '0'}{pct}"
    counts[norm] += 1
  for match in _NUMBER_WORD_RE.finditer(masked):
    counts[_NUMBER_WORDS[match.group(1).lower()]] += 1
  return counts


def compare_documents(
    original: str, revised: str, allow_restructure: bool = False
) -> list[Finding]:
  """Checks Revise-mode preservation limits between original and revised."""
  orig_blocks = parse_blocks(original.splitlines())
  rev_blocks = parse_blocks(revised.splitlines())
  findings: list[Finding] = []

  if not allow_restructure:
    orig_headings = [
        (
            b.size,
            _clean_inline(b.lines[0]).strip().rstrip(':').strip().lower(),
            b.lines[0].strip(),
        )
        for b in orig_blocks
        if b.kind == 'heading'
    ]
    rev_headings = [
        (b.size, _clean_inline(b.lines[0]).strip().rstrip(':').strip().lower())
        for b in rev_blocks
        if b.kind == 'heading'
    ]
    cursor = 0
    for level, norm_title, raw_title in orig_headings:
      matched = False
      while cursor < len(rev_headings):
        rev_level, rev_title = rev_headings[cursor]
        cursor += 1
        if rev_level == level and rev_title == norm_title:
          matched = True
          break
      if not matched:
        findings.append(
            Finding(
                1,
                'L-HEAD',
                f'original heading "{raw_title}" removed or reordered '
                '(keep existing headings unless restructuring was requested, '
                'then pass --allow-restructure)',
            )
        )

  orig_codes, orig_prose = _split_code_and_prose(orig_blocks)
  rev_codes, rev_prose = _split_code_and_prose(rev_blocks)
  if len(orig_codes) != len(rev_codes):
    findings.append(
        Finding(
            1,
            'L-CODE',
            f'code block count changed from {len(orig_codes)} to '
            f'{len(rev_codes)}',
        )
    )
  elif allow_restructure:
    orig_norm = collections.Counter(
        _normalize_code_block(b) for b in orig_codes
    )
    rev_norm = collections.Counter(_normalize_code_block(b) for b in rev_codes)
    if orig_norm != rev_norm:
      for rev_code in rev_codes:
        norm = _normalize_code_block(rev_code)
        if orig_norm[norm] > 0:
          orig_norm[norm] -= 1
        else:
          findings.append(
              Finding(
                  rev_code.line,
                  'L-CODE',
                  'code block content changed in Revise mode',
              )
          )
  else:
    for orig_code, rev_code in zip(orig_codes, rev_codes):
      if _normalize_code_block(orig_code) != _normalize_code_block(rev_code):
        findings.append(
            Finding(
                rev_code.line,
                'L-CODE',
                'code block content changed in Revise mode',
            )
        )

  orig_ids = {
      m.group(0).strip('`').strip() for m in _INLINE_CODE.finditer(orig_prose)
  }
  rev_ids = {
      m.group(0).strip('`').strip() for m in _INLINE_CODE.finditer(rev_prose)
  }
  for missing_id in sorted(orig_ids - rev_ids):
    findings.append(
        Finding(
            1,
            'L-ID',
            f'inline code identifier `{missing_id}` missing from revised text',
        )
    )

  orig_no_code = _INLINE_CODE.sub(' ', _COMMENT.sub(' ', orig_prose))
  rev_no_code = _INLINE_CODE.sub(' ', _COMMENT.sub(' ', rev_prose))

  orig_unlinked = _LINK_TARGET.sub(' ', orig_no_code)
  rev_unlinked = _LINK_TARGET.sub(' ', rev_no_code)
  orig_urls = {
      _normalize_url(u)
      for u in (
          [m.group(1) for m in _LINK_TARGET.finditer(orig_no_code)]
          + [m.group(0) for m in _RAW_URL.finditer(orig_unlinked)]
      )
  }
  rev_urls = {
      _normalize_url(u)
      for u in (
          [m.group(1) for m in _LINK_TARGET.finditer(rev_no_code)]
          + [m.group(0) for m in _RAW_URL.finditer(rev_unlinked)]
      )
  }
  for missing_url in sorted(orig_urls - rev_urls):
    findings.append(
        Finding(1, 'L-LINK', f'link target "{missing_url}" missing in revision')
    )

  orig_text_only = _RAW_URL.sub(' ', orig_unlinked)
  rev_text_only = _RAW_URL.sub(' ', rev_unlinked)
  orig_nums = _extract_numbers(orig_text_only)
  rev_nums = _extract_numbers(rev_text_only)
  for num_tok in sorted(orig_nums):
    if rev_nums[num_tok] == 0:
      findings.append(
          Finding(
              1,
              'L-NUM',
              f'number "{num_tok}" from original missing in revised text',
          )
      )
  for num_tok in sorted(rev_nums):
    if orig_nums[num_tok] == 0:
      findings.append(
          Finding(
              1,
              'L-NUM',
              f'new number "{num_tok}" in revised text (verify not invented)',
          )
      )
  return findings


def _print_words() -> None:
  for rule, forms, advice in WORDS:
    print(f'{rule}\t{forms.replace("|", ", ")}\t{advice}')
  for rule, pattern, advice in PATTERN_NOTES:
    print(f'{rule}\t{pattern}\t{advice}')


def _read_input(path: str) -> tuple[str, str]:
  if path == '-':
    return '<stdin>', sys.stdin.read()
  with open(path, encoding='utf-8') as handle:
    return path, handle.read()


def _report(
    label: str, findings: list[Finding], words: int, strict: bool
) -> int:
  """Prints the findings and the summary line. Returns the exit status."""
  for finding in findings:
    tag = f'{finding.rule} (advisory)' if finding.advisory else finding.rule
    print(f'{label}:{finding.line}: {tag}: {finding.message}')
  open_items = sum(1 for f in findings if f.rule == 'OPEN')
  advisories = sum(1 for f in findings if f.advisory)
  count = len(findings) - open_items - advisories
  noun = 'finding' if count == 1 else 'findings'
  item_noun = 'open item' if open_items == 1 else 'open items'
  extra = ''
  if advisories:
    adv_noun = 'advisory' if advisories == 1 else 'advisories'
    extra = f', {advisories} {adv_noun}'
  print(
      f'{label}: {count} {noun}{extra}, {open_items} {item_noun}, {words} words'
  )
  return 1 if count or (strict and (open_items or advisories)) else 0


def _link_base(path: str, link_root: str | None) -> pathlib.Path | None:
  if link_root:
    return pathlib.Path(link_root).resolve()
  return None if path == '-' else pathlib.Path(path).resolve().parent


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(
      description='Checks Markdown documents against measurable writing rules.'
  )
  parser.add_argument(
      'files', nargs='*', help='Markdown files to check, or "-" for stdin'
  )
  parser.add_argument(
      '--compare',
      nargs=2,
      metavar=('ORIGINAL', 'REVISED'),
      help='check Revise-mode preservation limits and lint REVISED',
  )
  parser.add_argument(
      '--profile',
      choices=('decision', 'docs'),
      default='decision',
      help='rule set: "decision" for design documents and proposals (default),'
      ' "docs" for developer and operator documentation',
  )
  parser.add_argument(
      '--link-root',
      metavar='DIR',
      help='directory that relative links start from (default: the directory'
      ' of the checked file)',
  )
  parser.add_argument(
      '--allow-restructure',
      action='store_true',
      help=(
          'with --compare, allow requested heading and section-order'
          ' restructuring while still checking code blocks, identifiers, links,'
          ' and numbers'
      ),
  )
  parser.add_argument(
      '--strict',
      action='store_true',
      help='count open items as findings for the exit status',
  )
  parser.add_argument(
      '--words',
      action='store_true',
      help='print the word list with the advice and stop',
  )
  args = parser.parse_args(argv)
  if args.words:
    _print_words()
    return 0
  if args.allow_restructure and not args.compare:
    parser.error('--allow-restructure requires --compare')
  if args.compare:
    if args.files:
      parser.error('do not combine positional files with --compare')
    orig_arg, rev_arg = args.compare
    if orig_arg == '-' and rev_arg == '-':
      parser.error('at most one of ORIGINAL and REVISED can be "-"')
    try:
      _, orig_text = _read_input(orig_arg)
      rev_label, rev_text = _read_input(rev_arg)
    except OSError as error:
      print(f'cannot read input file: {error}', file=sys.stderr)
      return 2
    pres_findings = compare_documents(
        orig_text, rev_text, allow_restructure=args.allow_restructure
    )
    lint_findings, words = lint(
        rev_text, _link_base(rev_arg, args.link_root), args.profile
    )
    return _report(rev_label, pres_findings + lint_findings, words, args.strict)
  if not args.files:
    parser.error('give one or more files, "-" for stdin, --compare, or --words')
  status = 0
  for path in args.files:
    try:
      label, text = _read_input(path)
    except OSError as error:
      print(f'{path}: cannot read the file: {error}', file=sys.stderr)
      status = 2
      continue
    findings, words = lint(text, _link_base(path, args.link_root), args.profile)
    status = max(status, _report(label, findings, words, args.strict))
  return status


if __name__ == '__main__':
  sys.exit(main())
