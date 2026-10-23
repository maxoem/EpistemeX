# [ISSUE-068] Conceptual & Domain Errors (Knowledge Graphs, Argument Mining, Argumentation, Structuralism, Network Science)

| Metadata              | Details                                                                                                                                                                                                                                                                                         |
|:----------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Issue ID**          | `ISSUE-068`                                                                                                                                                                                                                                                                                     |
| **Domain / Category** | `10-Formal & Conceptual Docs` — (c) Conceptual errors & domain issues                                                                                                                                                                                                                           |
| **Evaluated Docs**    | [`kg_vs_tg.md`](../../docs/concepts/kg_vs_tg.md), [`formal_graph_model.md`](../../docs/concepts/formal_graph_model.md), [`theory_nets_and_topologies.md`](../../docs/concepts/theory_nets_and_topologies.md), [`epistemology.md`](../../docs/concepts/epistemology.md)                             |
| **Priority**          | **High**                                                                                                                                                                                                                                                                                        |
| **Status**            | `Open`                                                                                                                                                                                                                                                                                          |

This file covers claims that conflict with the conventions or state of the art of the *technical* fields the documents
draw on: KG research, argument mining, formal argumentation, structuralist metascience, uncertainty modelling, and
network science. Philosophical issues proper are in [`ISSUE-069`](ISSUE-069-philosophical-errors.md).

---

## Knowledge-graph framing (`kg_vs_tg.md`)

### C-01 · The KG side of the comparison is a straw man — **Critical**

**Where.** [`kg_vs_tg.md#L20`](../../docs/concepts/kg_vs_tg.md#L20), [`#L34-L41`](../../docs/concepts/kg_vs_tg.md#L34-L41), [`#L86-L95`](../../docs/concepts/kg_vs_tg.md#L86-L95), [`#L127-L128`](../../docs/concepts/kg_vs_tg.md#L127-L128).

Claims that do not match the state of the art:

| Claim in the document                                                                         | State of the art                                                                                                                                                                                                                                                                                                                         |
|:----------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| KGs "assume a single, consistent, shared reality"; conflicts are "data quality errors"         | **Wikidata** explicitly stores *claims with sources*, allows multiple conflicting values with **ranks**, **qualifiers** and **references**, and is designed as "a secondary database" of statements, not of truths (Vrandečić & Krötzsch 2014). RDF uses the **open-world assumption**, and named graphs, RDF-star and nanopublications (Groth et al. 2010) attach context and provenance to statements. |
| KG claim status: "assumed static, objective, and true"                                         | See above; temporal qualifiers and deprecated ranks are standard. The ACM survey definition (Hogan et al. 2021) explicitly includes *contextual* and *defeasible* knowledge.                                                                                                                                                              |
| KG topology: "entity-centric clusters and star graphs"                                         | Large KGs are heavy-tailed, small-world graphs; "star graphs" is not an accepted characterisation.                                                                                                                                                                                                                                         |
| KG evolution: "monotonic accumulation"                                                          | Wikidata and DBpedia are continuously revised, and statements are deprecated. Monotonicity is a property of *consequence relations*, not of database update (see C-07).                                                                                                                                                                  |
| Only TGs model scholarly argument                                                               | Existing scholarly/argument KGs: **ORKG** (Jaradeh et al. 2019), **AIF / AIFdb** argument graphs (Chesñevar et al. 2006; Lawrence & Reed 2014), nanopublications, ClaimsKG, and the SPAR / CiTO ontologies for citation function.                                                                                                       |

Moreover, Episteme's **own L2 is a KG** ([L194](../../docs/concepts/kg_vs_tg.md#L194)), and L3 is stored in the same
property graph. So the right framing is not *KG vs. TG*: **a TG is a KG with an argumentative-epistemic schema and
evaluation semantics**.

**Fix.** Recast the comparison as *"factual-entity KGs vs. epistemic/argumentative KGs"*. Cite the systems above as
related work, and locate the actual novelty: integration of structuralist net structure, argumentative evaluation and
text provenance.

### C-02 · "Theory graph" is an established term with a different meaning — **Major**

In mathematical knowledge management, **theory graphs** (MMT/OMDoc) are graphs whose nodes are *formal theories* and
whose edges are *theory morphisms* (inclusions, views) (Rabe & Kohlhase 2013; Kohlhase 2014). This is close to
the structuralist notion of inter-theoretical links, and very different from an argument graph. The documents never
mention this.

**Fix.** Add a terminology note distinguishing Episteme's "Theory Graph" from MMT theory graphs, or choose a different
name, e.g. *epistemic theory graph*.

### C-03 · Example and concept list mix levels and misrepresent Kant — **Major**

**Where.** [`kg_vs_tg.md#L48-L49`](../../docs/concepts/kg_vs_tg.md#L48-L49), [`#L63-L80`](../../docs/concepts/kg_vs_tg.md#L63-L80).

1. **"Transcendental deduction" is not a concept or axiom.** It is an *argument* (KrV A84–130 / B116–169).
   *"Defeasible warrant"* is a *metatheoretical* term of argumentation theory, not an object-level construct of the
   analysed theories. The list mixes object-level, argument-level and meta-level items.
2. **"Categorical Imperative (Universalizability Principle)".** Universalizability is only the *Formula of Universal
   Law*. Kant gives several formulations (FUL, Humanity, Autonomy, Kingdom of Ends), and their equivalence is a central
   interpretive debate (Paton 1947; Wood 1999).
3. **"Axiom: CI ENTAILS Claim: Moral duty is categorical" inverts Kant's order.** That moral obligation is categorical
   (unconditional) is what makes the supreme principle a *categorical* imperative in the first place (GMS 4:414–420). At
   best the two are co-constitutive, not axiom → theorem.
4. **"Counterclaim: Utilitarian Consequentialism" is not a claim.** It is a whole normative *theory*, and treating it as
   one node attacking one claim is a granularity error. An argument would attack a specific premise, e.g. that the
   moral worth of actions is independent of consequences.
5. **"REFUTES / ATTACKS" are not interchangeable.** *Refutes* is a success (factive) verb; *attacks* is not.
   Typing a relation as "refutes" pre-judges the outcome that evaluation is supposed to compute.
6. **"(Theoretical Element)"** on the CLAIM node collides with the structuralist technical term *theory-element*
   $\langle K, I\rangle$.

**Fix.** Use non-factive relation names. Model rival theories as **sub-graphs** (or holon members), not single atoms.
Re-check Kant labels with a specialist.

---

## Argument mining & formal argumentation

### C-04 · Argument *components* are conflated with *arguments* — **Major**

**Where.** [`formal_graph_model.md#L127-L128`](../../docs/concepts/formal_graph_model.md#L127-L128), [`#L254-L260`](../../docs/concepts/formal_graph_model.md#L254-L260).

- **Claim and premise are roles, not types.** In argument mining they are *relational* roles: one proposition is a
  claim in one argument and a premise in the next (Peldszus & Stede 2013; Stab & Gurevych 2017). "Formally categorized
  as Claims or Premises" turns a role into a node type.
- **Dung's nodes are arguments, not components.** In Dung (1995) and QBAFs, nodes are **abstract arguments**. Mapping
  ADUs (argumentative discourse units) one-to-one onto Dung arguments is a known simplification. It needs explicit
  justification, e.g. "each atom stands for the argument whose conclusion it is".
- **The Dung reduction discards support.** It drops $\mathcal{R}_{sup}$ entirely. Standard practice derives
  *supported* and *secondary* attacks first, under the chosen support interpretation (deductive, necessary or evidential)
  (Cayrol & Lagasquie-Schiex 2005, 2013; Cohen et al. 2014).

### C-05 · Binary edges cannot represent linked premises, undercutters, or co-explanation — **Critical**

**Where.** [`formal_graph_model.md#L20`](../../docs/concepts/formal_graph_model.md#L20), [`#L186-L187`](../../docs/concepts/formal_graph_model.md#L186-L187); [`theory_nets_and_topologies.md#L111`](../../docs/concepts/theory_nets_and_topologies.md#L111), [`#L115-L116`](../../docs/concepts/theory_nets_and_topologies.md#L115-L116); [`epistemology.md#L207-L208`](../../docs/concepts/epistemology.md#L207-L208).

- **Linked vs. convergent arguments.** Freeman (1991) and Walton distinguish these: premises that support *only
  jointly*. The DN schema "Law ∧ Antecedent ⊢ Consequence" and ECHO's "co-hypotheses that jointly explain" are linked
  structures. With $\mathcal{R}_{sup}\subseteq\mathcal{A}\times\mathcal{A}$ they decompose into independent binary
  supports. That changes the semantics: each premise alone now supports the conclusion.
- **Undercutting attacks target the inference, not a node.** Undercutters (Pollock 1987; ASPIC+) attack an *edge*, which
  is impossible when $\mathcal{R}_{att}\subseteq\mathcal{A}\times\mathcal{A}$. Yet the D-QBAF text explicitly lists
  "undercutting" as a member of $\mathcal{R}_{att}$ ([FGM L186](../../docs/concepts/formal_graph_model.md#L186)).
- **The project's own simplicity principle presupposes hyperedges.** Thagard's simplicity principle ("weight inversely
  proportional to the number of co-hypotheses") needs explanation hyperedges to be computable.

**Fix.** Use a **bipartite inference graph** (AIF style: I-nodes for propositions; RA, CA and MA nodes for inference,
conflict and rephrase), or an argumentation framework with **sets of attacking/supporting arguments** (Nielsen & Parsons
2006, SETAFs). Undercutters then attack RA-nodes.

### C-06 · Relation taxonomy is flat and partly mistyped — **Major**

**Where.** [`kg_vs_tg.md#L50-L51`](../../docs/concepts/kg_vs_tg.md#L50-L51); [`formal_graph_model.md#L143-L153`](../../docs/concepts/formal_graph_model.md#L143-L153); [`theory_nets_and_topologies.md#L100-L117`](../../docs/concepts/theory_nets_and_topologies.md#L100-L117).

- **`ENTAILS` is not defeasible support.** It is *deductive*, i.e. monotone and non-defeasible. Subsuming it under a
  generic $\mathcal{R}_{sup}$ loses this. Bipolar argumentation distinguishes deductive, necessary and evidential support
  for exactly this reason (Cayrol & Lagasquie-Schiex 2013).
- **`UNDERMINES` is a subtype of attack.** It is the attack on a premise (ASPIC+), so listing it beside `ATTACKS` as a
  peer flattens the hierarchy. The standard triad is **rebut / undercut / undermine** (Modgil & Prakken 2014).
- **Some edge types are neither attack nor support.** `SPECIALIZES` ($\sigma$), constraints, links, reduction
  $RED$, mapping-law edges and every L2 relation fall into this group. Hence $E\cong R=\mathcal{R}_{att}\uplus\mathcal{R}_{sup}$
  (A-02, B-09) cannot hold. The DL-Lite$_R$ role hierarchy needs a third top role (e.g. `structural`) and a
  `factual` branch.
- **DL-Lite$_R$ supplies inclusion only.** Its role inclusions give *set inclusion* of extensions. They do not give
  "inheritance of the formal semantics" of attack. Attack semantics come from the argumentation layer, not from DL
  (Calvanese et al. 2007).

### C-07 · Non-monotonic inference, belief revision and theory change are conflated — **Major**

**Where.** [`kg_vs_tg.md#L94`](../../docs/concepts/kg_vs_tg.md#L94), [`#L125-L131`](../../docs/concepts/kg_vs_tg.md#L125-L131).

Three different phenomena are run together:

| Phenomenon                     | Formal home                                                                       | What changes                                         |
|:-------------------------------|:----------------------------------------------------------------------------------|:-----------------------------------------------------|
| **Non-monotonic inference**    | default logic, argumentation semantics (Dung 1995; Reiter 1980)                    | conclusions drawn from a *fixed* knowledge base       |
| **Belief revision**            | AGM (Alchourrón, Gärdenfors & Makinson 1985)                                       | the knowledge base itself under new input             |
| **Diachronic theory change**   | Kuhn, Lakatos; structuralist theory evolution (BMS 1987, ch. V)                    | theory-nets and their intended applications over time |

The "monotonic KG / non-monotonic TG" contrast is also inaccurate on the logic side. Adding facts to a classical KB
never *removes* consequences, but it can make the KB **inconsistent**, which is a problem KGs face too.

**Fix.** Separate the three. Attach each to its formal home and to the corresponding pipeline mechanism (gradual
semantics vs. graph update vs. versioned nets).

### C-08 · No unified ontology of uncertainty: 12+ unrelated scores — **Critical**

**Where.** All of [`formal_graph_model.md`](../../docs/concepts/formal_graph_model.md).

| Score                                             | Bearer       | Meaning (as stated)                   |
|:--------------------------------------------------|:-------------|:--------------------------------------|
| $\gamma$                                          | L2 node      | extraction confidence                 |
| $\delta$                                          | L2 edge      | certainty + evidence                  |
| $\tau$                                            | L3 node      | prior plausibility                    |
| $\tau_0=M(\phi)$                                  | L3 node      | authorial modal strength              |
| $\phi$                                            | L3 edge      | structural weight                     |
| $\mathcal{I}$                                     | L3 edge      | inferential warrant                   |
| $\mathcal{P}$                                     | L3 edge      | stance softmax                        |
| $\mathcal{C}$                                     | L3 edge      | calibration confidence                |
| $W$                                               | L3 edge      | effective weight                      |
| $s$, $s^*$, $\tau^*$, $\rho$                      | L3 node      | justification / acceptability         |
| $\beta,\delta,u$                                  | any element  | subjective-logic opinion              |
| $c$                                               | composite    | fuzzy min/max                         |
| $Z$, $Z_1$, $Z_2$                                 | $A\times B$  | mapping strength                      |
| $H(t)$                                            | graph        | ECHO harmony                          |
| $\mathcal{V}$, $E_{\text{tot}}$                   | L3 node      | volatility / weight                   |

The D-QBAF section starts the right move: it separates *extraction* uncertainty (about the pipeline's perception) from
*object-level* strength (in the text). This separation is not carried through. $\gamma$, $\delta$ and $\beta/\delta/u$
mix the two, and nothing says which scores propagate into which.

**Fix.** Add an explicit **three-tier uncertainty ontology** and require every score to be placed in exactly one tier,
with one calculus per tier:

1. **Perception / extraction**: is this atom or edge really in the text? Use probability with calibration (e.g.
   temperature scaling) or conformal sets.
2. **Authorial commitment**: hedging, modality.
3. **Evaluative acceptability**: argumentation semantics.

### C-09 · D-QBAF components: misattributed and technically confused — **Major**

**Where.** [`formal_graph_model.md#L188-L206`](../../docs/concepts/formal_graph_model.md#L188-L206).

- **Toulmin's modal qualifier is inferential.** It expresses the force with which the data, *via the warrant*, license
  the claim (Toulmin 1958, ch. 3). It is therefore an **inferential (edge-level)** quantity, which is the opposite of the
  document's argument for moving modality off edges. The document's own example (L177: "a deductive proof ($M=1.0$)")
  describes an *inferential* property.
- **Argument schemes are Walton's, not Toulmin's.** "Toulminian argument schemes (deductive entailment vs. empirical
  corroboration vs. defeasible analogy)" should cite Walton, Reed & Macagno (2008).
- **Schurz's epistemic status is not a score.** It refers to core vs. periphery, not to a numeric prior. The table row
  "Schurz (2014) Epistemic Status" for $\tau_0$ is a misattribution.
- **"Prakken (2020) Constellations" cannot be verified.** No such reference appears in any bibliography. See
  [`ISSUE-070`](ISSUE-070-bibliography-and-attribution-audit.md).
- **Conformal prediction is confused with calibration.** Conformal prediction produces **prediction sets** with
  marginal coverage guarantees (Angelopoulos & Bates 2023), not a per-edge "expected empirical precision under
  calibrated temperature buckets". The latter is **reliability-diagram calibration / temperature scaling** (Guo et al.
  2017). These are distinct techniques.
- **"Jev"** is undefined.

### C-10 · Five evaluation semantics with no stated relation — **Critical**

Within the documents the following coexist without any statement of which is normative, when each applies, or how they
relate:

1. D-QBAF quadratic-energy gradual semantics
2. ECHO connectionist harmony
3. Dung extensions (grounded, preferred, stable)
4. Maximal $B$-consistent subsets (Rescher–Manor)
5. Subjective-logic opinions and fuzzy min/max

They are known to disagree. Gradual semantics do not even satisfy the same principles as each other (Baroni, Rago & Toni
2019), and ECHO is undirected while QBAFs are directed (A-12).

**Fix.** Declare **one** primary acceptability semantics and treat the others as *alternative lenses*, with a short
comparison table (input structure, directedness, output type, principles satisfied).

---

## Structuralist metascience

### C-11 · Structuralist apparatus is incompletely or wrongly rendered — **Major**

**Where.** [`theory_nets_and_topologies.md#L12-L66`](../../docs/concepts/theory_nets_and_topologies.md#L12-L66), [`#L104-L107`](../../docs/concepts/theory_nets_and_topologies.md#L104-L107); [`formal_graph_model.md#L297-L341`](../../docs/concepts/formal_graph_model.md#L297-L341); [`kg_vs_tg.md#L147`](../../docs/concepts/kg_vs_tg.md#L147).

1. **The core is incomplete.** It must be $K=\langle M_p,M,M_{pp},GC,GL\rangle$. Constraints and links are missing,
   although TN later relies on them (B-23).
2. **Specialization is defined too loosely (BMS, ch. IV).** $T'\,\sigma\,T$ iff $M_p'=M_p$, $M_{pp}'=M_{pp}$,
   $M'\subseteq M$, $GC'\subseteq GC$, $GL'\subseteq GL$ **and $I'\subseteq I$**. The documents omit the identical
   conceptual frame and the condition on intended applications.
3. **Constraints are core components, not inter-element edges.** Constraints (e.g. the equality constraint for mass)
   restrict *combinations of models within a theory-element's applications*. They are not edges between theory-elements
   $T_1 \Leftrightarrow T_2$ (TN diagram L37). *Links* ($L$) are the inter-theoretical relations. "Constraint edges
   $(C, CL)$" merges the two and leaves $CL$ undefined.
4. **Intended applications are components, not children.** $I$ is the second component of $T=\langle K,I\rangle$. The
   diagram (L28-36) draws application domains as child nodes linked by unlabeled edges, which visually equates
   membership with specialization.
5. **Bourbaki's species of structures fix $M_p$, not specialization.** BMS use them to define the **potential models**
   through typification. Specialization does not "draw on" them. Also, in BMS special laws restrict $M$, not "the force
   function $F=ma$".
6. **$\alpha$ in the box is the relation, not the sub-theories.** `kg_vs_tg.md` L147 says "specialized sub-theories
   ($\alpha$)", which is wrong.
7. **Friction example.** $F=-\gamma v$ is *viscous* (linear) damping, not friction in general. Coulomb friction is
   velocity-independent. Use "Linear damping".

### C-12 · The bridge from argument mining to structuralist theory-nets is asserted, not defined — **Critical**

**Where.** [`kg_vs_tg.md#L145-L151`](../../docs/concepts/kg_vs_tg.md#L145-L151).

The central methodological claim is that argument mining is "the empirical linguistic vehicle to reconstruct
structuralist theory networks". It has no formal counterpart:

- Argument mining yields **propositions plus support/attack**, i.e. a statement-view object. Structuralist nets consist of
  **classes of set-theoretic structures** ($M_p,M,M_{pp}$), plus constraints, links and intended applications. No
  procedure maps ADUs to potential models or to special laws, and none decides $T$-theoreticity from text.
- Structuralist reconstructions are expert-intensive. The canonical examples (classical particle mechanics,
  thermodynamics, and others in Balzer, Sneed & Moulines (eds.) 2000, *Structuralist Knowledge Representation*) took years per
  theory. For the declared target domain (philosophical texts such as Kant), **there is usually no mathematical
  structure species at all**.

**Fix.** Be explicit about *which* parts of structuralism are operationalised. A defensible scope is a **"structuralism
light"** that uses only (i) the *net topology* (general law → special laws → applications) and (ii) the
*theoretical/non-theoretical* distinction as an annotation scheme. The model-theoretic apparatus (uniformities,
approximation, $\operatorname{Cn}(K)$) should then be presented as the **regulative ideal**, not as something the
pipeline computes. Cite the attempts to apply structuralism outside physics as precedent and limit.

### C-13 · "Theory" has five representations without identity criteria — **Major**

The documents represent a theory as:

1. an **L2 `Theory` entity** (FGM L110);
2. the **argument graph $TF$** (FGM L26);
3. a **theory-element** $\langle K,I\rangle$ or **theory-net** (TN L15-20);
4. a **Leiden community** at Level 2 ("paradigms, schools", TN L160);
5. a **holon member** (TN L129).

Nothing states when two of these represent the *same* theory, or which one is authoritative.

**Fix.** Define one canonical theory identifier and typed `REPRESENTS` / `REALIZES` relations from the other
representations.

### C-14 · Layer names misdescribe their content — **Minor**

- **"Empirical Manifold" (L1).** Text chunks are not empirical data in the sense of $B$ (see D-02), and "manifold" is a
  topological term (locally Euclidean space) used metaphorically.
- **"Deterministic Ontology" (L2).** It is produced by stochastic LLM extraction and carries confidences $\gamma,\delta$.
  It is neither deterministic nor an ontology in the TBox sense (it is an ABox, i.e. assertions).

**Fix.** Rename to "Source / Provenance Layer" and "Entity Layer (ABox)".

---

## Network science

### C-15 · Leiden communities are given an unwarranted semantic hierarchy — **Major**

**Where.** [`theory_nets_and_topologies.md#L136-L170`](../../docs/concepts/theory_nets_and_topologies.md#L136-L170).

1. **Schools and subfields cross-cut; they do not nest.** Kantianism spans epistemology, ethics and aesthetics. Logical
   positivism spans epistemology, philosophy of language and ontology. A *hierarchical* (nested) partition cannot
   output both "subfields" (Level 1) and "schools" (Level 2) as nested levels.
2. **The example hierarchy is inverted.** "Decision Theory" is Level 1 (meso) while "Bayesian Decision Theory" is
   Level 2 (macro), so a macro cluster is *narrower* than a meso cluster.
3. **Attack edges with positive weight merge opponents.** A dense debate between Kantians and utilitarians becomes one
   community. Either signed modularity (Traag & Bruggeman 2009) or attack-free projections are needed, and the purpose
   ("debates" vs. "schools") must be stated.
4. **Heterogeneous graph.** L2 entities and L3 components with different edge semantics are pooled. Modularity on such
   a graph has no clear interpretation without per-type weighting.
5. **Resolution limit.** Modularity cannot detect communities below a scale set by total edge weight (Fortunato &
   Barthélemy 2007). Level semantics therefore depend on $\gamma$, not on intellectual structure.
6. **"Hierarchical Leiden" is a recursive scheme, not Leiden itself.** Leiden yields a single partition; what is meant is
   recursive re-application to large communities (as in `graspologic` / GraphRAG). Name and cite it.
7. **Phase inconsistency.** "Phase 5" vs. "Phase 5b" (A-15).

**Fix.** Present levels as *resolution scales* with post-hoc labelling and validation against expert taxonomies. Do not
present them as ontological categories.

### C-16 · Centrality interpretations depend on unstated edge orientations — **Major**

**Where.** [`theory_nets_and_topologies.md#L174-L185`](../../docs/concepts/theory_nets_and_topologies.md#L174-L185); [`epistemology.md#L48-L49`](../../docs/concepts/epistemology.md#L48-L49).

- **Out-degree is ambiguous.** It means "unifying axiom" only on support edges oriented supporter → supported. On
  $\sigma$ (specialization → general) the root has in-degree, not out-degree. On attack edges, high out-degree means a
  prolific *attacker*.
- **Unification requires diversity, not degree.** A diversity-sensitive measure is needed, e.g. the **participation
  coefficient** across communities (Guimerà & Amaral 2005) or the number of distinct application domains reached.
- **Eigenvector centrality** is degenerate here (B-32).

### C-17 · Tractability section addresses the wrong problem — **Major**

See B-27. Candidate retrieval (bi-encoders, cross-encoders) solves a *recall/precision trade-off in relation extraction*.
It does not address the complexity of argumentation semantics. These are separate pipeline concerns and should be in
separate sections.

### C-18 · Evaluation section: proxies presented as the constructs — **Major**

**Where.** [`kg_vs_tg.md#L133-L141`](../../docs/concepts/kg_vs_tg.md#L133-L141); [`formal_graph_model.md#L395-L405`](../../docs/concepts/formal_graph_model.md#L395-L405).

- **The P/R/F1 contrast is overdrawn.** Argument mining itself is evaluated with P/R/F1 on components and relations
  (Stab & Gurevych 2017), and the project's own table uses them. Structural and epistemic metrics *complement* P/R/F1;
  they do not replace it.
- **"Empirical Content Ratio" is not empirical content.** The share of hypotheses with a $Z$-path to $B$ is a
  *connectivity* proxy, not empirical content in the sense of B-01. It also penalises non-empirical (e.g. normative)
  content by design, which in philosophy is the subject matter itself (D-01).
- **"Structural Coherence = $H(t)$ via ECHO"** is undefined on the directed, signed D-QBAF (A-12). Also, "absence of
  unmitigated circularities" is not what $H$ measures: $H$ measures constraint satisfaction.
- **"Can it quantify the empirical creativity … (Lakatos 1978)"** misattributes the concept. *Empirical creativity* is
  Schurz's notion, not Lakatos's.

### C-19 · Unsupported empirical claims in the motivation — **Minor**

**Where.** [`kg_vs_tg.md#L14-L18`](../../docs/concepts/kg_vs_tg.md#L14-L18), [`#L177-L184`](../../docs/concepts/kg_vs_tg.md#L177-L184).

- "Linear prose obscures long inferential chains for humans and LLMs" and "enabling language models to reason … without
  hallucinating" are empirical claims with no citation. Support them, e.g. with evidence on argument-mapping effects
  on critical thinking or on long-context reasoning failures, or soften them.
- "Knowledge graph—or **more formally**, *knowledge as structure*" (L10): "knowledge as structure" is not a more formal
  term for KG.
