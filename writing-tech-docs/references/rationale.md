# Rationale and evidence for the rules

Each rule in `writing-tech-docs` removes a measured or observed reader cost.
Consult this reference when an author disputes a rule or asks for primary
citations. Sources carry 4 labels: **Experiment** (controlled study), **Field
study** (workplace data or survey), **Argument** (expert analysis), or
**Practice** (style standard).

## Structure

-   **R1**, page-sized sections: Page-sized units build a stronger mental map
    and surface more structural defects than unbroken scrolling, within working
    memory's 4-item limit. Sources: Piolat, Roussey, and Thunin 1997
    (experiment). Cowan 2001 (review of experiments).
-   **R2**, answer first: Opening with the main point raises paragraph recall,
    and screen readers scan headings and opening lines before deciding to read
    further. Sources: Kieras 1978 (experiment). Nielsen Norman Group
    eye-tracking (field study).
-   **R3**, purpose, direction, then detail: Context before detail doubled
    recall, task-first manuals cut errors, and unlayered newcomer detail slows
    experts. Sources: Bransford and Johnson 1972, Carroll and others 1987
    (experiments). Luiten, Ames, and Ackerson 1980, Kalyuga and others 2003
    (reviews).
-   **R4**, one home for each item (DRY): Duplicated claims drift out of sync
    and erode engineer trust. Pairing an opaque ID with a short plain slug
    preserves information scent without split-attention jumps. Sources: Forward
    and Lethbridge 2002, Aghajani and others 2019 (field studies). Pirolli and
    Card 1999 (model). Schroeder and Cenkci 2018 (review).

## Selection of information

-   **R5**, exact contracts and worked examples: Incomplete error and boundary
    contracts are top developer blockers, while compact worked examples cut
    integration errors. Sources: Uddin and Robillard 2015, Aghajani and others
    2019 (field studies). Meng, Steinhardt, and Schubert 2020, Barbieri and
    others 2023 (experiment and review). Meyer 1992 (argument).
-   **R6**, cut low-signal text: Seductive or tangential details lower retention
    and transfer of the core causal argument. Sources: Harp and Mayer 1998
    (experiment). Rey 2012, Sundararajan and Adesope 2020 (reviews).
-   **R7**, problem without the solution: Solution examples in problem briefs
    trigger design fixation, and solution-first framing failed in half of 400
    organizational decisions. Sources: Jansson and Smith 1991 (experiments).
    Nutt 2008 (field study).
-   **R8**, status of each claim: Reviewers need claim provenance to spot
    defects, and even experts fail to notice omitted branches unless gaps are
    surfaced. Sources: Bacchelli and Bird 2013 (field study). Fischhoff, Slovic,
    and Lichtenstein 1978 (experiment).

## Lists, tables, diagrams, and code blocks

-   **R9**, lists for parallel items: Scannable vertical formatting improved
    measured usability by 47%. Source: Morkes and Nielsen 1997 (experiment).
-   **R10**, tables for conditions and comparisons: Readers evaluate branching
    conditions and 2-to-3-digit column numbers with fewer errors in tables than
    in prose. Sources: Wright and Reid 1973, Huysmans and others 2011
    (experiments). Ehrenberg 1977, Vessey 1991 (reviews).
-   **R11**, diagrams from source code (`tech-docs-diagrams`, D1 to D11): Any
    graphic increases liking, whereas only instructive 2D topology within
    crossing, degree, and memory limits improves comprehension. Sources: Larkin
    and Simon 1987, Sung and Mayer 2012, Ware and others 2002, Huang, Eades, and
    Hong 2014 (experiments). Okabe and Ito 2008, Moody 2009 (guidelines and
    argument).
-   **R12**, a frame for each block: Unframed blocks impose split-attention
    search costs, whereas lead-ins and takeaway captions anchor scanning.
    Sources: Chandler and Sweller 1991 (experiments). Schroeder and Cenkci 2018,
    Lorch 1989 (reviews).

## Sentences and paragraphs

-   **R13**, one claim in each sentence: Long multi-clause sentences strain
    working memory, and omitting "that" or repeated nouns causes garden-path
    regressions. Sources: Cowan 2001 (review). Garnsey and others 1997, Britton
    and Gülgöz 1991 (experiments).
-   **R14**, active voice, literal verb: Agentless passives hide obligation
    owners, noncanonical passives and nominalizations increase misparsing, and
    out-of-order temporal clauses raise working-memory load within 300 ms.
    Sources: Ferreira 2003, Charrow and Charrow 1979, Münte, Schiltz, and Kutas
    1998 (experiments). Femmer and others 2017, Frattini and others 2024 (field
    studies).
-   **R15**, plain words before code names: Plain behavior before code symbols
    cuts comprehension errors. Sources: Meng, Steinhardt, and Schubert 2020,
    Lawrie and others 2006 (experiments). Bacchelli and Bird 2013 (field study).
-   **R16**, numbers, not praise: Replacing promotional adjectives with neutral
    measurable facts improved usability by 27%. Source: Morkes and Nielsen 1997
    (experiment).

## Typography

-   **R17**, predictable headings: Literal topic headings with high information
    scent prevent wrong-branch navigation detours. Sources: Pirolli and Card
    1999 (model). Blackmon and others 2002 (experiment).
-   **R18**, bold for structure only: Selective structural bolding aids
    retention and scanning, whereas excessive highlighting depresses attention
    to unbolded caveats. Sources: Schneider and others 2018 (review). Lorch,
    Lorch, and Klusewitz 1995, Yue and others 2015 (experiments).
-   **R19**, one role for each style: Consistent styles let readers spot code
    and links pre-attentively. Markdown-backed code blocks prevent tab and
    smart-quote corruption in Google Docs. Source: practice.
-   **R20**, a calm page and readable body size: `ALL CAPS` and sub-10 pt fonts
    slow reading. Repeated callouts habituate attention, dropping warning
    compliance from 76% to 55%. Sources: Arditi and Cho 2007, Vance and others
    2018 (experiments). Wogalter, Conzola, and Smith-Jackson 2002 (review).

## Verifiable claims

-   **R21**, depth by cost of reversal: Higher review rates per hour catch fewer
    defects per page, so low-risk detail steals reviewer attention from
    irreversible decisions. Sources: Kemerer and Paulk 2009 (field study). Boehm
    1988 (argument).
-   **R22**, named, enforced, tested claims: Requirement traceability links sped
    up maintenance tasks by 24% with 50% fewer errors, and structured claim
    templates reduced ambiguity. Sources: Mäder and Egyed 2015 (experiment).
    Mavin and others 2009 (case study).

## Coverage and decisions

-   **R23**, stated coverage and stated negatives: Even domain experts overlook
    omitted fault-tree branches unless failure modes are enumerated explicitly.
    Sources: Fischhoff, Slovic, and Lichtenstein 1978, Porter, Votta, and Basili
    1995 (experiments).
-   **R24**, factual, unbiased comparisons: Recording trade-offs across complete
    competing criteria counters confirmation bias during design review. Sources:
    Tang and others 2006 (survey). Parnas and Clements 1986 (argument).
    Nickerson 1998 (review).

## Plain English for international readers

-   **R25 to R28:** Controlled vocabulary (ASD-STE100), disambiguated homonym
    jargon, conditional imperatives in place of ambiguous modals, and explicit
    quantifiers raise comprehension for non-native readers. Formal and
    semi-formal specs retain defined normative keywords (RFC 2119, uppercase or
    declared lowercase), and "might" marks unverified R8 possibilities. Sources:
    Shubert and others 1995, Britton and Gülgöz 1991, Sherman 1976
    (experiments). Berry, Kamsties, and Krieger 2003, Femmer and others 2017
    (field studies).

## Grounded, non-synthetic prose

-   **R29**, system-specific text only: Generic boilerplate adds reading cost
    without narrowing the design space, and specifications document target
    behavior rather than commit history. Sources: Harp and Mayer 1998
    (experiment). Forward and Lethbridge 2002 (field study).
-   **R30**, direct statements, not stagecraft: Concrete consequences carry
    weight without rhetorical announcements or sentence-initial adverbs
    ("Notably") overrepresented in machine prose. Sources: Morkes and Nielsen
    1997 (experiment). Brown and others 2024 (field study).
-   **R31**, named sources and bounded scope: Statistical AI-text detectors
    misclassified over 60% of non-native English writing. Verification checks
    primary citations and target-system bounds rather than authorship guesses.
    Source: Liang and others 2023 (experiment).
-   **R32**, plain copulas and literal modifiers: Plain verbs and literal
    modifiers prevent dictionary and machine-translation category errors.
    Source: ASD-STE100 practice.

## Limits of the evidence

-   **Populations:** Many controlled reading studies tested students or general
    readers rather than staff engineers reviewing distributed-system specs.
-   **Thresholds:** Empirical results establish the direction of each rule,
    while exact caps (25 words, 5 columns, 9 boxes, 400 words) are practical
    engineering cutoffs. Read primary papers directly before citing them in
    external publications.
