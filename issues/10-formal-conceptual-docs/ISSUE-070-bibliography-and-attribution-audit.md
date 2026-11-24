# [ISSUE-070] Bibliography, Citation Practice & Attribution Audit

| Metadata              | Details                                                                                                                                                                                                                                                                                         |
|:----------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Issue ID**          | `ISSUE-070`                                                                                                                                                                                                                                                                                     |
| **Domain / Category** | `10-Formal & Conceptual Docs` — cross-cutting (supports a–d)                                                                                                                                                                                                                                    |
| **Evaluated Docs**    | all four concept documents                                                                                                                                                                                                                                                                      |
| **Priority**          | **High** (wrong citations are the fastest way to lose a reviewer's trust)                                                                                                                                                                                                                       |
| **Status**            | `Open`                                                                                                                                                                                                                                                                                          |

---

## E-01 · Erroneous bibliographic data — **Major**

| # | Where                                                                                                       | As written                                                                                                     | Correction                                                                                                                                                                                                                         |
|:--|:------------------------------------------------------------------------------------------------------------|:---------------------------------------------------------------------------------------------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | [`kg_vs_tg.md#L122`](../../docs/concepts/kg_vs_tg.md#L122), [`#L151`](../../docs/concepts/kg_vs_tg.md#L151) | Lawrence & Reed, **2020**, `https://doi.org/10.1613/jair.1.12028`                                               | Lawrence, J., & Reed, C. (**2019**). Argument Mining: A Survey. *Computational Linguistics*, 45(4), 765–818. **doi:10.1162/coli_a_00364**. The JAIR DOI could not be resolved to this (or any matching) paper.                     |
| 2 | [`epistemology.md#L241`](../../docs/concepts/epistemology.md#L241)                                          | Sneed, J. D. (**1976**). *The Logical Structure of Mathematical Physics*                                        | Sneed (**1971**), Reidel; 2nd rev. ed. **1979**. Also inconsistent with `kg_vs_tg.md` L147 and `formal_graph_model.md` L299 ("Sneed, 1971"). EPI L5-6 ("Sneed and Stegmüller (1976)") should be split.                             |
| 3 | [`epistemology.md#L246`](../../docs/concepts/epistemology.md#L246)                                          | Duhem (1906). *La théorie physique: son objet, **et** sa structure*. **Marcel Rivière**.                         | *La théorie physique : son objet et sa structure*. Paris: **Chevalier & Rivière**, 1906 (2nd ed. Marcel Rivière, 1914). Engl. tr. *The Aim and Structure of Physical Theory*, Princeton UP, 1954.                                    |
| 4 | [`epistemology.md#L240`](../../docs/concepts/epistemology.md#L240)                                          | Lakatos (1978) …                                                                                                | Add editors: J. Worrall & G. Currie (eds.). For the ad-hoc taxonomy and rational reconstruction, also cite Lakatos (1970) and (1971) directly.                                                                                      |

## E-02 · Cited in text but absent from any reference list — **Major**

`kg_vs_tg.md`, `formal_graph_model.md` and `theory_nets_and_topologies.md` have **no reference list**. Works cited in
text with no full entry:

| Work                                                     | Cited at                          |
|:---------------------------------------------------------|:----------------------------------|
| Balzer, Moulines & Sneed (1987)                          | KG L23, L147; FGM L300; TN L12, L77 |
| Kuhn (1962)                                              | KG L116                           |
| Popper (no year)                                         | EPI L75                           |
| Toulmin (1958)                                           | FGM L199-202                      |
| Potyka (2018)                                            | FGM L241                          |
| Traag et al. (2019)                                      | TN L140                           |
| Dung (no year)                                           | KG L130; FGM L256                 |
| Bourbaki                                                 | TN L47                            |
| Nagumo, Gershgorin, Hirsch                               | FGM L238-241                      |
| Keynes, Gärdenfors                                       | FGM L246                          |
| DL-Lite$_R$                                              | FGM L145                          |
| Neurath                                                  | EPI L51                           |
| "Conformal Prediction / Jev"                             | FGM L192, L205                    |
| **"Prakken (2020) Constellations"**                      | FGM L204                          |

The Prakken reference could not be identified. Remove it or give the full reference.

## E-03 · Attributions to verify or relabel as own contributions — **Major**

| Claim                                                                  | Status                                                                                                                                                                                                                                                                              |
|:-----------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Schurz: "four primary methodological criteria" (EPI L16)               | Needs chapter/page. The section grouping does not match a four-item list (A-16).                                                                                                                                                                                                   |
| Schurz: "four-dimensional framework of theory statics" (EPI L96)       | Needs chapter/page. Likely a project synthesis.                                                                                                                                                                                                                                    |
| Schurz: Degeneration Index $D$ and failure types a/b (EPI L177-189)    | Not located. If own, say so (B-05).                                                                                                                                                                                                                                               |
| Schurz: $Z_1$ "correlational" / $Z_2$ "structural isomorphism" (FGM L276) | No basis found; project-specific (D-03).                                                                                                                                                                                                                                          |
| "Keynes–Gärdenfors formulation" (FGM L246)                             | Keynes (1921, ch. VI) introduced *weight of evidence*; Gärdenfors & Sahlin (1982) *epistemic reliability*. The formulas $E_{\text{total}}$ and $\mathcal{V}$ are the project's own and should be labelled "inspired by" (B-19).                                                         |
| "Correction to Potyka 2018" (FGM L241)                                  | Potyka (2018) and the *Attractor* tutorial do recommend $\delta=0.01$ on bounded-derivative grounds, so the attribution is plausible. The "correction" itself is mathematically unsupported (B-16). Quote Potyka verbatim, with page, if retained.                                    |
| Thagard TEC principles (EPI L203-219)                                  | Misreported (D-10).                                                                                                                                                                                                                                                                |
| ECHO weights $+0.05$ / $-0.20$ (TN L115-117)                           | Consistent with values reported for Thagard (1989). Later ECHO work commonly uses excitation $.04$, inhibition $-.06$, decay $.05$. State the source edition.                                                                                                                       |
| "Toulminian argument schemes" (FGM L190)                               | Argument schemes are Walton's (Walton, Reed & Macagno 2008). Toulmin's layout is not a scheme typology (C-09).                                                                                                                                                                   |
| Stegmüller (1976) as support for incommensurability (KG L116)          | Inverted; Stegmüller defuses incommensurability (D-13).                                                                                                                                                                                                                            |
| Lakatos (1978) for "empirical creativity" (KG L140-141)                | Empirical creativity is Schurz's concept (C-18).                                                                                                                                                                                                                                  |
| Balzer et al. & Schurz for "defeasible warrants" (KG L22-23)           | "Defeasible warrant" is from argumentation theory (Toulmin; Pollock), not structuralism or Schurz.                                                                                                                                                                                |
| Specialisation symbol $\alpha$ (TN L42)                                 | BMS (1987) use $\sigma$.                                                                                                                                                                                                                                                           |

## E-04 · Citation practice — **Minor**

- **Internal links are used as citations.** In-text author–year citations hyperlink to *internal documents* or the
  glossary ([KG L23](../../docs/concepts/kg_vs_tg.md#L23), [L116](../../docs/concepts/kg_vs_tg.md#L116),
  [L147](../../docs/concepts/kg_vs_tg.md#L147)) instead of reference entries. For publication, every author–year
  citation must resolve to a bibliography entry. Internal cross-references should be visually distinct ("see §…").
- **No page or chapter numbers.** Monographs (Schurz 2014; BMS 1987; Stegmüller 1976; Lakatos 1978) are cited without
  them. That is unacceptable for the formula-level attributions above.
- **Recommendation.** Maintain one shared `docs/concepts/references.bib` (or `references.md`) and cite from all four
  documents.

---

## E-05 · Proposed consolidated bibliography

The entries below are cited across ISSUE-066 to ISSUE-070. They are listed so the documents can add them directly
(check page ranges against your library before publishing).

**Argumentation & argument mining**

- Baroni, P., Rago, A., & Toni, F. (2019). From fine-grained properties to broad principles for gradual argumentation: A principled spectrum. *IJAR*, 105, 252–286.
- Cayrol, C., & Lagasquie-Schiex, M.-C. (2005). On the acceptability of arguments in bipolar argumentation frameworks. *ECSQARU 2005*, LNCS 3571, 378–389.
- Cayrol, C., & Lagasquie-Schiex, M.-C. (2013). Bipolarity in argumentation graphs: Towards a better understanding. *IJAR*, 54(7), 876–899.
- Chesñevar, C., et al. (2006). Towards an argument interchange format. *Knowledge Engineering Review*, 21(4), 293–316.
- Cohen, A., Gottifredi, S., García, A. J., & Simari, G. R. (2014). A survey of different approaches to support in argumentation systems. *Knowledge Engineering Review*, 29(5), 513–550.
- Dimopoulos, Y., & Torres, A. (1996). Graph theoretical structures in logic programs and default theories. *TCS*, 170(1–2), 209–244.
- Dung, P. M. (1995). On the acceptability of arguments and its fundamental role in nonmonotonic reasoning, logic programming and n-person games. *AIJ*, 77(2), 321–357.
- Dunne, P. E., & Bench-Capon, T. J. M. (2002). Coherence in finite argument systems. *AIJ*, 141(1–2), 187–203.
- Dvořák, W., & Dunne, P. E. (2018). Computational problems in formal argumentation and their complexity. In *Handbook of Formal Argumentation*, College Publications.
- Freeman, J. B. (1991). *Dialectics and the Macrostructure of Arguments*. Foris.
- Lawrence, J., & Reed, C. (2019). Argument Mining: A Survey. *Computational Linguistics*, 45(4), 765–818.
- Modgil, S., & Prakken, H. (2014). The ASPIC+ framework for structured argumentation: A tutorial. *Argument & Computation*, 5(1), 31–62.
- Mossakowski, T., & Neuhaus, F. (2018). Modular semantics and characteristics for bipolar weighted argumentation graphs. arXiv preprint.
- Nielsen, S. H., & Parsons, S. (2006). A generalization of Dung's abstract framework for argumentation: Arguing with sets of attacking arguments. *ArgMAS 2006*, LNCS 4766.
- Peldszus, A., & Stede, M. (2013). From argument diagrams to argumentation mining in texts: A survey. *IJCINI*, 7(1), 1–31.
- Pollock, J. L. (1987). Defeasible reasoning. *Cognitive Science*, 11(4), 481–518.
- Potyka, N. (2018). Continuous dynamical systems for weighted bipolar argumentation. *KR 2018*, 148–157.
- Stab, C., & Gurevych, I. (2017). Parsing argumentation structures in persuasive essays. *Computational Linguistics*, 43(3), 619–659.
- Toulmin, S. (1958). *The Uses of Argument*. Cambridge UP.
- Walton, D., Reed, C., & Macagno, F. (2008). *Argumentation Schemes*. Cambridge UP.

**Logic, belief revision, uncertainty**

- Alchourrón, C., Gärdenfors, P., & Makinson, D. (1985). On the logic of theory change. *JSL*, 50(2), 510–530.
- Angelopoulos, A. N., & Bates, S. (2023). Conformal prediction: A gentle introduction. *Foundations and Trends in ML*, 16(4), 494–591.
- Calvanese, D., De Giacomo, G., Lembo, D., Lenzerini, M., & Rosati, R. (2007). Tractable reasoning and efficient query answering in description logics: The DL-Lite family. *JAR*, 39(3), 385–429.
- Dubois, D., & Prade, H. (1988). *Possibility Theory*. Plenum.
- Gärdenfors, P., & Sahlin, N.-E. (1982). Unreliable probabilities, risk taking, and decision making. *Synthese*, 53(3), 361–386.
- Guo, C., Pleiss, G., Sun, Y., & Weinberger, K. Q. (2017). On calibration of modern neural networks. *ICML 2017*.
- Jøsang, A. (2016). *Subjective Logic*. Springer.
- Keynes, J. M. (1921). *A Treatise on Probability*. Macmillan.
- Kyburg, H. E. (1961). *Probability and the Logic of Rational Belief*. Wesleyan UP.
- Reiter, R. (1980). A logic for default reasoning. *AIJ*, 13(1–2), 81–132.
- Rescher, N., & Manor, R. (1970). On inference from inconsistent premisses. *Theory and Decision*, 1(2), 179–217.

**Dynamical systems & numerics**

- Filippov, A. F. (1988). *Differential Equations with Discontinuous Righthand Sides*. Kluwer.
- Hairer, E., & Wanner, G. (1996). *Solving Ordinary Differential Equations II* (2nd ed.). Springer.
- Hirsch, M. W. (1985). Systems of differential equations that are competitive or cooperative II: Convergence almost everywhere. *SIAM J. Math. Anal.*, 16(3), 423–439.
- Hopfield, J. J. (1982). Neural networks and physical systems with emergent collective computational abilities. *PNAS*, 79(8), 2554–2558.
- Smith, H. L. (1995). *Monotone Dynamical Systems*. AMS Mathematical Surveys and Monographs 41.

**Knowledge graphs & scholarly knowledge**

- Groth, P., Gibson, A., & Velterop, J. (2010). The anatomy of a nanopublication. *Information Services & Use*, 30(1–2), 51–56.
- Hogan, A., et al. (2021). Knowledge graphs. *ACM Computing Surveys*, 54(4), Article 71.
- Jaradeh, M. Y., et al. (2019). Open Research Knowledge Graph: Next generation infrastructure for semantic scholarly knowledge. *K-CAP 2019*.
- Kohlhase, M. (2014). Mathematical knowledge management: Transcending the one-brain-barrier with theory graphs. *EMS Newsletter*, 92, 22–27.
- Rabe, F., & Kohlhase, M. (2013). A scalable module system. *Information and Computation*, 230, 1–54.
- Vrandečić, D., & Krötzsch, M. (2014). Wikidata: A free collaborative knowledgebase. *CACM*, 57(10), 78–85.

**Network science**

- Fortunato, S., & Barthélemy, M. (2007). Resolution limit in community detection. *PNAS*, 104(1), 36–41.
- Guimerà, R., & Amaral, L. A. N. (2005). Functional cartography of complex metabolic networks. *Nature*, 433, 895–900.
- Traag, V. A., & Bruggeman, J. (2009). Community detection in networks with positive and negative links. *Phys. Rev. E*, 80, 036115.
- Traag, V. A., Waltman, L., & van Eck, N. J. (2019). From Louvain to Leiden: Guaranteeing well-connected communities. *Scientific Reports*, 9, 5233.

**Philosophy of science & epistemology**

- Balzer, W., Moulines, C. U., & Sneed, J. D. (1987). *An Architectonic for Science: The Structuralist Program*. Reidel.
- Balzer, W., Sneed, J. D., & Moulines, C. U. (Eds.) (2000). *Structuralist Knowledge Representation: Paradigmatic Examples*. Rodopi.
- Belnap, N. (1993). On rigorous definitions. *Philosophical Studies*, 72(2–3), 115–146.
- Carnap, R. (1956). The methodological character of theoretical concepts. *Minnesota Studies in the Philosophy of Science*, 1, 38–76.
- Daniels, N. (1979). Wide reflective equilibrium and theory acceptance in ethics. *Journal of Philosophy*, 76(5), 256–282.
- Duhem, P. (1906). *La théorie physique : son objet et sa structure*. Chevalier & Rivière.
- Feyerabend, P. (1962). Explanation, reduction, and empiricism. *Minnesota Studies*, 3, 28–97.
- Fitelson, B. (2002). Putting the irrelevance back into the problem of irrelevant conjunction. *Philosophy of Science*, 69(4), 611–622.
- Fodor, J., & Lepore, E. (1992). *Holism: A Shopper's Guide*. Blackwell.
- Friedman, M. (1974). Explanation and scientific understanding. *Journal of Philosophy*, 71(1), 5–19.
- Gemes, K. (1993). Hypothetico-deductivism, content, and the natural axiomatization of theories. *Philosophy of Science*, 60(3), 477–487.
- Glymour, C. (1980). *Theory and Evidence*. Princeton UP.
- Goodman, N. (1955). *Fact, Fiction, and Forecast*. Harvard UP.
- Haack, S. (1993). *Evidence and Inquiry*. Blackwell.
- Hanson, N. R. (1958). *Patterns of Discovery*. Cambridge UP.
- Hempel, C. G. (1950). Problems and changes in the empiricist criterion of meaning. *Revue Internationale de Philosophie*, 11, 41–63.
- Hempel, C. G., & Oppenheim, P. (1948). Studies in the logic of explanation. *Philosophy of Science*, 15(2), 135–175.
- Kellert, S. H., Longino, H. E., & Waters, C. K. (Eds.) (2006). *Scientific Pluralism*. Minnesota Studies 19.
- Kitcher, P. (1981). Explanatory unification. *Philosophy of Science*, 48(4), 507–531.
- Kuhn, T. S. (1962). *The Structure of Scientific Revolutions*. University of Chicago Press.
- Kuhn, T. S. (1983). Commensurability, comparability, communicability. *PSA 1982*, vol. 2, 669–688.
- Kuhn, T. S. (2000). *The Road since Structure*. University of Chicago Press.
- Kuipers, T. A. F. (2000). *From Instrumentalism to Constructive Realism*. Kluwer.
- Lakatos, I. (1970). Falsification and the methodology of scientific research programmes. In Lakatos & Musgrave (Eds.), *Criticism and the Growth of Knowledge* (pp. 91–196). Cambridge UP.
- Lakatos, I. (1971). History of science and its rational reconstructions. *Boston Studies in the Philosophy of Science*, 8, 91–136.
- Lynch, M. P. (2009). *Truth as One and Many*. Oxford UP.
- Popper, K. R. (1959). *The Logic of Scientific Discovery*. Hutchinson.
- Quine, W. V. O. (1951). Two dogmas of empiricism. *Philosophical Review*, 60(1), 20–43.
- Rawls, J. (1971). *A Theory of Justice*. Harvard UP.
- Schurz, G. (1991). Relevant deduction. *Erkenntnis*, 35, 391–437.
- Schurz, G. (2014). *Philosophy of Science: A Unified Approach*. Routledge.
- Schurz, G., & Lambert, K. (1994). Outline of a theory of scientific understanding. *Synthese*, 101(1), 65–120.
- Sneed, J. D. (1971). *The Logical Structure of Mathematical Physics*. Reidel (2nd ed. 1979).
- Stegmüller, W. (1976). *The Structure and Dynamics of Theories*. Springer.
- Thagard, P. (1978). The best explanation: Criteria for theory choice. *Journal of Philosophy*, 75(2), 76–92.
- Thagard, P. (1989). Explanatory coherence. *Behavioral and Brain Sciences*, 12(3), 435–467.
- Thagard, P. (1992). *Conceptual Revolutions*. Princeton UP.
- Thagard, P., & Verbeurgt, K. (1998). Coherence as constraint satisfaction. *Cognitive Science*, 22(1), 1–24.
- Worrall, J. (1985). Scientific discovery and theory-confirmation. In J. C. Pitt (Ed.), *Change and Progress in Modern Science*. Reidel.
- Wright, C. (1992). *Truth and Objectivity*. Harvard UP.
- Zahar, E. (1973). Why did Einstein's programme supersede Lorentz's? *BJPS*, 24(2), 95–123; 24(3), 223–262.

**Historiography, hermeneutics, Kant, rhetoric**

- Butterfield, H. (1931). *The Whig Interpretation of History*. G. Bell.
- Gadamer, H.-G. (1960). *Wahrheit und Methode*. Mohr (Siebeck).
- Hyland, K. (1998). *Hedging in Scientific Research Articles*. John Benjamins.
- Paton, H. J. (1947). *The Categorical Imperative*. Hutchinson.
- Rorty, R. (1984). The historiography of philosophy: Four genres. In Rorty, Schneewind & Skinner (Eds.), *Philosophy in History* (pp. 49–75). Cambridge UP.
- Skinner, Q. (1969). Meaning and understanding in the history of ideas. *History and Theory*, 8(1), 3–53.
- Wood, A. W. (1999). *Kant's Ethical Thought*. Cambridge UP.
