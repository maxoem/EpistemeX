# [ISSUE-067] Mathematical & Formal-Logical Errors in the Conceptual Formalisms

| Metadata              | Details                                                                                                                                                                                                                                                                     |
|:----------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Issue ID**          | `ISSUE-067`                                                                                                                                                                                                                                                                 |
| **Domain / Category** | `10-Formal & Conceptual Docs` — (b) Mathematical errors & issues                                                                                                                                                                                                            |
| **Evaluated Docs**    | [`epistemology.md`](../../docs/concepts/epistemology.md), [`formal_graph_model.md`](../../docs/concepts/formal_graph_model.md), [`theory_nets_and_topologies.md`](../../docs/concepts/theory_nets_and_topologies.md)                                                           |
| **Priority**          | **Critical**                                                                                                                                                                                                                                                                |
| **Status**            | `Open`                                                                                                                                                                                                                                                                      |
| **Related**           | [`ISSUE-066`](ISSUE-066-cross-document-inconsistencies-and-notation.md) (notation table A-03)                                                                                                                                                                              |

Throughout, $L_E$ is the empirical sub-language, $\operatorname{Cn}$ is classical consequence, and
$E(X) := \operatorname{Cn}(X)\cap L_E$ is empirical content.

> [!NOTE]
> **Verified as correct** (no action needed beyond notation):
> - the Potyka (2018) quadratic-energy update form;
> - forward invariance of $[0,1]^n$ (Prop. 2; check: $\dot s_i\rvert_{s_i=1} = (w_i-1)(1-h(E_i)) - w_i h(-E_i) \le 0$ and $\dot s_i\rvert_{s_i=0} = w_i(1-h(-E_i)) + (1-w_i)h(E_i)\ge 0$);
> - $\lvert\dot s_i\rvert<1$;
> - the Gershgorin constant $0.65 \approx \max_x h'(x) = h'(1/\sqrt3) = 9/(8\sqrt3)\approx 0.6495$;
> - the DAG fixed-point formula of Prop. 5 and its $O(\lvert\mathcal A\rvert+\lvert\mathcal R\rvert)$ complexity;
> - Prop. 1 (pointwise convergence off $x=\tau$);
> - ECHO harmony $H=\sum_{ij}w_{ij}a_ia_j$;
> - the three poset axioms;
> - the strict-partial-order property of the progress relation.

---

## Part I — `epistemology.md`

### B-01 · The empirical-creativity criterion is trivially satisfied — **Critical**

**Where.** [`epistemology.md#L25-L31`](../../docs/concepts/epistemology.md#L25-L31).

The stated criterion is $E(H_1\wedge H_2)\supset E(H_1)\cup E(H_2)$.

**Counter-argument.** $E(\cdot)$ is closed under conjunction. Take any $e_1\in E(H_1)\setminus\operatorname{Cn}(E(H_2))$
and $e_2\in E(H_2)\setminus\operatorname{Cn}(E(H_1))$. Then $e_1\wedge e_2\in E(H_1\wedge H_2)$, but $e_1\wedge e_2$ is in
neither $E(H_1)$ nor $E(H_2)$. So **every** pair of hypotheses with independent empirical content is "creative".
This includes the tacked conjunction *physics ∧ "telepathy exists"* that the document's own §Homogeneity treats as the
paradigm of non-creativity (see A-08).

Secondary issues:

- $\supset$ is ambiguous: it means $\supseteq$ in some conventions and material implication in others. Use $\supsetneq$.
- "Observable deductive consequences" (L26) conflicts with $\operatorname{Cn}$ including "probabilistically entailed"
  sentences (L142–143; see B-07).

**Correction.**

$$
H_1\wedge H_2 \text{ is empirically creative} \iff E(H_1\wedge H_2) \supsetneq \operatorname{Cn}\big(E(H_1)\cup E(H_2)\big)\cap L_E,
$$

i.e. $\exists e\in L_E:\; H_1\wedge H_2\vdash e$ and $E(H_1)\cup E(H_2)\nvdash e$.

---

### B-02 · The homogeneity (non-factorizability) definition is degenerate — **Critical**

**Where.** [`epistemology.md#L82-L89`](../../docs/concepts/epistemology.md#L82-L89).

As written, $T$ is heterogeneous if $T\equiv T_1\wedge T_2$, $E(T)=\operatorname{Cn}(E_1\cup E_2)$, $T_1\vdash E_1$,
$T_2\vdash E_2$, with $E_1,E_2$ "disjoint". This fails in four ways:

1. **Trivial factorization.** $T\equiv T\wedge\top$ with $T_1=T$, $T_2=\top$, $E_1=E(T)$, $E_2=\emptyset$ satisfies the
   condition. Likewise $T\equiv T\wedge T$. **Every theory is factorizable.**
2. **Disguised factorization.** Even if $T_i\nvdash T$ is required, $T\equiv(T\vee p)\wedge(T\vee\neg p)$ with $p\in L_E$
   yields $\operatorname{Cn}(E(T\vee p)\cup E(T\vee\neg p))\supseteq E(T)$ (since $e\vee p$ and $e\vee\neg p$ give $e$).
   This is the well-known content-part problem (Gemes 1993; Schurz 1991).
3. **"Disjoint" is unsatisfiable** for deductively closed sets, which always share the tautologies. It must mean
   "disjoint modulo logical truth" or "disjoint non-logical vocabulary".
4. $T_i\vdash E_i$ only says $E_i\subseteq E(T_i)$. The condition must be stated with $E_i=E(T_i)$, otherwise
   $E_1,E_2$ can be chosen arbitrarily small.

**Correction (uses the documents' own natural axioms $Ax(T)$).**
$T$ is *factorizable* iff there is a partition $Ax(T)=Ax_1\uplus Ax_2$ into non-empty parts such that

$$
E(T) = \operatorname{Cn}\big(E(Ax_1)\cup E(Ax_2)\big)\cap L_E .
$$

$T$ is *homogeneous* iff it is not factorizable. This makes homogeneity exactly "creativity for **every** split of the
natural axioms" and fixes A-08. Cite Schurz's relevance-based natural axiomatisation (or Gemes 1993) for $Ax(T)$.

---

### B-03 · The progress order misstates the comparative criterion — **Major**

**Where.** [`epistemology.md#L60-L71`](../../docs/concepts/epistemology.md#L60-L71).

$E(T_1)\supseteq E(T_2)\wedge M(T_1)\subset M(T_2)$:

- **Excludes** the standard case of progress where successes grow and failures stay equal
  ($E_1\supsetneq E_2$, $M_1=M_2$).
- **Contradicts its own gloss.** "Progress requires *expanding* verified successes" (L70), while the formula allows
  $E_1=E_2$.
- **Presupposes a common individuation of phenomena** for $T_1,T_2$. This is precisely what incommensurability, raised
  in `kg_vs_tg.md` L111–116, denies (D-13).
- **Overloads $E$**: here it means successes, two sections earlier it means empirical content (A-03).

**Correction.** The standard comparative criterion (as in Schurz 2014, ch. 5; Kuipers 2000) is

$$
T_1 \succ T_2 \iff \mathsf{Succ}(T_2)\subseteq\mathsf{Succ}(T_1)\;\wedge\;\mathsf{Fail}(T_1)\subseteq\mathsf{Fail}(T_2)\;\wedge\;\text{at least one inclusion strict}.
$$

This is a strict partial order (irreflexive, transitive). Rename "rational scientific progress" to "empirically more
successful". Rationality of theory choice is a further claim.

---

### B-04 · The ad-hoc ("Type b") condition is never satisfiable and modifies the hard core — **Critical**

**Where.** [`epistemology.md#L179-L181`](../../docs/concepts/epistemology.md#L179-L181).

The condition reads $\operatorname{Cn}(K_{i+1})\setminus\{a\}\subseteq\operatorname{Cn}(K_i)$.

1. **$a$ is undefined.** It could be the anomaly or the auxiliary hypothesis.
2. **Never satisfied.** $\operatorname{Cn}(K_{i+1})$ is deductively closed. Removing the single sentence $a$ leaves
   $a\wedge a$, $a\wedge\top$, $a\wedge k$ ($k\in K_i$), …, none of which (for non-trivial new $a$) is in
   $\operatorname{Cn}(K_i)$. Removing one sentence from an infinite closed set never "subtracts" its content.
3. **If $a$ is the anomaly**, $K_i\vdash\neg a$, so $\operatorname{Cn}(K_i)$ and $\operatorname{Cn}(K_{i+1})$ disagree
   on $a$ itself, and the inclusion test is ill-posed. Comparison needs a *contraction* of $\neg a$.
4. **It is applied to $K$** (the hard core), whose constancy defines a Lakatosian programme (A-10).
5. **It captures only Lakatos's *ad hoc₁***. Lakatos (1970; 1971) distinguishes ad hoc₁ (no excess empirical
   content), ad hoc₂ (excess content not corroborated), and ad hoc₃ (not generated by the positive heuristic).

**Correction.** Let $T^{(j)}=\mathbf{HC}\cup\Pi^{(j)}$, with anomaly $e$ ($T^{(j)}\vdash\neg e$). The modification
$T^{(j+1)}$ accommodates $e$ **ad hoc₁** iff $T^{(j+1)}\nvdash\neg e$ and

$$
E(T^{(j+1)}) \subseteq \operatorname{Cn}\big((E(T^{(j)}) \div \neg e)\cup\{e\}\big)\cap L_E ,
$$

with $\div$ an AGM contraction (Alchourrón, Gärdenfors & Makinson 1985): *no empirical consequence beyond the
accommodated fact*.

---

### B-05 · The Degeneration Index is ill-defined and anti-monotone — **Major**

**Where.** [`epistemology.md#L185-L194`](../../docs/concepts/epistemology.md#L185-L194).

The index is $D=\lvert M_b\rvert/(\lvert E\rvert+\lvert M_a\rvert)$.

1. **Division by zero.** It is undefined when $\lvert E\rvert+\lvert M_a\rvert=0$, i.e. for a version consisting *only*
   of ad-hoc patches. That is the most degenerate case.
2. **Perverse monotonicity.** $\partial D/\partial\lvert M_a\rvert<0$: *more direct refutations make a programme look
   less degenerate*.
3. **Unbounded.** $D\in[0,\infty)$, so "$D\gg0$" has no scale. "$D\to0$" uses limit notation without a sequence.
4. **Counting.** It contradicts L69 (A-06) and needs a canonical individuation of "phenomena". Without one, $D$ is not
   invariant under splitting or merging anomalies.
5. **Attribution.** "Schurz operationalizes Lakatos's criterion through the Degeneration Index" needs an exact
   chapter and page. We could not locate this formula in Schurz (2014). See [`ISSUE-070`](ISSUE-070-bibliography-and-attribution-audit.md).

**Correction (if a scalar is wanted).** Use
$D=\lvert\mathsf{Fail}_b\rvert/(\lvert\mathsf{Succ}\rvert+\lvert\mathsf{Fail}_a\rvert+\lvert\mathsf{Fail}_b\rvert)\in[0,1]$,
with $D:=0$ for an empty denominator, i.e. the share of ad-hoc accommodations among all empirical interactions. Evaluate
it as a **trend over versions** $j\mapsto D(T^{(j)})$, since Lakatos's notion is defined over problem shifts. Label it
explicitly as a project-specific proxy.

---

### B-06 · Further formal slips in `epistemology.md` — **Minor**

- [L142–143](../../docs/concepts/epistemology.md#L142-L143): "$Ax(T)\vdash\operatorname{Cn}(T)$". Write
  $\operatorname{Cn}(T)=\{\varphi: Ax(T)\vdash\varphi\}$.
- [L110](../../docs/concepts/epistemology.md#L110) uses $C(T)$, the text uses $\operatorname{Cn}(T)$.
- [L188](../../docs/concepts/epistemology.md#L188): German subscripts inside formulas; two symbol sets in parallel.
- [L217](../../docs/concepts/epistemology.md#L217): ECHO activations lie in $[-1,1]$ (Thagard 1989). This is not stated,
  and it clashes with $[0,1]$ elsewhere (A-12).

### B-07 · "Logically **or probabilistically** entailed" breaks $\operatorname{Cn}$ — **Major**

**Where.** [`epistemology.md#L142-L143`](../../docs/concepts/epistemology.md#L142-L143).

$\operatorname{Cn}$ is a Tarskian closure operator (reflexive, monotone, idempotent, closed under conjunction). High-probability
consequence is **not closed under conjunction** (lottery paradox; Kyburg 1961). Mixing the two invalidates B-01, B-02
and B-04, which rely on conjunction closure.
**Fix.** Keep $\operatorname{Cn}$ deductive. Treat probabilistic support as a separate graded relation, e.g. via
$\mathcal{I}$ on edges.

---

## Part II — `formal_graph_model.md`

### B-08 · A multigraph cannot have $E\subseteq V\times V$ — **Major**

**Where.** [`#L12-L22`](../../docs/concepts/formal_graph_model.md#L12-L22).

With $E\subseteq V\times V$ there is at most one edge per ordered pair, so $G$ is a **simple** digraph, not a
multigraph. Then $\lambda_e:E\to T_e$ allows only one relation type per pair. In practice a pair can be connected by,
e.g., `SUPPORTS` and `SPECIALIZES`.
**Fix.** Either $E$ is an abstract finite set with $\mathrm{src},\mathrm{tgt}:E\to V$, or $E\subseteq V\times T_e\times V$.
The same applies to $\mathcal{E}_{L2}$ (L112).

### B-09 · "Isomorphism" $V\cong At$, $E\cong R$ is ill-typed — **Major**

**Where.** [`#L31-L35`](../../docs/concepts/formal_graph_model.md#L31-L35).

- Between bare sets, "$\cong$" is just a bijection. A *graph* isomorphism requires a bijection $f:V\to At$ with
  $(u,v)\in E\iff(f(u),f(v))\in R$, and label preservation.
- $R$ is described as "the set of argumentative **relations**" (relation *types*). An edge-to-type bijection is a
  category error.
- $V$ contains entities that are not atoms (A-02).

**Fix.** Define $(At,R)$ as the **induced labelled subgraph** $G[V_3]$, with $R=E\cap(V_3\times T_e^{\text{arg}}\times V_3)$.

### B-10 · Score functions are equated with type labellings — **Major**

**Where.** [`#L164-L166`](../../docs/concepts/formal_graph_model.md#L164-L166).

The text sets "$\tau$ … (vertex labeling $\lambda_v$)" and "$\phi$ … (edge labeling $\lambda_e$)". But
$\lambda_v:V\to T_v$ and $\lambda_e:E\to T_e$ map into type hierarchies, while $\tau,\phi$ map into $[0,1]$.
**Fix.** Introduce separate attribute maps, e.g. $\beta:V_3\to[0,1]$ and $\omega:E_3\to[0,1]$.

### B-11 · Three incompatible argument sets — **Major**

**Where.** [L127](../../docs/concepts/formal_graph_model.md#L127), [L161](../../docs/concepts/formal_graph_model.md#L161), [L185](../../docs/concepts/formal_graph_model.md#L185), [L258](../../docs/concepts/formal_graph_model.md#L258).

1. In $\Lambda$, $A$ = "Claims or Premises" ($a\in\mathcal{V}_{L3}$).
2. Elsewhere in $\Lambda$, $A$ = "theoretical antecedents", which **excludes $B$**.
3. In $\mathcal{Q}$, $\mathcal{A}=B\uplus A$.
4. In the Dung mapping, $A\subseteq\mathcal{V}_{L3}$.

So whether observations are arguments at all differs between definitions. $\mathcal{V}_{L3}$ is never defined, and
$\Lambda$ is defined twice with differing glosses (L122 vs L157).
**Fix.** Use one set $\mathcal{A}=V_3=B\uplus H$, with $H$ for hypotheses so that it does not clash with $\mathcal{A}$.

### B-12 · Layer typings — **Minor**

- [L115](../../docs/concepts/formal_graph_model.md#L115): $\delta:\mathcal{E}_{L2}\to[0,1]\times\mathcal{P}(L1)$, but $L1$
  is a *tuple* $(C,\lambda_c,\pi)$. Use $\mathcal{P}(\mathrm{Span})$ with $\mathrm{Span}\subseteq C\times\mathbb{N}^2$
  (chunk, start, end).
- [L77](../../docs/concepts/formal_graph_model.md#L77) "Document Chunks $C=(t_1,\dots,t_N)$" vs. L96 $C=\{c_1,\dots,c_m\}$:
  a sequence of tokens vs. a set of chunks.
- [L89](../../docs/concepts/formal_graph_model.md#L89) "token sequences" vs. L99 "character substring": decide tokens or
  characters (offsets should be characters).

### B-13 · D-QBAF tuple: undefined and redundant components — **Minor**

**Where.** [`#L182-L192`](../../docs/concepts/formal_graph_model.md#L182-L192).

- $\mathcal{R}$ (domain of $\mathcal{I},\mathcal{P},\mathcal{C}$) is never defined. Presumably
  $\mathcal{R}=\mathcal{R}_{att}\uplus\mathcal{R}_{sup}$.
- If $\mathcal{P}$ is *calibrated*, $\mathcal{C}$ is a function of $\mathcal{P}$ (reliability diagram), and the two
  thresholds are redundant. If it is not calibrated, $\mathcal{C}$ needs a defined estimator. See C-09.

### B-14 · The Filippov / bifurcation justification for Mode 2 is mathematically wrong — **Critical**

**Where.** [`#L219-L221`](../../docs/concepts/formal_graph_model.md#L219-L221).

$\mathcal{F}$ depends only on $\mathcal{P}(r),\mathcal{C}(r)$. These are **fixed data**, not state variables. Hence
$W_{ji}$ are **constant parameters** of the ODE

$$
\dot s_i = f_i(s;W,w),
$$

and $f$ is $C^1$ in $s$ ($h$ is $C^1$ because $\max\{x,0\}^2$ is) **whichever filter is used**. Filippov theory concerns
right-hand sides that are discontinuous **in the state** (Filippov 1988). With a hard filter, $W$ is discontinuous in the
*parameters* $(\mathcal{P},\mathcal{C},\tau_P,\tau_C)$. That matters for **sensitivity analysis and gradient-based
calibration of thresholds**, not for ODE well-posedness. "Bifurcation catastrophes" is unsupported, since no bifurcation
analysis is given.
**Fix.** Re-motivate Mode 2 as *a differentiable relaxation for learning or sensitivity analysis w.r.t. thresholds*, or
drop it. Also address A-11 (dilution).

### B-15 · Proposition 3 is stated incorrectly — **Major**

**Where.** [`#L240`](../../docs/concepts/formal_graph_model.md#L240).

"If $E_i(t)=0$ then $s_i(t)=w(i)$ identically for all $t\ge0$." A pointwise condition at one $t$ only gives
$\dot s_i(t)=w_i-s_i(t)$. The correct statement is: *if $E_i(t)=0$ for all $t\ge0$, then (since $s_i(0)=w_i$)
$s_i\equiv w_i$*. Because $E_i$ depends on evolving predecessors, this hypothesis rarely holds except for isolated
nodes or exactly cancelling constant inputs. As stated, Prop. 3 also contradicts its own name "Balance": balance at
equilibrium ($E_i^*=0$) gives $s_i^*=w_i$, which is the useful corollary of Prop. 5.

### B-16 · Proposition 4 (the "correction to Potyka") does not hold — **Critical**

**Where.** [`#L241`](../../docs/concepts/formal_graph_model.md#L241).

1. **An upper bound cannot refute stability.** Gershgorin gives $\rho(J)\le\max_i\big(1+\sum_j\lvert J_{ij}\rvert\big)$.
   Showing that an *upper* bound exceeds the RK4 stability threshold proves nothing about instability. That requires an
   actual eigenvalue, or a lower bound, outside the stability region.
2. **Free index.** The bound is written with $\text{indegree}(i)$ for a global $\rho(J)$. It must be
   $\max_i\big(1+0.65\sum_{j}W_{ji}\big)$.
3. **The numbers are wrong.** The real-axis stability limit of classical RK4 is $\approx2.785$ (Hairer & Wanner 1996).
   With $\delta=0.01$, instability needs $\rho(J)>278.5$, i.e. $\sum_jW_{ji}>(278.5-1)/0.6495\approx427$. "Indegree
   $\gg50$" is **not** sufficient: at indegree 50 and $W\equiv1$, the bound gives $\delta\rho\le0.335$.
4. **On DAGs, Prop. 4 is false outright.** In topological order the Jacobian is strictly lower-triangular plus
   $-I$. Its eigenvalues are **all exactly $-1$**, so $\rho(J)=1$ for any in-degree. Hubs alone cannot cause
   eigenvalue-driven RK4 divergence. Only *cycles* can (non-normal transient growth is a separate effect and is not what
   is argued).
5. **$h'(0)=0$.** Near balance the off-diagonal entries vanish, so the Gershgorin bound is very loose there.
6. **Overclaim.** "Adaptive-step solvers … are **mathematically mandatory**". Smaller fixed steps, implicit methods,
   fixed-point iteration, or the closed form on DAGs (Prop. 5) all work too.
7. **Attribution.** Potyka (2018) and the *Attractor* tutorial do recommend $\delta=0.01$, arguing from bounded
   derivatives. Calling the present text a "correction" is only warranted with a *demonstrated* counter-example (an
   explicit cyclic graph whose $J$ has $\lvert\lambda\rvert>278$).

**Fix.** Replace with: *"Bounded $\lvert\dot s\rvert$ does not preclude stiffness; on cyclic graphs with large weighted
in-degree, eigenvalues of $J$ may leave the RK4 stability region. We therefore use adaptive or implicit integrators;
on DAGs we use the closed form (Prop. 5)."* Add a concrete example if a "correction" is to be claimed.

### B-17 · Convergence claims mis-cite Hirsch and overstate "empirical" convergence — **Major**

**Where.** [`#L239`](../../docs/concepts/formal_graph_model.md#L239).

- **Hirsch's theorem is the wrong citation.** For support-only graphs the system is **cooperative**
  ($\partial f_i/\partial s_j\ge0$, $i\ne j$). Hirsch's theorem gives convergence for **almost every** initial condition
  of an irreducible cooperative system (Hirsch 1985), not for all of them. The *specific* start $s(0)=w$ is covered by a
  simpler and stronger argument: $f_i(w)=(1-w_i)h(E_i)\ge0$, so the trajectory is monotone non-decreasing
  (Kamke–Müller; Smith 1995, Prop. 3.2.1) and bounded, hence convergent. Cite that instead.
- **"Mixed cyclic networks converge empirically" is not a guarantee.** Divergence and oscillation in cyclic weighted
  bipolar graphs have been documented for several modular semantics (Mossakowski & Neuhaus 2018). State the open
  status explicitly and report detection (e.g. a non-convergence event) instead.

### B-18 · Prop. 5 wording — **Minor**

"Predecessors **reach** constant equilibrium" should be "converge to". The symbol $s^*$ (Prop. 5) vs. $\tau^*$ (L248)
denotes the same quantity.

### B-19 · The Epistemic Volatility Index does not measure controversy — **Major**

**Where.** [`#L246-L252`](../../docs/concepts/formal_graph_model.md#L246-L252).

$\mathcal{V}=\frac{E_{\text{tot}}}{1+E_{\text{tot}}}\,(1-2\lvert\tau^*-0.5\rvert)$ measures closeness of the
*equilibrium* to $0.5$. Equilibrium closeness to $0.5$ depends on the **base score**, not on the support/attack balance.

*Counter-example.*

- (i) $\tau_0=0.9$, 10 supporters and 10 attackers with equal strength ($E^*_i=0$, maximal controversy):
  $\tau^*=0.9$ by Prop. 3. With $s^*_j=0.5$ and $W=1$, $E_{\text{tot}}=10$, so $\mathcal{V}\approx0.91\cdot0.2=0.18$.
- (ii) $\tau_0=0.5$, one uncontested supporter ($W=1$, $s=0.5$): $E=0.5$, $h=0.2$, $\tau^*=0.6$, so
  $\mathcal{V}=0.33\cdot0.8=0.27$.

The *uncontested* claim scores as more "volatile" than the maximally contested one. Further, the name "orthogonal
dimensions" is false ($\mathcal{V}$ is a function of $\tau^*$), and the "Keynes–Gärdenfors formulation" label suggests the
formula is theirs (it is not; see [`ISSUE-070`](ISSUE-070-bibliography-and-attribution-audit.md)).

**Correction.** With support mass $S_i=\sum_{\text{sup}}W_{ji}s^*_j$ and attack mass $A_i=\sum_{\text{att}}W_{ki}s^*_k$:

$$
\text{Weight}(a_i)=\frac{S_i+A_i}{1+S_i+A_i},\qquad \text{Controversy}(a_i)=\begin{cases}1-\dfrac{\lvert S_i-A_i\rvert}{S_i+A_i} & S_i+A_i>0\\[2pt] 0 & \text{else}\end{cases},\qquad \mathcal{V}=\text{Weight}\cdot\text{Controversy}.
$$

This is genuinely independent of $\beta(a_i)$.

### B-20 · The justification-path set $J(at)$ is ill-defined — **Major**

**Where.** [`#L285-L293`](../../docs/concepts/formal_graph_model.md#L285-L293).

1. **Orientation.** $(a_j,a_i)\in\mathcal{R}_{sup}$ means $a_j$ supports $a_i$. A justification of $at$ therefore runs
   from evidence **towards** $at$, $b\to\cdots\to at$, but the path is written from $at$ to $b$ along $\mathcal{R}_{sup}$.
   Either use $\mathcal{R}_{sup}^{-1}$ or reverse the path.
2. **$Z$ is a function** $A\times B\to[0,1]$, not an edge set. Use $\operatorname{supp}(Z)=\{(a,b):Z(a,b)>0\}$ or a
   threshold.
3. **With cycles, the set of walks is infinite.** Restrict to simple paths. The count is still exponential, which
   matters for any "dynamic inference".
4. **"Provably grounded" does not follow.** The mere existence of a support path ignores attacks and defeated
   intermediate nodes. Grounding should be conditioned on acceptability (e.g. every node on the path has $s^*\ge\theta$,
   or the path lies in a grounded or preferred extension).

### B-21 · Mapping-law functions are ill-typed — **Major**

**Where.** [`#L270-L283`](../../docs/concepts/formal_graph_model.md#L270-L283).

- $Z_1:A\times B\to\mathcal{P}$: $\mathcal{P}$ is undefined (power set? probability?) and then "mapped to $[0,1]$".
- $Z_2:A\times B\to\sigma(\kappa(a),\kappa(b))$: the codomain is an *expression* that depends on the arguments, not a set.
  Write $Z_2(a,b)=\sigma(\kappa(a),\kappa(b))\in[0,1]$, and define $\kappa$ and $\sigma$.
- How $Z$ combines $Z_1,Z_2$ is unspecified.

For the deeper philosophical problem (mapping laws are object-level sentences, not numeric functions), see D-03.

### B-22 · Uniform-space axioms are incomplete — **Major**

**Where.** [`#L314-L328`](../../docs/concepts/formal_graph_model.md#L314-L328).

A uniformity $\mathcal{U}$ on $X$ is a non-empty family of subsets of $X\times X$ satisfying:

1. $\Delta_X\subseteq u$ for all $u\in\mathcal{U}$;
2. **upward closure**: $u\in\mathcal{U}$ and $u\subseteq v$ imply $v\in\mathcal{U}$;
3. $u_1\cap u_2\in\mathcal{U}$;
4. $\forall u\,\exists v\in\mathcal{U}:\,v\circ v\subseteq u$;
5. **symmetry**: $u\in\mathcal{U}$ implies $u^{-1}\in\mathcal{U}$.

The text omits (2) and (5) and states (4) without quantifiers. $\text{Bound}(\mathcal{A})$ is undefined.
"$\mathcal{A}$" collides with the argument set $\mathcal{A}$ of the D-QBAF in the **same file**. BMS (1987, ch. VII)
define admissible blurs relative to a uniformity on $M_p$ and induce one on $\operatorname{Pot}(M_{pp})$. That step is
needed for B-24 and is missing.

### B-23 · The model-theoretic triad is not "nested" — **Major**

**Where.** [`#L304-L312`](../../docs/concepts/formal_graph_model.md#L304-L312).

$M\subseteq M_p$ holds, but $M_{pp}\not\subseteq M_p$. $M_{pp}=\{r(x):x\in M_p\}$ for the **restriction (forgetful)
function** $r:M_p\to M_{pp}$, which removes $T$-theoretical components. Moreover, the BMS core is
$K=\langle M_p,M,M_{pp},GC,GL\rangle$ (global constraints and links), with $I\subseteq M_{pp}$. Constraints and links are
omitted, though `theory_nets_and_topologies.md` relies on constraints.

### B-24 · The approximative-adequacy formula is ill-typed — **Critical**

**Where.** [`#L338-L341`](../../docs/concepts/formal_graph_model.md#L338-L341).

The formula is $\exists X\in M:\,(I,X)\in u,\;u\in\mathcal{A}$.

- $I$ is a **set** of partial potential models ($I\subseteq M_{pp}$), $X\in M$ is a **single** potential model, and
  $u\subseteq M_p\times M_p$. The pair $(I,X)$ is of the wrong type for $u$, at two different levels.
- The quantifier on $u$ is missing ($\exists u\in\mathcal{A}$).
- The restriction $r$ and the constraints, which are what make the empirical claim non-trivial, are absent.

**Correction (BMS 1987, ch. II & VII, simplified).** The exact empirical claim of $T=\langle K,I\rangle$ is

$$
I\in\operatorname{Cn}(K):=\bar r\big(\operatorname{Pot}(M)\cap GC\cap GL\big),
$$

where $\bar r$ is $r$ lifted to sets. The approximate claim is: there exist $X\in\operatorname{Pot}(M)\cap GC\cap GL$ and
$u\in\mathcal{A}$ such that $\langle I,\bar r(X)\rangle\in\tilde u$, with $\tilde u$ the induced entourage on
$\operatorname{Pot}(M_{pp})$.

### B-25 · "Tenability: $I\subseteq M_{pp}$" is a definitional condition — **Major**

**Where.** [`#L334-L337`](../../docs/concepts/formal_graph_model.md#L334-L337).

In BMS, $I\subseteq M_{pp}$ is **part of the definition** of a theory-element. It is not an empirical or evaluative
"validity condition". Labelling it *Haltbarkeit/tenability* is non-standard and misleading. The evaluative claim is the
empirical claim of B-24.

### B-26 · "Probabilistic semantics" uses non-probabilistic operators — **Major**

**Where.** [`#L362-L374`](../../docs/concepts/formal_graph_model.md#L362-L374).

- $\beta,\delta,u$ with $u=1-\beta-\delta$ is a **subjective-logic opinion** (Jøsang 2016), which also needs a base rate
  $a$. It is not "probabilistic semantics" and should be cited as such.
- $c(A\wedge B)=\min$ and $c(A\vee B)=\max$ are the **Gödel t-norm/t-conorm** (fuzzy logic), or possibility-theoretic
  necessity and possibility (Dubois & Prade 1988). In probability, these are only the **Fréchet bounds**
  $\max(0,p_A+p_B-1)\le P(A\wedge B)\le\min(p_A,p_B)$, attained only under extreme dependence.
- $c$ is not related to $\beta,\delta$, to the D-QBAF scores, or to $\gamma$ in L2.
- "Implication weighted by …" is not a definition.

**Fix.** Choose **one** uncertainty calculus per quantity (see C-08). Rename the section accordingly.

### B-27 · Complexity claims are inaccurate — **Major**

**Where.** [`#L380-L391`](../../docs/concepts/formal_graph_model.md#L380-L391).

- "Computing admissible extensions … is NP-hard". The empty set is always admissible, so **computing an** admissible
  set is trivial, and **verifying** admissibility is polynomial. The hard problems are:

  | Problem                                   | Complexity              |
  |:------------------------------------------|:------------------------|
  | credulous acceptance (admissible/preferred) | NP-complete             |
  | skeptical acceptance (preferred)          | $\Pi_2^p$-complete      |
  | existence of a stable extension           | NP-complete             |
  | grounded extension                        | polynomial (P-complete) |

  Sources: Dimopoulos & Torres 1996; Dunne & Bench-Capon 2002; Dvořák & Dunne 2018.
- "Verifying constraint satisfaction over posets is NP-hard" is too vague to evaluate. Checking the poset axioms is
  $O(n^3)$.
- **Maximal $B$-consistent subsets** (Rescher & Manor 1970). Write "every **proper** superset $\Sigma'\supsetneq\Sigma$,
  $\Sigma'\subseteq A$". Note that even consistency checking is NP-complete (propositional) or undecidable
  (first-order) — and the atoms are natural-language sentences, for which the notion needs an NLI proxy.
- **Non sequitur.** Bi-encoder MIPS and cross-encoder reranking reduce *candidate-pair generation* for relation
  extraction. They do not address extension computation.
- "ML-guided solvers approximate stable extensions in polynomial time" has no approximation guarantee, and stable
  extensions may not exist at all.

### B-28 · Quality table — **Minor**

**Where.** [`#L399-L405`](../../docs/concepts/formal_graph_model.md#L399-L405).

The first row is broken by unescaped `|`. "Semantic Soft Matching" uses $E_{\text{ctx}}$ (yet another $E$). "Empirical
Content Ratio" is not empirical content in the sense of B-01 (see C-18).

---

## Part III — `theory_nets_and_topologies.md`

### B-29 · Root is called "minimal"; unique root does not make a tree — **Major**

**Where.** [`#L42-L66`](../../docs/concepts/theory_nets_and_topologies.md#L42-L66).

- **Wrong extremum.** With $T_j\,\alpha\,T_i$ read as "$T_j$ is a specialization of $T_i$", the root $T_0$ satisfies
  $T\,\alpha\,T_0$ for all $T$. It is the **greatest (maximum)** element, not a minimal one. "Top-level minimal" is
  self-contradictory. BMS call such elements *basic*.
- **A unique maximum does not make a tree.** A "diamond" ($T_3$ specializes both $T_1$ and $T_2$, which both specialize
  $T_0$) has a unique root but is not a tree. A theory-*tree* additionally needs every principal up-set
  $\{T': T\,\alpha\,T'\}$ to be a chain (Hasse diagram is a rooted tree).
- **Connectedness.** With a unique maximum it is automatic; stating it separately is redundant.
- **"Well-founded"** is an order-theoretic term (no infinite descending chains). Every finite poset is well-founded, so
  the normative use is a pun.
- **"$B(TN)$"** collides with the observation base $B$.
- **Symbol.** BMS write specialization as $\sigma$, not $\alpha$.

### B-30 · Poset ≠ DAG; antisymmetry is about cycles, not definitions — **Minor**

**Where.** [L51](../../docs/concepts/theory_nets_and_topologies.md#L51), [L128](../../docs/concepts/theory_nets_and_topologies.md#L128).

A reflexive relation has loops, so it is not a DAG. Its *strict part* or Hasse diagram is. Antisymmetry and
transitivity exclude specialization **cycles**. They do not prevent "circular **definitions**", which is a property of
concept definitions (cf. Belnap 1993), not of $\sigma$.

### B-31 · Falsification schemata use the wrong turnstile and one is invalid — **Major**

**Where.** [`#L110-L113`](../../docs/concepts/theory_nets_and_topologies.md#L110-L113).

- $\Vdash$ denotes forcing or Kripke satisfaction. Derivability is $\vdash$; semantic consequence is $\models$.
- *Schema I* ("Singular Empirical Evidence $\Vdash\neg$Law") is **invalid** unless the evidence is a counter-instance
  $Fa\wedge\neg Ga$ of $\forall x(Fx\to Gx)$. In that case Schemas I and II differ only by $\exists$-introduction.
- The explanation schema needs a conjunctive premise (law ∧ antecedent), which a binary edge in $E\subseteq V\times V$
  cannot express (see C-05).
- Cite Hempel & Oppenheim (1948) for the DN schema.

### B-32 · Eigenvector centrality is degenerate on DAGs and signed graphs — **Major**

**Where.** [`#L184-L185`](../../docs/concepts/theory_nets_and_topologies.md#L184-L185).

- **DAGs.** The adjacency matrix is nilpotent, so all eigenvalues are $0$ and eigenvector centrality is identically zero
  or undefined. This applies to the Theory-Net, which the docs say is a DAG. Use **Katz** or **PageRank**, which work
  thanks to damping and teleportation.
- **Signed graphs.** With attack edges carrying negative sign, Perron–Frobenius does not apply.
- **Orientation.** "Out-degree = unifying axioms" holds only under the support orientation $j\to i$. Under
  specialization or L2 orientations it flips (see C-16).

### B-33 · Leiden objective and per-community "modularity score" — **Minor**

**Where.** [`#L150`](../../docs/concepts/theory_nets_and_topologies.md#L150), [L167-L168](../../docs/concepts/theory_nets_and_topologies.md#L167-L168).

- **Objective.** Leiden optimises **modularity or CPM** (Traag et al. 2019). State which, and the resolution parameter
  $\gamma$.
- **Per-community score.** Modularity is a **partition-level** quantity. A per-community "modularity score" must be
  defined, e.g. as the community's additive contribution.
- **Signed edges.** Attack edges require signed modularity (Traag & Bruggeman 2009); see C-15.
