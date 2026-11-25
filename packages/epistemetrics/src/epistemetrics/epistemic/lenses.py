"""Secondary analytical lenses over Dialectical Argument Graphs (Layer 3).

Provides explicit projections from Episteme's primary directed D-QBAF into:
1. **Symmetrized ECHO Explanatory Coherence Lens** (Thagard, 1989; 1992):
   explicit symmetrization map with co-hypothesis dilution and bounded
   relaxation over activations in ``[-1, 1]`` and Hopfield harmony ``H_echo``.
2. **Support-Preserving Bipolar-to-Dung Lens** (Dung, 1995; Cayrol &
   Lagasquie-Schiex, 2005, 2013): derives supported and secondary attacks
   according to support semantics before computing grounded, preferred, and
   stable extensions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from epistemetrics.core.models import NodeType, RelationType, TheoryEdge, TheoryNode
from epistemetrics.graph.theory_graph import TheoryGraph


class ECHOLensResult(BaseModel):
    """Result container for the symmetrized ECHO explanatory coherence lens.

    Parameters
    ----------
    activations : dict of str to float
        Converged node activations :math:`a_i^{\\text{echo}} \\in [-1, 1]`.
    harmony : float
        Hopfield-type global harmony :math:`\\mathcal{H}_{\\text{echo}}(t^*)`.
    symmetric_weights : dict of tuple[str, str] to float
        Canonical undirected symmetric edge weights ``(u, v) -> w_uv`` (``u < v``).
    iterations : int
        Number of relaxation iterations executed.
    converged : bool
        Whether the relaxation converged within tolerance.
    """

    model_config = ConfigDict(frozen=True)

    activations: dict[str, float] = Field(default_factory=dict)
    harmony: float = Field(default=0.0)
    symmetric_weights: dict[tuple[str, str], float] = Field(default_factory=dict)
    iterations: int = Field(default=0)
    converged: bool = Field(default=True)


class DungLensResult(BaseModel):
    """Result container for the support-preserving Dung argumentation lens.

    Parameters
    ----------
    arguments : set of str
        Argument set :math:`\\mathcal{A}`.
    direct_attacks : set of tuple[str, str]
        Direct attack pairs ``(u, v)`` in :math:`\\mathcal{R}_{\\text{att}}`.
    derived_attacks : set of tuple[str, str]
        Supported and secondary attacks derived from :math:`\\mathcal{R}_{\\text{sup}}`.
    effective_attacks : set of tuple[str, str]
        Union of direct and derived attacks :math:`\\leadsto_{\\text{eff}}`.
    support_type : {"deductive", "necessary", "evidential"}
        Bipolar support interpretation applied during reduction.
    grounded_extension : frozenset of str
        Unique grounded extension (polynomial fixpoint).
    preferred_extensions : list of frozenset of str
        Maximal admissible extensions (computed when ``|A| <= max_exact_nodes``).
    stable_extensions : list of frozenset of str
        Stable extensions (computed when ``|A| <= max_exact_nodes``).
    """

    model_config = ConfigDict(frozen=True)

    arguments: set[str] = Field(default_factory=set)
    direct_attacks: set[tuple[str, str]] = Field(default_factory=set)
    derived_attacks: set[tuple[str, str]] = Field(default_factory=set)
    effective_attacks: set[tuple[str, str]] = Field(default_factory=set)
    support_type: Literal["deductive", "necessary", "evidential"] = "deductive"
    grounded_extension: frozenset[str] = Field(default_factory=frozenset)
    preferred_extensions: list[frozenset[str]] = Field(default_factory=list)
    stable_extensions: list[frozenset[str]] = Field(default_factory=list)


def _normalize_lens_inputs(
    nodes: TheoryGraph | Mapping[str, Any] | Sequence[Any],
    edges: Sequence[Any] | None = None,
) -> tuple[list[str], set[str], list[tuple[tuple[str, ...], str, int, float]]]:
    """Normalize node IDs, data-priority nodes, and dialectical inferences."""
    if isinstance(nodes, TheoryGraph):
        raw_nodes: Mapping[str, Any] | Sequence[Any] = nodes.nodes
        raw_edges: Sequence[Any] = edges if edges is not None else nodes.edges
    else:
        raw_nodes = nodes
        raw_edges = edges if edges is not None else ()

    node_ids: list[str] = []
    data_nodes: set[str] = set()

    if isinstance(raw_nodes, Mapping):
        for nid, val in raw_nodes.items():
            sid = str(nid)
            node_ids.append(sid)
            if isinstance(val, TheoryNode) and val.node_type == NodeType.EVIDENCE:
                data_nodes.add(sid)
            elif isinstance(val, Mapping) and str(
                val.get("node_type", val.get("component_type", ""))
            ).lower() in {"evidence", "observationunit", "observation_unit"}:
                data_nodes.add(sid)
    else:
        for item in raw_nodes:
            if isinstance(item, TheoryNode):
                node_ids.append(item.id)
                if item.node_type == NodeType.EVIDENCE:
                    data_nodes.add(item.id)
            elif isinstance(item, Mapping):
                sid = str(item.get("id", item.get("node_id", "")))
                if sid:
                    node_ids.append(sid)
                    if str(
                        item.get("node_type", item.get("component_type", ""))
                    ).lower() in {"evidence", "observationunit", "observation_unit"}:
                        data_nodes.add(sid)
            else:
                node_ids.append(str(item))

    node_set = set(node_ids)
    normalized_edges: list[tuple[tuple[str, ...], str, int, float]] = []

    for e in raw_edges:
        if isinstance(e, TheoryEdge):
            if e.relation_type == RelationType.ALTERNATIVE_READING_OF:
                continue
            pol = e.polarity if e.polarity != 0 else e.relation_type.default_polarity
            if pol == 0:
                continue
            prems = e.effective_premise_ids
            w = float(
                e.effective_weight
                if e.effective_weight is not None
                else e.active_weight
            )
            tgt = e.target
        elif isinstance(e, Mapping):
            rtype = str(e.get("relation_type", e.get("type", ""))).upper()
            if rtype == "ALTERNATIVE_READING_OF":
                continue
            pol_raw = e.get("polarity")
            if pol_raw is not None:
                pol = int(pol_raw)
            else:
                pol = (
                    -1
                    if rtype
                    in {"ATTACKS", "REBUTS", "UNDERCUTS", "UNDERMINES", "INHIBITS", "CONTRADICTS", "REFUTES"}
                    else 1
                )
            if pol == 0:
                continue
            raw_prems = e.get("premise_ids")
            src = str(e.get("source", e.get("source_id", "")))
            prems = tuple(str(p) for p in raw_prems) if raw_prems else ((src,) if src else ())
            tgt = str(e.get("target", e.get("target_id", "")))
            w = float(
                e.get("effective_weight")
                or e.get("active_weight")
                or e.get("weight")
                or 1.0
            )
        elif isinstance(e, (tuple, list)) and len(e) >= 2:
            prems = (str(e[0]),)
            tgt = str(e[1])
            w = float(e[2]) if len(e) >= 3 else 1.0
            pol = int(e[3]) if len(e) >= 4 else 1
            if pol == 0:
                continue
        else:
            continue

        if not prems or not tgt:
            continue
        for ep in (*prems, tgt):
            if ep not in node_set:
                node_set.add(ep)
                node_ids.append(ep)
        normalized_edges.append((prems, tgt, 1 if pol > 0 else -1, max(0.0, w)))

    return node_ids, data_nodes, normalized_edges


def project_to_echo_network(
    nodes: TheoryGraph | Mapping[str, Any] | Sequence[Any],
    edges: Sequence[Any] | None = None,
    *,
    excitation: float = 0.04,
    inhibition: float = 0.06,
) -> tuple[list[str], set[str], dict[tuple[str, str], float]]:
    """Project a directed D-QBAF into a symmetric signed ECHO network.

    For each explanatory support warrant with :math:`m` conjunctive premises
    explaining conclusion :math:`q`, assigns symmetric excitatory weight
    :math:`w_{pq}^{\\text{echo}} = (\\epsilon^+ / m) W` between each premise
    and :math:`q`, and between each pair of co-hypotheses (TEC Principle E2c).
    For each attack/contradiction, assigns symmetric inhibitory weight
    :math:`-\\epsilon^- W`.

    Parameters
    ----------
    nodes : TheoryGraph or Mapping or Sequence
        Argument nodes.
    edges : Sequence or None, optional
        Directed dialectical inferences.
    excitation : float, default 0.04
        Base excitatory coupling :math:`\\epsilon^+ > 0` (Thagard, 1992).
    inhibition : float, default 0.06
        Base inhibitory coupling :math:`\\epsilon^- > 0` (Thagard, 1992).

    Returns
    -------
    tuple of (list[str], set[str], dict[tuple[str, str], float])
        Node list, data-priority node set, and symmetric undirected weights.
    """
    node_ids, data_nodes, norm_edges = _normalize_lens_inputs(nodes, edges)
    sym_weights: dict[tuple[str, str], float] = {}

    def _pair(u: str, v: str) -> tuple[str, str]:
        return (u, v) if u <= v else (v, u)

    for prems, tgt, pol, w in norm_edges:
        m = max(1, len(prems))
        if pol > 0:
            delta = (excitation / float(m)) * w
            for p in prems:
                if p != tgt:
                    key = _pair(p, tgt)
                    sym_weights[key] = sym_weights.get(key, 0.0) + delta
            # Co-hypothesis mutual coherence (TEC Principle E2a/E2c)
            for i in range(len(prems)):
                for j in range(i + 1, len(prems)):
                    if prems[i] != prems[j]:
                        key = _pair(prems[i], prems[j])
                        sym_weights[key] = sym_weights.get(key, 0.0) + delta
        else:
            delta = -inhibition * w
            for p in prems:
                if p != tgt:
                    key = _pair(p, tgt)
                    sym_weights[key] = sym_weights.get(key, 0.0) + delta

    return node_ids, data_nodes, sym_weights


def solve_echo_lens(
    nodes: TheoryGraph | Mapping[str, Any] | Sequence[Any],
    edges: Sequence[Any] | None = None,
    *,
    data_nodes: set[str] | None = None,
    excitation: float = 0.04,
    inhibition: float = 0.06,
    data_priority_weight: float = 0.05,
    decay: float = 0.05,
    max_iterations: int = 200,
    tolerance: float = 1e-4,
) -> ECHOLensResult:
    """Run the symmetrized ECHO parallel constraint-satisfaction lens.

    Parameters
    ----------
    nodes : TheoryGraph or Mapping or Sequence
        Argument nodes.
    edges : Sequence or None, optional
        Directed dialectical inferences.
    data_nodes : set of str or None, optional
        Optional explicit evidential base nodes receiving defeasible Data
        Priority activation from the special evidence unit (activation ``+1.0``).
    excitation : float, default 0.04
        Excitatory weight multiplier :math:`\\epsilon^+`.
    inhibition : float, default 0.06
        Inhibitory weight multiplier :math:`\\epsilon^-`.
    data_priority_weight : float, default 0.05
        Excitatory link from the special evidence unit to each data node.
    decay : float, default 0.05
        Per-step activation decay :math:`\\theta \\in (0, 1)`.
    max_iterations : int, default 200
        Maximum synchronous update steps.
    tolerance : float, default 1e-4
        Convergence threshold on max absolute activation shift.

    Returns
    -------
    ECHOLensResult
        Converged activations in ``[-1, 1]``, Hopfield harmony, and symmetric weights.
    """
    node_ids, inferred_data, sym_weights = project_to_echo_network(
        nodes, edges, excitation=excitation, inhibition=inhibition
    )
    eff_data = set(data_nodes) if data_nodes is not None else inferred_data

    adj: dict[str, list[tuple[str, float]]] = {nid: [] for nid in node_ids}
    for (u, v), w in sym_weights.items():
        adj[u].append((v, w))
        adj[v].append((u, w))

    act: dict[str, float] = {nid: 0.01 for nid in node_ids}
    converged = False
    iters = 0

    for step in range(1, max_iterations + 1):
        iters = step
        next_act: dict[str, float] = {}
        max_delta = 0.0
        for nid in node_ids:
            net = sum(w * act[nbr] for nbr, w in adj[nid])
            if nid in eff_data:
                net += data_priority_weight * 1.0
            a_old = act[nid]
            if net > 0.0:
                a_new = a_old * (1.0 - decay) + net * (1.0 - a_old)
            else:
                a_new = a_old * (1.0 - decay) + net * (a_old - (-1.0))
            a_new = max(-1.0, min(1.0, a_new))
            next_act[nid] = a_new
            max_delta = max(max_delta, abs(a_new - a_old))
        act = next_act
        if max_delta < tolerance:
            converged = True
            break

    harmony = 0.0
    for (u, v), w in sym_weights.items():
        harmony += 2.0 * w * act[u] * act[v]
    for d in eff_data:
        if d in act:
            harmony += 2.0 * data_priority_weight * act[d]

    return ECHOLensResult(
        activations={k: round(v, 6) for k, v in act.items()},
        harmony=round(float(harmony), 6),
        symmetric_weights=sym_weights,
        iterations=iters,
        converged=converged,
    )


def reduce_bipolar_to_dung(
    nodes: TheoryGraph | Mapping[str, Any] | Sequence[Any],
    edges: Sequence[Any] | None = None,
    *,
    support_type: Literal["deductive", "necessary", "evidential"] = "deductive",
) -> tuple[set[str], set[tuple[str, str]], set[tuple[str, str]]]:
    """Derive effective Dung attacks from a bipolar graph preserving support semantics.

    Implements Cayrol & Lagasquie-Schiex (2005, 2013) complex-attack closure:
    - Transitive support closure :math:`S^+`: ``a S+ b``.
    - **Deductive support**:
      - Supported attack: ``a S+ b`` and ``b R_att c`` implies ``a -> c``.
      - Mediated (secondary) attack: ``a R_att b`` and ``c S+ b`` implies ``a -> c``.
    - **Necessary support**:
      - Secondary attack: ``a R_att b`` and ``b S+ c`` implies ``a -> c``.
      - Extended attack: ``b S+ a`` and ``b R_att c`` implies ``a -> c``.
    - **Evidential support**:
      - Supported attack: ``a S+ b`` and ``b R_att c`` implies ``a -> c``.
      - Secondary attack: ``a R_att b`` and ``b S+ c`` implies ``a -> c``.

    Parameters
    ----------
    nodes : TheoryGraph or Mapping or Sequence
        Argument nodes.
    edges : Sequence or None, optional
        Bipolar dialectical relations.
    support_type : {"deductive", "necessary", "evidential"}, default "deductive"
        Support interpretation governing derived attacks.

    Returns
    -------
    tuple of (set[str], set[tuple[str, str]], set[tuple[str, str]])
        Argument set, direct attacks, and newly derived complex attacks.
    """
    node_ids, _, norm_edges = _normalize_lens_inputs(nodes, edges)
    args = set(node_ids)
    supports: set[tuple[str, str]] = set()
    direct_attacks: set[tuple[str, str]] = set()

    for prems, tgt, pol, _ in norm_edges:
        for p in prems:
            if pol > 0:
                supports.add((p, tgt))
            else:
                direct_attacks.add((p, tgt))

    # Transitive closure of support relation S+
    supp_closure: set[tuple[str, str]] = set(supports)
    changed = True
    while changed:
        changed = False
        new_pairs: set[tuple[str, str]] = set()
        for a, b in supp_closure:
            for c, d in supports:
                if b == c and (a, d) not in supp_closure:
                    new_pairs.add((a, d))
        if new_pairs:
            supp_closure.update(new_pairs)
            changed = True

    derived: set[tuple[str, str]] = set()
    if support_type == "deductive":
        for a, b in supp_closure:
            for x, c in direct_attacks:
                if b == x:
                    derived.add((a, c))
        for a, b in direct_attacks:
            for c, d in supp_closure:
                if d == b:
                    derived.add((a, c))
    elif support_type == "necessary":
        for a, b in direct_attacks:
            for x, c in supp_closure:
                if b == x:
                    derived.add((a, c))
        for b, a in supp_closure:
            for x, c in direct_attacks:
                if b == x:
                    derived.add((a, c))
    elif support_type == "evidential":
        for a, b in supp_closure:
            for x, c in direct_attacks:
                if b == x:
                    derived.add((a, c))
        for a, b in direct_attacks:
            for x, c in supp_closure:
                if b == x:
                    derived.add((a, c))
    else:
        raise ValueError(
            f"Unsupported support_type '{support_type}'. "
            "Expected 'deductive', 'necessary', or 'evidential'."
        )

    derived -= direct_attacks
    return args, direct_attacks, derived


def compute_dung_extensions(
    nodes: TheoryGraph | Mapping[str, Any] | Sequence[Any],
    edges: Sequence[Any] | None = None,
    *,
    support_type: Literal["deductive", "necessary", "evidential"] = "deductive",
    max_exact_nodes: int = 16,
) -> DungLensResult:
    """Compute grounded, preferred, and stable extensions after bipolar reduction.

    The grounded extension is always computed in polynomial time via the
    characteristic function fixpoint. Preferred and stable extensions are
    enumerated exactly when ``len(arguments) <= max_exact_nodes``.

    Parameters
    ----------
    nodes : TheoryGraph or Mapping or Sequence
        Argument nodes.
    edges : Sequence or None, optional
        Bipolar dialectical relations.
    support_type : {"deductive", "necessary", "evidential"}, default "deductive"
        Bipolar support interpretation.
    max_exact_nodes : int, default 16
        Upper bound on ``|A|`` for exact preferred/stable enumeration.

    Returns
    -------
    DungLensResult
        Effective attack framework and computed extensions.
    """
    args, direct_att, derived_att = reduce_bipolar_to_dung(
        nodes, edges, support_type=support_type
    )
    eff_att = direct_att | derived_att

    attackers_of: dict[str, set[str]] = {a: set() for a in args}
    for u, v in eff_att:
        attackers_of[v].add(u)

    def _is_defended(a: str, ext: set[str]) -> bool:
        for b in attackers_of[a]:
            if not any(c in ext for c in attackers_of[b]):
                return False
        return True

    # Grounded extension: least fixpoint of F(S) = {a in A | S defends a}
    grounded: set[str] = set()
    while True:
        next_g = {a for a in args if _is_defended(a, grounded)}
        if next_g == grounded:
            break
        grounded = next_g

    preferred: list[frozenset[str]] = []
    stable: list[frozenset[str]] = []

    if len(args) <= max_exact_nodes:
        arg_list = sorted(args)
        admissible: list[frozenset[str]] = []
        n = len(arg_list)

        for mask in range(1 << n):
            subset = {arg_list[i] for i in range(n) if (mask >> i) & 1}
            # Conflict-free check
            if any((u in subset and v in subset) for u, v in eff_att):
                continue
            # Admissibility check
            if all(_is_defended(a, subset) for a in subset):
                fs = frozenset(subset)
                admissible.append(fs)
                # Stable check: attacks every argument outside subset
                outside = args - subset
                if all(any(u in subset for u in attackers_of[o]) for o in outside):
                    stable.append(fs)

        preferred = [
            s
            for s in admissible
            if not any(s < other for other in admissible)
        ]

    return DungLensResult(
        arguments=args,
        direct_attacks=direct_att,
        derived_attacks=derived_att,
        effective_attacks=eff_att,
        support_type=support_type,
        grounded_extension=frozenset(grounded),
        preferred_extensions=preferred,
        stable_extensions=stable,
    )
