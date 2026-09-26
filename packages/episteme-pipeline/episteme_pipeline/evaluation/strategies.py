"""Evaluation strategies and registry for pluggable, dataset-agnostic evaluation.

Provides the sovereign `EvaluationStrategy` protocol, standard concrete strategies
(structuralist theory-nets, L2 information extraction, L3 argumentation), and a
`StrategyRegistry` allowing automatic inference or user-injected evaluation routines.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

import networkx as nx

import epistemetrics as em
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    Phase1ArtifactsView,
    Phase2ArtifactsView,
    Phase3ArtifactsView,
    Phase4ArtifactsView,
)
from episteme_pipeline.contracts.domain import (
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryNet,
    TheoryRelation,
)
from episteme_pipeline.evaluation.benchmarks.arg_microtexts import load_arg_microtexts_subset
from episteme_pipeline.evaluation.benchmarks.scierc import load_scierc_subset
from episteme_pipeline.evaluation.benchmarks.structuralist import (
    load_structuralist_benchmark,
    load_structuralist_theory_graph,
)
from episteme_pipeline.evaluation.models import (
    DatasetType,
    EvaluationLevel,
    EvaluationMetric,
    EvaluationOutcome,
    EvaluationResult,
)
from episteme_pipeline.evaluation.scorers.domain_bridge import (
    artifact_collection_to_theory_graph,
    l2_triples_to_digraph,
    theory_net_to_theory_graph,
)
from episteme_pipeline.evaluation.scorers.model_scorer import ModelScorer
from episteme_pipeline.evaluation.scorers.oep import OptimalEditPathEvaluator

logger = logging.getLogger(__name__)


@runtime_checkable
class EvaluationStrategy(Protocol):
    """Protocol defining a sovereign evaluation strategy contract."""

    async def evaluate(
        self,
        predicted: Any,
        gold: Any,
        run_id: str,
        context: dict[str, Any] | None = None,
    ) -> list[EvaluationResult]:
        """Evaluate predicted pipeline representations against gold standard benchmarks.

        Parameters
        ----------
        predicted : Any
            Predicted pipeline output representation.
        gold : Any
            Gold standard reference representation or path.
        run_id : str
            Run identifier for tracking and telemetry.
        context : dict of str to Any, optional
            Additional contextual configuration (thresholds, corpus paths, metadata).

        Returns
        -------
        list of EvaluationResult
            List of evaluated results across stage or component levels.
        """
        ...


class StructuralistStrategy:
    """Strategy for evaluating formal Bourbaki structuralist TheoryNets and theory dynamics.

    Evaluates model component completeness (MCC), property fidelity score (PFS),
    axiom omission rate (AOR), and specialization poset hierarchies.
    """

    def __init__(self, model_scorer: ModelScorer | None = None) -> None:
        """Initialize the structuralist evaluation strategy.

        Parameters
        ----------
        model_scorer : ModelScorer, optional
            Underlying Bourbaki model component scorer. If None, instantiates a default.
        """
        self.model_scorer = model_scorer or ModelScorer()

    async def evaluate(
        self,
        predicted: Any,
        gold: Any,
        run_id: str,
        context: dict[str, Any] | None = None,
    ) -> list[EvaluationResult]:
        """Evaluate structuralist theory components and optional poset hierarchies.

        Parameters
        ----------
        predicted : Any
            Predicted TheoryNet, ArtifactCollection, or TheoryGraph.
        gold : Any
            Path to STNB JSON-LD file, TheoryGraph, or NetworkX DiGraph.
        run_id : str
            Run identifier.
        context : dict of str to Any, optional
            Evaluation hyperparameters such as min_mcc, min_pfs, dataset_ref.

        Returns
        -------
        list of EvaluationResult
            Structuralist evaluation results.
        """
        ctx = context or {}
        dataset_ref = ctx.get("dataset_ref")
        gold_target = gold

        if isinstance(gold, (str, Path)) and Path(gold).is_file():
            if not dataset_ref:
                dataset_ref = str(gold)
            _, gold_target = load_structuralist_benchmark(gold)

        min_mcc = ctx.get("min_mcc", self.model_scorer.min_mcc)
        min_pfs = ctx.get("min_pfs", self.model_scorer.min_pfs)
        sim_threshold = ctx.get("sim_threshold", self.model_scorer.sim_threshold)

        scorer = ModelScorer(min_mcc=min_mcc, min_pfs=min_pfs, sim_threshold=sim_threshold)
        stage_res = scorer.evaluate_to_result(
            predicted=predicted,
            gold=gold_target,
            run_id=run_id,
            phase_name=ctx.get("phase_name", "Phase 6: TheoryNet Projection"),
            dataset_ref=dataset_ref or (str(gold) if isinstance(gold, (str, Path)) else "in_memory_gold"),
        )
        return [stage_res]


class ExtractionStrategy:
    """Strategy for evaluating Layer 2 Named Entity Recognition and Relation Extraction.

    Evaluates exact and token-level entity discovery (F1, Precision, Recall)
    and relation extraction triples, as well as Optimal Edit Path (OEP) error rates.
    """

    def __init__(self, match_case_sensitive: bool = False) -> None:
        """Initialize the extraction evaluation strategy.

        Parameters
        ----------
        match_case_sensitive : bool, optional
            Whether entity and relation string matching should be case-sensitive (default: False).
        """
        self.match_case_sensitive = match_case_sensitive

    async def evaluate(
        self,
        predicted: Any,
        gold: Any,
        run_id: str,
        context: dict[str, Any] | None = None,
    ) -> list[EvaluationResult]:
        """Evaluate extracted entities and relation triples against gold annotations.

        Parameters
        ----------
        predicted : Any
            Predicted representation (ArtifactCollection, list of L2Triple/Entity, or DiGraph).
        gold : Any
            Gold standard representation (path to SciERC json, dict with l2_entities/triples, or DiGraph).
        run_id : str
            Run identifier.
        context : dict of str to Any, optional
            Additional contextual configuration.

        Returns
        -------
        list of EvaluationResult
            Entity and relation extraction evaluation results.
        """
        ctx = context or {}
        dataset_ref = ctx.get("dataset_ref")

        # 1. Extract predicted entities and triples
        pred_entities: list[L2Entity] = []
        pred_triples: list[L2Triple] = []

        if isinstance(predicted, ArtifactCollection):
            p2 = Phase2ArtifactsView.from_collection(predicted)
            pred_entities = p2.entities
            pred_triples = list(p2.local_triples)
            p3 = Phase3ArtifactsView.from_collection(predicted)
            pred_triples.extend(p3.global_triples)
        elif isinstance(predicted, list):
            for item in predicted:
                if isinstance(item, L2Entity):
                    pred_entities.append(item)
                elif isinstance(item, L2Triple):
                    pred_triples.append(item)
        elif isinstance(predicted, nx.DiGraph):
            for nid, data in predicted.nodes(data=True):
                pred_entities.append(
                    L2Entity(
                        id=str(nid),
                        name=str(data.get("name", nid)),
                        label=str(data.get("label", data.get("node_type", "Entity"))),
                    )
                )
            for u, v, edata in predicted.edges(data=True):
                pred_triples.append(
                    L2Triple(
                        subject_id=str(u),
                        predicate=str(edata.get("label", edata.get("relation", "related_to"))),
                        object_id=str(v),
                        confidence=float(edata.get("confidence", 1.0)),
                        scope=str(edata.get("scope", "local")),
                    )
                )

        # 2. Extract gold entities and triples
        gold_entities: list[L2Entity] = []
        gold_triples: list[L2Triple] = []

        if isinstance(gold, (str, Path)) and Path(gold).is_file():
            if not dataset_ref:
                dataset_ref = str(gold)
            gold_data = load_scierc_subset(gold, limit=ctx.get("limit", 1000))
            gold_entities = gold_data.get("l2_entities", [])
            gold_triples = gold_data.get("l2_triples", [])
        elif isinstance(gold, dict):
            gold_entities = gold.get("l2_entities", [])
            gold_triples = gold.get("l2_triples", [])
        elif isinstance(gold, nx.DiGraph):
            for nid, data in gold.nodes(data=True):
                gold_entities.append(
                    L2Entity(
                        id=str(nid),
                        name=str(data.get("name", nid)),
                        label=str(data.get("label", data.get("node_type", "Entity"))),
                    )
                )
            for u, v, edata in gold.edges(data=True):
                gold_triples.append(
                    L2Triple(
                        subject_id=str(u),
                        predicate=str(edata.get("label", edata.get("relation", "related_to"))),
                        object_id=str(v),
                        confidence=float(edata.get("confidence", 1.0)),
                        scope=str(edata.get("scope", "local")),
                    )
                )

        # 3. Compute Entity Extraction Metrics
        norm = (lambda s: s.strip()) if self.match_case_sensitive else (lambda s: s.strip().lower())
        pred_ent_names = {norm(e.name) for e in pred_entities if e.name}
        gold_ent_names = {norm(e.name) for e in gold_entities if e.name}

        tp_ent = len(pred_ent_names & gold_ent_names)
        fp_ent = len(pred_ent_names - gold_ent_names)
        fn_ent = len(gold_ent_names - pred_ent_names)

        ent_prec = tp_ent / len(pred_ent_names) if pred_ent_names else (1.0 if not gold_ent_names else 0.0)
        ent_rec = tp_ent / len(gold_ent_names) if gold_ent_names else 1.0
        ent_f1 = (2 * ent_prec * ent_rec) / (ent_prec + ent_rec) if (ent_prec + ent_rec) > 0 else 0.0

        # 4. Compute Relation Extraction Metrics
        pred_ent_id_to_name = {e.id: norm(e.name or e.id) for e in pred_entities}
        gold_ent_id_to_name = {e.id: norm(e.name or e.id) for e in gold_entities}

        pred_rel_tuples = {
            (pred_ent_id_to_name.get(t.subject_id, norm(t.subject_id)), norm(t.predicate), pred_ent_id_to_name.get(t.object_id, norm(t.object_id)))
            for t in pred_triples
        }
        gold_rel_tuples = {
            (gold_ent_id_to_name.get(t.subject_id, norm(t.subject_id)), norm(t.predicate), gold_ent_id_to_name.get(t.object_id, norm(t.object_id)))
            for t in gold_triples
        }

        tp_rel = len(pred_rel_tuples & gold_rel_tuples)
        rel_prec = tp_rel / len(pred_rel_tuples) if pred_rel_tuples else (1.0 if not gold_rel_tuples else 0.0)
        rel_rec = tp_rel / len(gold_rel_tuples) if gold_rel_tuples else 1.0
        rel_f1 = (2 * rel_prec * rel_rec) / (rel_prec + rel_rec) if (rel_prec + rel_rec) > 0 else 0.0

        # 5. Compute Graph Edit Rates (OEP)
        pred_graph = l2_triples_to_digraph(pred_entities, pred_triples)
        gold_graph = l2_triples_to_digraph(gold_entities, gold_triples)

        matched_preds = []
        matched_golds = []
        for u, v, data in pred_graph.edges(data=True):
            lbl = norm(str(data.get("label", "")))
            gold_e = (u, v)
            if gold_graph.has_edge(u, v):
                g_lbl = norm(str(gold_graph.edges[u, v].get("label", "")))
                if lbl == g_lbl:
                    matched_preds.append((u, v))
                    matched_golds.append(gold_e)

        hallucination_rate, omission_rate = OptimalEditPathEvaluator.compute_rates(
            pred_graph, gold_graph, matched_preds, matched_golds
        )

        outcome = (
            EvaluationOutcome.PASS
            if (ent_f1 >= 0.5 and rel_f1 >= 0.4)
            else EvaluationOutcome.WARNING
            if (ent_f1 > 0 or rel_f1 > 0)
            else EvaluationOutcome.FAIL
        )

        metrics = [
            EvaluationMetric(name="entity_precision", value=ent_prec),
            EvaluationMetric(name="entity_recall", value=ent_rec),
            EvaluationMetric(name="entity_f1", value=ent_f1),
            EvaluationMetric(name="relation_precision", value=rel_prec),
            EvaluationMetric(name="relation_recall", value=rel_rec),
            EvaluationMetric(name="relation_f1", value=rel_f1),
            EvaluationMetric(name="hallucination_rate", value=hallucination_rate),
            EvaluationMetric(name="omission_rate", value=omission_rate),
        ]

        markdown_report = (
            "## Layer 2 Information Extraction Evaluation Report\n\n"
            f"- **Entity F1:** {ent_f1:.4f} (P: {ent_prec:.4f}, R: {ent_rec:.4f})\n"
            f"- **Relation F1:** {rel_f1:.4f} (P: {rel_prec:.4f}, R: {rel_rec:.4f})\n"
            f"- **Hallucination Rate:** {hallucination_rate:.4f}\n"
            f"- **Omission Rate:** {omission_rate:.4f}\n"
            f"- **Predicted Entities/Triples:** {len(pred_entities)} / {len(pred_triples)}\n"
            f"- **Gold Entities/Triples:** {len(gold_entities)} / {len(gold_triples)}\n"
        )

        result = EvaluationResult(
            run_id=run_id,
            evaluation_level=EvaluationLevel.STAGE,
            phase_name=ctx.get("phase_name", "Phase 2 & 3: Information Extraction"),
            dataset_ref=dataset_ref or "in_memory_extraction",
            dataset_type=DatasetType.GOLD,
            metrics=metrics,
            outcome=outcome,
            notes={
                "category": "information_extraction",
                "markdown_report": markdown_report,
            },
        )
        return [result]


class ArgumentationStrategy:
    """Strategy for evaluating Layer 3 Argument Component (ADU) and Relation (ARC) Mining."""

    async def evaluate(
        self,
        predicted: Any,
        gold: Any,
        run_id: str,
        context: dict[str, Any] | None = None,
    ) -> list[EvaluationResult]:
        """Evaluate argument component identification and stance relation extraction.

        Parameters
        ----------
        predicted : Any
            Predicted representation containing TheoryAtom and TheoryRelation objects.
        gold : Any
            Gold standard benchmark representation (path or dictionary).
        run_id : str
            Run identifier.
        context : dict of str to Any, optional
            Additional contextual configuration.

        Returns
        -------
        list of EvaluationResult
            Argumentation evaluation results.
        """
        ctx = context or {}
        dataset_ref = ctx.get("dataset_ref")

        pred_atoms: list[TheoryAtom] = []
        pred_relations: list[TheoryRelation] = []

        if isinstance(predicted, ArtifactCollection):
            p4 = Phase4ArtifactsView.from_collection(predicted)
            pred_atoms = p4.theory_atoms
            pred_relations = p4.theory_relations
        elif isinstance(predicted, list):
            for item in predicted:
                if isinstance(item, TheoryAtom):
                    pred_atoms.append(item)
                elif isinstance(item, TheoryRelation):
                    pred_relations.append(item)

        gold_atoms: list[TheoryAtom] = []
        gold_relations: list[TheoryRelation] = []

        if isinstance(gold, (str, Path)) and Path(gold).is_file():
            if not dataset_ref:
                dataset_ref = str(gold)
            gold_data = load_arg_microtexts_subset(gold, limit=ctx.get("limit", 1000))
            gold_atoms = gold_data.get("l3_atoms", [])
            gold_relations = gold_data.get("l3_relations", [])
        elif isinstance(gold, dict):
            gold_atoms = gold.get("l3_atoms", [])
            gold_relations = gold.get("l3_relations", [])

        pred_texts = {a.text.strip().lower() for a in pred_atoms if a.text}
        gold_texts = {a.text.strip().lower() for a in gold_atoms if a.text}

        tp_adu = len(pred_texts & gold_texts)
        prec_adu = tp_adu / len(pred_texts) if pred_texts else (1.0 if not gold_texts else 0.0)
        rec_adu = tp_adu / len(gold_texts) if gold_texts else 1.0
        f1_adu = (2 * prec_adu * rec_adu) / (prec_adu + rec_adu) if (prec_adu + rec_adu) > 0 else 0.0

        pred_atom_id_to_text = {a.id: a.text.strip().lower() for a in pred_atoms if a.text}
        gold_atom_id_to_text = {a.id: a.text.strip().lower() for a in gold_atoms if a.text}

        pred_rels = {
            (
                pred_atom_id_to_text.get(r.source_id, r.source_id.lower()),
                r.relation_type.lower().strip(),
                pred_atom_id_to_text.get(r.target_id, r.target_id.lower()),
            )
            for r in pred_relations
        }
        gold_rels = {
            (
                gold_atom_id_to_text.get(r.source_id, r.source_id.lower()),
                r.relation_type.lower().strip(),
                gold_atom_id_to_text.get(r.target_id, r.target_id.lower()),
            )
            for r in gold_relations
        }

        tp_rel = len(pred_rels & gold_rels)
        prec_rel = tp_rel / len(pred_rels) if pred_rels else (1.0 if not gold_rels else 0.0)
        rec_rel = tp_rel / len(gold_rels) if gold_rels else 1.0
        f1_rel = (2 * prec_rel * rec_rel) / (prec_rel + rec_rel) if (prec_rel + rec_rel) > 0 else 0.0

        metrics = [
            EvaluationMetric(name="adu_precision", value=prec_adu),
            EvaluationMetric(name="adu_recall", value=rec_adu),
            EvaluationMetric(name="adu_f1", value=f1_adu),
            EvaluationMetric(name="arc_precision", value=prec_rel),
            EvaluationMetric(name="arc_recall", value=rec_rel),
            EvaluationMetric(name="arc_f1", value=f1_rel),
        ]

        markdown_report = (
            "## Layer 3 Argumentation Evaluation Report\n\n"
            f"- **ADU Component F1:** {f1_adu:.4f} (P: {prec_adu:.4f}, R: {rec_adu:.4f})\n"
            f"- **ARC Relation F1:** {f1_rel:.4f} (P: {prec_rel:.4f}, R: {rec_rel:.4f})\n"
            f"- **Predicted Components/Relations:** {len(pred_atoms)} / {len(pred_relations)}\n"
            f"- **Gold Components/Relations:** {len(gold_atoms)} / {len(gold_relations)}\n"
        )

        result = EvaluationResult(
            run_id=run_id,
            evaluation_level=EvaluationLevel.STAGE,
            phase_name=ctx.get("phase_name", "Phase 4: Argument Mining"),
            dataset_ref=dataset_ref or "in_memory_argumentation",
            dataset_type=DatasetType.GOLD,
            metrics=metrics,
            outcome=EvaluationOutcome.PASS if f1_adu >= 0.5 else EvaluationOutcome.WARNING,
            notes={
                "category": "argumentation_mining",
                "markdown_report": markdown_report,
            },
        )
        return [result]


class StrategyRegistry:
    """Registry maintaining available evaluation strategies and handling auto-inference."""

    def __init__(self) -> None:
        """Initialize the strategy registry with standard built-in strategies."""
        self._strategies: dict[str, type[EvaluationStrategy] | Callable[[], EvaluationStrategy] | EvaluationStrategy] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default strategies."""
        self.register("structuralist", StructuralistStrategy)
        self.register("stnb", StructuralistStrategy)
        self.register("theorynet", StructuralistStrategy)
        self.register("l4", StructuralistStrategy)

        self.register("extraction", ExtractionStrategy)
        self.register("scierc", ExtractionStrategy)
        self.register("ner", ExtractionStrategy)
        self.register("re", ExtractionStrategy)
        self.register("l2", ExtractionStrategy)

        self.register("argumentation", ArgumentationStrategy)
        self.register("arg_microtexts", ArgumentationStrategy)
        self.register("l3", ArgumentationStrategy)

    def register(
        self,
        name: str,
        strategy: type[EvaluationStrategy] | Callable[[], EvaluationStrategy] | EvaluationStrategy,
    ) -> None:
        """Register a strategy by name.

        Parameters
        ----------
        name : str
            Unique key identifying the strategy.
        strategy : type of EvaluationStrategy, Callable, or EvaluationStrategy
            Strategy instance, class, or factory.
        """
        self._strategies[name.lower().strip()] = strategy

    def get(self, name: str) -> EvaluationStrategy:
        """Retrieve an evaluation strategy by name or module path.

        Parameters
        ----------
        name : str
            Registered name or fully-qualified class path ('module.path:ClassName').

        Returns
        -------
        EvaluationStrategy
            Instantiated evaluation strategy.

        Raises
        ------
        ValueError
            If the requested strategy name cannot be resolved.
        """
        key = name.lower().strip()
        if key in self._strategies:
            strat = self._strategies[key]
            if isinstance(strat, type) or callable(strat):
                return strat()
            return strat

        # Support dynamic import: 'my_module:MyStrategy' or 'my_module.MyStrategy'
        if ":" in name or "." in name:
            try:
                mod_path, cls_name = name.split(":", 1) if ":" in name else name.rsplit(".", 1)
                mod = importlib.import_module(mod_path)
                cls = getattr(mod, cls_name)
                return cls()
            except Exception as e:
                raise ValueError(f"Failed to dynamically import evaluation strategy '{name}': {e}") from e

        raise ValueError(
            f"Unknown evaluation strategy: '{name}'. Available registered strategies: {list(self._strategies.keys())}"
        )

    def infer(
        self,
        predicted: Any = None,
        gold: Any = None,
        dataset_type: str | None = None,
    ) -> EvaluationStrategy:
        """Infer the appropriate evaluation strategy from inputs.

        Parameters
        ----------
        predicted : Any, optional
            Predicted pipeline representation.
        gold : Any, optional
            Gold standard benchmark representation or path.
        dataset_type : str, optional
            Declared dataset type (e.g. from manifest).

        Returns
        -------
        EvaluationStrategy
            Inferred strategy instance.
        """
        # 1. Match dataset_type if provided
        if dataset_type:
            dt_clean = dataset_type.lower().strip()
            if dt_clean in self._strategies:
                return self.get(dt_clean)

        # 2. Inspect gold path or structure
        if isinstance(gold, (str, Path)):
            g_str = str(gold).lower()
            if "stnb" in g_str or g_str.endswith(".jsonld") or "principia" in g_str:
                return self.get("structuralist")
            if "scierc" in g_str or "scifact" in g_str:
                return self.get("extraction")
            if "arg_microtexts" in g_str or "argument" in g_str:
                return self.get("argumentation")

        if isinstance(gold, dict):
            if "l2_entities" in gold or "l2_triples" in gold:
                return self.get("extraction")
            if "l3_atoms" in gold or "l3_relations" in gold:
                return self.get("argumentation")

        # 3. Inspect predicted representation
        if isinstance(predicted, TheoryNet) or isinstance(predicted, em.TheoryGraph):
            return self.get("structuralist")

        if isinstance(predicted, ArtifactCollection):
            p4 = Phase4ArtifactsView.from_collection(predicted)
            if p4.theory_atoms:
                return self.get("structuralist")
            p2 = Phase2ArtifactsView.from_collection(predicted)
            if p2.entities or p2.local_triples:
                return self.get("extraction")

        # Default fallback
        logger.debug("Falling back to default StructuralistStrategy for evaluation.")
        return self.get("structuralist")


default_registry = StrategyRegistry()
