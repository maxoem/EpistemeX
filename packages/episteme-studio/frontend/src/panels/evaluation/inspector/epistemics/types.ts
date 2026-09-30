export interface BourbakiSubElement {
  id: string;
  name: string;
  symbol: string;
  classType: "Mp" | "M" | "Mpp" | "C" | "I";
  parentAxiomId?: string;
  reference_count: number;
  predicted_count: number;
  matched_count: number;
  coverage: number;
  status: "pass" | "root_cause_omission" | "cascade_masked_orphan" | "active";
  rationale?: string;
  formula?: string;
  quote?: string;
  citation?: string;
  topologicalRank?: number;
  dependencies?: string[];
  dependents?: string[];
  inferentialPolarity?: {
    predicate: "SUPPORTS" | "ATTACKS" | "PROVES" | "REFUTES" | "UNDERCUTS";
    goldPredicate: "SUPPORTS" | "ATTACKS" | "PROVES" | "REFUTES" | "UNDERCUTS";
    targetNode: string;
    similarity: number;
    concordance: "CONCORDANT" | "CRITICAL_INVERSION" | "MODERATE_MISALIGNMENT";
    dialecticalNote: string;
  };
  dagProperties?: {
    isAcyclic: boolean;
    transitiveReductionRetained: boolean;
    reachabilityScore: number;
    posetDepth: number;
  };
}

export const CLASS_METADATA: Record<
  string,
  { label: string; symbol: string; color: string; bg: string; border: string; description: string }
> = {
  Mp: {
    label: "Potential Models",
    symbol: "Mp",
    color: "text-blue-500 dark:text-blue-400",
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
    description: "Mathematical frame structures and foundational axioms of the theory.",
  },
  M: {
    label: "Actual Models",
    symbol: "M",
    color: "text-emerald-500 dark:text-emerald-400",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
    description: "Core physical laws and domain axioms fulfilling the potential models.",
  },
  Mpp: {
    label: "Partial Potential Models",
    symbol: "Mpp",
    color: "text-amber-500 dark:text-amber-400",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    description: "Empirical basis and non-theoretical conceptual structures.",
  },
  C: {
    label: "Constraints",
    symbol: "C",
    color: "text-purple-500 dark:text-purple-400",
    bg: "bg-purple-500/10",
    border: "border-purple-500/30",
    description: "Cross-model constraints ensuring parameter consistency (e.g. constant masses).",
  },
  I: {
    label: "Intended Applications",
    symbol: "I",
    color: "text-orange-500 dark:text-orange-400",
    bg: "bg-orange-500/10",
    border: "border-orange-500/30",
    description: "Concrete empirical paradigms and target systems (e.g. planetary orbits, pendulums).",
  },
};

/**
 * Generates the canonical list of Bourbaki structuralist elements, complete with
 * mathematical formulations, textual citations, DAG dependencies, and inferential polarity.
 */
export function getBourbakiSubElements(
  activeReport?: any,
  decompositionEntries?: any[]
): BourbakiSubElement[] {
  const omitted = activeReport?.omitted_components || [];
  const hasMpOmission =
    omitted.some((c: string) => c.toLowerCase().includes("axiom") || c.toLowerCase().includes("mp")) ||
    (decompositionEntries?.find((d) => d.symbol === "Mp" || d.class_name?.includes("potential"))?.completeness ?? 1) < 1.0;

  return [
    // Mp Elements (Foundational Axioms)
    {
      id: "ax_01_space_metric",
      name: "Axiom-01 (Spatiotemporal Kinematics)",
      symbol: "Mp.1",
      classType: "Mp",
      reference_count: 1,
      predicted_count: 1,
      matched_count: 1,
      coverage: 1.0,
      status: "pass",
      formula: "M = ⟨R³ × R, g_μν, ∇⟩  (Affine Euclidean Space-Time)",
      quote:
        "Space and time are presupposed as smooth affine 4-manifolds endowed with a Euclidean metric on each spatial slice.",
      citation: "Newton (1687) Principia Mathematica, Scholium on Space & Time",
      topologicalRank: 0,
      dependencies: [],
      dependents: ["m_01_inertial_dynamics", "i_01_planetary_orbits"],
      inferentialPolarity: {
        predicate: "PROVES",
        goldPredicate: "PROVES",
        targetNode: "Sub-Model 01-A (Inertial Force Equations)",
        similarity: 0.94,
        concordance: "CONCORDANT",
        dialecticalNote: "Foundational structural entailment verified against classical mechanics frame.",
      },
      dagProperties: {
        isAcyclic: true,
        transitiveReductionRetained: true,
        reachabilityScore: 1.0,
        posetDepth: 0,
      },
      rationale: "Topology and metric spaces accurately grounded in primary text.",
    },
    {
      id: "ax_02_dynamical_conservation",
      name: "Axiom-02 (Conservation of Momentum/Force)",
      symbol: "Mp.2",
      classType: "Mp",
      reference_count: 1,
      predicted_count: 0,
      matched_count: 0,
      coverage: 0.0,
      status: "root_cause_omission",
      formula: "∑ F_ext = 0 ⟹ d/dt (∑ p_i) = 0",
      quote:
        "To every action there is always opposed an equal reaction; or the mutual actions of two bodies upon each other are always equal.",
      citation: "Newton (1687) Principia, Axiomata sive Leges Motus, Lex III",
      topologicalRank: 0,
      dependencies: [],
      dependents: ["m_02_gravitational_law", "i_02_lunar_perturbation"],
      inferentialPolarity: {
        predicate: "UNDERCUTS",
        goldPredicate: "PROVES",
        targetNode: "Sub-Model 02-A (Gravitational Force Balance)",
        similarity: 0.28,
        concordance: "CRITICAL_INVERSION",
        dialecticalNote:
          "Root extraction failure severed entailment path; pipeline inverted dependency from supportive entailment to undercutting.",
      },
      dagProperties: {
        isAcyclic: true,
        transitiveReductionRetained: false,
        reachabilityScore: 0.0,
        posetDepth: 0,
      },
      rationale: "Extraction failed to extract foundational conservation condition from Chapter II, §4.",
    },
    {
      id: "ax_03_inertial_frames",
      name: "Axiom-03 (Inertial Frame Equivalence)",
      symbol: "Mp.3",
      classType: "Mp",
      reference_count: 1,
      predicted_count: 1,
      matched_count: 1,
      coverage: 1.0,
      status: "pass",
      formula: "x' = x - vt,  t' = t  (Galilean Invariance)",
      quote:
        "The motions of bodies included in a given space are the same among themselves, whether that space is at rest or moves uniformly forwards in a right line.",
      citation: "Galileo (1632) Dialogo; Newton Cor. V",
      topologicalRank: 0,
      dependencies: [],
      dependents: ["m_03_harmonic_spring", "i_03_terrestrial_free_fall"],
      inferentialPolarity: {
        predicate: "PROVES",
        goldPredicate: "PROVES",
        targetNode: "Sub-Model 03-C (Hookean Elastic Restoring Force)",
        similarity: 0.92,
        concordance: "CONCORDANT",
        dialecticalNote: "Equivalence invariance confirmed across inertial reference frames.",
      },
      dagProperties: {
        isAcyclic: true,
        transitiveReductionRetained: true,
        reachabilityScore: 1.0,
        posetDepth: 0,
      },
      rationale: "Extracted and mapped to Galilean relativity schema.",
    },

    // M Elements (Actual Models)
    {
      id: "m_01_inertial_dynamics",
      name: "Sub-Model 01-A (Inertial Force Equations)",
      symbol: "M.1",
      classType: "M",
      parentAxiomId: "ax_01_space_metric",
      reference_count: 1,
      predicted_count: 1,
      matched_count: 1,
      coverage: 1.0,
      status: "pass",
      formula: "F = d(mv)/dt = m · a",
      quote:
        "The alteration of motion is ever proportional to the motive force impress'd; and is made in the direction of the right line in which that force is impress'd.",
      citation: "Newton (1687) Principia, Lex II",
      topologicalRank: 1,
      dependencies: ["ax_01_space_metric"],
      dependents: ["i_01_planetary_orbits"],
      inferentialPolarity: {
        predicate: "SUPPORTS",
        goldPredicate: "SUPPORTS",
        targetNode: "Paradigm I-01 (Keplerian Planetary Orbits)",
        similarity: 0.96,
        concordance: "CONCORDANT",
        dialecticalNote: "Second law of motion provides the dynamical engine for planetary orbital deduction.",
      },
      dagProperties: {
        isAcyclic: true,
        transitiveReductionRetained: true,
        reachabilityScore: 1.0,
        posetDepth: 1,
      },
      rationale: "F = m*a derived successfully from Spatiotemporal frame.",
    },
    {
      id: "m_02_gravitational_law",
      name: "Sub-Model 02-A (Gravitational Force Balance)",
      symbol: "M.2",
      classType: "M",
      parentAxiomId: "ax_02_dynamical_conservation",
      reference_count: 1,
      predicted_count: 0,
      matched_count: 0,
      coverage: 0.0,
      status: "cascade_masked_orphan",
      formula: "F_12 = -G · (m_1 · m_2 / |r_12|²) · r̂_12",
      quote:
        "Every particle of matter attracts every other particle with a force proportional to the product of their masses and inversely as the square of the distance.",
      citation: "Newton (1687) Principia, Book III, Prop. VII",
      topologicalRank: 1,
      dependencies: ["ax_02_dynamical_conservation"],
      dependents: ["i_02_lunar_perturbation"],
      inferentialPolarity: {
        predicate: "ATTACKS",
        goldPredicate: "PROVES",
        targetNode: "Empirical Claim 08 (Lunar Perturbation & Tides)",
        similarity: 0.38,
        concordance: "CRITICAL_INVERSION",
        dialecticalNote:
          "Cascade-orphaned law flagged as dialectical attack instead of deductive foundation.",
      },
      dagProperties: {
        isAcyclic: true,
        transitiveReductionRetained: false,
        reachabilityScore: 0.0,
        posetDepth: 1,
      },
      rationale:
        "Orphaned due to missing parent Axiom-02. Masked under Bourbaki cascade doctrine to prevent double-penalization.",
    },
    {
      id: "m_03_harmonic_spring",
      name: "Sub-Model 03-C (Hookean Elastic Restoring Force)",
      symbol: "M.3",
      classType: "M",
      parentAxiomId: "ax_03_inertial_frames",
      reference_count: 1,
      predicted_count: 1,
      matched_count: 1,
      coverage: 1.0,
      status: "pass",
      formula: "F_restoring = -k · Δx",
      quote: "Ut tensio, sic vis: the power of any spring is in the same proportion with the tension thereof.",
      citation: "Hooke (1678) De Potentia Restitutiva",
      topologicalRank: 1,
      dependencies: ["ax_03_inertial_frames"],
      dependents: ["i_03_terrestrial_free_fall"],
      inferentialPolarity: {
        predicate: "SUPPORTS",
        goldPredicate: "SUPPORTS",
        targetNode: "Empirical Claim 03 (Terrestrial Free Fall in Vacuum)",
        similarity: 0.88,
        concordance: "CONCORDANT",
        dialecticalNote: "Oscillator bounds provide empirical consistency checks for terrestrial dynamics.",
      },
      dagProperties: {
        isAcyclic: true,
        transitiveReductionRetained: true,
        reachabilityScore: 1.0,
        posetDepth: 1,
      },
      rationale: "Linear oscillator laws mapped with correct parameters.",
    },

    // Mpp Elements (Partial Potential Models)
    {
      id: "mpp_01_kinematic_particles",
      name: "Kinematic Positions & Velocities",
      symbol: "Mpp.1",
      classType: "Mpp",
      reference_count: 1,
      predicted_count: 1,
      matched_count: 1,
      coverage: 1.0,
      status: "pass",
      formula: "γ: I → R³,  v(t) = dγ/dt",
      quote: "Observed particle trajectory coordinates measured by terrestrial and astronomical observations.",
      citation: "Galileo (1638) Discorsi e Dimostrazioni Matematiche",
      topologicalRank: 0,
      dependencies: [],
      dependents: ["m_01_inertial_dynamics"],
      inferentialPolarity: {
        predicate: "SUPPORTS",
        goldPredicate: "SUPPORTS",
        targetNode: "Sub-Model 01-A (Inertial Force Equations)",
        similarity: 0.95,
        concordance: "CONCORDANT",
        dialecticalNote: "Empirical kinematic trajectories match the actual model formulation.",
      },
      dagProperties: {
        isAcyclic: true,
        transitiveReductionRetained: true,
        reachabilityScore: 1.0,
        posetDepth: 0,
      },
      rationale: "Empirical observation base successfully matched to text tokens.",
    },
    {
      id: "mpp_02_time_measurement",
      name: "Chronometric Standard Clock Intervals",
      symbol: "Mpp.2",
      classType: "Mpp",
      reference_count: 1,
      predicted_count: 1,
      matched_count: 1,
      coverage: 1.0,
      status: "pass",
      formula: "Δt = t_2 - t_1 ∈ R⁺  (Standard Unit Measure)",
      quote: "Absolute, true, and mathematical time, of itself, and from its own nature, flows equably without relation to anything external.",
      citation: "Newton (1687) Principia, Scholium §1",
      topologicalRank: 0,
      dependencies: [],
      dependents: ["m_01_inertial_dynamics"],
      inferentialPolarity: {
        predicate: "SUPPORTS",
        goldPredicate: "SUPPORTS",
        targetNode: "Sub-Model 01-A (Inertial Force Equations)",
        similarity: 0.93,
        concordance: "CONCORDANT",
        dialecticalNote: "Temporal metric standards verified across all dynamical schemas.",
      },
      dagProperties: {
        isAcyclic: true,
        transitiveReductionRetained: true,
        reachabilityScore: 1.0,
        posetDepth: 0,
      },
      rationale: "Temporal measure concepts verified.",
    },

    // C Elements (Constraints)
    {
      id: "c_01_mass_equality",
      name: "Invariance of Gravitational & Inertial Mass",
      symbol: "C.1",
      classType: "C",
      reference_count: 1,
      predicted_count: 1,
      matched_count: 1,
      coverage: 1.0,
      status: "pass",
      formula: "m_inertial ≡ m_gravitational  (∀ x ∈ Matter)",
      quote: "By experiments made with pendulums, I found the quantity of matter in bodies to be proportional to their weight.",
      citation: "Newton (1687) Principia, Book III, Prop. VI; Bessel (1832)",
      topologicalRank: 1,
      dependencies: ["ax_01_space_metric"],
      dependents: ["m_02_gravitational_law"],
      inferentialPolarity: {
        predicate: "PROVES",
        goldPredicate: "PROVES",
        targetNode: "Sub-Model 02-A (Gravitational Force Balance)",
        similarity: 0.97,
        concordance: "CONCORDANT",
        dialecticalNote: "Universal equivalence constraint correctly links kinematics with gravitational coupling.",
      },
      dagProperties: {
        isAcyclic: true,
        transitiveReductionRetained: true,
        reachabilityScore: 1.0,
        posetDepth: 1,
      },
      rationale: "Equivalence constraint verified across multiple model instances.",
    },

    // I Elements (Intended Applications / Empirical Paradigms)
    {
      id: "i_01_planetary_orbits",
      name: "Paradigm I-01 (Keplerian Planetary Orbits)",
      symbol: "I.1",
      classType: "I",
      parentAxiomId: "ax_01_space_metric",
      reference_count: 1,
      predicted_count: 1,
      matched_count: 1,
      coverage: 1.0,
      status: "pass",
      formula: "r(θ) = p / (1 + ε · cos(θ - θ_0))  (Conic Sections)",
      quote: "The orbit of each planet is an ellipse with the Sun at one of the two foci.",
      citation: "Kepler (1609) Astronomia Nova, Cap. LVI",
      topologicalRank: 2,
      dependencies: ["ax_01_space_metric", "m_01_inertial_dynamics"],
      dependents: [],
      inferentialPolarity: {
        predicate: "PROVES",
        goldPredicate: "PROVES",
        targetNode: "Sub-Model 01-A (Inertial Force Equations)",
        similarity: 0.98,
        concordance: "CONCORDANT",
        dialecticalNote: "Elliptical orbit deduction rigorously established from 1/r² force law.",
      },
      dagProperties: {
        isAcyclic: true,
        transitiveReductionRetained: true,
        reachabilityScore: 1.0,
        posetDepth: 2,
      },
      rationale: "Solar system orbit paradigm grounded in historical corpus.",
    },
    {
      id: "i_02_lunar_perturbation",
      name: "Empirical Claim 08 (Lunar Perturbation & Tides)",
      symbol: "I.2",
      classType: "I",
      parentAxiomId: "ax_02_dynamical_conservation",
      reference_count: 1,
      predicted_count: 0,
      matched_count: 0,
      coverage: 0.0,
      status: "cascade_masked_orphan",
      formula: "δa_lunar = -G · M_☉ · ( (r_M - r_☉)/|r_M - r_☉|³ - (r_E - r_☉)/|r_E - r_☉|³ )",
      quote: "Solar tidal forces perturb the lunar apsides, demonstrating complex multi-body gravitational perturbation.",
      citation: "Newton (1687) Principia, Book III, Prop. XXV",
      topologicalRank: 2,
      dependencies: ["ax_02_dynamical_conservation", "m_02_gravitational_law"],
      dependents: [],
      inferentialPolarity: {
        predicate: "UNDERCUTS",
        goldPredicate: "PROVES",
        targetNode: "Sub-Model 02-A (Gravitational Force Balance)",
        similarity: 0.35,
        concordance: "CRITICAL_INVERSION",
        dialecticalNote:
          "Dependent on Sub-Model 02-A (Gravitation). Masked under Bourbaki cascade doctrine.",
      },
      dagProperties: {
        isAcyclic: true,
        transitiveReductionRetained: false,
        reachabilityScore: 0.0,
        posetDepth: 2,
      },
      rationale:
        "Dependent on Sub-Model 02-A (Gravitation). Masked under Bourbaki cascade doctrine.",
    },
    {
      id: "i_03_terrestrial_free_fall",
      name: "Empirical Claim 03 (Terrestrial Free Fall in Vacuum)",
      symbol: "I.3",
      classType: "I",
      parentAxiomId: "ax_03_inertial_frames",
      reference_count: 1,
      predicted_count: 1,
      matched_count: 1,
      coverage: 1.0,
      status: "pass",
      formula: "s(t) = 1/2 · g · t²,  v(t) = g · t",
      quote:
        "In a medium totally devoid of resistance, all bodies would fall with the very same speed, irrespective of their specific gravities.",
      citation: "Galileo Galilei (1638) Two New Sciences, Third Day, Theorem I",
      topologicalRank: 2,
      dependencies: ["ax_03_inertial_frames", "m_03_harmonic_spring"],
      dependents: [],
      inferentialPolarity: {
        predicate: "SUPPORTS",
        goldPredicate: "SUPPORTS",
        targetNode: "Sub-Model 03-C (Hookean Elastic Restoring Force)",
        similarity: 0.91,
        concordance: "CONCORDANT",
        dialecticalNote:
          "Verified empirical paradigm confirms inertial dynamics boundary condition without deviation.",
      },
      dagProperties: {
        isAcyclic: true,
        transitiveReductionRetained: true,
        reachabilityScore: 1.0,
        posetDepth: 2,
      },
      rationale: "Galilean inclined plane and tower drop experiments grounded.",
    },
  ];
}
