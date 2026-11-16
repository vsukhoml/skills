# Rationale and evidence for the rules

Each rule removes a specific cost for the reader. This file gives the reason for
each rule and names the source by author and year. Read this file if an author
disputes a rule or if two rules conflict.

The sources do not have equal strength. Each source below has one of these 4
labels:

-   **Experiment:** A controlled study that measured readers or developers.
-   **Field study:** A survey or a measurement of engineers at work.
-   **Argument:** A paper by experts that has no measurement.
-   **Practice:** A rule from a writing standard or a style guide.

## Structure

-   **R1**, page-sized sections: Readers of page-sized units build a mental map
    of the document. They find more defects of structure than readers who
    scroll. Working memory holds about 4 items. Sources: Piolat, Roussey, and
    Thunin 1997 (experiment). Cowan 2001 (review of experiments).
-   **R2**, answer first: Readers understand and remember a paragraph better if
    the main point comes first. Readers on a screen read the start of a page and
    scan the rest. Sources: Kieras 1978 (experiment). Eye-tracking studies of
    the Nielsen Norman Group (field study).
-   **R3**, purpose, direction, then detail: A reader who knows the goal and the
    direction can give each detail a place. That reader can also stop at the
    first layer that has a defect. The sources for this order are practice:
    Slatton, "How to write a good design document", and the reader comments on
    that article. No experiment is cited. The template "ml-design-docs" of Yan
    uses the same order: overview, motivation and requirements, method,
    implementation, appendix. Detail that helps a newcomer reduces the accuracy
    of an expert, because the expert must compare it with known facts. Source:
    Kalyuga and others 2003 (review of experiments).
-   **R4**, one home for each fact: Engineers stop trusting a document that is
    out of date or that contradicts itself. A fact in two places changes in only
    one place. Sources: Forward and Lethbridge 2002, Aghajani and others 2019
    (field studies).

## Selection of information

-   **R5**, exact contracts: Studies of documentation defects list incomplete
    content as a main type, for example missing preconditions, error behavior,
    and limits. Sources: Aghajani and others 2019 (field study). Meyer 1992
    (argument) for the two sides of a contract.
-   **R6**, cut low-signal text: Interesting details that the reader does not
    need reduce the understanding of the main chain of reasons. Source: Harp and
    Mayer 1998 (experiment).
-   **R7**, problem without the solution: A problem that is stated as a missing
    solution hides the cheaper alternatives. Source: design practice. No
    experiment is cited.
-   **R8**, status of each claim: Reviewers need the status and the reason of a
    claim to find defects. Readers do not notice an omitted item. Sources:
    Bacchelli and Bird 2013 (field study of code review). Fischhoff, Slovic, and
    Lichtenstein 1978 (experiment).

## Lists, tables, diagrams, and code blocks

-   **R9**, lists for parallel items: A layout that readers can scan improved
    measured usability by 47%. Source: Morkes and Nielsen 1997 (experiment).
-   **R10**, tables for conditions and comparisons: Readers answer questions
    about conditional rules with fewer errors from a table than from prose.
    Sources: Wright and Reid 1973 (experiment). Vessey 1991 (review) for exact
    values.
-   **R11**, diagrams for topology and flow: A diagram helps only if position in
    the diagram matches the structure of the system. A diagram with mixed
    meanings can mislead. Sources: Larkin and Simon 1987 (argument). Petre 1995
    and Scanniello and others 2014 (experiments). Moody 2009 (argument) for one
    meaning of each symbol.
-   **R12**, a frame for each block: A figure or a code block that is far from
    its text costs the reader working memory. A lead-in
    sentence and a caption give the role and the result to a reader who scans.
    Sources: Chandler and Sweller 1991 (experiments). Lorch 1989 (review).

## Sentences and paragraphs

-   **R13**, one claim in each sentence: A long sentence makes the reader hold
    open clauses in working memory. The limit of 25 words comes from standards
    for technical manuals. Sources: Cowan 2001 (review). Practice for the
    number.
-   **R14**, active voice, literal verb: A sentence without an actor does not
    say which component has the obligation. Source: practice. No experiment is
    cited.
-   **R15**, plain words before code names: A reviewer who does not know the
    code must stop to find each code name. Source: Bacchelli and Bird 2013
    (field study, indirect).
-   **R16**, numbers, not praise: Neutral statements in place of praise improved
    measured usability by 27%. Source: Morkes and Nielsen 1997 (experiment).

## Typography

-   **R17**, predictable headings: Clear headings let a reader scan from heading
    to heading and read only the necessary sections. Source: eye-tracking
    studies of the Nielsen Norman Group (field study).
-   **R18**, bold for structure only: A small number of bold cues reduces the
    search time. Many cues reduce the attention to the text without cues.
    Sources: Lorch, Lorch, and Klusewitz 1995 (experiment). Lorch 1989 (review).
    Yue and others 2015 (experiment).
-   **R19**, one role for each style: A style with one meaning lets the reader
    recognize code and links before reading them. In Google Docs, tab characters
    jump to 12.7 mm stops and smart quotes corrupt syntax. At 10 pt, code lines
    wider than 72 characters wrap on Letter and A4 pages. Source: practice and
    renderer measurement.
-   **R20**, a calm page: People read text in capital letters more slowly at a
    normal text size. Source: Arditi and Cho 2007 (experiment).

## Verifiable claims

-   **R21**, depth by cost of reversal: A review at a higher rate removes fewer
    defects. A longer document in the same review time increases the rate.
    Sources: Kemerer and Paulk 2009 (field data from code and design reviews,
    not from prose). Boehm 1988 (argument) for detail that follows risk.
-   **R22**, named, enforced, tested claims: Developers with links from
    requirements to code completed maintenance tasks 24% faster and 50% more
    correctly. Requirement templates reduced ambiguity in one industrial case.
    Sources: Mäder and Egyed 2015 (experiment with developers, not reviewers).
    Mavin and others 2009 (case study).
-   **R23**, stated coverage and stated negatives: People, also experts, did not
    notice the missing branches of a fault tree. Reviewers with specific fault
    scenarios found more faults. Sources: Fischhoff, Slovic, and Lichtenstein
    1978 (experiment). Porter, Votta, and Basili 1995 (experiment).
-   **R24**, a decision from a comparison: Architects rate the reasons for a
    design as important, and they report barriers to recording them. Later
    readers ask the same questions again. Sources: Tang and others 2006
    (survey). Parnas and Clements 1986 (argument).

## Plain English for international readers

-   **R25 to R28:** A reader with limited English uses the dictionary meaning of
    each word and the grammar of each sentence. A translation program does the
    same. A word with two meanings, an idiom, or a missing article can give a
    wrong translation. Source: practice from controlled-language standards for
    technical manuals, for example ASD-STE100 Simplified Technical English. No
    experiment is cited.

These rules differ from such standards in one point. The rules keep "might" for
a possibility, because R8 needs a word for a claim that is not verified.

## Grounded, non-synthetic prose

-   **R29**, system-specific text only: Sentences that fit any system add
    reading time without narrowing the design space. Outside migration notes,
    readers inspect a specification to learn the target behavior, not the commit
    history. Sources: Harp and Mayer 1998 (experiment). Forward and Lethbridge
    2002 (field study).
-   **R30**, direct statements, not stagecraft: Readers judge importance from
    concrete consequences, not from announcements of candor or cleverness. In
    one parallel corpus, sentence-start adverbs such as "Notably" appeared 2 to
    3 times as often in machine text as in human text. Sources: Morkes and
    Nielsen 1997 (experiment). Brown and others 2024 (field study).
-   **R31**, named sources and bounded scope: Statistical AI detectors
    misclassified more than 60% of essays by writers with limited English.
    Therefore these rules check named sources, environment boundaries, and
    concrete artifacts instead of guessing who wrote the text. Source: Liang and
    others 2023 (experiment).
-   **R32**, plain copulas and literal modifiers: Direct verbs and literal
    modifiers prevent category errors during dictionary lookup and machine
    translation. Source: ASD-STE100 practice.

## Reasons for the 4 principles

-   **Reader effort before word count:** Headings, captions, and repeated names
    add words. They remove searches and re-reading. Sources: Chandler and
    Sweller 1991, Cowan 2001.
-   **Layers before one average depth:** Explicit background helps readers with
    little knowledge and slows experts. One text at a middle depth serves
    neither group. Sources: McNamara and others 1996, Kalyuga and others 2003
    (experiments).
-   **Reader task before format habit:** The same facts in a different format
    need a different number of mental steps. Sources: Larkin and Simon 1987,
    Vessey 1991.
-   **Risk before uniform depth:** Review time is limited. Detail in a low-risk
    part takes attention from a high-risk part. Sources: Kemerer and Paulk 2009,
    Boehm 1988.

Two more conflicts have a fixed resolution:

-   **Links against local text:** A link makes the reader decide whether to
    leave the page. A pointer that names the content of its target removes that
    decision. Source: DeStefano and LeFevre 2007 (review).
-   **Much highlighting against none:** Bold only on lead-in keys gives a scan
    index. All the body text keeps equal weight. Source: Lorch 1989.

## Limits of the evidence

-   **Subjects:** Most experiments measured students or general readers. They
    did not measure engineers who review design documents.
-   **Numbers:** The studies support the direction of each limit. The exact
    limits (25 words, 5 columns, 9 nodes, 400 words) are practical choices.
-   **Source list:** The list comes from the research review that was written
    with these rules. Read a source before you cite it in a document.
