# [ISSUE-069] Philosophical Errors & Issues (Philosophy of Science, Epistemology, Historiography)

| Metadata              | Details                                                                                                                                                                                                                                                                                         |
|:----------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Issue ID**          | `ISSUE-069`                                                                                                                                                                                                                                                                                     |
| **Domain / Category** | `10-Formal & Conceptual Docs` — (d) Philosophical errors & issues                                                                                                                                                                                                                               |
| **Evaluated Docs**    | [`epistemology.md`](../../docs/concepts/epistemology.md), [`kg_vs_tg.md`](../../docs/concepts/kg_vs_tg.md), [`formal_graph_model.md`](../../docs/concepts/formal_graph_model.md), [`theory_nets_and_topologies.md`](../../docs/concepts/theory_nets_and_topologies.md)                             |
| **Priority**          | **Critical** (D-01, D-02, D-04 concern the foundations of the project)                                                                                                                                                                                                                         |
| **Status**            | `Open`                                                                                                                                                                                                                                                                                          |

---

## Foundational tensions

### D-01 · An empiricist evaluation apparatus is applied to a largely non-empirical domain — **Critical**

**Where.** [`epistemology.md#L19-L92`](../../docs/concepts/epistemology.md#L19-L92), [`#L167-L194`](../../docs/concepts/epistemology.md#L167-L194); [`formal_graph_model.md#L264-L268`](../../docs/concepts/formal_graph_model.md#L264-L268), [`#L404`](../../docs/concepts/formal_graph_model.md#L404); [`kg_vs_tg.md#L48-L55`](../../docs/concepts/kg_vs_tg.md#L48-L55), [`#L160-L166`](../../docs/concepts/kg_vs_tg.md#L160-L166).

All the evaluative criteria are tied to **observational/empirical content**:

- empirical creativity;
- globality via novel predictions;
- success/failure sets;
- the Degeneration Index;
- Data Priority;
- mapping laws to $B$;
- the "Empirical Content Ratio".

These are Schurz's and Lakatos's criteria for **empirical science**. The documents' own showcase domain is
*philosophy*: Kantian ethics, transcendental arguments, and utilitarianism vs. deontology. Applied there, the apparatus:

- classifies Kant's practical philosophy wholesale as "metaphysical surplus" or "empirical deadweight"
  ([EPI L35](../../docs/concepts/epistemology.md#L35)), as "decaying into speculative metaphysics"
  ([EPI L151](../../docs/concepts/epistemology.md#L151)), and as "ungrounded metaphysical baggage"
  ([FGM L404](../../docs/concepts/formal_graph_model.md#L404));
- leaves $\mathsf{Succ}$, $\mathsf{Fail}$ and $D$ **undefined** for normative theories, so the Lakatosian framing in
  `kg_vs_tg.md` (L54-55, L165-166) cannot be applied as stated;
- rebuilds, through its vocabulary, a **verificationist criterion of meaningfulness**. That criterion is the
  logical-empiricist position abandoned after Hempel (1950) and Quine (1951), and Schurz himself does not endorse it for
  philosophy.

**Fix (choose explicitly).**

1. **Restrict** the empirical criteria to empirical-scientific corpora and state this scope; or
2. **Generalise "evidence"** per domain. For normative theories, use considered judgments / intuitions as the
   evidential base (reflective equilibrium: Goodman 1955; Rawls 1971; Daniels 1979). For exegesis, use textual
   evidence (but see D-02). Also state that Lakatos's methodology in ethics and metaphysics is a contested analogy, not
   an established method.

Remove the positivist register ("metaphysical surplus", "deadweight") in either case.

### D-02 · Textual provenance is conflated with empirical justification — **Critical**

**Where.** [`formal_graph_model.md#L75-L85`](../../docs/concepts/formal_graph_model.md#L75-L85) ("Empirical Manifold"; "Traversals terminating in B → L1"), [`#L291-L293`](../../docs/concepts/formal_graph_model.md#L291-L293) ("provably grounded in **empirical textual evidence**"); [`kg_vs_tg.md#L183-L184`](../../docs/concepts/kg_vs_tg.md#L183-L184).

Two kinds of evidence are merged:

- (a) **exegetical evidence**: that author $X$ asserted $p$. A text span in L1 is evidence for this.
- (b) **epistemic evidence**: that $p$ is true or warranted. Observation sentences $b\in B$ are evidence of this kind,
  and only *within the analysed theory*.

The diagram's dotted edge "Traversals terminating in $B$" points to **L1**, so it identifies (b) with (a). This is the
classic **use/mention** confusion: the chunk *mentions* an observation; it is not one. A Kant passage asserting that
rational agents are autonomous is excellent evidence *that Kant held it* and no evidence *that it is true*.

**Fix.** Keep two orthogonal relations: `GROUNDED_IN` (atom → span; provenance; measured by evidence precision) and
`JUSTIFIED_BY` (atom → atom; within the theory; ends in $B$). Never call provenance "empirical".

### D-03 · *Zuordnungsgesetze* are recast as inter-layer database edges and numeric functions — **Critical**

**Where.** [`formal_graph_model.md#L83`](../../docs/concepts/formal_graph_model.md#L83), [`#L264-L283`](../../docs/concepts/formal_graph_model.md#L264-L283); [`epistemology.md#L150-L151`](../../docs/concepts/epistemology.md#L150-L151).

In Schurz (2014), as in the earlier tradition of *correspondence rules* (Carnap 1956) or bridge principles (Hempel),
mapping laws are **object-level sentences of the theory**. They are *mixed sentences* containing both $L_T$ and $L_E$
terms, e.g. "temperature (theoretical) is measured by mercury-column height (empirical)". `epistemology.md` gets this
right (L150).

`formal_graph_model.md` instead turns them into:

- an **edge between architectural layers** (L3 → L2) — a category mistake, since L2 holds persons, works and concepts,
  not empirical sentences;
- a **function** $Z:A\times B\to[0,1]$;
- a split into "correlational" $Z_1$ and "structural isomorphism" $Z_2$, which has **no basis in Schurz**.

**Fix.** Model a mapping law as an **atom** of semantic type `MIXED` (contains $L_T$ and $L_E$ terms) that participates
in inferences linking $A$-atoms to $B$-atoms. If a graded "anchoring strength" is wanted, give it a new name and present
it as a project-specific heuristic.

### D-04 · Statement view and non-statement view are combined without reconciliation — **Critical**

**Where.** [`formal_graph_model.md#L299-L300`](../../docs/concepts/formal_graph_model.md#L299-L300) ("Theories are model-theoretic entities rather than syntactic statement lists") vs. [`epistemology.md#L136-L153`](../../docs/concepts/epistemology.md#L136-L153) (axioms, $\operatorname{Cn}(T)$, sentence types) and the entire L3 (propositional atoms).

Schurz's analysis, Lakatos's methodology, ECHO and argumentation frameworks are **statement-view** frameworks. Theories
there are sets of sentences, and truth, consequence, consistency and refutation apply to sentences. Structuralism
(Sneed 1971; Stegmüller 1976; BMS 1987) is the **non-statement view**: theories are model-theoretic entities, *not true
or false*; only their **empirical claims** $I\in\operatorname{Cn}(K)$ are.

The documents assert the non-statement view and then apply statement-view predicates to structuralist theories:

- "the **theory** is falsified" ([FGM L327](../../docs/concepts/formal_graph_model.md#L327));
- "Root ... embodies the fundamental invariant **law**" (TN L64-65).

**Fix.** Adopt an explicit **two-level stance**: theory-*elements* (non-statement) and their *formulations and claims*
(statements, the L3 atoms). Give a bridge as in C-12. Note that structuralists treat the core as unfalsifiable and the
empirical claim as falsifiable. For the debate on intertranslatability of the views, cite Stegmüller (1976, ch. on
the non-statement view) and Schurz's own discussion of structuralism (Schurz 2014, ch. 5).

### D-05 · Sneed's $T$-theoreticity is misread as observability — **Major**

**Where.** [`formal_graph_model.md#L311-L312`](../../docs/concepts/formal_graph_model.md#L311-L312); [`theory_nets_and_topologies.md#L79-L80`](../../docs/concepts/theory_nets_and_topologies.md#L79-L80); [`formal_graph_model.md#L43-L44`](../../docs/concepts/formal_graph_model.md#L43-L44).

Sneed's criterion was introduced *precisely to replace* the observational/theoretical dichotomy. A term is
$T$-theoretical iff every determination of its values presupposes the successful application of $T$. $T$-non-theoretical
terms can be highly theoretical relative to other theories. For example, position and time in classical particle
mechanics are CPM-non-theoretical, but they are not "directly observable" in any naive sense.

Calling $M_{pp}$ "directly observable" and $B$ "verifiable" ignores this. It also ignores the **theory-ladenness of
observation** (Hanson 1958; Kuhn 1962), which the documents' own fallibilist stance (kg_vs_tg L52) would demand.

**Fix.** Use "$T$-non-theoretical (determinable without presupposing $T$)" and "pre-theoretical relative to $T$" (A-09).
Drop "verifiable".

### D-06 · Lakatos's hard core, Kuhn's paradigm and the structuralist core are silently identified — **Major**

**Where.** [`epistemology.md#L155-L163`](../../docs/concepts/epistemology.md#L155-L163); [`theory_nets_and_topologies.md#L86-L87`](../../docs/concepts/theory_nets_and_topologies.md#L86-L87); [`kg_vs_tg.md#L170`](../../docs/concepts/kg_vs_tg.md#L170).

- **Lakatos's unit is the research programme**, i.e. a *sequence* of theories. "Theories are structured into
  differential epistemic strata" puts hard core and belt inside single theories.
- **Abandoning the core does not "collapse the paradigm".** For Lakatos it means *leaving the programme* by definition.
  "Paradigm" is Kuhn's term, with a different meaning (disciplinary matrix, exemplars).
- **Core ↔ hard core is a thesis, not a given.** Identifying the structuralist core of the basic element with Lakatos's
  hard core, and core expansions with the belt, is Stegmüller's reconstruction thesis (Stegmüller 1976). It is contested
  in its details: belt modifications in Lakatos are statement-level and heuristic-driven, while specialisations are
  model-class restrictions.
- **The hard core is constant.** See B-04 / A-10: the ad-hoc definition modifies $K$.

**Fix.** Cite Stegmüller for the bridge. Keep Lakatos's unit (programme) and Kuhn's term (paradigm) separate.

### D-07 · Testing holism does not follow from meaning holism — **Major**

**Where.** [`epistemology.md#L51-L58`](../../docs/concepts/epistemology.md#L51-L58).

"From this [holism of meaning] follows the Holism of Theory Testing" is historically and logically wrong:

- **Duhem's thesis** (1906) rests on the *logical* fact that predictions need auxiliary hypotheses. Duhem was **not** a
  meaning holist, and he restricted his thesis to physics.
- **Quine (1951)** combines testing holism with semantic holism, but the latter is an independent and much stronger
  thesis (Fodor & Lepore 1992).
- **The derivation should run the other way.** Testing holism follows from the *empirical-content* holism of EPI L12-14
  ("empirical content emerges only globally") without any thesis about meaning.

The documents' own falsification schemata (TN L112-113) assume single-law falsifiability, which is in tension with the
holism stated here (A-13).

**Fix.** Separate the two holisms, state the actual dependency, and attribute correctly (Duhem: physics, testing; Quine:
global, plus meaning).

### D-08 · Unification is conflated with novel prediction — **Major**

**Where.** [`epistemology.md#L37-L49`](../../docs/concepts/epistemology.md#L37-L49).

- **Explanatory unification** (Friedman 1974; Kitcher 1981/1989; Schurz & Lambert 1994) is about *reducing the number of
  independent phenomena or argument patterns* needed to explain a body of facts. It can be fully achieved for *known*
  data; Newton's unification of Kepler's and Galileo's laws is the standard example. **Novel predictive success**
  (Lakatos; Zahar 1973; Worrall 1985) is a *different* virtue.
- The section first says unification "cannot be operationalized merely by counting post-hoc explanations", then
  measures it by out-degree (A-06).
- **The satellite example fails.** "Predicting that artificial satellites can maintain a stable orbit" is not
  qualitatively new: the **Moon** is a satellite in a stable orbit, already explained by the same mechanism, and Newton
  discussed the projectile-to-orbit case himself (the "Newton's cannonball" thought experiment). Standard novel
  predictions of Newtonian mechanics are the return of Halley's comet (1758/59), the oblateness of the Earth, and Neptune
  (1846).

**Fix.** Two separate criteria: unification (Schurz & Lambert 1994) and novel predictive success (use-novelty /
temporal novelty). Use a standard example.

### D-09 · The tacking paradox is mischaracterised, and the example defeats itself — **Major**

**Where.** [`epistemology.md#L73-L80`](../../docs/concepts/epistemology.md#L73-L80).

- **The tacking problem is standardly about confirmation.** If $E$ hypothetico-deductively confirms $H$, it also
  confirms $H\wedge X$ for arbitrary $X$ (Glymour 1980; Fitelson 2002). The document frames it as a problem of
  *content maximisation*. A content variant exists and fits Schurz's relevance programme, but it needs the precise
  source, and the confirmation version should be mentioned.
- **"Telepathy exists" adds no empirical content.** It is a **purely existential** statement, which in Popper's own
  framework is unfalsifiable and has *no* empirical content (Popper 1959, §15). So $T\wedge H$ does **not** "strictly
  possess a vastly increased empirical content", and the example undermines the point.
- **Popper's "boldness" is high content, not unexamined content.** Popper demanded high *logical/empirical content* and
  *improbability*, not "unexamined" content.

**Fix.** Use a testable but irrelevant empirical law, e.g. "all ravens are black" tacked onto mechanics. Cite Glymour
(1980) and Schurz's relevance work.

### D-10 · Thagard's Theory of Explanatory Coherence is misreported — **Major**

**Where.** [`epistemology.md#L198-L219`](../../docs/concepts/epistemology.md#L198-L219).

Thagard's principles (1989; with Competition added in 1992):

1. **Symmetry**
2. **Explanation**, with sub-clauses on coherence, simplicity and higher-level explanation
3. **Analogy**
4. **Data Priority**
5. **Contradiction**
6. **Competition**
7. **Acceptance**

Compared with the document:

| Document item                            | Actual status                                                                                                     |
|:-----------------------------------------|:------------------------------------------------------------------------------------------------------------------|
| 1 "Symmetry: if $P$ explains $Q$ they cohere" | Merges Principle 1 (coherence is symmetric) with 2a (explanation creates coherence)                         |
| 2 Explanatory breadth                    | A *consequence* of the network dynamics (more links), not a TEC principle; partly Thagard (1978) "consilience"   |
| 3 Simplicity                             | Principle 2c ✓                                                                                                    |
| 4 **Unification**                        | **Not a TEC principle**                                                                                           |
| 5 Higher-level warrant                   | Principle 2b (being explained); "warrant" is Toulmin's term, not Thagard's                                        |
| 6 Data priority                          | Principle 4 ✓, but data acceptability is **defeasible** in TEC, not "verified" (see D-14)                          |
| 7 **System coherence $H$**               | **Not a principle.** Harmony is a property of the ECHO *implementation*                                           |
| *(missing)* Analogy, **Contradiction**, Competition, Acceptance | Contradiction is what generates the inhibitory links that $H$ uses                                |

**Fix.** Reproduce the principles faithfully (Thagard 1989, p. 436 ff.; 1992, ch. 4). Separate TEC (theory) from ECHO
(implementation, including harmony and parameters). Cite Thagard & Verbeurgt (1998) for coherence as constraint
satisfaction.

---

## Epistemology & historiography

### D-11 · The presentism section condemns the project's own method — **Major**

**Where.** [`epistemology.md#L223-L233`](../../docs/concepts/epistemology.md#L223-L233).

Presentism is defined as analysing historical theories "using modern concepts, **formalisms**, or measurement
instruments that were unavailable to the historical authors". By that definition, the whole project is presentist:
QBAFs, structuralist model theory, Schurz's indices and Leiden communities were all unavailable to Kant.

The historiographical literature distinguishes:

- **anachronistic attribution of content** (reading later doctrines into a text: Skinner's "mythology of doctrines" and
  "prolepsis", 1969);
- **anachronistic evaluation** (judging by later evidence: Butterfield 1931, "Whig history");
- **legitimate rational reconstruction** with modern tools (Lakatos 1971, "History of science and its rational
  reconstructions"; Rorty 1984 on the "four genres").

"Historical neutrality" is moreover not attainable in the hermeneutic tradition (Gadamer 1960), which the documents
invoke as their method (kg_vs_tg L92). The constructive part of the section is sound: evaluate relative to $B(t)$. It
also matches Lakatos's *temporal novelty*.

**Fix.** Redefine as "avoid anachronistic **attribution** and **evaluation**". Explicitly endorse rational
reconstruction as the project's method. Keep $B(t)$, renamed to avoid clashing with $B$.

### D-12 · "Truth pluralism" is a misnomer; "ontological" divide is epistemic — **Major**

**Where.** [`kg_vs_tg.md#L27-L30`](../../docs/concepts/kg_vs_tg.md#L27-L30), [`#L39`](../../docs/concepts/kg_vs_tg.md#L39), [`#L52`](../../docs/concepts/kg_vs_tg.md#L52).

- **Truth pluralism** is a specific thesis in the metaphysics of truth: different domains have different truth
  properties (Wright 1992; Lynch 2009). Nothing in Episteme presupposes it. What is meant is **doxastic / theoretical
  pluralism**: tolerating rival, mutually inconsistent theories in the representation (Kellert, Longino & Waters 2006),
  plus defeasibility. Representing rival claims requires neither plural truth nor paraconsistent truth. Argumentation
  semantics work with classical truth.
- **The heading says "Ontological Divide"** and the next sentence says it "stems from underlying **epistemic**
  assumptions". KGs vs. TGs differ in *epistemic stance and representational commitments*, not in ontology.
- **"Monological"** (table L91) is argumentation-theoretic jargon (monological vs. dialogical argument structure), not a
  term for a world-view. Use "single-perspective".

### D-13 · Incommensurability is reduced to homonymy — **Major**

**Where.** [`kg_vs_tg.md#L111-L116`](../../docs/concepts/kg_vs_tg.md#L111-L116).

- **Homonymy is the wrong notion.** "Identical lexical terms denote radically different concepts … homonyms mask
  incommensurable paradigms" is not incommensurability. Kuhn's later notion is **taxonomic / local incommensurability**:
  the *lexical structures* (kind hierarchies) of two theories cannot be mapped onto each other without loss, so
  point-by-point comparison fails (Kuhn 1983; 2000). Homonymy is a much weaker, lexical phenomenon that entity linking
  can in principle resolve. Incommensurability, by hypothesis, cannot be resolved that way.
- **The second example is not a paradigm case.** "Rationality in economics vs. Frankfurt School" is **cross-disciplinary
  polysemy**, not two paradigms of one science. The *mass* example is the canonical one (Kuhn; Feyerabend 1962).
- **Stegmüller is cited the wrong way round.** Stegmüller (1976) is *the* structuralist attempt to show that theory
  dislodgement *without* common observational language can still be rational. It defuses rather than supports the
  incommensurability thesis.
- **The thesis undermines the project's own progress order.** If incommensurability is taken seriously, the
  set-inclusion order $\mathsf{Succ}(T_2)\subseteq\mathsf{Succ}(T_1)$ (B-03) is **undefined** for rival paradigms.

### D-14 · Foundationalist and coherentist epistemologies are mixed unacknowledged — **Major**

**Where.** [`formal_graph_model.md#L285-L293`](../../docs/concepts/formal_graph_model.md#L285-L293) (justification = paths terminating in $B$); [`epistemology.md#L198-L219`](../../docs/concepts/epistemology.md#L198-L219) (ECHO); [`theory_nets_and_topologies.md#L131-L132`](../../docs/concepts/theory_nets_and_topologies.md#L131-L132).

- **$J(at)$ is foundationalist.** Justification flows from basic beliefs ($B$) along chains.
- **ECHO is coherentist**, softened by Data Priority. The coherentist holon option repeats this.
- **$B$ is treated as given.** It is called "verifiable", "verified empirical data nodes", with "intrinsic
  acceptability". That is classical foundationalism, which TEC itself avoids: data can be rejected.

A combined position exists, e.g. Haack's **foundherentism** (1993) or BonJour's coherentism with observation input, but
it must be stated.

Also, the topological reading ("foundationalist = DAG, coherentist = cyclic") of inter-*theory* links is an analogy. The
foundationalism/coherentism debate concerns the structure of *justification of beliefs*, not intertheoretical
presupposition.

### D-15 · Authorial hedging is used as an epistemic prior — **Major**

**Where.** [`formal_graph_model.md#L188-L189`](../../docs/concepts/formal_graph_model.md#L188-L189).

$\tau_0(a)\equiv M(\phi_a)$ makes the *author's assertoric force*, a pragmatic and illocutionary feature, the
*epistemic* base score of the proposition. Consequences:

- **Acceptability tracks rhetoric.** Confident authors, or disciplines and languages with weaker hedging conventions,
  get systematically higher acceptability. Hedging is a **genre, discipline and language convention** (Hyland 1998),
  which matters for a German/English corpus.
- **Self-assessment is circular.** Evaluation is supposed to be *normative* ("does the theory deserve acceptance?"),
  but the prior is the author's *self*-assessment. That is a form of argument from authority.
- **Toulmin places the qualifier at the inference.** The qualifier belongs to the data → claim step (C-09), so the
  move off edges contradicts the cited source.

**Fix.** Keep $M(\phi_a)$ as a **descriptive** attribute ("authorial commitment"). Make the base score a separate,
explicitly chosen prior (uniform, Data-Priority-based, or expert-set), and report sensitivity to the choice.

### D-16 · Schurz attributions that need verification — **Major**

The following are presented as Schurz's but could not be matched to Schurz (2014) as stated. Either supply chapter and
page or present them as the project's own extensions:

1. the "four primary methodological criteria" (EPI L16);
2. "Schurz's four-dimensional framework of theory statics" (EPI L96-99);
3. the Degeneration Index (EPI L185; B-05);
4. Failure types a/b (EPI L177-181);
5. $Z_1/Z_2$ (FGM L276-283; D-03);
6. "Schurz (2014) Epistemic Status" as a numeric prior (FGM L200).

Additionally, "**natural axioms** = irreducible, non-redundant core laws that define the theory" (EPI L140) conflates:

- *natural axiomatisation*, a relevance-based technical notion (Schurz 1991; Gemes 1993), not mere non-redundancy;
- the Lakatosian *core*.

### D-17 · "Hermeneutic interpretation" as the construction method of an automated pipeline — **Minor**

**Where.** [`kg_vs_tg.md#L92`](../../docs/concepts/kg_vs_tg.md#L92).

Hermeneutics in the strict sense (Schleiermacher, Dilthey, Gadamer) designates a reflective, self-involving practice of
understanding. Attributing it to an LLM extraction pipeline is at least a strong claim. Either qualify it (e.g.
"computationally supported interpretation, with human-in-the-loop adjudication of readings") or justify it. This links
to the missing reading index (A-14).
