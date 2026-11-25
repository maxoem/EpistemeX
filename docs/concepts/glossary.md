# Glossary

Definitions of key computational, graph-theoretic, and epistemological terms used throughout the Episteme documentation and codebase. All symbols align with the [Canonical Notation & Symbol Reference](notation.md), and full bibliographic details appear in the [Consolidated References & Bibliography](references.md).

---

## A

### <span id="adu-argumentative-discourse-unit"></span>ADU (Argumentative Discourse Unit)
A segment of text functioning as an atomic propositional unit in Layer 3 ($\mathcal{A}$), taking on relational roles such as premise, intermediate conclusion, or main claim depending on incident inference warrants.

### <span id="approximative-empirische-adaquatheit-approximative-empirical-adequacy"></span>Approximative Empirical Adequacy (Approximative empirische Adäquatheit)
The structuralist condition that intended applications $I \subseteq M_{pp}$ lie within an induced admissible blur $\tilde{u}$ ($u \in \mathfrak{A} \subseteq \mathcal{U}$) of the non-theoretical restriction $\bar{r}(X)$ of a constraint- and link-satisfying set of actual models $X \in \operatorname{Pot}(M) \cap GC \cap GL$ ([Balzer et al., 1987](https://doi.org/10.1007/978-94-009-3759-8), ch. VII).

### <span id="apoc-awesome-procedures-on-cypher"></span>APOC (Awesome Procedures On Cypher)
Neo4j plugin providing additional graph algorithms, data integration utilities, and procedural Cypher extensions.

### <span id="argumentative-diskrepanz"></span>Argumentative Discrepancy (Argumentative Diskrepanz)
A tension between normative rational reconstruction and historical textual emphasis where structurally central axioms or implicit premises are barely articulated in surface prose ([Stegmüller, 1976](https://doi.org/10.1007/978-3-642-66440-3)).

### <span id="artifact"></span>Artifact
Persistent, content-addressed output from a pipeline phase (stored under `.pipeline_artifacts/`) for execution caching, resume workflows, and auditability.

---

## B

### <span id="balzer-gahde-invarianz-kriterium"></span>Balzer–Gähde Invariance Criterion (Balzer–Gähde-Invarianzkriterium)
A formal structuralist criterion for distinguishing $T$-non-theoretical terms from $T$-theoretical terms based on invariance across theory applications ([Balzer et al., 1987](https://doi.org/10.1007/978-94-009-3759-8)).

---

## C

### <span id="centrality"></span>Centrality
A structural graph-theoretic metric quantifying the relative topological importance, influence, or prominence of a node within a network ([Newman, 2018](https://doi.org/10.1093/oso/9780198805090.001.0001)). See also [Degree Centrality](#degree-centrality), [Eigenvector Centrality](#eigenvector-centrality), [Katz Centrality](#katz-centrality), and [PageRank](#pagerank).

### <span id="chunk"></span>Chunk
A segment of parsed document text (typically 500–1500 tokens) partitioned along rhetorical section boundaries, serving as the unit of ingestion in Layer 1 ($V_1 = C$).

### <span id="concept"></span>Concept
An abstract theoretical entity representing an intellectual notion, paradigm construct, or philosophical category stored as a canonical referential node in Layer 2 ($V_2$), optionally carrying perspective-specific `EntityConception` facets.

### <span id="confidence-score"></span>Confidence Score
A normalized Tier-1 perception metric ($\in [0, 1]$, e.g., $\gamma_v, \gamma_e, \mathcal{P}, \mathcal{C}_{\text{cal}}$) indicating extraction reliability, kept strictly separate from authorial commitment ($M_{\text{mod}}$) and evaluative acceptability ($s_i^*$).

### <span id="constraint-c"></span>Global Constraint ($GC$)
A core component ($GC \subseteq \operatorname{Pot}(M_p)$) demanding that intrinsic theoretical parameters (such as mass, charge, or utility values) maintain invariant or consistent values when identical individuals appear across overlapping intended applications of a theory-element ([Stegmüller, 1976](https://doi.org/10.1007/978-3-642-66440-3); [Balzer et al., 1987](https://doi.org/10.1007/978-94-009-3759-8)). Distinct from intertheoretical links ($GL$).

---

## D

### <span id="degree-centrality"></span>Degree Centrality
A baseline centrality metric counting edges incident to a node. Interpretation in directed graphs depends strictly on edge orientation (e.g., support out-degree counts direct supported consequences, whereas child-to-parent specialization in-degree identifies foundational roots; [Newman, 2018](https://doi.org/10.1093/oso/9780198805090.001.0001)).

### <span id="degenerations-index-lakatosianische-degeneration"></span>Bounded Degeneration Proxy ($D_{\text{deg}}$, Lakatosian Degeneration)
Episteme's project-specific heuristic proxy inspired by [Lakatos (1970)](references.md#lakatos-1970) and [Schurz (2014)](https://doi.org/10.4324/9780203366271), defined over version $T^{(j)} = \mathbf{HC} \cup \Pi^{(j)}$ as $D_{\text{deg}}(T^{(j)}) = \lvert \mathsf{Fail}_b \rvert / (\lvert \mathsf{Succ}^{\text{nov}} \rvert + \lvert \mathsf{Fail}_b \rvert) \in [0, 1]$ (0 on empty denominator) and evaluated as a diachronic trend alongside the overall empirical failure rate $R_{\text{fail}}$.

---

## E

### <span id="eigenvector-centrality"></span>Eigenvector Centrality
A spectral centrality metric where a node's score is proportional to the sum of the centralities of its neighbors ($x_i = \kappa^{-1} \sum_j A_{ij} x_j$; [Newman, 2018](https://doi.org/10.1093/oso/9780198805090.001.0001)). Degenerates to zero on DAGs (nilpotent adjacency matrix) and lacks Perron–Frobenius guarantees on signed graphs; Episteme therefore uses [Katz Centrality](#katz-centrality) and [PageRank](#pagerank) on positive-support or structural projections.

### <span id="empirical-focus-empirischer-fokus"></span><span id="empirischer-fokus-empirical-focus"></span>Empirical Focus (Empirischer Fokus)
The capacity of theoretical terms and their constraints to restrict the volume of admissible observable states, thereby increasing an empirical theory's empirical content and refutability ([Stegmüller, 1976](https://doi.org/10.1007/978-3-642-66440-3)).

### <span id="entity"></span>Entity
A conceptual or real-world object extracted from text into Layer 2 ($V_2$), typed according to an ontology (e.g., *Concept*, *Person*, *Theory*, *Work*, *Institution*).

### <span id="entity-linking"></span>Entity Linking
The algorithmic process of resolving surface text mentions across distinct chunks and documents to a stable canonical Layer 2 node ID using dense vector similarity and cross-encoder reranking.

### <span id="epistemic-cycle-epistemischer-zyklus"></span><span id="epistemischer-zyklus-epistemic-cycle"></span>Epistemic Cycle (Epistemischer Zyklus)
The methodological risk of circular justification arising when a term's measurement or a claim's standing depends solely on a structure whose own validity presupposes that same term or claim ([Stegmüller, 1976](https://doi.org/10.1007/978-3-642-66440-3); [Balzer et al., 1987](https://doi.org/10.1007/978-94-009-3759-8)).

### <span id="event-emitter"></span>Event Emitter / Domain Event Bus
An asynchronous publish-subscribe subsystem broadcasting structured domain events during pipeline execution for telemetry, logging, and Langfuse tracing.

---

## F

### <span id="faithfulness"></span>Faithfulness
An intrinsic evaluation metric measuring whether extracted entities and relations are warranted by verbatim source text spans (exegetical provenance) without hallucination.

### <span id="fusion"></span>Fusion
Phase 5 of the pipeline, which aligns semantically equivalent argument components across documents and computes multi-scale communities via recursive Leiden partitioning.

---

## G

### <span id="graph-schema"></span>Graph Schema
The formal specification of allowed vertex labels, relationship edge types, and property constraints within the property graph.

### <span id="graph-store"></span>Graph Store
The persistent graph database backend (Neo4j) accessed via an asynchronous Cypher driver.

---

## H

### <span id="homogenitat"></span>Homogeneity (Homogenität)
The requirement of structural, semantic, or axiomatic unity within an empirical scientific theory.

* <span id="homogenitat-methodologische-konstruktvaliditat"></span>**Methodological Homogeneity (Konstruktvalidität):** Ensures empirical indicators strongly correlate because they measure a common theoretical latent cause.
* <span id="homogenitat-semantisch-axiomatische"></span>**Semantic-Axiomatic Homogeneity:** A formal non-factorizability criterion over a relevant natural axiomatization $\mathrm{Ax}(T)$ stating that no non-empty partition $\mathrm{Ax}(T) = \mathrm{Ax}_1 \uplus \mathrm{Ax}_2$ satisfies $E_{\text{emp}}(T) = \operatorname{Cn}(E_{\text{emp}}(\mathrm{Ax}_1) \cup E_{\text{emp}}(\mathrm{Ax}_2)) \cap L_E$, preventing conjunctive tacking ([Schurz, 1991](references.md#schurz-1991); [Schurz, 2014](https://doi.org/10.4324/9780203366271); [Gemes, 1993](references.md#gemes-1993)).

---

## I

### <span id="intertheoretische-links-community-bridges"></span>Intertheoretical Links ($GL$) / Community Bridges
Global relations connecting distinct theory-elements across theories or sub-disciplines (distinct from intra-core constraints $GC$), mediating conceptual imports and theoretical reductions ([Balzer et al., 1987](https://doi.org/10.1007/978-94-009-3759-8)).

---

## K

### <span id="katz-centrality"></span>Katz Centrality
An extension of eigenvector centrality assigning a baseline score $\beta$ to all nodes in addition to the attenuated sum of neighbor centralities ($x_i = \alpha \sum_j A_{ij} x_j + \beta$), preventing vanishing scores in directed acyclic topologies ([Newman, 2018](https://doi.org/10.1093/oso/9780198805090.001.0001)).

### <span id="knowledge-graph"></span>Knowledge Graph (KG)
An entity-relational graph representing entities, predicates, and often provenance qualifiers and references (such as Wikidata, ORKG, or Episteme's Layer 2), extended by Epistemic Theory Graphs with formal dialectical semantics and structuralist theory-net layers ([Hogan et al., 2021](references.md#hogan-2021)).

### <span id="kuhn-thomas"></span>Kuhn, Thomas S. (1922–1996)
Historian and philosopher of science who introduced the concepts of scientific *paradigms* (disciplinary matrices and exemplars) and *taxonomic / local incommensurability* ([Kuhn, 1962](references.md#kuhn-1962), [1983](references.md#kuhn-1983), [2000](references.md#kuhn-2000)).

---

## L

### <span id="litellm"></span>LiteLLM
A unified provider-agnostic abstraction layer standardizing API calls to OpenAI, Anthropic, Ollama, and local models.

### <span id="llm-large-language-model"></span>LLM (Large Language Model)
Deep transformer models utilizing billions of parameters for contextual text understanding, extraction, and argument classification.

---

## M

### <span id="misserfolg-typ-a-direkter-widerspruch"></span>Failure Type a / Direct Refutation ($\mathsf{Fail}_a$)
An accepted empirical statement $e \in L_E$ that directly contradicts a theory version $T^{(j)}$ deductively ($T^{(j)} \vdash \neg e$; [Schurz, 2014](https://doi.org/10.4324/9780203366271); [Lakatos, 1970](references.md#lakatos-1970)).

### <span id="misserfolg-typ-b-immunisierter-misserfolg-scheinbarer-erfolg"></span>Failure Type b / Ad-Hoc₁ Immunization ($\mathsf{Fail}_b$)
An empirical anomaly $e$ contradicting $T^{(j)}$ that is absorbed by a protective-belt modification $T^{(j+1)} = \mathbf{HC} \cup \Pi^{(j+1)}$ generating no excess empirical content beyond $e$ under AGM contraction ($E_{\text{emp}}(T^{(j+1)}) \subseteq \operatorname{Cn}((E_{\text{emp}}(T^{(j)}) \div \neg e) \cup \{e\}) \cap L_E$; [Lakatos, 1970](references.md#lakatos-1970); [Alchourrón, Gärdenfors, & Makinson, 1985](references.md#alchourron-1985)).

---

## N

### <span id="ner-named-entity-recognition"></span>NER (Named Entity Recognition)
The process of identifying and categorizing named entities and abstract concepts within text chunks.

### <span id="non-statement-view-modell-ansatz"></span>Non-Statement View / Model-Theoretic Approach (Modell-Ansatz)
The structuralist philosophy of science perspective that reconstructs scientific theories as model-theoretic structures ($T = \langle K, I \rangle$, with $K = \langle M_p, M, M_{pp}, GC, GL \rangle$) rather than sets of sentences; cores are neither true nor false, while their empirical claims $I \in \operatorname{Cn}_{\text{str}}(K)$ are truth-apt ([Sneed, 1971](references.md#sneed-1971); [Stegmüller, 1976](https://doi.org/10.1007/978-3-642-66440-3); [Balzer et al., 1987](https://doi.org/10.1007/978-94-009-3759-8)).

---

## P

### <span id="pagerank"></span>PageRank
A variant of Katz centrality that scales a node's contributed centrality inversely by its out-degree with damping/teleportation, remaining well-defined on directed acyclic graphs ([Newman, 2018](https://doi.org/10.1093/oso/9780198805090.001.0001)).

### <span id="perspektive-historische-adaquatheit"></span>Perspective / Historical Adequacy (Perspektive)
Evaluating a historical theory relative to the contemporary evidential horizon $\mathcal{B}_{\text{hist}}(t)$ and conceptual apparatus available at epoch $t$, avoiding anachronistic evaluation while permitting transparent rational reconstruction ([Stegmüller, 1976](https://doi.org/10.1007/978-3-642-66440-3); [Lakatos, 1971](references.md#lakatos-1971)).

### <span id="phase"></span>Phase
A discrete stage of pipeline execution with strictly defined Pydantic input and output boundaries.

### <span id="prognostische-leistung-prognostic-power"></span>Prognostic Power (Prognostische Leistung)
The capacity of theoretical constraints crossing overlapping application domains to enable strict empirical predictions in previously unmeasured domains ([Stegmüller, 1976](https://doi.org/10.1007/978-3-642-66440-3)).

### <span id="provenance"></span>Provenance
Deterministic exegetical tracking metadata ($\mathrm{Span} \subseteq C \times \mathbb{N}^2$: chunk ID, character offsets, bibliographic source) connecting graph elements directly to verbatim source text. Strictly distinct from within-theory epistemic justification.

---

## R

### <span id="ramsey-sneed-behauptung-ramsey-sneed-sentence"></span>Ramsey–Sneed Empirical Claim (Ramsey–Sneed-Behauptung)
The structuralist empirical claim $I \in \operatorname{Cn}_{\text{str}}(K)$ asserting that intended applications $I \subseteq M_{pp}$ are the non-theoretical restrictions of actual models $X \subseteq M$ satisfying global constraints $GC$ and links $GL$ ([Balzer et al., 1987](https://doi.org/10.1007/978-94-009-3759-8)).

### <span id="relationship"></span>Relationship
A directed multigraph edge token connecting vertices across or within layers, typed by $\lambda_e$ and accompanied by tier-specific attributes.

### <span id="retrospektive-verzerrung-presentism"></span>Retrospective Bias / Anachronism (Presentism)
Illegitimately projecting later doctrines into historical texts (*anachronistic attribution*; [Skinner, 1969](references.md#skinner-1969)) or judging historical rationality by later evidence (*anachronistic evaluation*; [Butterfield, 1931](references.md#butterfield-1931)). Distinct from legitimate **rational reconstruction** using modern formalisms ([Lakatos, 1971](references.md#lakatos-1971); [Rorty, 1984](references.md#rorty-1984)).

---

## S

### <span id="same_as"></span>SAME_AS
A structural equivalence relationship indicating that two entity mentions or argument components across different texts denote the identical canonical referent or proposition.

### <span id="sneedian-structuralism"></span>Sneedian Structuralism
The model-theoretic philosophy-of-science programme initiated by [Sneed (1971)](references.md#sneed-1971) and developed by [Stegmüller (1976)](https://doi.org/10.1007/978-3-642-66440-3) and [Balzer, Moulines, & Sneed (1987)](https://doi.org/10.1007/978-94-009-3759-8), analyzing theories as specialization posets (Theory-Nets) of theory-elements $T = \langle K, I \rangle$.

### <span id="sneedsches-funktionales-kriterium-fur-t-theoretizitat"></span>Sneed's Functional Criterion for $T$-Theoreticity (Sneed'sches Kriterium)
A theory-relative criterion defining a concept or function as $T$-theoretical iff every method of determining its value presupposes the successful application of $T$ — replacing naive observational/unobservable dichotomies ([Sneed, 1971](references.md#sneed-1971); [Balzer et al., 1987](https://doi.org/10.1007/978-94-009-3759-8)).

### <span id="starke-idealisierte-empirische-adaquatheit-newmans-problem"></span>Exact Empirical Adequacy (Starke empirische Adäquatheit)
The idealized structuralist empirical claim $I \in \operatorname{Cn}_{\text{str}}(K)$ without measurement noise; in practice relaxed to [Approximative Empirical Adequacy](#approximative-empirische-adaquatheit-approximative-empirical-adequacy) using admissible blurs $\mathfrak{A}$ ([Balzer et al., 1987](https://doi.org/10.1007/978-94-009-3759-8)).

### <span id="statement-view-satz-ansatz"></span>Statement View (Satz-Ansatz)
The linguistic view of scientific theories as sets of deductive sentences (axioms and consequences), reconciled with structuralism in Episteme via an explicit two-level model linking Layer 3 statements to Layer 4 theory-elements ([Stegmüller, 1976](https://doi.org/10.1007/978-3-642-66440-3); [Schurz, 2014](https://doi.org/10.4324/9780203366271)).

### <span id="stegmuller-wolfgang"></span>Stegmüller, Wolfgang (1923–1991)
Philosopher of science who systematized Sneedian structuralism, proposed the bridge thesis linking Lakatosian research programmes to structuralist theory-nets, and developed a structuralist response defusing radical incommensurability ([Stegmüller, 1976](https://doi.org/10.1007/978-3-642-66440-3)).

---

## T

### <span id="tacking-paradoxie"></span>Tacking Paradox / Irrelevant Conjunction (Klebeparadoxon)
In confirmation theory, the problem that hypothetico-deductive confirmation of $T$ spreads to $T \wedge X$ for arbitrary $X$ ([Glymour, 1980](references.md#glymour-1980); [Fitelson, 2002](references.md#fitelson-2002)); in content-based methodology, the inflation of empirical content ($E_{\text{emp}}(T \wedge X) \supsetneq E_{\text{emp}}(T)$) by conjoining an unrelated testable law $X$. Ruled out by demanding axiomatic [Homogeneity](#homogenitat-semantisch-axiomatische) ([Schurz, 1991](references.md#schurz-1991), [2014](https://doi.org/10.4324/9780203366271)).

### <span id="theorie-baum-theory-tree"></span>Theory-Tree (Theorie-Baum)
A structuralist Theory-Net $\mathcal{N} = \langle N, \sigma \rangle$ with a unique greatest (basic) element $\mathrm{Basic}(\mathcal{N}) = \{T_0\}$ such that every principal up-set $\{T' \in N : T \,\sigma\, T'\}$ is a chain (equivalently, its Hasse diagram is a rooted tree; [Balzer et al., 1987](https://doi.org/10.1007/978-94-009-3759-8)).

### <span id="theorie-holon"></span>Theory-Holon (Theorie-Holon)
The macroscopic inter-theory network connecting distinct scientific theories via intertheoretical links ($GL$), reductions, and presuppositions ([Balzer et al., 1987](https://doi.org/10.1007/978-94-009-3759-8), ch. VIII).

### <span id="theory-graph"></span>Epistemic Theory Graph ($G$)
Episteme's stratified four-layer labeled directed multigraph $G = (V_1 \uplus V_2 \uplus V_3 \uplus V_4, E_{\text{intra}} \uplus E_{\text{inter}}, \mathrm{src}, \mathrm{tgt}, \lambda_v, \lambda_e)$ integrating verbatim source provenance ($L_1$), canonical entity ABox ($L_2$), bipartite Dialectical Argument Graph $\mathcal{D}$ ($L_3$), and Structuralist Theory-Net projection $\mathcal{N}$ ($L_4$). Distinct from MMT/OMDoc formal theory graphs ([Rabe & Kohlhase, 2013](references.md#rabe-2013)).

### <span id="triple"></span>Triple
A subject–predicate–object factual assertion in Layer 2 ($E_2$) carrying Tier-1 extraction confidence ($\gamma_e$) and verbatim span provenance ($\mathrm{prov}_2$).

---

## V

### <span id="vector-index"></span>Vector Index
Neo4j or in-memory vector index enabling dense Maximum Inner Product Search (MIPS) over contextual embeddings ($\mathrm{emb}_{\text{ctx}}$).

---

## W

### <span id="workflow"></span>Workflow
The coordinated execution sequence of pipeline phases transforming raw documents into materialized Epistemic Theory Graphs.

---

## Z

### <span id="zulassige-unscharfen-admissible-blurs-a"></span>Admissible Blurs (Zulässige Unschärfen, $\mathfrak{A}$)
The pragmatically bounded sub-family $\mathfrak{A} \subseteq \mathcal{U}$ of entourage relations within a Bourbaki uniform space $(M_p, \mathcal{U})$, inducing set-level blurs $\tilde{u}$ on $\operatorname{Pot}(M_{pp})$ for approximative empirical adequacy ([Balzer et al., 1987](https://doi.org/10.1007/978-94-009-3759-8), ch. VII).
