"""Generator for canned demonstration run manifests and artifact envelopes.

Transforms domain paradigms into self-contained artifact envelopes and manifests
packaged directly within episteme_studio.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def generate_fixtures(base_dir: Path | None = None) -> None:
    """Generate demonstration manifests and artifact envelopes.

    Parameters
    ----------
    base_dir : Path or None, optional
        Target fixtures directory. If None, defaults to current module parent.
    """
    if base_dir is None:
        base_dir = Path(__file__).parent

    runs_dir = base_dir / "runs"
    artifacts_dir = base_dir / "artifacts"
    runs_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    _generate_physics_run(runs_dir, artifacts_dir)
    _generate_psychology_run(runs_dir, artifacts_dir)
    _generate_festinger1959_run(runs_dir, artifacts_dir)


def _write_envelope(
    target_dir: Path,
    artifact_id: str,
    kind: str,
    payload: dict[str, Any],
    run_id: str,
    phase_name: str,
) -> None:
    envelope = {
        "artifact_id": artifact_id,
        "identity_key": artifact_id,
        "kind": kind,
        "run_id": run_id,
        "phase_name": phase_name,
        "payload": payload,
        "provenance": {
            "source_path": f"datasets/{run_id}.cypher",
            "notes": {"generated": "demo_fixture"},
        },
        "created_at": "2026-09-01T10:00:00Z",
    }
    file_path = target_dir / f"{artifact_id}.json"
    file_path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")


def _generate_physics_run(runs_dir: Path, artifacts_dir: Path) -> None:
    run_id = "run-demo-physics"
    run_art_dir = artifacts_dir / run_id
    run_art_dir.mkdir(parents=True, exist_ok=True)

    # 1. Document & Chunks (L1)
    _write_envelope(
        run_art_dir,
        "doc_physics",
        "document",
        {
            "id": "doc_physics",
            "title": "Physics Paradigm Shift: Classical Mechanics to General Relativity",
            "filename": "physics_comprehensive_paradigms.cypher",
            "author": "Isaac Newton / Albert Einstein / Urbain Le Verrier",
        },
        run_id,
        "Phase 1: Data Foundation",
    )

    chunks = [
        ("chunk_phys_1", "Empirical power & T-theoreticity: Inertial mass, spatial distance, and astrometric measurements."),
        ("chunk_phys_2", "Newtonian mechanics (v1): Gravitational law F=G(m1m2)/r^2, motion F=ma, and Keplerian orbital derivations."),
        ("chunk_phys_3", "Theory dynamics & anomaly: Mercury perihelion 43 arcsec/century anomaly and Le Verrier's Vulcan hypothesis."),
        ("chunk_phys_4", "General relativity (v1): Equivalence principle, curved spacetime manifold, and geodesic orbital explanations."),
        ("chunk_phys_5", "Metatheoretical reduction and electrostatics: Coulomb inverse-square law isomorphism and Newtonian reduction."),
    ]
    for cid, text in chunks:
        _write_envelope(
            run_art_dir,
            cid,
            "chunk",
            {
                "id": cid,
                "text": text,
                "chunk_index": int(cid.split("_")[-1]),
                "confidence": 1.0,
            },
            run_id,
            "Phase 1: Data Foundation",
        )

    # 2. Entities (L2)
    entities = [
        ("PT_MASS", "PrimitiveTerm", "Inertial Mass", "Fundamental physical quantity describing inertial resistance."),
        ("PT_DIST", "PrimitiveTerm", "Spatial Distance", "Geometric interval between spatial coordinates."),
        ("EI_TELE", "EmpiricalIndicator", "Telescope Astrometry", "High-precision telescopic tracking of planetary positions."),
        ("TC_ORBIT", "TheoreticalConstruct", "Planetary Orbital Path", "Theoretical construct modeling planetary trajectories."),
        ("TC_ABS_SPACE", "TheoreticalConstruct", "Absolute Space and Time", "Newtonian Euclidean absolute coordinate framework."),
        ("TC_SPACETIME", "TheoreticalConstruct", "Curved Spacetime Manifold", "4-dimensional pseudo-Riemannian metric manifold."),
        ("TN_NEWTON_V1", "TheoryNet", "Classical Mechanics (v1)", "Unifying framework of Newton's laws and universal gravitation."),
        ("CORE_N_V1", "TheoryCore", "Newtonian Core", "Hard core of classical mechanics: laws of motion and gravitation."),
        ("TN_NEWTON_V2", "TheoryNet", "Classical Mechanics (v2)", "Revised Newtonian framework incorporating Vulcan perturbation."),
        ("CORE_N_V2", "TheoryCore", "Newtonian Core (Revised)", "Revised hard core of Newtonian mechanics."),
        ("TN_RELATIVITY_V1", "TheoryNet", "General Relativity (v1)", "Einsteinian geometric theory of gravitation."),
        ("CORE_REL_V1", "TheoryCore", "Einsteinian Core", "Hard core of General Relativity: Equivalence Principle & field equations."),
        ("TN_ELECTRO", "TheoryNet", "Classical Electromagnetism", "Maxwellian electromagnetic field theory."),
        ("APP_JUP_V1", "EmpiricalApplication", "Jupiter Orbit Application", "Application predicting Jupiter's orbital kinematics."),
        ("APP_MERC_REL", "EmpiricalApplication", "Mercury Precession Application", "Application explaining Mercury's 43 arcsec precession."),
    ]
    for eid, etype, name, desc in entities:
        _write_envelope(
            run_art_dir,
            f"entity_{eid}",
            "linked_entity",
            {
                "entity_id": eid,
                "entity_type": etype,
                "canonical_name": name,
                "description": desc,
                "confidence": 0.95,
                "source_chunk_ids": ["chunk_phys_1"],
            },
            run_id,
            "Phase 2: Entity & Local Relation Discovery",
        )

    # 3. Triples / Relations (L2)
    l2_relations = [
        ("rel_ei_tc", "EI_TELE", "MEASURES", "TC_ORBIT"),
        ("rel_tc_pt", "TC_ORBIT", "DETERMINED_BY", "PT_DIST"),
        ("rel_core_tn1", "CORE_N_V1", "BELONGS_TO", "TN_NEWTON_V1"),
        ("rel_core_tn2", "CORE_N_V2", "BELONGS_TO", "TN_NEWTON_V2"),
        ("rel_core_evolves", "CORE_N_V1", "EVOLVES_TO", "CORE_N_V2"),
        ("rel_tn_evolves", "TN_NEWTON_V1", "EVOLVES_TO", "TN_NEWTON_V2"),
        ("rel_core_rel", "CORE_REL_V1", "BELONGS_TO", "TN_RELATIVITY_V1"),
        ("rel_app_jup", "APP_JUP_V1", "BELONGS_TO", "TN_NEWTON_V1"),
        ("rel_app_merc", "APP_MERC_REL", "BELONGS_TO", "TN_RELATIVITY_V1"),
        ("rel_rel_subsumes", "TN_RELATIVITY_V1", "SUBSUMES", "TN_NEWTON_V1"),
        ("rel_rel_reduces", "TN_RELATIVITY_V1", "REDUCES_TO", "TN_NEWTON_V1"),
    ]
    for rid, src, pred, tgt in l2_relations:
        _write_envelope(
            run_art_dir,
            rid,
            "global_relation",
            {
                "relation_id": rid,
                "subject_entity_id": src,
                "predicate": pred,
                "object_entity_id": tgt,
                "confidence": 0.95,
                "scope": "global",
            },
            run_id,
            "Phase 3: Global Relation Extraction",
        )

    # 4. Theory Atoms (L3)
    atoms = [
        ("EV_JUPITER", "Evidence", "Jupiter's orbit follows predicted elliptical path.", "Success", 1.0, 1.0),
        ("EV_MERCURY", "Evidence", "Mercury's perihelion precesses by 43 arcseconds/century more than predicted.", "Anomaly", 1.0, 1.0),
        ("EV_NO_VULCAN", "Evidence", "Telescopic searches reveal no intramercurial planet.", "Failure", 1.0, 1.0),
        ("AX_GRAVITY", "BasicAxiom", "F = G(m1m2)/r^2", "A", 0.98, 1.0),
        ("AX_MOTION", "BasicAxiom", "F = ma", "A", 0.98, 1.0),
        ("DL_KEPLER", "DerivedEmpiricalLaw", "Planets orbit in ellipses.", "B", 0.95, 0.95),
        ("HYP_VULCAN", "Claim", "An unseen planet 'Vulcan' exerts gravitational pull on Mercury.", "A", 0.4, 0.3),
        ("AX_EQUIV", "BasicAxiom", "Equivalence Principle (Inertial mass = Gravitational mass)", "A", 0.99, 1.0),
        ("DL_GEODESIC", "DerivedEmpiricalLaw", "Objects follow geodesics in curved spacetime.", "B", 0.98, 0.99),
        ("AX_COULOMB", "BasicAxiom", "F = k(q1q2)/r^2", "A", 0.95, 1.0),
    ]
    for aid, atype, text, part, conf, plaus in atoms:
        _write_envelope(
            run_art_dir,
            f"atom_{aid}",
            "theory_atom",
            {
                "component_id": aid,
                "component_type": atype,
                "text": text,
                "epistemic_status": part,
                "confidence": conf,
                "plausibility": plaus,
                "source_chunk_id": "chunk_phys_2",
            },
            run_id,
            "Phase 4: Argument Mining",
        )

    # 5. Theory Relations (L3)
    theory_relations = [
        ("trel_grav_kep", "AX_GRAVITY", "SUPPORTS", "DL_KEPLER", 1.0),
        ("trel_mot_kep", "AX_MOTION", "SUPPORTS", "DL_KEPLER", 1.0),
        ("trel_kep_jup", "DL_KEPLER", "EXPLAINS", "APP_JUP_V1", 0.95),
        ("trel_jup_ev", "APP_JUP_V1", "MATCHES_EVIDENCE", "EV_JUPITER", 1.0),
        ("trel_vulc_merc", "HYP_VULCAN", "RESOLVES_ANOMALY", "EV_MERCURY", 0.4),
        ("trel_novulc_att", "EV_NO_VULCAN", "ATTACKS", "HYP_VULCAN", -1.0),
        ("trel_eq_geo", "AX_EQUIV", "SUPPORTS", "DL_GEODESIC", 1.0),
        ("trel_geo_merc", "DL_GEODESIC", "EXPLAINS", "APP_MERC_REL", 0.99),
        ("trel_merc_ev", "APP_MERC_REL", "MATCHES_EVIDENCE", "EV_MERCURY", 1.0),
        ("trel_rel_space_att", "CORE_REL_V1", "ATTACKS", "TC_ABS_SPACE", -0.9),
        ("trel_rel_vulc_att", "APP_MERC_REL", "ATTACKS", "HYP_VULCAN", -0.9),
        ("trel_coul_grav_analog", "AX_COULOMB", "ANALOGOUS_TO", "AX_GRAVITY", 0.85),
    ]
    for trid, src, rtype, tgt, weight in theory_relations:
        _write_envelope(
            run_art_dir,
            trid,
            "theory_relation",
            {
                "relation_id": trid,
                "source_component_id": src,
                "relation_type": rtype,
                "target_component_id": tgt,
                "weight": weight,
                "confidence": abs(weight),
                "scope": "global",
            },
            run_id,
            "Phase 5: Inter-Document Argument Web",
        )

    # Run Manifest
    manifest = {
        "run_id": run_id,
        "pipeline_version": "0.1.0",
        "schema_version": "v1",
        "status": "completed",
        "created_at": "2026-09-01T10:00:00Z",
        "started_at": "2026-09-01T10:00:05Z",
        "completed_at": "2026-09-01T10:04:25Z",
        "duration_seconds": 260.0,
        "primary_input": "physics_comprehensive_paradigms.cypher",
        "input_sources": ["datasets/physics_comprehensive_paradigms.cypher"],
        "tags": ["demo", "physics", "paradigm-shift", "general-relativity"],
        "models": {
            "llm_model": "anthropic/claude-3-5-sonnet",
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "reranker_model": "Alibaba-NLP/gte-reranker-modernbert-base",
            "thinking_level": "high",
        },
        "phase_records": [
            {"ordinal": 1, "phase_name": "Phase 1: Data Foundation", "status": "completed", "reused": False, "artifact_count": 6},
            {"ordinal": 2, "phase_name": "Phase 2: Entity & Local Relation Discovery", "status": "completed", "reused": False, "artifact_count": 15},
            {"ordinal": 3, "phase_name": "Phase 3: Global Relation Extraction", "status": "completed", "reused": False, "artifact_count": 11},
            {"ordinal": 4, "phase_name": "Phase 3b: Latent Graph Consolidation", "status": "completed", "reused": False, "artifact_count": 5},
            {"ordinal": 5, "phase_name": "Phase 4: Entity Maturation", "status": "completed", "reused": False, "artifact_count": 15},
            {"ordinal": 6, "phase_name": "Phase 4: Argument Mining", "status": "completed", "reused": False, "artifact_count": 10},
            {"ordinal": 7, "phase_name": "Phase 5: Inter-Document Argument Web", "status": "completed", "reused": False, "artifact_count": 12},
            {"ordinal": 8, "phase_name": "Phase 6: TheoryNet Projection", "status": "completed", "reused": False, "artifact_count": 8},
        ],
        "artifact_counts_by_kind": {
            "document": 1,
            "chunk": 5,
            "entity": 15,
            "global_relation": 11,
            "theory_atom": 10,
            "theory_relation": 12,
        },
        "config_snapshot": {
            "default_embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "models": {
                "llm_model": "anthropic/claude-3-5-sonnet",
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                "reranker_model": "Alibaba-NLP/gte-reranker-modernbert-base",
            },
            "graph_schema": {
                "version": "v1",
                "node_types": ["PrimitiveTerm", "EmpiricalIndicator", "TheoreticalConstruct", "TheoryNet", "TheoryCore", "EmpiricalApplication"],
                "relation_types": ["MEASURES", "DETERMINED_BY", "BELONGS_TO", "EVOLVES_TO", "SUBSUMES", "REDUCES_TO"],
                "component_types": ["BasicAxiom", "DerivedEmpiricalLaw", "Evidence", "Claim"],
                "argument_relation_types": ["SUPPORTS", "EXPLAINS", "MATCHES_EVIDENCE", "RESOLVES_ANOMALY", "ATTACKS", "ANALOGOUS_TO"],
                "relation_polarities": {
                    "SUPPORTS": 1,
                    "EXPLAINS": 1,
                    "MATCHES_EVIDENCE": 1,
                    "RESOLVES_ANOMALY": 1,
                    "ANALOGOUS_TO": 1,
                    "ATTACKS": -1,
                },
                "component_partitions": {
                    "BasicAxiom": "A",
                    "Claim": "A",
                    "DerivedEmpiricalLaw": "B",
                    "Evidence": "B",
                },
            },
        },
        "fingerprints": {},
    }
    (runs_dir / f"{run_id}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _generate_psychology_run(runs_dir: Path, artifacts_dir: Path) -> None:
    run_id = "run-demo-psychology"
    run_art_dir = artifacts_dir / run_id
    run_art_dir.mkdir(parents=True, exist_ok=True)

    # 1. Document & Chunks (L1)
    _write_envelope(
        run_art_dir,
        "doc_psychology",
        "document",
        {
            "id": "doc_psychology",
            "title": "Paradigm Shifts in Psychology: Phobia Etiology Models",
            "filename": "psychology_paradigms.cypher",
            "author": "Sigmund Freud / B.F. Skinner / Joseph LeDoux",
        },
        run_id,
        "Phase 1: Data Foundation",
    )

    chunks = [
        ("chunk_psych_1", "Shared empirical grounding: Elevated heart rate, fMRI amygdala hyperactivation, and ancestral venomous threats."),
        ("chunk_psych_2", "Freudian psychoanalysis: Phobia as symbolic displacement of repressed psychosexual trauma."),
        ("chunk_psych_3", "Classical behaviorism: Phobia as direct conditioned reflex from painful traumatic events."),
        ("chunk_psych_4", "Evolutionary neuroscience: Phobia as hyper-sensitized evolutionary threat-detection circuit in the amygdala."),
        ("chunk_psych_5", "Paradigm conflict: Epistemic safety, conservatism, and mutual attacks between neuroscientific and clinical models."),
    ]
    for cid, text in chunks:
        _write_envelope(
            run_art_dir,
            cid,
            "chunk",
            {
                "id": cid,
                "text": text,
                "chunk_index": int(cid.split("_")[-1]),
                "confidence": 1.0,
            },
            run_id,
            "Phase 1: Data Foundation",
        )

    # 2. Entities (L2)
    entities = [
        ("T_FREUD", "Theory", "Freudian Psychoanalysis", "Spider phobia as displaced psychosexual conflict."),
        ("T_BEHAVIOR", "Theory", "Classical Behaviorism", "Spider phobia as a purely conditioned associative reflex."),
        ("T_NEURO", "Theory", "Evolutionary Neuroscience", "Spider phobia as hyper-sensitized, evolutionary threat-detection."),
    ]
    for eid, etype, name, desc in entities:
        _write_envelope(
            run_art_dir,
            f"entity_{eid}",
            "linked_entity",
            {
                "entity_id": eid,
                "entity_type": etype,
                "canonical_name": name,
                "description": desc,
                "confidence": 0.95,
                "source_chunk_ids": ["chunk_psych_1"],
            },
            run_id,
            "Phase 2: Entity & Local Relation Discovery",
        )

    # 3. Theory Atoms (L3)
    atoms = [
        ("E1", "EmpiricalSentence", "Subject exhibits elevated heart rate and avoidance behavior when exposed to spiders.", "B", 1.0, 1.0),
        ("E2", "EmpiricalSentence", "fMRI scans show severe hyperactivation in the amygdala during spider exposure.", "B", 1.0, 1.0),
        ("E3", "EmpiricalSentence", "Venomous spiders posed a lethal threat to early hominid ancestors.", "B", 1.0, 1.0),
        ("PB1", "Premise", "The spider is a symbolic displacement of a phallic threat or repressed psychosexual childhood trauma.", "A", 0.5, 0.3),
        ("PB2", "Premise", "The Ego represses trauma into the unconscious to prevent psychological fragmentation.", "A", 0.6, 0.4),
        ("CB", "Claim", "The phobia is a neurotic defense mechanism to avoid confronting repressed childhood conflicts.", "A", 0.4, 0.35),
        ("PC1", "Premise", "The subject experienced a direct, painful conditioning event involving a spider in the past.", "A", 0.7, 0.6),
        ("CC", "Claim", "Phobias are strictly learned associative reflexes (Pavlovian conditioning).", "A", 0.65, 0.6),
        ("PA1", "Premise", "The amygdala is the brain's primary threat-detection and fear-processing center.", "A", 0.95, 0.95),
        ("PA2", "Premise", "Innate fear of historic evolutionary threats provides a survival advantage.", "A", 0.9, 0.9),
        ("CA", "Claim", "Phobias are hyper-sensitized, evolutionary threat-detection circuits localized in the amygdala.", "A", 0.95, 0.95),
    ]
    for aid, atype, text, part, conf, plaus in atoms:
        _write_envelope(
            run_art_dir,
            f"atom_{aid}",
            "theory_atom",
            {
                "component_id": aid,
                "component_type": atype,
                "text": text,
                "epistemic_status": part,
                "confidence": conf,
                "plausibility": plaus,
                "source_chunk_id": "chunk_psych_1",
            },
            run_id,
            "Phase 4: Argument Mining",
        )

    # 4. Theory Relations (L3)
    relations = [
        # Freud chain
        ("trel_pb1_tf", "PB1", "BELONGS_TO", "T_FREUD", 1.0),
        ("trel_pb2_tf", "PB2", "BELONGS_TO", "T_FREUD", 1.0),
        ("trel_cb_tf", "CB", "BELONGS_TO", "T_FREUD", 1.0),
        ("trel_e1_pb1", "E1", "SUPPORTS", "PB1", 0.2),
        ("trel_pb1_pb2", "PB1", "SUPPORTS", "PB2", 0.3),
        ("trel_pb2_cb", "PB2", "SUPPORTS", "CB", 0.4),
        # Behaviorism chain
        ("trel_pc1_tc", "PC1", "BELONGS_TO", "T_BEHAVIOR", 1.0),
        ("trel_cc_tc", "CC", "BELONGS_TO", "T_BEHAVIOR", 1.0),
        ("trel_e1_pc1", "E1", "SUPPORTS", "PC1", 0.7),
        ("trel_pc1_cc", "PC1", "SUPPORTS", "CC", 0.8),
        # Neuroscience chain
        ("trel_pa1_ta", "PA1", "BELONGS_TO", "T_NEURO", 1.0),
        ("trel_pa2_ta", "PA2", "BELONGS_TO", "T_NEURO", 1.0),
        ("trel_ca_ta", "CA", "BELONGS_TO", "T_NEURO", 1.0),
        ("trel_e2_pa1", "E2", "SUPPORTS", "PA1", 0.95),
        ("trel_e3_pa2", "E3", "SUPPORTS", "PA2", 0.90),
        ("trel_pa1_ca", "PA1", "SUPPORTS", "CA", 0.95),
        ("trel_pa2_ca", "PA2", "SUPPORTS", "CA", 0.90),
        ("trel_e1_ca", "E1", "SUPPORTS", "CA", 0.85),
        # Paradigm conflicts
        ("trel_ca_att_cb", "CA", "ATTACKS", "CB", -0.9),
        ("trel_cc_att_cb", "CC", "ATTACKS", "CB", -0.6),
        ("trel_cb_att_cc", "CB", "ATTACKS", "CC", -0.6),
        ("trel_ca_att_cc", "CA", "ATTACKS", "CC", -0.4),
    ]
    for trid, src, rtype, tgt, weight in relations:
        _write_envelope(
            run_art_dir,
            trid,
            "theory_relation",
            {
                "relation_id": trid,
                "source_component_id": src,
                "relation_type": rtype,
                "target_component_id": tgt,
                "weight": weight,
                "confidence": abs(weight),
                "scope": "global",
            },
            run_id,
            "Phase 5: Inter-Document Argument Web",
        )

    # Run Manifest
    manifest = {
        "run_id": run_id,
        "pipeline_version": "0.1.0",
        "schema_version": "v1",
        "status": "completed",
        "created_at": "2026-09-01T11:00:00Z",
        "started_at": "2026-09-01T11:00:05Z",
        "completed_at": "2026-09-01T11:03:45Z",
        "duration_seconds": 220.0,
        "primary_input": "psychology_paradigms.cypher",
        "input_sources": ["datasets/psychology_paradigms.cypher"],
        "tags": ["demo", "psychology", "paradigm-conflict", "epistemic-safety"],
        "models": {
            "llm_model": "openai/gpt-4o",
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "reranker_model": "Alibaba-NLP/gte-reranker-modernbert-base",
            "thinking_level": "medium",
        },
        "phase_records": [
            {"ordinal": 1, "phase_name": "Phase 1: Data Foundation", "status": "completed", "reused": False, "artifact_count": 6},
            {"ordinal": 2, "phase_name": "Phase 2: Entity & Local Relation Discovery", "status": "completed", "reused": False, "artifact_count": 3},
            {"ordinal": 3, "phase_name": "Phase 3: Global Relation Extraction", "status": "completed", "reused": False, "artifact_count": 0},
            {"ordinal": 4, "phase_name": "Phase 3b: Latent Graph Consolidation", "status": "completed", "reused": False, "artifact_count": 2},
            {"ordinal": 5, "phase_name": "Phase 4: Entity Maturation", "status": "completed", "reused": False, "artifact_count": 3},
            {"ordinal": 6, "phase_name": "Phase 4: Argument Mining", "status": "completed", "reused": False, "artifact_count": 11},
            {"ordinal": 7, "phase_name": "Phase 5: Inter-Document Argument Web", "status": "completed", "reused": False, "artifact_count": 22},
            {"ordinal": 8, "phase_name": "Phase 6: TheoryNet Projection", "status": "completed", "reused": False, "artifact_count": 5},
        ],
        "artifact_counts_by_kind": {
            "document": 1,
            "chunk": 5,
            "entity": 3,
            "theory_atom": 11,
            "theory_relation": 22,
        },
        "config_snapshot": {
            "default_embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "models": {
                "llm_model": "openai/gpt-4o",
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                "reranker_model": "Alibaba-NLP/gte-reranker-modernbert-base",
            },
            "graph_schema": {
                "version": "v1",
                "node_types": ["Theory"],
                "relation_types": ["BELONGS_TO"],
                "component_types": ["EmpiricalSentence", "Premise", "Claim"],
                "argument_relation_types": ["SUPPORTS", "ATTACKS", "BELONGS_TO"],
                "relation_polarities": {
                    "SUPPORTS": 1,
                    "BELONGS_TO": 1,
                    "ATTACKS": -1,
                },
                "component_partitions": {
                    "Premise": "A",
                    "Claim": "A",
                    "EmpiricalSentence": "B",
                },
            },
        },
        "fingerprints": {},
    }
    (runs_dir / f"{run_id}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _generate_festinger1959_run(runs_dir: Path, artifacts_dir: Path) -> None:
    """Generate demonstration run manifest and artifact envelopes for Festinger & Carlsmith (1959).

    Produces exact span groundings in `festinger_carlsmith_1959.md`, formal ratio axioms,
    experimental corroboration models, and dialectical Janis-King rebuttal relationships.

    Parameters
    ----------
    runs_dir : Path
        Directory destination for run manifests.
    artifacts_dir : Path
        Directory destination for run artifact envelope bundles.
    """
    run_id = "run-demo-festinger1959"
    run_art_dir = artifacts_dir / run_id
    run_art_dir.mkdir(parents=True, exist_ok=True)

    # 1. Document (L1)
    _write_envelope(
        run_art_dir,
        "doc_festinger1959",
        "document",
        {
            "id": "festinger_carlsmith_1959",
            "title": "Cognitive Consequences of Forced Compliance",
            "filename": "festinger_carlsmith_1959.md",
            "author": "Leon Festinger & James M. Carlsmith",
            "year": 1959,
            "journal": "Journal of Abnormal and Social Psychology",
            "volume": 58,
            "issue": 2,
            "pages": "203-210",
            "doi": "10.1037/h0041593",
        },
        run_id,
        "Phase 1: Data Foundation",
    )

    # 2. Chunks (L1) with exact verified character offsets in datasets/festinger_carlsmith_1959.md
    chunks = [
        (
            "chunk_fc1959_ratio_law",
            1,
            3723,
            4072,
            'In evaluating the total magnitude of dissonance, one must take account of both dissonances and consonances. Let us think of the sum of all the dissonances involving some particular cognition as "D" and the sum of all the consonances as "C." Then we might think of the total magnitude of dissonance as being a function of "D" divided by "D" plus "C."',
        ),
        (
            "chunk_fc1959_inverse_reward_prediction",
            2,
            5565,
            5703,
            "The prediction [from 3 and 4 above] is that the larger the reward given to the subject, the smaller will be the subsequent opinion change.",
        ),
        (
            "chunk_fc1959_corroboration_finding",
            3,
            23586,
            23892,
            "In short, when an S was induced, by offer of reward, to say something contrary to his private opinion, this private opinion tended to change so as to correspond more closely with what he had said. The greater the reward offered (beyond what was necessary to elicit the behavior) the smaller was the effect.",
        ),
        (
            "chunk_fc1959_procedure_summary",
            4,
            31652,
            31983,
            "A laboratory experiment was designed to test these derivations. Subjects were subjected to a boring experience and then paid to tell someone that the experience had been interesting and enjoyable. The amount of money paid the subject was varied. The private opinions of the subjects concerning the experiences were then determined.",
        ),
        (
            "chunk_fc1959_rehearsal_hypothesis",
            5,
            28025,
            28417,
            "Specifically, as applied to our results, this alternative explanation would maintain that perhaps, for some reason, the Ss in the One Dollar condition worked harder at telling the waiting girl that the tasks were fun and enjoyable. That is, in the One Dollar condition they may have rehearsed it more mentally, thought up more ways of saying it, may have said it more convincingly, and so on.",
        ),
        (
            "chunk_fc1959_rehearsal_defeated",
            6,
            30394,
            30608,
            "We are certainly justified in concluding that the Ss in the One Dollar condition did not improvise more nor act more convincingly. Hence, the alternative explanation discussed above cannot account for the findings.",
        ),
    ]
    for cid, idx, c_start, c_end, text in chunks:
        _write_envelope(
            run_art_dir,
            cid,
            "chunk",
            {
                "id": cid,
                "text": text,
                "chunk_index": idx,
                "char_start": c_start,
                "char_end": c_end,
                "confidence": 1.0,
                "doc_id": "festinger_carlsmith_1959",
            },
            run_id,
            "Phase 1: Data Foundation",
        )

    # 3. Entities (L2)
    entities = [
        ("str:TE_DissF", "TheoryElement", "T(DissF) - Forced Compliance Domain Core", "Structuralist theory-element core for forced compliance cognitive dissonance."),
        ("str:TE_DissF6", "TheoryElement", "T(DissF6) - Festinger-Carlsmith Forced Compliance Reward Model", "Specialized theory-element model predicting magnitude of opinion change under varied incentive rewards."),
        ("str:MP_DissF6", "PotentialModel", "M_p(DissF6) - Potential Models of Forced Compliance", "Potential models structure M_p = <S, X, notX, Reward, Dissonance, Consonance, OpinionChange>."),
        ("str:M_DissF6_RatioLaw", "ActualModel", "M(DissF6) - Dissonance Magnitude Ratio Law", "Actual model axiom defining dissonance magnitude as ratio D / (D + C)."),
        ("str:M_DissF6_InverseRewardLaw", "ActualModel", "M(DissF6) - Inverse Reward Prediction Law", "Axiom stating negative partial derivative of opinion change with respect to magnitude of reward."),
        ("str:M_DissF6_Corroboration", "ActualModel", "M(DissF6) - Experimental Corroboration Law", "Observed empirical model: opinion change in $1 condition exceeds $20 condition."),
        ("str:I0_Carlsmith1959", "Paradigm", "I_0(Carlsmith1959) - $1/$20 Forced Compliance Experimental Paradigm", "Paradigm intended application using peg-turning spools and confederate interview."),
        ("str:TE_Alternative_Rehearsal", "Hypothesis", "Hypothesis: Janis-King Mental Rehearsal Alternative Explanation", "Alternative incentive/rehearsal explanation positing greater cognitive rehearsal in $1 subjects."),
        ("str:EV_Rehearsal_Defeated", "Evidence", "Evidence: Table 2 Observer Ratings Defeating Mental Rehearsal", "Empirical observer ratings demonstrating no difference in persuasiveness or rehearsal."),
    ]
    for eid, etype, name, desc in entities:
        clean_eid = eid.replace("str:", "")
        _write_envelope(
            run_art_dir,
            f"entity_{clean_eid}",
            "linked_entity",
            {
                "entity_id": eid,
                "entity_type": etype,
                "canonical_name": name,
                "description": desc,
                "confidence": 1.0,
                "source_chunk_ids": ["chunk_fc1959_ratio_law"],
            },
            run_id,
            "Phase 2: Entity & Local Relation Discovery",
        )

    # 4. Theory Atoms (L3) with grounded TextAnchors
    atoms = [
        ("str:TE_DissF", "TheoryElement", "T(DissF) - Forced Compliance Domain Core", "chunk_fc1959_ratio_law", None),
        (
            "str:TE_DissF6",
            "TheoryElement",
            "T(DissF6) - Festinger-Carlsmith Forced Compliance Reward Model",
            "chunk_fc1959_inverse_reward_prediction",
            {
                "sourceDocId": "festinger_carlsmith_1959",
                "chunkId": "chunk_fc1959_inverse_reward_prediction",
                "charStart": 5565,
                "charEnd": 5703,
                "verbatimQuote": "The prediction [from 3 and 4 above] is that the larger the reward given to the subject, the smaller will be the subsequent opinion change.",
            },
        ),
        (
            "str:MP_DissF6",
            "PotentialModel",
            "M_p(DissF6) = <S, X, notX, Reward, Dissonance, Consonance, OpinionChange>",
            "chunk_fc1959_ratio_law",
            {
                "sourceDocId": "festinger_carlsmith_1959",
                "chunkId": "chunk_fc1959_ratio_law",
                "charStart": 3723,
                "charEnd": 4072,
                "verbatimQuote": 'In evaluating the total magnitude of dissonance, one must take account of both dissonances and consonances. Let us think of the sum of all the dissonances involving some particular cognition as "D" and the sum of all the consonances as "C." Then we might think of the total magnitude of dissonance as being a function of "D" divided by "D" plus "C."',
            },
        ),
        (
            "str:M_DissF6_RatioLaw",
            "ActualModel",
            "diss_magnitude = f(D / (D + C))",
            "chunk_fc1959_ratio_law",
            {
                "sourceDocId": "festinger_carlsmith_1959",
                "chunkId": "chunk_fc1959_ratio_law",
                "charStart": 3723,
                "charEnd": 4072,
                "verbatimQuote": 'In evaluating the total magnitude of dissonance, one must take account of both dissonances and consonances. Let us think of the sum of all the dissonances involving some particular cognition as "D" and the sum of all the consonances as "C." Then we might think of the total magnitude of dissonance as being a function of "D" divided by "D" plus "C."',
            },
        ),
        (
            "str:M_DissF6_InverseRewardLaw",
            "ActualModel",
            "forall s in S: reward(s) > reward_min -> d(opinion_change)/d(reward) < 0",
            "chunk_fc1959_inverse_reward_prediction",
            {
                "sourceDocId": "festinger_carlsmith_1959",
                "chunkId": "chunk_fc1959_inverse_reward_prediction",
                "charStart": 5565,
                "charEnd": 5703,
                "verbatimQuote": "The prediction [from 3 and 4 above] is that the larger the reward given to the subject, the smaller will be the subsequent opinion change.",
            },
        ),
        (
            "str:M_DissF6_Corroboration",
            "ActualModel",
            "opinion_change(s | reward=1) > opinion_change(s | reward=20) >= opinion_change(s | control)",
            "chunk_fc1959_corroboration_finding",
            {
                "sourceDocId": "festinger_carlsmith_1959",
                "chunkId": "chunk_fc1959_corroboration_finding",
                "charStart": 23586,
                "charEnd": 23892,
                "verbatimQuote": "In short, when an S was induced, by offer of reward, to say something contrary to his private opinion, this private opinion tended to change so as to correspond more closely with what he had said. The greater the reward offered (beyond what was necessary to elicit the behavior) the smaller was the effect.",
            },
        ),
        (
            "str:I0_Carlsmith1959",
            "Paradigm",
            "I_0(Carlsmith1959) - $1/$20 Forced Compliance Experimental Paradigm",
            "chunk_fc1959_procedure_summary",
            {
                "sourceDocId": "festinger_carlsmith_1959",
                "chunkId": "chunk_fc1959_procedure_summary",
                "charStart": 31652,
                "charEnd": 31983,
                "verbatimQuote": "A laboratory experiment was designed to test these derivations. Subjects were subjected to a boring experience and then paid to tell someone that the experience had been interesting and enjoyable. The amount of money paid the subject was varied. The private opinions of the subjects concerning the experiences were then determined.",
            },
        ),
        (
            "str:TE_Alternative_Rehearsal",
            "Hypothesis",
            "Hypothesis: Janis-King Mental Rehearsal Alternative Explanation",
            "chunk_fc1959_rehearsal_hypothesis",
            {
                "sourceDocId": "festinger_carlsmith_1959",
                "chunkId": "chunk_fc1959_rehearsal_hypothesis",
                "charStart": 28025,
                "charEnd": 28417,
                "verbatimQuote": "Specifically, as applied to our results, this alternative explanation would maintain that perhaps, for some reason, the Ss in the One Dollar condition worked harder at telling the waiting girl that the tasks were fun and enjoyable. That is, in the One Dollar condition they may have rehearsed it more mentally, thought up more ways of saying it, may have said it more convincingly, and so on.",
            },
        ),
        (
            "str:EV_Rehearsal_Defeated",
            "Evidence",
            "Evidence: Table 2 Observer Ratings Defeating Mental Rehearsal",
            "chunk_fc1959_rehearsal_defeated",
            {
                "sourceDocId": "festinger_carlsmith_1959",
                "chunkId": "chunk_fc1959_rehearsal_defeated",
                "charStart": 30394,
                "charEnd": 30608,
                "verbatimQuote": "We are certainly justified in concluding that the Ss in the One Dollar condition did not improvise more nor act more convincingly. Hence, the alternative explanation discussed above cannot account for the findings.",
            },
        ),
    ]
    for aid, atype, text, chunk_id, anchor in atoms:
        clean_aid = aid.replace("str:", "")
        payload: dict[str, Any] = {
            "component_id": aid,
            "component_type": atype,
            "text": text,
            "confidence": 1.0,
            "source_chunk_id": chunk_id,
        }
        if anchor:
            payload["text_anchor"] = anchor
        _write_envelope(
            run_art_dir,
            f"atom_{clean_aid}",
            "theory_atom",
            payload,
            run_id,
            "Phase 4: Argument Mining",
        )

    # 5. Theory Relations (L3)
    theory_relations = [
        ("trel_fc_spec", "str:TE_DissF", "specializes", "str:TE_DissF6", 1.0),
        ("trel_fc_mp", "str:TE_DissF6", "hasPotentialModel", "str:MP_DissF6", 1.0),
        ("trel_fc_m1", "str:TE_DissF6", "hasActualModel", "str:M_DissF6_RatioLaw", 1.0),
        ("trel_fc_m2", "str:TE_DissF6", "hasActualModel", "str:M_DissF6_InverseRewardLaw", 1.0),
        ("trel_fc_m3", "str:TE_DissF6", "hasActualModel", "str:M_DissF6_Corroboration", 1.0),
        ("trel_fc_i0", "str:TE_DissF6", "hasParadigm", "str:I0_Carlsmith1959", 1.0),
        ("trel_fc_alt_att", "str:TE_Alternative_Rehearsal", "attacks", "str:TE_DissF6", -1.0),
        ("trel_fc_ev_att", "str:EV_Rehearsal_Defeated", "attacks", "str:TE_Alternative_Rehearsal", -1.0),
    ]
    for trid, src, rtype, tgt, weight in theory_relations:
        _write_envelope(
            run_art_dir,
            trid,
            "theory_relation",
            {
                "relation_id": trid,
                "source_component_id": src,
                "relation_type": rtype,
                "target_component_id": tgt,
                "weight": weight,
                "confidence": abs(weight),
                "scope": "global",
            },
            run_id,
            "Phase 5: Inter-Document Argument Web",
        )

    # 6. Run Manifest
    manifest = {
        "run_id": run_id,
        "pipeline_version": "0.1.0",
        "schema_version": "v1",
        "status": "completed",
        "created_at": "2026-09-02T14:00:00Z",
        "started_at": "2026-09-02T14:00:05Z",
        "completed_at": "2026-09-02T14:03:45Z",
        "duration_seconds": 220.0,
        "primary_input": "festinger_carlsmith_1959.md",
        "input_sources": ["datasets/festinger_carlsmith_1959.md"],
        "tags": ["demo", "psychology", "cognitive-dissonance", "festinger-carlsmith", "structuralism"],
        "models": {
            "llm_model": "anthropic/claude-3-5-sonnet",
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "reranker_model": "Alibaba-NLP/gte-reranker-modernbert-base",
            "thinking_level": "high",
        },
        "phase_records": [
            {"ordinal": 1, "phase_name": "Phase 1: Data Foundation", "status": "completed", "reused": False, "artifact_count": 7},
            {"ordinal": 2, "phase_name": "Phase 2: Entity & Local Relation Discovery", "status": "completed", "reused": False, "artifact_count": 9},
            {"ordinal": 3, "phase_name": "Phase 3: Global Relation Extraction", "status": "completed", "reused": False, "artifact_count": 0},
            {"ordinal": 4, "phase_name": "Phase 3b: Latent Graph Consolidation", "status": "completed", "reused": False, "artifact_count": 3},
            {"ordinal": 5, "phase_name": "Phase 4: Entity Maturation", "status": "completed", "reused": False, "artifact_count": 9},
            {"ordinal": 6, "phase_name": "Phase 4: Argument Mining", "status": "completed", "reused": False, "artifact_count": 9},
            {"ordinal": 7, "phase_name": "Phase 5: Inter-Document Argument Web", "status": "completed", "reused": False, "artifact_count": 8},
            {"ordinal": 8, "phase_name": "Phase 6: TheoryNet Projection", "status": "completed", "reused": False, "artifact_count": 9},
        ],
        "artifact_counts_by_kind": {
            "document": 1,
            "chunk": 6,
            "entity": 9,
            "theory_atom": 9,
            "theory_relation": 8,
        },
        "config_snapshot": {
            "default_embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "models": {
                "llm_model": "anthropic/claude-3-5-sonnet",
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                "reranker_model": "Alibaba-NLP/gte-reranker-modernbert-base",
            },
            "graph_schema": {
                "version": "v1",
                "node_types": ["TheoryElement", "PotentialModel", "ActualModel", "Paradigm", "Hypothesis", "Evidence"],
                "relation_types": ["specializes", "hasPotentialModel", "hasActualModel", "hasParadigm", "attacks"],
                "component_types": ["TheoryElement", "PotentialModel", "ActualModel", "Paradigm", "Hypothesis", "Evidence"],
                "argument_relation_types": ["specializes", "hasPotentialModel", "hasActualModel", "hasParadigm", "attacks"],
                "relation_polarities": {
                    "specializes": 1,
                    "hasPotentialModel": 1,
                    "hasActualModel": 1,
                    "hasParadigm": 1,
                    "attacks": -1,
                },
                "component_partitions": {
                    "TheoryElement": "A",
                    "PotentialModel": "A",
                    "ActualModel": "A",
                    "Hypothesis": "A",
                    "Paradigm": "B",
                    "Evidence": "B",
                },
            },
        },
        "fingerprints": {},
    }
    (runs_dir / f"{run_id}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    generate_fixtures()
    print("Demo fixtures successfully generated in episteme_studio/fixtures/")
