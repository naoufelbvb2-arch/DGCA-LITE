# DGCA LITE — Layer 3: Cognition

**Canonical Mathematical and Implementation Specification — v0.2**  
**Status:** FORMAL SPECIFICATION CLOSED · READY FOR CODEX COMPREHENSION · PRODUCTION IMPLEMENTATION NOT YET AUTHORIZED  
**Dependencies:** `01_CORE_v0.4.md` — Layer 1 Core, FROZEN · `02_MEMORY_RETRIEVAL.md` — Layer 2 Memory & Retrieval, FROZEN  
**Layer-3 persistent cognitive state:** NONE  
**Canonical capabilities:** Prediction · Causality · Reasoning  
**Date:** 2 October 2026

---

## Abstract

DGCA LITE Layer 3 defines **Cognition** as bounded, transient, authority-controlled computation over the persistent distributed structure stored by Layer 1 and the immutable reconstructed views produced by Layer 2. It introduces no second knowledge database, no learned global controller, no persistent hypothesis store, no prediction graph, no causal graph, no contradiction database, and no learned executable rule memory.

Layer 3 contains three canonical capabilities:

1. **Prediction** — transient projection and bounded prospective forecast commitments;
2. **Causality** — prospective contrast collection and narrowly identified treatment-operation effects under explicit identification contracts;
3. **Reasoning** — licensed composition plus explicit constraint/contradiction detection.

The governing architecture is:

\[
\boxed{
\text{Persistent structure lives below Cognition; Layer 3 derives transient cognitive state without manufacturing evidence or authority.}
}
\]

Layer 3 is built around a single transient authority unit, the `CognitiveInferenceEpoch (CIE)`, together with invocation-scoped authority, finite non-renewable budgets, immutable environment bindings, typed epistemic dependencies, bounded operators, atomic publication, and explicit cross-capability firewalls.

The strongest conservation statement is:

\[
\boxed{
\Delta Core=0,\qquad
\Delta Layer2=0,\qquad
\Delta PersistentCognitiveState_{L3}=0
}
\]

for ordinary Layer-3 cognition. No Prediction, Causality, Reasoning, Constraint, retrieval, projection, conflict, or derived conclusion automatically becomes Layer-1 learning evidence.

This document is the canonical closed Layer-3 formal specification. It incorporates the completed architecture closure, PAR01 paper-only adversarial findings, PAR02 consolidation repairs, and the successful PAR03 closure re-audit. It authorizes the Codex comprehension/planning gate only; production implementation remains unauthorized until that interpretation is independently reviewed and accepted.

---

# 1. Purpose and Scope

Layer 3 answers three questions:

> **Prediction:** Given current lawful cognitive state, what future structural outcomes may be projected or prospectively checked?

> **Causality:** Under what explicit prospective contrasts may a treatment-operation-level effect be identified without converting association into causation?

> **Reasoning:** What conclusions may lawfully follow from available assertions, and what assertions may not lawfully coexist under explicit constraints?

Layer 3 contains:

- invocation-scoped cognitive authority;
- `CognitiveInferenceEpoch (CIE)`;
- finite non-renewable cognitive work budgets;
- immutable cognitive environment bindings;
- typed assertions, scopes, epistemic dependencies, and derivation lineage;
- bounded multi-session Layer-2 consumption;
- transient prediction projections;
- root-anchored prospective forecast commitments;
- prospective causal-study authority;
- observational and interventional study results with explicit limits;
- closed deterministic replay identification;
- licensed formal composition;
- constraint and contradiction detection;
- cross-capability provenance conservation;
- capability-free cognitive adapters;
- deterministic, failure-atomic publication.

Layer 3 does **not** contain:

- language generation policy;
- decoding or answer wording;
- semantic tokenization or embeddings;
- persistent Layer-3 knowledge memory;
- global learned scoring or ranking;
- arbitrary confidence scalars;
- global planning;
- action policy;
- analogy in v0;
- quantified logic in v0;
- rule induction in v0;
- unrestricted theorem proving;
- causal-law induction;
- causal probability estimation;
- causal-strength learning;
- belief revision or automatic truth arbitration;
- automatic learning feedback from prediction, causality, or contradiction.

Planning and generation belong to later layers. Analogy, quantified logic, learned rule induction, and autonomous long-running experimental authority are future extensions and are not prerequisites for Layer-3 v0.

---

# 2. Layer Discipline

Layer 3 depends on Layers 1 and 2 but may not redefine either.

Layer 1 remains the sole authority for:

- `Cell`;
- `Synapse`;
- `Assembly`;
- activation and emission;
- `LOCAL`, `ASSOCIATIVE`, and `CROSS_TERRITORY`;
- Synaptic strength and evidence mass;
- learning evidence;
- recruitment;
- Assembly formation and growth;
- temporal learning context;
- root/evidence authority;
- Surface Event learning.

Layer 2 remains the sole authority for:

- trusted/internal retrieval entry separation;
- bounded immutable retrieval acquisition;
- Assembly and Atomic Sources;
- pattern reconstruction;
- root-witness separation;
- one-hop forward associative retrieval;
- target reconstruction;
- immutable `RetrievalResult`;
- Layer-2 retrieval provenance.

Layer 3 may consume those interfaces. It may not silently repair a Layer-3 problem by changing Layer-1 or Layer-2 semantics.

A proven lower-layer defect requires a formal lower-layer revision and downstream regression.

---

# 3. Persistent-State Thesis

Layer 3 introduces no persistent cognitive knowledge store:

\[
\boxed{
PersistentCognitiveState_{L3}=\varnothing
}
\]

The following may exist transiently or operationally:

- an active `InvocationAuthority`;
- an `InvocationBudgetLedger`;
- one active `CognitiveInferenceEpoch`;
- bounded CIE arena state;
- staged derivations and constraint findings;
- bounded live `ForecastRuntimeRecord`s;
- bounded prospective `CausalStudy` owners;
- bounded `ReplayComparisonEpoch`s;
- immutable completed result views;
- capability and registry infrastructure.

These are not a general-purpose Layer-3 memory.

A completed result may remain available to a caller as immutable output, but:

\[
\boxed{
ResultPersistence\neq CognitiveMemoryAuthority
}
\]

and:

\[
\boxed{
HistoricalResult\neq OperationalCapability.
}
\]

---

# 4. Layer-3 Architecture Overview

```text
                      TRUSTED / FORMAL INGRESSES
                                  |
                                  v
                        InvocationCauseID
                                  |
                                  v
                       InvocationAuthority
                     + InvocationBudgetLedger
                                  |
                                  v
                  CognitiveInferenceEpoch (CIE)
                                  |
                   +--------------+--------------+
                   |              |              |
                   v              v              v
              PREDICTION      CAUSALITY      REASONING
                   |              |              |
                   +--------------+--------------+
                                  |
                                  v
                 Capability-Free Result Views
                                  |
                                  v
                        LAYER 4 — GENERATION
```

Layer 2 is consumed through immutable retrieval results and internal retrieval sessions. Layer 1 is observed only through authorized, bounded integration paths. No ordinary Layer-3 operator mutates either lower layer.

---

# 5. Invocation Cause and Authority

## 5.1 Invocation cause

A trusted accepted cognitive invocation is identified by:

\[
\boxed{InvocationCauseID}
\]

derived from the external occurrence or trusted invocation event that caused cognition to begin.

A transport retry of the same cause does not create a new cause.

\[
\boxed{
SameInvocationCause\Rightarrow NoFreshAuthority,\ NoFreshBudget
}
\]

## 5.2 Invocation authority

For one accepted cause there is at most one live `InvocationAuthority`.

The authority is:

- opaque;
- nonconstructible by ordinary cognitive callers;
- nonserializable as live authority;
- bound to the invocation cause;
- bound to the current runtime identity;
- lifecycle controlled.

Canonical lifecycle:

```text
ACTIVE -> CLOSING -> CLOSED
```

`CLOSING` forbids creation of new child authority.

No closed invocation may be reopened.

## 5.3 One CIE at a time

At most one CIE is open for an invocation at any instant.

Sequential CIEs may exist under the same still-active invocation when a capability requires multi-epoch operation, but a second live CIE may not overlap the first.

A stale or terminal CIE must close before a replacement opens.

---

# 6. Invocation Budget Ledger

Each invocation owns a finite non-renewable:

\[
\boxed{InvocationBudgetLedger}
\]

The ledger is authority infrastructure, not cognitive state.

Budget is not confidence, truth, utility, or importance.

## 6.1 Non-renewability

Budget may not be:

- regenerated because an operation failed;
- refunded after substantive work;
- copied;
- transferred between independent owners;
- increased because a result is interesting;
- adaptively topped up according to cognitive outcome.

\[
\boxed{
ConsumedOrRetiredBudgetNeverReturnsToAvailable
}
\]

## 6.2 Work ownership

Every charged Layer-3 work item has exactly one valid budget source.

Allowed source classes in v0:

```text
INVOCATION_GENERAL
FORECAST_ESCROW
CAUSAL_STUDY_ESCROW
```

No implicit fourth pool exists.

## 6.3 Full-frontier reservation

When an operation requires completeness, budget must cover the complete frozen work frontier or the operation does not begin semantically.

No Top-K fallback, first-N subset, silent truncation, or outcome-dependent work reduction may masquerade as completeness.

---

# 7. Cognitive Environment Binding

Every CIE is bound to an immutable:

\[
\boxed{
CEB=
\langle
CoreStateBinding,
L2PolicyBinding,
L3PolicyBinding
\rangle
}
\]

The binding identifies the exact environment under which cognitive results were derived.

Canonical descriptors are identity-bearing structures. Hashes may be used as indexes, but a hash alone is never cognitive identity.

Any descriptor collision must fail closed.

The CEB is frozen for the CIE. A policy or Core-state change that invalidates the binding makes in-flight publication stale.

---

# 8. Core Transition Barrier

Layer 3 recognizes the complete Layer-1 accepted event transition as one authority boundary.

`CoreTransitionBarrier` covers the full canonical Core event operation, including temporal publication.

Layer-3 capture that claims post-event authority must occur only against a coherent post-commit state.

A final Layer-3 publication that depends on the current Core binding must revalidate that binding before publication.

No Layer-3 operator may observe a torn state between Core mutation and temporal publication.

---

# 9. Cognitive Inference Epoch

## 9.1 Definition

A `CognitiveInferenceEpoch (CIE)` is the unique transient owner of one bounded reasoning/projection/evaluation episode inside an invocation.

It owns:

- frozen CEB;
- immutable ingress assertions/views;
- `CIEArena`;
- active epistemic contexts;
- work tickets/charge bindings;
- staged derivations;
- staged constraint results;
- retrieval needs and received immutable retrieval views;
- final immutable result construction.

It does not own persistent knowledge.

## 9.2 Opening

A CIE opens only after:

- invocation authority is `ACTIVE`;
- trusted ingress is accepted;
- required post-ingress state is quiescent;
- CEB is frozen;
- initial budget/capacity requirements are validated.

## 9.3 Closure

A CIE becomes terminal by:

- successful atomic publication;
- explicit abort;
- budget/capacity failure;
- environment staleness;
- invocation entering `CLOSING`;
- internal contract violation.

Once terminal, it cannot resume.

## 9.4 Non-resumable result

A `CognitiveResultView` is immutable and nonresumable. Possessing it does not permit reopening the producing CIE.

---

# 10. CIE Arena

The `CIEArena` is bounded transient storage for:

- assertions;
- source support records;
- dependency roots;
- scopes;
- derivation witnesses;
- retrieval views;
- prediction views;
- causal result views;
- constraint findings;
- clearance certificates;
- staging records.

Capacity failure aborts the operation requiring new arena state. It does not evict or truncate earlier semantic state according to importance.

There is no LRU semantic forgetting policy inside a CIE.

---

# 11. Operator Model

Cognitive operators are pure bounded transformations over immutable inputs.

An operator may:

- inspect frozen CIE data supplied to it;
- compute bounded candidate structures;
- return staged data;
- emit a typed `RetrievalNeedView` when retrieval is required.

An operator may not:

- call Core mutation;
- call Layer-2 learning;
- open a CIE;
- start a new invocation;
- reserve budget;
- mint trusted authority;
- recurse by dispatching itself;
- silently start another operator;
- perform semantic ranking outside its frozen schema.

The orchestrator, not the operator, performs authorized dispatch.

---

# 12. Orchestrator Discipline

The Layer-3 orchestrator is **cognitively dumb**.

It may perform:

- authority validation;
- dependency validation;
- ticket/charge validation;
- operator dispatch;
- bounded retrieval dispatch;
- staleness checks;
- fixed-point scheduling;
- atomic publication;
- lifecycle closure.

It may not perform:

- semantic ranking;
- cue invention;
- path selection by semantic preference;
- causal interpretation;
- rule invention;
- premise rewriting;
- hidden winner selection;
- query reinterpretation.

All cognitive semantics must reside in frozen typed operators/schemas.

---

# 13. Canonical Semantic Identity

Layer 3 separates proposition content from assertion semantics and source occurrence.

## 13.1 Claim content

\[
\boxed{ClaimContentID}
\]

identifies canonical proposition content.

Content identity does not encode truth, authority, confidence, source, or scope.

## 13.2 Assertion semantic key

\[
\boxed{
ASK=
(
ClaimContentID,
AssertionBasis,
ScopeIdentity,
EpistemicDependencySet
)
}
\]

Two assertions with identical content but different basis, scope, or dependencies are semantically distinct assertions.

## 13.3 Source assertion key

`SourceAssertionKey` identifies one canonical source occurrence or provenance record supporting an assertion:

\[
\boxed{
SourceAssertionKey=(
SourceKind,
OriginAuthorityBinding,
CanonicalSourceOccurrenceDescriptor
)
}
\]

The same external/source occurrence replayed, transported, or presented again with the same canonical source key is idempotent:

\[
\boxed{
SameSourceOccurrenceReplay
\neq NewSourceSupport
}
\]

Several independent sources may support the same ASK without changing the ASK itself. Source multiplicity is preserved as bounded provenance but does not automatically become confidence arithmetic.

Inference candidate matching is performed over semantic assertion records keyed by ASK and schema role bindings. It MUST NOT form a Cartesian product over `SourceAssertionKey` support multiplicity. Source references are witnesses to support, not independent semantic premise copies:

\[
\boxed{
SourceMultiplicity
\neq DerivationMultiplicity
\neq ConfidenceArithmetic
}
\]

---

# 14. Assertion Basis

Canonical v0 bases are:

```text
FORMAL_GIVEN
FORMAL_ASSUMPTION
EXTERNAL_OBSERVATION
INTERNAL_RETRIEVAL
HYPOTHETICAL
PREDICTION_VIEW
CAUSAL_RESULT_VIEW
DERIVED
```

Basis values are not caller-controlled labels.

Each basis is minted only by its authorized constructor. Authority is established by an opaque, nonconstructible, nonserializable issuance capability or by a previously validated Layer-3 operational owner; matching bytes, identifiers, or descriptors are never sufficient.

A genuine new trusted/formal occurrence enters Layer 3 only through an `ExternalOccurrenceCapability` (or a narrower typed formal/constraint/controller capability) issued by the corresponding trusted boundary. Its live issuance record is canonically bound to:

\[
\boxed{
ExternalOccurrenceCapabilityBinding=(
IngressClass,
CanonicalSourceOccurrenceIdentity,
RuntimeOrCoreIdentity,
IssuanceRevision,
AuthorizedScope
)
}
\]

The capability itself is opaque, nonconstructible, nonserializable as live authority, and validated against issuer-maintained immutable/current issuance state. It cannot be reconstructed from cognitive data, copied descriptors, or caller-selected fields.

\[
\boxed{
SameContentBytes
\neq ExternalOccurrenceCapability
}
\]

### 14.1 Canonical basis-minting matrix

| Assertion basis | Sole lawful constructor / issuer | Mandatory dependency semantics | Forbidden promotion |
| --- | --- | --- | --- |
| `FORMAL_GIVEN` | `FormalReasoningIngress` under a valid formal-source occurrence capability | no extra dependency root unless the formal source itself is scoped/dependent | internal/derived/retrieved content cannot self-promote |
| `FORMAL_ASSUMPTION` | `FormalReasoningIngress` under an explicit assumption-issuance capability | must carry the canonical assumption dependency root | assumption cannot become `FORMAL_GIVEN` by derivation |
| `EXTERNAL_OBSERVATION` | `TrustedObservationAdapter` from a genuinely new trusted lower-layer/external occurrence capability | preserves the exact trusted occurrence provenance; does not acquire prediction/causal origin merely by content equality | Prediction MATCH, retrieval, or derived content cannot mint it |
| `INTERNAL_RETRIEVAL` | Layer-2 internal retrieval adapter only | must carry `InternalRetrievalDependencyRoot` | cannot become trusted/root-authorized by reuse |
| `HYPOTHETICAL` | authorized hypothesis constructor inside the current CIE | must carry the hypothesis dependency root | cannot become observation/formal authority without a new external issuance |
| `PREDICTION_VIEW` | capability-free Prediction adapter from a valid Prediction result | must carry `PredictionDependencyRoot` | cannot become observation, formal conditional, or forecast-origin authority |
| `CAUSAL_RESULT_VIEW` | capability-free Causality adapter from a valid typed causal result | must carry `CausalResultDependencyRoot` | cannot become generic `CAUSES`, intervention authority, or Core evidence |
| `DERIVED` | `InferenceRoundPublisher` only | exactly the union of parent EDS; may mint no new dependency root | never inherits a stronger parent basis |

The table is normative and exhaustive for v0. Any additional assertion basis or minting path requires a Layer-3 specification revision.

Every generic inference output has:

\[
\boxed{Basis=DERIVED}
\]

Only the inference publication path may mint `DERIVED`.

A derived conclusion never inherits `EXTERNAL_OBSERVATION`, `PREDICTION_VIEW`, or `CAUSAL_RESULT_VIEW` as its basis merely because its parents had those bases.

---

# 15. Basis Dependency Contracts

Each basis has the fixed mandatory dependency contract defined by the canonical basis-minting matrix in Section 14.1. A basis constructor may add only dependency kinds authorized by that basis and the exact source/assumption scope.

For derived assertions:

\[
\boxed{
EDS(Derived)=\bigcup_{p\in Parents}EDS(p)
}
\]

and the derived constructor may mint no new dependency root.

An empty dependency set has one narrow meaning only:

\[
\boxed{
EDS=\varnothing\;\Longleftrightarrow\;NoAdditionalDependencyRoots
}
\]

It does **not** mean `FACT`, trusted truth, unconditional truth, external observation, or stronger authority.

---

# 16. Epistemic Dependency Roots

A dependency root has canonical identity:

\[
\boxed{
DependencyRootIdentity=
(
DependencyKind,
OriginAuthorityBinding,
CanonicalOriginDescriptor
)
}
\]

Hashes are indexes only.

Dependency roots are finite, typed, and bounded inside the CIE.

They do not cancel one another and are not ranked.

\[
\boxed{
EDS(Derived)=\bigcup_{p\in Parents}EDS(p)
}
\]

No inference operator may remove a parent dependency root.

---

# 17. Modal Dependency Roots

Cross-capability origin that must remain visible after derivation is represented by typed dependency roots.

Canonical families include:

```text
PredictionDependencyRoot
CausalResultDependencyRoot
InternalRetrievalDependencyRoot
```

Thus:

\[
PREDICTION\_VIEW\Rightarrow D_{pred}\in EDS
\]

\[
CAUSAL\_RESULT\_VIEW\Rightarrow D_{causal}\in EDS
\]

\[
INTERNAL\_RETRIEVAL\Rightarrow D_{retrieval}\in EDS
\]

A modal dependency root is provenance, not operational authority.

\[
\boxed{
ModalDependencyRoot\neq Capability
}
\]

It cannot open a forecast, causal study, retrieval root, CIE, or trusted ingress.

---

# 18. Scope Identity

Scopes are typed canonical objects:

\[
\boxed{
ScopeIdentity=
(
ScopeKind,
ScopeAuthorityBinding,
CanonicalDescriptor
)
}
\]

Cross-kind equality is forbidden.

Generic reasoning uses exact scope unless an explicit schema defines a lawful scope transformation.

There is no generic scope broadening and no universal `meet` operation in v0.

A result derived under one replay origin, forecast scope, temporal scope, or formal assumption scope cannot silently become a broader claim.

## 18.1 Canonical operational binding identities

Security-critical bindings are canonical typed identities, never caller-chosen strings or hashes alone.

The environment identity is the canonical tuple itself:

\[
\boxed{
CEBIdentity=(CoreStateBinding,L2PolicyBinding,L3PolicyBinding)
}
\]

Every invocation carries a monotonic lifecycle `InvocationRevision` that changes on every authority-relevant lifecycle transition. Every CIE is assigned a deterministic per-invocation `CIESequenceIndex` in canonical creation order. Define:

\[
\boxed{
CIEIdentity=(InvocationCauseID,CIESequenceIndex)
}
\]

\[
\boxed{
CIEBinding=(CIEIdentity,InvocationRevision,CEBIdentity)
}
\]

A CIE arena snapshot has:

\[
\boxed{
SnapshotBinding=(CIEBinding,ArenaVersion,RoundIdentity)
}
\]

`ArenaVersion` and `RoundIdentity` advance only through canonical atomic publication, never by thread completion order.

Each epistemic branch receives a deterministic `BranchIdentity` in canonical branch-creation/publication order inside the CIE. Its active dependency context is:

\[
\boxed{
AECIdentity=(BranchIdentity,CanonicalDependencyRootSet,CIEBinding)
}
\]

For constraint-gated derivations:

\[
\boxed{
DerivationContextBinding=(AECIdentity,ConstraintEnvironmentBinding,ConsumerSchemaIdentity)
}
\]

`ConsumerSchemaIdentity` is the canonical identity of the exact frozen inference-schema instance under `L3PolicyBinding`; hashes are indexes only.

Canonical descriptors are authority-free data. Live authority is validated against the current runtime registry/revision before use. Historical copies cannot reconstruct operational authority.

---

# 19. Formal Assertion Boundary

Natural-language content does not itself create formal logic authority.

A trusted:

\[
\boxed{FormalReasoningIngress}
\]

is required to issue formal givens, formal assumptions, formal relation properties, and ground conditional premises. It accepts only the corresponding typed formal occurrence/issuance capability; caller-supplied basis labels or copied descriptors are insufficient.

A separate:

\[
\boxed{TrustedObservationAdapter}
\]

converts a genuinely new trusted lower-layer/external occurrence capability into an `EXTERNAL_OBSERVATION` assertion while preserving the exact occurrence identity and scope. A Layer-2 `RootView` or trusted receipt descriptor is not itself this capability, and an internal Layer-2 retrieval result never passes this adapter. The same trusted occurrence replay is idempotent and cannot create a second external observation assertion source.

A retrieved statement that linguistically resembles:

```text
if P then Q
```

does not become an executable conditional.

Likewise a retrieved statement that resembles:

```text
R is transitive
```

does not activate transitivity.

\[
\boxed{
LearnedOrRetrievedContent\neq ExecutableInferenceAuthority
}
\]

---

# 20. Formal Assertion Building AST

Formal semantic content is represented by a finite, typed, canonical, acyclic structure:

\[
\boxed{FAB\text{-}AST}
\]

The AST is closed: it may contain only declared node types.

No opaque semantic metadata may be inspected by schemas.

`DeepReferentClosure` recursively validates that every referent is lawful, bounded, type-correct, and already available through the authorized semantic construction path.

The closed FAB-AST vocabulary includes:

```text
GroundState(Participant,StateIdentity)
```

Both `Participant` and `StateIdentity` are closed ground referents governed by `DeepReferentClosure`. `GroundRelation(...)`, `GroundState(Participant,StateIdentity)`, and `Assign(Entity,Slot,Value)` are distinct semantic forms with no implicit conversion.

No schema may manufacture arbitrary new semantic participants, relation identities, or operators outside its declared constructor closure.

---

# 21. Derivation Lineage

`DerivationLineage` records transient same-CIE derivation history.

It is distinct from Layer-1 evidence ancestry.

\[
\boxed{
DerivationLineage\neq LearningEvidence
}
\]

Repeated retrieval or inference does not create independent external evidence.

## 21.1 Parent witnesses

Every derivation uses immutable `ParentAssertionWitness` records captured at the relevant arena snapshot.

A witness contains the exact parent ASK, basis, scope, EDS, snapshot identity, and source/derivation support used.

Later source support cannot backdate an earlier derivation.

## 21.2 Acyclic justification

Content cycles may exist, but circular justification is forbidden.

A new derivation must possess an `AcyclicSupportWitness` whose transitive derivation ancestry does not already require the conclusion being established.

If the same assertion has both circular and independent support, a lawful independent acyclic path may be used.

---

# 22. Resource Envelopes

Every cognitive schema/operator defines a deterministic pre-execution resource envelope from frozen inputs.

Possible bounds include:

- maximum candidate bindings;
- maximum outputs;
- maximum AST nodes;
- maximum new assertion records;
- maximum derivation records;
- maximum witness references;
- maximum dependency references;
- maximum validation work;
- maximum retrieval needs;
- maximum constraint checks.

If required capacity or budget is unavailable, the corresponding operation does not execute partially.

An implementation that exceeds its declared envelope is an internal contract violation.

---

# 23. Synchronous Cognitive Rounds

Generic reasoning proceeds in immutable synchronous rounds.

For round \(k\):

1. freeze `ArenaSnapshot_k`;
2. discover the complete lawful work frontier for the round;
3. reserve required budget/capacity;
4. execute operators against the frozen snapshot;
5. stage outputs in `RoundStagingArena`;
6. validate;
7. publish atomically as `Arena_{k+1}`.

New outputs from the current round are not premises within the same round.

No semantic prefetch for round \(k+1\) is allowed before round \(k\) commits.

---

# 24. Fixed Point and Incompleteness

A CIE may declare a reasoning fixed point only after a complete committed round finds no pending authorized derivation.

Budget or capacity exhaustion before a required frontier completes yields an incomplete status.

An incomplete run may preserve earlier fully committed rounds in its internal result representation where the query contract permits, but it may not label the result a fixed point or complete closure.

No subset is selected by semantic ranking to fit remaining budget.

---

# 25. Prediction — Scope

Prediction v0 distinguishes:

\[
\boxed{
Projection
\neq
ForecastCommitment
\neq
Observation
\neq
Evaluation
\neq
LearningEvidence
}
\]

Prediction is not language generation.

It operates over structural outcomes and typed cognitive views.

---

# 26. Conditional Projection

A `ConditionalProjection` is transient cognition.

It may use:

- internal retrieval;
- mixed trusted/internal retrieval;
- reasoning-derived state;
- hypotheses.

It may produce possible future structural continuations or candidate target descriptions.

It does **not** create prospective observation authority.

It cannot be sealed into a root-anchored forecast merely by later discarding its internal provenance.

\[
\boxed{
MixedOrInternalProjection\not\rightarrow RootAnchoredForecast
}
\]

---

# 27. Root-Anchored Forecast Origin

A prospective root-anchored forecast requires a trusted-only origin retrieval satisfying all required origin predicates, including:

- `internal_cue = empty`;
- nonempty authorized root witness support;
- valid current CEB;
- trusted post-ingress capture;
- no purification from a mixed session.

The session origin is authoritative as a whole. A caller may not select only the trusted-looking portion of a mixed result.

---

# 28. Forecast Target Classes

Canonical prediction target forms are:

## 28.1 Branch pattern

```text
BranchPattern
  target_assembly_id
  anchor_carriers
  pattern_cells
  source_identity
```

`anchor_carriers` are the direct associative target seeds that justify the target branch.

`pattern_cells` are the reconstructed target structure.

Targets remain source-specific. Different sources reaching the same target Assembly do not become one aggregated forecast target.

## 28.2 Atomic carrier

A lawful direct associative hit not covered by an assembled branch may be represented as an atomic forecast carrier.

No target class creates semantic labels or probabilities.

---

# 29. Forecast Commitment

A sealed forecast commitment is self-contained.

Its identity and content include all information required to evaluate the forecast prospectively without reinterpreting its original retrieval later.

A `TargetGuard` is the immutable canonical identity guard for the sealed target. It binds the target class, source identity, target Assembly/atomic carrier identities, anchor carriers, pattern cells where applicable, and the target-construction policy revision. Evaluation must fail `TARGET_STALE` rather than remap a stale target to a new structural identity.

The historical origin binding is distinct from future-evaluation currentness. `OriginCoreStateBinding` records the trusted post-ingress state used to seal the forecast and is never required to remain the current Core version/tick. `FutureEvaluationBinding` instead binds the Core instance, prediction policy, target guard, and observation contract that must remain valid for future evaluation. Normal future Core version/tick advancement caused by genuine observations does not by itself make the forecast stale.

A commitment records, as applicable:

- origin binding;
- source identity;
- target descriptor;
- forecast horizon;
- observation policy;
- target guard;
- environment binding;
- boundary policy;
- resource escrow identity;
- canonical commitment identity.

There is no backdating. A forecast begins only after successful sealing.

---

# 30. Forecast Runtime Record

A live forecast uses a bounded operational:

\[
\boxed{ForecastRuntimeRecord}
\]

The record is operational state, not persistent cognitive memory.

It stores only what is necessary to:

- track the logical forecast offsets and their capture states as defined in §33;
- accept lawful future trusted observation captures;
- evaluate the sealed target;
- maintain an append-only observation/evaluation ledger;
- record idempotent observation processing;
- terminalize;
- retire resources.

A previously admitted future occurrence record is never rewritten, removed, or replaced by a later observation. Corrections to operational metadata create a new revision/event record; they do not backdate cognitive evaluation.

The global live-forecast registry is bounded by a fixed Core/runtime capacity \(K_F\).

Capacity failure aborts the whole commitment. No lowest-priority forecast is silently evicted.

---

# 31. Forecast Observation Capture

Forecast evaluation may consume only lawful future trusted observation/root captures produced through the normal lower-layer trusted path.

`ForecastDelegatedAuthority` does not mint future roots.

A lawful future trusted capture exposes a capability-free `FutureTrustedOccurrenceID`, derived from the exact trusted occurrence identity issued by the trusted observation path plus the bound Core/runtime identity. Replaying the same trusted occurrence yields the same ID; a different genuine occurrence yields a different ID.

The normal trusted observation path binds this occurrence identity independently of forecast capture success. A missing or failed forecast capture does not erase a genuine trusted occurrence or its logical offset. Neither an absent capture nor a caller-supplied descriptor may manufacture a trusted occurrence identity; a failed Core event is not a genuine trusted occurrence.

Each commitment/future-root evaluation has canonical identity:

\[
\boxed{
ForecastEvaluationID=(CommitmentID,FutureTrustedOccurrenceID)
}
\]

`ForecastEvaluationID` is idempotent. Reprocessing or retransmitting the same future occurrence does not create a second observation, evaluation, status transition, or evidence event.

A genuinely empty trusted observation may count as empty only if the trusted adapter explicitly proves that emptiness; absence of a capture is not automatically a negative observation.

---

# 32. Forecast Match Semantics

For a sealed `BranchPattern` target \(T\), define:

\[
T=(A_T,P_T)
\]

where \(A_T\) is the frozen `anchor_carriers` set and \(P_T\) is the frozen `pattern_cells` set. The sealed target Assembly and source identities remain guarded as specified in §§28–29.

For a lawful future trusted occurrence \(o\), \(W_o(T)\) is the root-authorized witness set of the exact sealed target Assembly, and \(V_o(T)\) is the reconstructed Cell set of that same exact target Assembly.

\[
AnchorConfirmed(T,o)\iff A_T\cap W_o(T)\neq\varnothing
\]

\[
PatternReinstated(T,o)\iff P_T\subseteq V_o(T)
\]

\[
BranchMatched(T,o)\iff AnchorConfirmed(T,o)\land PatternReinstated(T,o)
\]

There is no partial-pattern threshold, similarity score, confidence score, percentage match, target remapping, branch union, or reuse of Layer-2 \(\theta_{PC}\) as a forecast acceptance threshold. Complete pattern reinstatement without anchor confirmation is not a match.

For an `AtomicCarrier(c)`, let \(W_o\) be the genuine future root-authorized witness set in the lawful capture:

\[
AtomicMatched(c,o)\iff c\in W_o
\]

An internally reconstructed Cell alone cannot match an atomic carrier.

Prediction does not rank multiple forecast targets by global confidence.

## 32.1 Future Reconstruction Lane Binding

A sealed `BranchPattern` is constructed from a source-specific associative target branch at prediction/origin time, but its future reinstatement is evaluated only through the exact target Assembly's root-seeded `SourceView`.

For a sealed `T = BranchPattern(source_identity=x, target_assembly_id=g, anchor_carriers=A_T, pattern_cells=P_T)` and one lawful successful future trusted Layer-2 retrieval result `R_o`, select the unique source view, if it exists:

```text
S_o(g) = SourceView in R_o.sources
         where SourceView.source_id == ("ASM", g)

W_o(T) = set(S_o(g).root_authorized_witnesses)
V_o(T) = set(S_o(g).reconstructed_cells)
```

Both `W_o(T)` and `V_o(T)` in the unchanged §32 matching equations come from this exact root-seeded `SourceView("ASM", g)`.

If the target Assembly remains valid under `TargetGuard` but no exact `SourceView("ASM", g)` exists in the successful future retrieval, define `W_o(T) = empty` and `V_o(T) = empty`. This is a lawful nonmatch, not `TARGET_STALE`. Target staleness remains reserved for failure of the sealed target identity / `TargetGuard`, not absence of future target activation.

Associative `BranchViews` are excluded from both `PatternReinstated` and `AnchorConfirmed`. No `BranchView` may contribute Cells to `V_o(T)`, including the branch with the exact sealed source and target, a branch from another source, or any union of branches. There is no branch fallback, branch selection, cross-source aggregation, or `SourceView`/`BranchView` merging.

The sealed `source_identity=x` remains part of the target/commitment identity and guards the origin of the prediction. It does not select the future reconstruction lane. Associative `BranchView` reconstruction is authority-free internal retrieval and cannot increase future forecast-match evidence.

```text
OriginPredictionLane != FutureObservationLane
FutureAssociativeReconstruction != FutureTargetObservationReinstatement
PredictionGenerationBranch != PredictionVerificationLane
SourceLane != TargetBranchLane
```

These distinctions hold even when both lanes refer to the same Assembly. For target Assembly `7`, source `("ATOM",5)`, anchors `{3,9}`, and sealed pattern `{3,4,9}`, a future exact Assembly `SourceView` with witnesses and reconstructed Cells `{3,9}` produces `AnchorConfirmed = True`, `PatternReinstated = False`, and `BranchMatched = False`, even if the exact source-specific `BranchView` reconstructs `{3,4,9}`. That branch is ignored. At the final horizon offset, absent another terminal condition, this is a lawful covered nonmatch and §33.2 determines window closure.

---

# 33. Forecast Status Algebra

Canonical forecast terminal/status families include:

```text
PENDING
MATCHED
WINDOW_ELAPSED_WITHOUT_MATCH
INCONCLUSIVE_OBSERVATION_GAP
TARGET_STALE
BOUNDARY_TERMINATED
CANCELLED
ENVIRONMENT_STALE
```

A hard boundary terminates continuity according to the sealed boundary policy.

A stale target or environment is not reinterpreted under new identities.

## 33.1 Logical horizon and capture coverage

A sealed commitment freezes an integer logical trusted-occurrence horizon:

\[
1\le H\le H_{max}
\]

where \(H_{max}\) is the finite bound in the frozen prediction policy. Horizon semantics are not wall-clock based.

Each genuine new trusted external Core occurrence after successful sealing, within the same continuity stream and admitted by the lawful evaluation ordering in §33.3, receives the next canonical offset in trusted Core occurrence order:

\[
\Delta=1,2,\ldots,H.
\]

Reprocessing the same `FutureTrustedOccurrenceID` is idempotent: it creates neither another offset nor another evaluation. Internal reconstruction and a failed Core event do not advance the horizon.

Every required offset advances even if forecast capture is missing or fails. Its capture state is exactly one of:

```text
CAPTURED         complete lawful trusted capture; explicitly proven empty captures use PROVEN_EMPTY
PROVEN_EMPTY     explicit lawful trusted proof of empty capture
OBSERVATION_GAP  missing or failed forecast capture
```

`CAPTURED` and `PROVEN_EMPTY` provide complete lawful coverage for that offset. `OBSERVATION_GAP` does not. Absence of capture is never proof of emptiness. The occurrence, offset, and capture state are recorded in the bounded append-only FRR ledger; a duplicate or later retry cannot replace an admitted gap, backdate a capture, or reevaluate that occurrence.

## 33.2 Match and window closure

A lawful match under §32 at any offset \(1\le\Delta\le H\), including exactly \(\Delta=H\), terminalizes as `MATCHED`. A lawful match takes precedence over gap or elapsed-window closure, including when an earlier offset recorded a gap.

Otherwise, when offset \(H\) is completed:

- if every required offset has complete lawful coverage and none matched, terminalize as `WINDOW_ELAPSED_WITHOUT_MATCH`;
- if any required offset is `OBSERVATION_GAP`, terminalize as `INCONCLUSIVE_OBSERVATION_GAP`.

Before offset \(H\), a nonmatch remains `PENDING` unless another canonical termination applies; a gap alone does not preclude a later lawful match. Missing or failed capture never postpones its offset or leaves a completed horizon indefinitely `PENDING`.

## 33.3 Authority-sensitive ordering

Boundary termination, cancellation, target/environment staleness, and future-occurrence evaluation are ordered by their authority-sensitive linearization points under the existing lifecycle and Core barriers. An occurrence whose evaluation lawfully linearizes before termination may complete that exact evaluation. Termination that linearizes first prevents the occurrence from entering the forecast window. This does not authorize a new evaluation after termination or revive a terminal FRR.

Within a lawful future evaluation, validation follows this canonical order:

```text
FutureEvaluationBinding -> TargetGuard -> Capture -> Match -> WindowClosure
```

Failure of future binding or target guard validation follows the canonical stale status, rather than remapping a target or treating invalid authority as a capture gap. A final-offset match is decided before elapsed/gap window closure. Historical `OriginCoreStateBinding` remains distinct from future-evaluation currentness: ordinary Core tick/version advancement after sealing does not by itself stale the forecast (§29).

---

# 34. Prediction Evaluation Is Read-Only

Layer-3 Prediction v0 has:

\[
\boxed{
PREDICTION\_V0\_READ\_ONLY\_NO\_LEARNING\_FEEDBACK
}
\]

Therefore:

\[
MATCHED\nRightarrow ExtraPositiveCoreEvidence
\]

and:

\[
WINDOW\_ELAPSED\_WITHOUT\_MATCH\nRightarrow NegativeCoreEvidence.
\]

The future root, if real, is learned through the normal Layer-1 external path once. Prediction does not add a second \(y=1\).

A miss is nonoccurrence under an observation protocol, not the explicit contrary evidence required by the Core \(y=0\) interface.

Repeated misses do not accumulate learning evidence.

---

# 35. Forecast Delegated Authority

A forecast may remain operational after its parent invocation closes only if it was sealed while that invocation was active and received:

\[
\boxed{ForecastDelegatedAuthority\ (FDA)}
\]

during the same atomic sealing transaction. The normative seal transaction is:

\[
\boxed{
OriginRevalidation
+ForecastBudgetEscrowReservation
+ForecastRegistryAdmission
+ForecastRuntimeRecordRegistration
+FDAIssuance
+CommitmentSeal
}
\]

All six steps validate and publish atomically with respect to the Core/Invocation lifecycle barriers. Failure of any step publishes no sealed commitment, FDA, live registry entry, or delegated budget owner.

FDA is:

- opaque;
- nonconstructible;
- nonserializable;
- nontransferable;
- bound to one commitment;
- bound to one FRR;
- bound to one horizon and policy;
- bound to one forecast budget pool.

FDA may only:

- consume lawful future trusted observations for its commitment;
- evaluate that commitment;
- update its bounded operational coverage;
- terminalize;
- release/retire its own operational state.

FDA may not:

- open a CIE;
- start a causal study;
- create another forecast;
- mint trusted roots;
- top up budget;
- mutate Core;
- produce learning evidence.

---

# 36. Forecast Resource Escrow

A forecast reserves prospectively:

\[
\boxed{2H}
\]

work units for the canonical v0 acquisition/evaluation upper bound over horizon \(H\), subject to the final implementation mapping from logical work units to resource envelopes.

For each logical offset there is at most one acquisition/capture work allocation and one evaluation work allocation. A missing or failed capture still completes its offset and coverage evaluation within this bound; it does not authorize a retry allocation. Duplicate occurrences require no new allocation. Capture-state recording, match evaluation, and window closure remain within the corresponding already-allocated work envelopes, not a new charge exemption.

The escrow is reserved from the parent invocation before delegation.

After successful delegation, it becomes a forecast-owned pool.

Unused forecast resources are retired, not refunded, transferred, or reused for another offset or owner.

---

# 37. Causality — Governing Principles

Causality v0 obeys:

\[
\boxed{
ASSOCIATION\neq CAUSATION
}
\]

\[
\boxed{
PredictionSuccess\neq CausalEvidence
}
\]

\[
\boxed{
CausalityRequiresContrast
}
\]

\[
\boxed{
NonObservation\neq Negation
}
\]

\[
\boxed{
PersistentCausalState_{L3}=\varnothing
}
\]

Layer 3 does not learn a persistent causal graph.

The default causal product is a transient typed result or hypothesis.

---

# 38. Causal Hypothesis

A `CausalHypothesis` is a transient claim that a causal relation or treatment contrast may merit prospective evaluation.

It is not a causal fact.

Associative retrieval may seed a causal hypothesis, but:

\[
\boxed{
ASSOCIATIVE\ Support\Rightarrow HypothesisOnly
}
\]

No associative edge strength becomes causal strength.

---

# 39. Prospective Causal Study Authority

A causal study begins only under explicit:

\[
\boxed{CausalStudyAuthority}
\]

created while its parent invocation is active.

The study is prospective: its comparison structure is frozen before the relevant outcomes are observed.

A `CausalStudyPlan` contains at least:

```text
QuerySpec
DomainBinding
ConditionAxisSpec
OutcomeSpec
CaseSlotPlan
ComparisonPlan
StoppingRule
MatchingSemantics
ResourceBounds
ProtocolBindings
```

The plan is immutable for the study.

In v0, `MatchingSemantics` is exactly the prospectively frozen `ExactOutcomeClassification(ExpectedOutcome, ExplicitConflictOutcomes)` form defined in §41. No second executable generic causal matching family exists without a specification revision.

`StoppingRule` MUST be outcome-independent: whether the study stops, continues, or exhausts its planned slots may depend only on the prospectively frozen schedule/resource rule, never on observed outcome values, favorable comparisons, or emerging effect direction.

Every planned case slot has a terminal reporting state. All planned slots must be represented in the final study record as fulfilled, failed, unresolved, or lawfully unexecuted under the frozen outcome-independent stopping rule. A slot may not disappear from reporting because its outcome is inconvenient.

No retrospective selection of favorable cases is allowed.

---

# 40. Trusted Case Occurrence

A causal case is admitted only as a:

\[
\boxed{TrustedCaseOccurrence}
\]

captured under the active study through the authorized external/trusted path.

An internal retrieval, prediction result, hypothesis, derived assertion, or copied identifier cannot become a causal case.

Planned case slots are predeclared. A failed or missing slot is not silently replaced by a more convenient later occurrence unless the original prospective plan explicitly defined such a substitution independently of outcome.

A `TrustedCaseOccurrence` has a canonical occurrence identity issued by the trusted case-capture path. Reuse or retransmission of the same occurrence is idempotent and does not create independent case evidence.

Where `ComparisonPlan` declares separate comparator occurrence sets, those sets must be disjoint by canonical occurrence identity. The same trusted occurrence cannot populate two slots that the frozen plan requires to be independent comparators.

\[
\boxed{
SameTrustedCaseOccurrenceReplay
\neq NewIndependentCase
}
\]

---

# 41. Condition and Outcome Semantics

The causal axis and measured outcome are frozen before observation.

Case comparison states include:

```text
MATCH
CONFLICT
UNRESOLVED
```

There is no generic `ABSENT` state that turns nonobservation into a negative fact.

Outcome matching uses frozen typed semantics and exact structural identity as specified by the study.

The sole executable generic causal matching family in v0 is:

```text
ExactOutcomeClassification(
    ExpectedOutcome,
    ExplicitConflictOutcomes
)
```

`ExpectedOutcome` is one complete canonical typed outcome descriptor. `ExplicitConflictOutcomes` is a finite canonical ordered unique set of complete canonical typed outcome descriptors. All members must be lawful under the frozen `OutcomeSpec`, and `ExpectedOutcome` MUST NOT occur in `ExplicitConflictOutcomes`. The complete classifier is frozen in the prospective `CausalStudyPlan` before relevant observations. Hashes are indexes only; full canonical typed identity determines equality.

For a lawful successfully measured outcome `O`, classification is exactly:

```text
if CanonicalIdentity(O) == CanonicalIdentity(ExpectedOutcome):
    MATCH
else if CanonicalIdentity(O) is an exact member of ExplicitConflictOutcomes:
    CONFLICT
else:
    UNRESOLVED
```

Therefore:

```text
UnequalObservation != CausalConflict
NotMatch != Conflict
DifferentCanonicalOutcome != Conflict
```

`CONFLICT` requires the exact outcome to have been explicitly listed in the frozen prospective contrary-outcome contract. No lexical similarity, structural distance, semantic analogy, negation inference, probability, score, threshold, or learned relation participates.

For `ExpectedOutcome = GroundState(X,A)`, `ExplicitConflictOutcomes = {}`, and `ObservedOutcome = GroundState(X,B)`, the classification is `UNRESOLVED`, not `CONFLICT`. If the prospectively frozen conflict set instead contains that exact `GroundState(X,B)`, the classification is `CONFLICT`. Adding it after observing it is forbidden retrospective adaptation and invalidates the study operation.

A missing, failed, invalid, unavailable, or incomplete measurement supplies no outcome value to the classifier. Its causal comparison state is `UNRESOLVED`, while the planned case slot separately preserves its exact terminal reporting state, such as `FAILED`, `UNRESOLVED`, or `LAWFULLY_UNEXECUTED`, according to the frozen plan.

```text
MissingMeasurement != NegativeOutcome
FailedMeasurement != Conflict
NonObservation != Negation
```

No generic `ABSENT` outcome is introduced. Causal `CONFLICT` is defined only by the frozen causal `MatchingSemantics`. Reasoning constructs such as `FormalNegation`, `MutuallyExclusive`, `SingleValued`, `IncompatibilityView`, and `ConstraintClearanceView` do not automatically define causal case conflict:

```text
ReasoningIncompatibility != CausalCaseConflict
```

Matching bytes or logically incompatible assertions do not alter the causal classifier unless the exact outcome was already frozen in `ExplicitConflictOutcomes`.

`ExpectedOutcome` and `ExplicitConflictOutcomes` may not change because of observed outcomes, favorable/unfavorable direction, missing cases, treatment branch, intermediate comparisons, or remaining budget. A changed classifier is a different study plan, not a revision of the active study.

Only lawful `MATCH` and `CONFLICT` classifications may participate where the frozen `ComparisonPlan` explicitly requires resolved classified outcomes. `UNRESOLVED` remains unresolved and must not be silently coerced to either side. The frozen `ComparisonPlan` may explicitly specify how unresolved slots affect completion/reporting, but may not retrospectively substitute or ignore them based on observed results.

---

# 42. Intervention Authority

A canonical `TreatmentDescriptor` identifies the treatment operation at the level required by the frozen study:

\[
\boxed{
TreatmentDescriptor=(
TreatmentOperationIdentity,
MechanismDescriptor,
AssignmentSemantics,
ExposureDescriptor,
DomainBinding,
ProtocolRevision
)
}
\]

`ExposureDescriptor` includes dose/duration/timing semantics where applicable; non-applicable dimensions use an explicit canonical `NOT_APPLICABLE` value rather than omission. Two treatment labels with different application semantics are different treatments.

The contrast identity uses a canonical unordered pair:

\[
\boxed{
CanonicalTreatmentPair=CanonicalUnorderedPair(TreatmentDescriptor_A,TreatmentDescriptor_B)
}
\]

Branch-specific treatment-to-outcome orientation remains explicit in the execution/result record and is not inferred from pair ordering.

A requested intervention is not an applied intervention.

Actual application requires:

\[
\boxed{AppliedInterventionReceipt}
\]

issued by the trusted controller/domain path.

The receipt is bound to:

- the study;
- the domain;
- the treatment operation;
- the exact case/branch;
- the application occurrence.

A hypothetical reasoning statement such as `DoLike(X)` or `AppliedTreatment(X)` does not create an intervention receipt.

\[
\boxed{
HypotheticalProjection\neq do(X)
}
\]

---

# 43. Protocol Control, Isolation, and Randomization

`ProtocolControlReceipt` is distinct from intervention application.

Randomization, when claimed, requires explicit authority/provenance from the protocol controller.

Isolation/reset authority is distinct from both treatment authority and randomization authority.

A study may not infer randomization, isolation, or independence merely because two executions look similar.

---

# 44. Observational and Interventional Results

Observational studies may establish only the covariation or comparison relation explicitly licensed by their design.

They do not establish causal attribution.

An interventional comparison without an identification basis may establish that outcomes discriminate between treatment conditions under the observed protocol, but v0 does not automatically convert that into a general causal-effect claim.

Causal result classes remain explicit and typed.

---

# 45. Closed Replay Identification

The strongest v0 causal identification uses a closed deterministic replay domain.

A:

\[
\boxed{ClosedReplayDomainContract}
\]

must bind:

- complete relevant domain state;
- exogenous input schedule;
- logical-time contract;
- treatment application semantics;
- branch isolation;
- execution bounds;
- measurement contract;
- determinism as trusted domain property.

Any unbound influence makes the closed replay identification basis invalid.

The replay environment is represented by:

\[
\boxed{
ReplayEnvironmentBinding=(
DomainRuntimeIdentity,
CanonicalEnvironmentDescriptor,
EnvironmentRevisionToken
)
}
\]

`EnvironmentRevisionToken` is monotonic and advances on every semantically relevant environment mutation even if the later descriptor returns to a byte-identical earlier value. Therefore:

\[
\boxed{
Environment_A
\rightarrow Environment_B
\rightarrow Environment_A

\neq SameReplayEnvironmentRevision
}
\]

This prevents ABA-style currentness forgery. Hashes/descriptors are indexes; the monotonic revision/currentness token participates in authority validation.

Repeatability observed after the fact does not establish determinism authority.

---

# 46. Replay Origin and Forking

A replay begins from an immutable:

\[
\boxed{ReplayOrigin}
\]

Forking the same origin creates isolated branches. A fork is not a reset to some unspecified equivalent state.

Branches must share the same exact exogenous schedule except for the prospectively declared treatment contrast.

No branch may observe another branch's mutable state.

---

# 47. Logical Time

Replay uses canonical logical time:

\[
\boxed{\tau\in[0,H_R]}
\]

The treatment and measurement schedule is defined over logical time.

Wall-clock timing is either bounded as operational infrastructure or forbidden from semantic effect.

A faster or slower physical execution cannot change the causal result.

---

# 48. Measurement Contract

Measurement is:

- frozen before outcomes;
- pure with respect to the experimental state;
- treatment-label blind exactly when the frozen `MeasurementContract` requires blinding; runtime outcome inspection cannot enable or disable blinding;
- separated from control-plane authority;
- incapable of adapting its target based on observed outcomes.

Measurement may report only the prespecified outcome semantics.

---

# 49. Replay Comparison Epoch

A:

\[
\boxed{ReplayComparisonEpoch\ (RCE)}
\]

is the bounded operational owner for one canonical replay comparison.

Receipts are RCE-bound.

The RCE has explicit revision/currentness state.

No receipt from another RCE may be substituted.

No open RCE survives invalidation of its parent causal study.

---

# 50. Replay Execution Bundle

A valid replay comparison produces an all-or-nothing:

\[
\boxed{ReplayExecutionBundle}
\]

containing the required branch-execution receipt, `AppliedInterventionReceipt`, branch-isolation execution receipt, exact exogenous-schedule binding, measurement receipt, and actual execution/consumption receipts required by the frozen plan. Each receipt is bound to the RCE, branch, treatment descriptor, logical-time slot, and environment revision where applicable.

Partial bundles do not yield a causal result.

No branch may be retried or substituted based on observed outcome.

---

# 51. Identification Basis Identity

Canonical identification basis includes:

\[
\boxed{
IdentificationBasisIdentity=
(
ClosedReplayContract,
ReplayEnvironmentBinding,
LogicalTimeContract,
BranchIsolationContract,
ExecutionBound,
ExogenousBinding,
MeasurementContract
)
}
\]

Each component is identified by canonical descriptor/authority binding, not by hash alone.

---

# 52. Canonical Replay Contrast Identity

Define:

\[
\boxed{
CRCI=
(
Domain,
ReplayOrigin,
CanonicalTreatmentPair,
IdentificationBasisIdentity
)
}
\]

The treatment pair is canonicalized according to the frozen comparison semantics, not according to outcome.

There is at most one canonical causal result for one valid CRCI. `CanonicalTreatmentPair` is formed from the exact canonical `TreatmentDescriptor`s; treatment mechanism/assignment/exposure differences therefore produce a different CRCI.

Repeated execution of the same CRCI verifies the same logical contrast; it does not create independent causal evidence.

Canonical causal-result issuance is linearizable. The final publication transaction performs, as one currentness decision:

\[
\boxed{
ValidateStudyAuthorityCurrent
+ValidateRCECurrent
+ValidateReplayEnvironmentRevision
+ValidateExecutionBundle
+ValidateCRCIUniqueness
+MintCanonicalCausalResult
}
\]

If any binding or revision becomes stale before the transaction linearizes, no RICTE or other canonical causal result is minted. This final gate prevents validation/publication races and replay-environment ABA.

If the same deterministic CRCI produces disagreeing lawful results:

\[
\boxed{
DETERMINISM\_CONTRACT\_VIOLATION
}
\]

rather than a probability estimate.

---

# 53. Replay-Identified Treatment Effect

For a valid closed replay bundle, if the prespecified outcome differs between the canonical treatment branches, Layer 3 may issue:

\[
\boxed{
ReplayIdentifiedTreatmentEffect\ (RICTE)
}
\]

Its semantics are narrow:

> Under this exact closed replay domain, replay origin, treatment-operation pair, identification basis, logical-time contract, exogenous schedule, and measurement contract, the treatment-operation contrast produced a prespecified outcome discrimination.

It is **not**:

- a universal variable-level causal law;
- a causal strength;
- a probability;
- proof of mechanism;
- proof of transitive causality;
- proof of effect under another origin;
- permission for counterfactual generalization.

If the prespecified outcomes are the same, the result is:

```text
NO_PRESPECIFIED_OUTCOME_DISCRIMINATION
```

not a universal `NO_EFFECT` claim.

---

# 54. Causal Result Conservation

Causal results do not become Layer-1 evidence.

\[
\boxed{
CausalResult\nRightarrow AdjudicatedEvidence
}
\]

A RICTE may be consumed by Reasoning through a typed capability-free cognitive view, but Reasoning cannot reinterpret it as a generic `CAUSES(X,Y)` relation unless a future explicit schema is separately authorized.

No such schema exists in v0.

---

# 55. Causal Study Lifetime

A causal study may span sequential CIEs only while its parent invocation remains `ACTIVE`.

Causal studies do not receive post-invocation delegation in v0.

When the invocation enters `CLOSING`:

- no new study operation may be authorized;
- open studies begin abort/terminalization;
- open RCEs become invalid;
- late receipts become stale;
- no causal publication may linearize after closing began.

A result published lawfully before closing remains an immutable historical result.

---

# 56. Causal Study Resource Envelope

Before a causal study opens, its prospective plan defines a finite `CausalStudyResourceEnvelope`, including all bounded case, comparison, replay, measurement, and validation work.

The envelope is reserved from the invocation ledger.

After reservation, study work is charged to:

```text
CAUSAL_STUDY_ESCROW
```

Unused study resources are retired on terminalization or abort.

No result-dependent top-up exists.

---

# 57. Reasoning — Governing Principle

Reasoning v0 is:

\[
\boxed{
\text{bounded derivation of new transient claims from available structural claims under explicit inference licenses}
}
\]

It contains exactly two canonical sub-capabilities:

1. **Inference License & Composition** — what may lawfully follow;
2. **Constraint & Contradiction** — what may not lawfully coexist under explicit constraints.

Analogy is deferred.

Planning is deferred.

---

# 58. Path Existence Is Not Inference License

A structural path in Core or Layer 2 does not create logical entailment.

\[
\boxed{
PathExistence\neq InferenceLicense
}
\]

Likewise:

\[
ASSOCIATIVE\ Edge\neq Implication
\]

and:

\[
PredictionView\neq Implication
\]

and:

\[
CausalResultView\neq GenericRelation
\]

unless a specific frozen schema consumes that exact typed result.

---

# 59. Inference Schema

An:

\[
\boxed{InferenceSchema}
\]

is executable, fixed, finite, and frozen in `L3PolicyBinding`.

A formal premise is data.

An inference schema is execution authority.

\[
\boxed{
InferenceSchema\neq FormalPremise
}
\]

Learned, retrieved, predicted, causal, or derived content cannot create a new executable schema.

There is no self-modifying rule engine in v0.

---

# 60. Canonical Composition Families

The canonical executable generic composition schema families in v0 are **exactly** the closed design forms below. No additional executable inference schema family may be added by implementation, configuration, or learned content without a formal Layer-3 specification revision.

## 60.1 Ground Modus Ponens

A ground conditional may be applied only when the antecedent matches exactly under canonical identity and required scope/dependency contracts.

No free variables or universal quantification are introduced.

## 60.2 Transitive Composition

Transitive composition for a relation \(R\) requires an explicit formal premise establishing the property:

\[
\boxed{Transitive(R)}
\]

under the active formal authority.

The relation name alone, lexical similarity, or repeated path does not grant transitivity.

No hard-coded semantic relation-name table exists.

## 60.3 Formal Rule-Premise Basis Admissibility

The two generic v0 inference schemas distinguish **formal rule-premise roles** from ordinary assertion-premise roles.

The canonical admissible basis set for a formal rule-premise role is:

```text
FORMAL_GIVEN
FORMAL_ASSUMPTION
```

For `GROUND_MODUS_PONENS`, the `conditional` role is a formal rule-premise role.

For `TRANSITIVE_COMPOSITION`, the explicit `Transitive(R)` property role is a formal rule-premise role.

Assertions with basis:

```text
DERIVED
EXTERNAL_OBSERVATION
INTERNAL_RETRIEVAL
HYPOTHETICAL
PREDICTION_VIEW
CAUSAL_RESULT_VIEW
```

cannot occupy either formal rule-premise role merely because their canonical content is a `GroundConditional(...)` or `Transitive(R)`.

Such assertions remain lawful assertions under their original basis and may be represented, returned, matched as ordinary content where a schema permits, or preserved as provenance-bearing results. Their content shape does not promote their basis or grant formal rule-premise authority.

Ordinary non-rule premise roles remain governed by their own canonical scope, AEC, dependency, lineage, constraint, and schema admissibility contracts. A lawful `DERIVED` ordinary proposition or relation assertion may therefore participate in a later synchronous round.

A `FORMAL_ASSUMPTION` used in a formal rule-premise role retains its assumption dependency root. No assumption discharge occurs.

Therefore:

```text
DerivedGroundConditional != FormalConditionalPremiseAuthority
DerivedTransitiveProperty != TransitivityActivationAuthority
```

and:

```text
SameContentBytes != FormalReasoningIngressAuthority
```

This role-level restriction does not make a formal premise an executable schema. The executable inference authority remains the frozen `InferenceSchema`.

---

# 61. Explicitly Unavailable Logic in v0

The following are unavailable unless a future formal schema is added:

- universal quantification;
- existential introduction beyond declared ground constructors;
- free-variable unification;
- conditional introduction;
- assumption discharge;
- induction;
- contraposition;
- proof by contradiction;
- De Morgan transformations;
- double-negation elimination;
- excluded middle;
- ex falso;
- probabilistic reasoning;
- learned executable rules.

---

# 62. Premise Role Binding

Every schema declares named premise roles.

A derivation binds assertions to those roles explicitly.

Parent role order is semantic unless the schema explicitly declares symmetry.

A canonical derivation identity is:

\[
\boxed{
DerivationKey=
(
ConclusionASK,
SchemaInstanceID,
CanonicalRoleBoundParentTuple
)
}
\]

Historical witness identity is separate from semantic identity.

---

# 63. Inference Work Units

A schema may partition work only by structurally independent frozen partitions declared by the schema.

An `InferenceWorkUnit` may not be chosen because one candidate looks more promising.

No semantic beam search, Top-K, best-first traversal, or learned ranking exists in v0.

---

# 64. Inference Completeness Groups

When a request requires an exhaustive group, membership is determined from the frozen request, schema, and snapshot independently of remaining budget.

The complete group must be reserved before execution.

If insufficient budget exists:

```text
PARTIAL_BUDGET / INCOMPLETE
```

is returned according to the calling contract.

No subset becomes semantically privileged.

---

# 65. Constraint Reasoning — Governing Principle

Constraint reasoning is:

\[
\boxed{
\text{detecting when a bounded set of assertions cannot jointly hold under an explicit constraint}
}
\]

It does not choose which assertion is true.

\[
\boxed{
Different\neq Incompatible
}
\]

\[
\boxed{
NoDetectedConflict\neq Compatibility
}
\]

\[
\boxed{
Incompatibility\neq LogicalComplement
}
\]

\[
\boxed{
Detection\neq Resolution
}
\]

---

# 66. Incompatibility View

A positive constraint result is an immutable typed:

\[
\boxed{IncompatibilityView}
\]

containing at least:

```text
FindingID
ConstraintSchemaRef
RoleBoundParticipantAssertions
ActiveConstraintBindings
ScopeIdentity
EpistemicDependencySet
Derivation/ConstraintWitness
ConstraintEnvironmentBinding
SnapshotBinding
```

It contains no:

- winner;
- loser;
- truth score;
- confidence;
- deletion command;
- Core evidence;
- automatic hypothesis pruning.

An `IncompatibilityView` is not a generic `ClaimAssertion` and cannot be passed to ordinary Modus Ponens or transitivity as if it were a proposition.

Its canonical finding identity is:

\[
\boxed{
FindingID=(
ConstraintSchemaInstanceID,
ConstraintEnvironmentBinding,
ScopeIdentity,
CanonicalRoleBoundAssertionTuple,
CanonicalActiveConstraintBindings,
EDS(F)
)
}
\]

Schema-declared symmetry alone may canonicalize role order. Repeated construction of the same finding is idempotent and does not create conflict strength.

---

# 67. Constraint Schema

A:

\[
\boxed{ConstraintSchema}
\]

is executable and frozen in `L3PolicyBinding`.

A:

\[
\boxed{ConstraintPremise}
\]

is data.

The two are not interchangeable.

Retrieved or derived content cannot self-activate as a constraint law.

---

# 68. Formal Constraint Ingress

An active constraint premise may be created only through:

\[
\boxed{FormalConstraintIngress}
\]

under an authorized formal constraint source.

Canonical active bases in v0 are:

```text
FORMAL_GIVEN
FORMAL_ASSUMPTION
```

The following cannot self-activate a constraint:

```text
INTERNAL_RETRIEVAL
DERIVED
PREDICTION_VIEW
CAUSAL_RESULT_VIEW
HYPOTHETICAL
```

Thus:

\[
\boxed{
ConstraintContent\neq ConstraintActivationAuthority
}
\]

---

# 69. Active Constraint Semantic Identity

Constraint semantics are separated from constraint source occurrence.

Define:

\[
\boxed{
ConstraintSemanticKey=
(
ConstraintContentID,
Basis,
ScopeIdentity,
EDS
)
}
\]

and a separate source occurrence identity.

Several independent formal sources with the same semantic key preserve multiple provenance references but create one semantic constraint work item.

\[
\boxed{
ConstraintSourceMultiplicity\neq ConstraintSemanticMultiplicity
}
\]

Source multiplicity does not create constraint strength.

Canonical source identity is:

\[
\boxed{
ConstraintSourceKey=(
FormalConstraintSourceAuthorityBinding,
CanonicalSourceOccurrenceIdentity,
ConstraintContentID,
ScopeIdentity
)
}
\]

The active semantic record is:

```text
ActiveConstraintSemanticRecord
  ConstraintSemanticKey
  canonical ConstraintContent
  Basis
  ScopeIdentity
  EDS
  bounded SourceConstraintRefs
```

The evaluator executes once per `ConstraintSemanticKey`; repeated source occurrences add provenance only. Replay of the same `ConstraintSourceKey` is idempotent.

---

# 70. Canonical Constraint Families

Constraint/Contradiction v0 begins with exactly three semantic families.

## 70.1 Ground Negation Conflict

`FormalNegation(P)` is a typed ground proposition-content operator created only through formal authority.

Conflict requires exact canonical target-content identity and lawful same-scope applicability.

Natural-language text `"not P"` is not formal negation.

Ground negation does not automatically enable double-negation elimination, excluded middle, contraposition, De Morgan rules, or proof by contradiction.

## 70.2 Explicit Mutual Exclusion

A formal premise:

\[
MutuallyExclusive(S_1,S_2)
\]

has canonical `StateIdentity` operands, not arbitrary proposition contents.

Participant binding is explicit:

```text
ParticipantBinding(GroundState(X,S)) = X
StateIdentityOf(GroundState(X,S)) = S
```

`ParticipantBinding` is undefined for every other generic FAB proposition form in v0 unless that form's canonical schema explicitly defines a participant role. In particular, `ParticipantBinding(R(A,B))` is undefined for an ordinary ground binary relation.

Participant identity must never be inferred from first argument, second argument, shared argument, overlapping argument, relation-name convention, or lexical convention.

A lawful incompatibility requires exact participant assertions:

```text
GroundState(X,S1)
GroundState(X,S2)
```

or the schema-declared symmetric state-role ordering, together with an active lawful `MutuallyExclusive(S1,S2)`, exact same canonical `Participant X`, exact lawful same `ScopeIdentity`, applicable AEC, current constraint environment/use binding, complete required coverage, and the exact EDS construction specified by §73.

State identity comparison uses complete canonical typed identity.

Mutual exclusion is symmetric only because this schema explicitly declares symmetry.

`Different(S1,S2)` does not create mutual exclusion.

Ordinary relation assertions such as `R(A,B)` and `R(B,C)` are not eligible participant-state assertions for this family merely because they contain or share referents. `MutuallyExclusive(R(A,B),R(B,C))` is not a lawful v0 premise because its operands are proposition contents rather than state identities; formal constraint-shape validation must reject it rather than interpret it. It cannot block otherwise lawful transitive composition, subject to all other canonical contracts.

`Assign(X,Slot,V)` is not reinterpreted through this family. Slot/value exclusivity remains governed only by `SingleValued(Slot)` and its existing exact assignment semantics.

Malformed:

\[
MutuallyExclusive(S,S)
\]

is rejected by formal constraint-shape validation; it cannot manufacture self-conflict.

## 70.3 Single-Valued Slot Conflict

Given an active formal premise:

\[
SingleValued(Slot)
\]

and two assignments:

\[
Assign(X,Slot,V_1)
\]

\[
Assign(X,Slot,V_2)
\]

with exact same entity, exact same slot, lawful same scope, and:

\[
V_1\neq V_2
\]

by canonical identity, the schema may establish incompatibility.

`SingleValued` means at most one value. Absence of a value is not a violation.

No alias/similarity resolution is implied.

---

# 71. No Ex Falso

Even when:

\[
P,\ FormalNegation(P)
\]

are both present, Layer 3 may establish incompatibility only.

It may not derive arbitrary \(Q\).

\[
\boxed{
ExFalsoQuodlibet=FORBIDDEN
}
\]

Conflicting formal givens may remain represented as an inconsistency finding without truth resolution.

---

# 72. Active Epistemic Context

Reasoning branches use an immutable:

\[
\boxed{ActiveEpistemicContext\ (AEC)}
\]

containing the dependency roots active in that branch.

An assertion is admissible as a premise only if:

\[
\boxed{
EDS(A)\subseteq AEC
}
\]

The AEC is not merely the union of current premise dependencies.

It may contain active assumptions or modal roots that are not required by every current premise.

Adding an assumption creates a child context rather than mutating the old context.

Assumption discharge is unavailable in v0.

---

# 73. Constraint Applicability

A constraint finding is applicable to a consumer use only when all required conditions hold, including:

- current constraint/environment binding matches;
- required scope semantics match;
- required role-bound participants are present;
- the constraint family is in the consumer preflight profile;
- finding dependencies are active:

\[
\boxed{
EDS(F)\subseteq AEC_{use}
}
\]

A conflict conditional on an assumption in another branch cannot block the current branch.

The dependency set of a finding is not caller-provided and is computed exactly from every semantic participant required by the proof:

\[
\boxed{
EDS(F)=
\left(\bigcup_{A\in ParticipantAssertions(F)}EDS(A)\right)
\cup
\left(\bigcup_{C\in ActiveConstraintPremises(F)}EDS(C)\right)
}
\]

A finding may mint no additional dependency root and may omit none. Therefore a constraint premise that is active only under assumption `H` necessarily produces a finding dependent on `H`; it cannot become an unconditional block.

---

# 74. Constraint Environment Binding

Every live constraint evaluation is bound to:

\[
\boxed{
ConstraintEnvironmentBinding=
(
CIEBinding,
ConstraintSchemaSetIdentity,
ActiveConstraintSetIdentity,
L3PolicyBinding
)
}
\]

`ConstraintSchemaSetIdentity` is the canonical ordered identity of the exact frozen v0 constraint-schema set in `L3PolicyBinding`. `ActiveConstraintSetIdentity` is the canonical ordered set of active `ConstraintSemanticKey` values for the current snapshot; source-support multiplicity does not change this semantic set identity.

Historical findings or clearances from another binding are data only.

They cannot operate as current composition gates.

---

# 75. Constraint Use Binding

Constraint clearance is use-specific.

Define:

\[
\boxed{
ConstraintUseBinding=
(
ConsumerOperationIdentity,
ConsumerSchemaInstanceID,
RoleBoundPremiseTuple,
ConstraintPreflightProfile,
AECIdentity
)
}
\]

A clearance for one consumer schema, role order, AEC, or operation cannot be reused for another.

`ConsumerSchemaInstanceID` identifies the exact frozen inference-schema instance under the current policy. `ConsumerOperationIdentity` identifies the exact canonical requested use of that schema at the current `SnapshotBinding`; it is deterministic and cannot be chosen by the caller.

`CanonicalActiveConstraintBindings` means the canonical role-bound tuple of every active constraint semantic record/premise witness actually required by a finding.

Role reversal requires a fresh check unless symmetry is explicitly declared.

---

# 76. Constraint Profile Completeness

Each `ConstraintSchema` declares a conservative:

\[
\boxed{ConstraintInteractionEnvelope}
\]

Each multi-premise consumer schema declares a:

\[
\boxed{ConsumerPremiseEnvelope}
\]

At `L3PolicyBinding` validation, compute the set of constraint families that may interact with the consumer premise envelope.

Every relevant family must appear in the `ConstraintPreflightProfile`.

\[
\boxed{
RelevantConstraints(S)\subseteq PreflightProfile(S)
}
\]

Unknown interaction is conservatively included.

`EXPLICIT_MUTUAL_EXCLUSION` structurally interacts only with eligible `GroundState` participant assertions. Generic relation argument position, overlap, or shared referents do not create interaction.

A `ConstraintPreflightNotApplicable` declaration requires an explicit `NoConstraintInteractionCertificate`.

Complete execution of an incomplete profile does not constitute a complete constraint check.

---

# 77. Constraint Coverage and Clearance

Absence of an incompatibility finding is not sufficient for composition.

A complete check maintains a bounded:

\[
\boxed{ConstraintCoverageLedger}
\]

over the frozen required frontier.

The operational result is exactly one of:

```text
CONSTRAINT_BLOCKED(F)
CONSTRAINT_CLEARED(CV)
CONSTRAINT_CHECK_INCOMPLETE
```

A `ConstraintClearanceView` means only:

> Under this exact frozen constraint environment, use binding, AEC, scope, snapshot, and complete required constraint frontier, no applicable incompatibility was established.

It does **not** assert:

```text
Compatible(A,B)
```

or any global consistency claim.

---

# 78. Constraint Query Modes

Canonical modes include:

```text
EXISTS_INCOMPATIBILITY
ENUMERATE_ALL_INCOMPATIBILITIES
```

For `EXISTS_INCOMPATIBILITY`, candidate work is ordered by a canonical frontier order and the first applicable finding in that order is the canonical witness.

Thread completion order is never semantic order.

For `ENUMERATE_ALL_INCOMPATIBILITIES`, the entire required frontier must complete before the result is called exhaustive.

---

# 79. Constraint Gate Publication

Constraint evaluation uses staged findings.

The final live gate result is minted only by a linearizable finalization step that revalidates:

- CIE;
- snapshot;
- AEC;
- constraint environment;
- consumer use binding;
- coverage or positive canonical witness.

A candidate finding is not itself operational block authority.

A historical `ConstraintClearanceView` cannot be serialized and later reused as live clearance.

---

# 80. Constraint-Gated Composition

For multi-premise generic composition:

```text
RoleBoundCandidateTuple
    -> validate premises against AEC
    -> build ConstraintUseBinding
    -> complete ConstraintPreflight
    -> BLOCKED | CLEARED | INCOMPLETE
```

Only:

```text
CLEARED
```

permits the exact bound consumer use.

`BLOCKED` does not delete either premise.

`INCOMPLETE` never grants composition authority.

---

# 81. Derived Support Is Constraint-Context Bound

A derived assertion may have the same ASK under several derivations, but a derived support path used as a premise must be lawful in the current constraint context.

Every constraint-gated derivation stores an immutable:

\[
\boxed{ConstraintGateWitness}
\]

bound to its derivation context.

A derived premise may be used under a current context only if at least one lawful acyclic derivation support path exists under the exact current `DerivationContextBinding`.

v0 uses exact context identity rather than assuming monotonic reuse under a larger AEC.

Therefore:

\[
\boxed{
DerivedInAEC_1\not\rightarrow DerivedPremiseInAEC_2
}
\]

automatically.

If the result is needed in \(AEC_2\), it must be lawfully rederived there.

A separate `FORMAL_GIVEN` or `EXTERNAL_OBSERVATION` with the same content remains a distinct assertion source and is not invalidated by a context-local derived path.

---

# 82. Cross-Capability Adapter Principle

All cognitive cross-capability adapters are:

\[
\boxed{
Typed,\ CapabilityFree,\ SemanticallyNonStrengthening
}
\]

They may preserve or narrow source semantics.

They may not strengthen them.

\[
\boxed{
AdapterOutputSemantics\not\supset SourceResultSemantics
}
\]

No generic adapter may silently reinterpret one capability's result as a stronger primitive belonging to another capability.

---

# 83. Capability-Free Cognitive Views

A cognitive cross-capability view may contain only closed immutable data such as:

- canonical IDs;
- typed descriptors;
- typed scopes;
- result class;
- non-authoritative provenance descriptors;
- modal dependency roots;
- immutable semantic payload.

It may not contain:

- trusted receipts;
- writable Core references;
- live L2 handles;
- invocation capabilities;
- FDA;
- causal study authority;
- replay execution capability;
- intervention/control capability;
- registry mutation handles;
- publisher capabilities;
- budget reservation handles.

Validation is recursive over the closed schema.

Unknown nested authority-bearing types fail closed.

\[
\boxed{
CognitivePlane\cap OperationalCapabilityPlane=\varnothing
}
\]

---

# 84. Prediction-to-Reasoning Adapter

A Prediction outcome consumed by Reasoning remains a typed prediction statement, for example:

```text
PredictionOutcomeCognitiveView
  commitment_identity
  prediction_class
  target_descriptor
  outcome_status
  prediction_scope_descriptor
  future_observation_provenance_descriptor?
  PredictionDependencyRoot
```

`MATCHED` means the forecast matched under its protocol.

It does not create a second external observation assertion.

`WINDOW_ELAPSED_WITHOUT_MATCH` does not become formal negation.

A conditional projection does not become a formal ground conditional merely because its content resembles one.

---

# 85. Causality-to-Reasoning Adapter

A causal result consumed by Reasoning remains a typed causal result view, for example:

```text
CausalResultCognitiveView
  result_class
  canonical_result_identity
  CRCI
  treatment_pair_descriptor
  treatment_outcome_map
  outcome_relation
  replay_scope_descriptor
  domain_descriptor
  measurement_contract_descriptor
  CausalResultDependencyRoot
```

It contains descriptors, not live replay/domain capabilities.

A RICTE does not become a generic `CAUSES(X,Y)` assertion.

Its exact replay scope remains part of its semantics.

---

# 86. Layer-2-to-Reasoning Adapter

Layer-2 retrieval results consumed by Reasoning are immutable data-only views.

Internal retrieval remains authority-free.

Layer 3 may initiate new Layer-2 sessions using lawful committed Cell IDs from prior results, but those cues are internal:

\[
\boxed{Authority=0}
\]

Internal multi-session chaining never manufactures a trusted root.

---

# 87. No Internal Authority Re-Ingress

No Layer-3 internal result may be looped back into a trusted/formal ingress to gain stronger authority.

Forbidden examples include:

```text
DERIVED -> FORMAL_GIVEN
PredictionOutcome -> EXTERNAL_OBSERVATION
CausalResult -> FORMAL_CONSTRAINT
ConstraintFinding -> EXTERNAL_OBSERVATION
InternalRetrieval -> TRUSTED_ROOT
```

without a genuinely new independently authorized external occurrence.

\[
\boxed{
SameContentBytes\neq NewExternalAuthority
}
\]

If an external source later presents the same content independently, that is a new source occurrence and may lawfully create a new assertion under its own basis.

---

# 88. Invocation Lifecycle Linearization

The invocation lifecycle uses:

```text
ACTIVE -> CLOSING -> CLOSED
```

`BeginInvocationClose` linearizes the transition to `CLOSING`.

After that point:

- no CIE may open;
- no forecast may seal;
- no causal study may open;
- no child authority may be created;
- no CIE or causal final publication may newly linearize under the parent invocation.

Closure is two-phase:

```text
BeginClose
  -> drain/abort nondelegated children
  -> FinalizeClose
```

The lifecycle barrier is not held while waiting for children.

Already delegated forecasts are not children that block invocation closure.

---

# 89. Forecast Delegation vs Invocation Closure

Forecast sealing and invocation closing are linearly ordered.

If `SealForecastAndDelegate` linearizes first while the invocation is active, the FDA is lawful and the forecast may outlive the invocation.

If `BeginInvocationClose` linearizes first, forecast sealing fails.

No partial state may exist in which budget is committed but FDA/FRR sealing is not coherently completed.

---

# 90. Causality vs Invocation Closure

Causal result publication and invocation closing are linearly ordered.

If causal final publication linearizes first, the immutable result remains valid.

If `BeginInvocationClose` linearizes first, causal publication fails as stale and open study/replay owners abort.

Previously authorized physical external work may finish, but no late cognitive causal result may bypass the closed parent authority.

---

# 91. Global Barrier/Lock Order

The canonical Layer-3 acquisition order is:

\[
\boxed{
CoreTransitionBarrier
\prec
InvocationLifecycleBarrier
\prec
InvocationBudgetLedger
\prec
CIEArena
\prec
OperationalOwnerState
\prec
OperationalRegistry
}
\]

No operation may acquire these in reverse order.

Owner runtime code may not acquire the CIE arena from below the owner-state boundary. Required cognitive inputs must be frozen before entering the owner operation.

Invocation closing never waits for child completion while holding `InvocationLifecycleBarrier`.

---

# 92. Operation Contract

Every Layer-3 operation has a frozen:

\[
\boxed{
OperationContract=
(
OperationType,
BudgetClass,
EffectClass,
AuthorityRequirements,
WorkClass,
ResourceEnvelope,
PublicationPolicy
)
}
\]

The caller does not choose its budget class, effect class, or authority class.

Unknown operation types fail closed.

---

# 93. Work Effect Classes

Canonical v0 effect classes are:

```text
PURE_COMPUTE
OPERATIONAL_EFFECT
```

## 93.1 Pure compute

`PURE_COMPUTE` receives a capability-free execution environment.

It may compute staged immutable data only.

It may not:

- publish semantic results;
- create child authority;
- open retrieval/session owners;
- mutate registries;
- send external requests;
- perform Core/L2 writes.

A pure computation authorized before owner closure may finish after closure, but its staged output cannot be published without current publication authority.

## 93.2 Operational effect

`OPERATIONAL_EFFECT` includes any operation that creates visible semantic or operational change, including:

- semantic publication;
- child authority creation;
- operational owner registration;
- external replay/intervention request commitment;
- forecast sealing;
- causal result publication.

Its authority-sensitive effect must commit while its owner authority is live.

---

# 94. Budget Charge Binding

Every charged work item has exactly one:

\[
\boxed{
BudgetChargeBinding=
(
ChargeSourceKind,
ChargeSourceIdentity,
ReservationIdentity,
ChargeUnitIdentity,
WorkClass
)
}
\]

A budget charge identifies who pays for the work.

It is not authority to execute the work.

\[
\boxed{
BudgetAvailability\neq OperationalAuthority
}
\]

Executable work requires both current operational authority and a valid charge.

---

# 95. Owner Revision

Operational owners carry monotonic revision/currentness tokens.

A work authorization binds:

\[
(OwnerID,OwnerRevision)
\]

A lifecycle transition invalidates stale revision-bound work.

Owner identity alone is insufficient.

This prevents stale/ABA-style authorization.

---

# 96. Authorize and Charge

Pure charged work dispatch uses a linearizable authorization operation that verifies:

- required owner authority is live;
- owner revision is current;
- environment binding is current;
- budget owner matches operational owner;
- work class matches reservation;
- exact charge unit is available.

It then consumes the charge and issues an exact-work nonreusable permit.

Owner closure and work authorization are linearly ordered.

A closed owner cannot be resurrected by an unused budget reservation.

---

# 97. Work Execution Permit

A pure-compute permit is bound to:

```text
ExactWorkIdentity
OwnerIdentity
OwnerRevision
ChargeIdentity
DispatchEpoch
```

It is:

- opaque;
- nonserializable;
- nontransferable;
- nonreusable;
- valid for one exact work item.

Reusing a dispatched permit fails.

A work permit does not itself grant semantic publication authority.

---

# 98. Canonical Effect Descriptor

Before an operational effect can be authorized, the complete effect is frozen as:

\[
\boxed{
CanonicalEffectDescriptor=
(
EffectType,
TargetIdentity,
CanonicalPayload,
ScopeBinding,
EnvironmentRevision,
OwnerBinding,
ExecutionContract
)
}
\]

No placeholder target or later semantic choice is allowed.

The authority decision is about this exact effect.

---

# 99. Authorize, Charge, and Commit Effect

Operational effects use one linearizable authority transaction:

\[
\boxed{
AuthorizeChargeAndCommitEffect
}
\]

The transaction:

1. validates the live operational owner;
2. validates current owner revision;
3. validates environment;
4. validates exactly one budget charge;
5. validates work/effect class;
6. validates the canonical effect descriptor;
7. consumes the charge;
8. commits the exact logical effect.

If owner closure linearizes first, the effect does not commit.

If effect commit linearizes first, later physical transport/execution may complete only the already-committed exact effect.

---

# 100. Effect Commit Identity and Retry

An `EffectCommitID` identifies one exact immutable logical effect.

Transport retry of the same committed effect reuses the same logical identity.

\[
\boxed{
TransportRetry\neq NewLogicalEffect
}
\]

Duplicate receipts for one logical effect are idempotently recognized.

If an external provider cannot guarantee physical exactly-once delivery, Layer 3 still guarantees at most one **authorized logical effect** for the commit identity.

A different effect requires a new commit, live authority, and a new charge.

---

# 101. No Deferred Child Authority Creation

Child authority must be created at the authority-sensitive effect commit point.

A previously issued work permit may not be held across parent closure and later used to mint:

- FDA;
- CIE;
- CausalStudyAuthority;
- ReplayComparisonEpoch;
- any new operational owner.

\[
\boxed{
NoDeferredChildAuthorityCreation
}
\]

---

# 102. Charge-Exempt Control Plane

Every Layer-3 operation belongs exactly to one class:

\[
\boxed{
CHARGED\_WORK
\oplus
CHARGE\_EXEMPT\_CONTROL\_PLANE
}
\]

There is no third category.

Charge exemption is determined by the canonical frozen v0 allowlist below, never by caller choice:

```text
READ_IMMUTABLE_LIFECYCLE_FLAG
RETIRE_UNUSED_CHARGE_UNITS
RELEASE_TERMINAL_REGISTRY_CAPACITY
ATTACH_ALREADY_PRODUCED_DESCRIPTOR
CANONICAL_COMPARE_WITHIN_ALREADY_CHARGED_PARENT_WORK
AUTHORITY_REDUCING_LIFECYCLE_BOOKKEEPING
```

An implementation may split these into private helpers only if the helpers are semantically equivalent, strictly bounded, and do not add a new exempt public/dispatchable operation type. Adding another exemption requires a Layer-3 specification revision.

Exempt operations may perform only strictly bounded administrative work.

They may reduce or close authority.

They may not create:

- semantic results;
- new authority;
- external effects;
- retrieval;
- inference;
- constraint evaluation;
- prediction evaluation;
- causal evaluation.

An exempt wrapper cannot hide transitively charged cognitive work.

Any traversal/discovery whose cost depends on a cognitive frontier rather than a constant or already-reserved parent structure is charged work.

---

# 103. Budget Lifecycle

A budget unit transitions only through lawful states such as:

```text
AVAILABLE -> RESERVED -> CONSUMED
AVAILABLE -> RESERVED -> RETIRED
```

A consumed or retired unit never becomes available again.

Ordinary reservations cannot be transferred between owner classes. The only lawful owner-class transition in v0 is the one-way delegation performed atomically at forecast sealing:

```text
INVOCATION_GENERAL: RESERVED_FOR_FORECAST
        -> DELEGATED_FORECAST_POOL
```

This transition is issuance of the forecast-owned pool, not a later transfer or refund. After delegation, a unit can only be consumed or retired within that forecast pool and can never return to invocation-general ownership or move to another owner class. Causal-study reservation remains a child reservation of the active invocation and never survives invocation closure.

No unused forecast budget becomes causal or reasoning budget.

No unused causal budget becomes forecast or reasoning budget.

---

# 104. Prediction Budget Ownership

Once forecast delegation succeeds, delegated forecast budget is owned by the forecast pool.

Future forecast work uses only `FORECAST_ESCROW`, even if the parent invocation happens to remain active.

It may not fall back to invocation-general budget.

Forecast closure retires unused units.

---

# 105. Causal Budget Ownership

Once a causal study reserve succeeds, all study-plan work uses `CAUSAL_STUDY_ESCROW`.

Unrelated reasoning under the same invocation remains invocation-general work and may not consume causal escrow.

When the invocation begins closing, remaining causal escrow is retired as the study aborts.

---

# 106. Failure Atomicity

Layer 3 follows:

\[
\boxed{
Build\rightarrow Validate\rightarrow Publish
}
\]

or, for operational effects:

\[
\boxed{
BuildDescriptor\rightarrow Validate\rightarrow AuthorizeChargeAndCommit
}
\]

No partial cognitive result is published on failure.

No failure path may:

- invent a fallback winner;
- silently lower a constraint profile;
- truncate an exhaustive frontier;
- convert stale state into current state;
- retry for free;
- create new budget;
- strengthen result semantics.

---

# 107. Generic Failure Algebra

Layer-3 public/internal failure families include, as applicable:

```text
INVALID_INPUT
INVALID_FORMAL_AUTHORITY
INVALID_DEPENDENCY
INVALID_SCOPE
INVALID_POLICY_BINDING
ENVIRONMENT_STALE
INVOCATION_NOT_ACTIVE
CIE_STALE
OWNER_AUTHORITY_STALE
BUDGET_ABORT
CAPACITY_ABORT
PARTIAL_BUDGET
CONSTRAINT_CHECK_INCOMPLETE
CONSTRAINT_CHECK_STALE
STALE_CONSTRAINT_CLEARANCE
PARENT_AUTHORITY_STALE
OPERATIONAL_EFFECT_AUTHORITY_STALE
EFFECT_PAYLOAD_MISMATCH
MISSING_BUDGET_CHARGE
AMBIGUOUS_BUDGET_OWNER
BUDGET_WORKCLASS_MISMATCH
UNKNOWN_OPERATION_TYPE
EXEMPTION_CONTRACT_VIOLATION
CROSS_CAPABILITY_AUTHORITY_LEAK
CROSS_CAPABILITY_ADAPTER_TYPE_VIOLATION
INTERNAL_CONTRACT_VIOLATION
```

A specific capability may refine these into its own typed status.

Failures are deterministic under the same frozen inputs and environment.

---

# 108. Determinism

Given identical:

- canonical ingress;
- CEB;
- policy;
- budgets/capacities;
- lower-layer immutable results;
- operational receipts;
- scheduling-independent logical events;

Layer 3 must produce the same canonical cognitive result.

Wall-clock timing, thread completion order, random UUIDs, object addresses, hash-map insertion order, and diagnostics may not alter cognitive semantics.

Canonical frontier ordering is administrative determinism, not semantic ranking.

---

# 109. Locality and Boundedness

Layer 3 may chain multiple **separate** Layer-2 sessions within a CIE, but each session remains bounded by Layer-2 rules.

Layer 3 itself must bound:

- number of retrieval needs;
- number of CIE assertions;
- derivation rounds;
- schema candidate frontiers;
- constraint work;
- live forecasts;
- forecast horizon;
- causal cases;
- replay horizon;
- replay branches;
- result records;
- provenance witnesses.

No normal Layer-3 cognition may perform an unbounded global scan of Core or a hidden whole-history scan.

---

# 110. No Ranking Authority

Layer 3 v0 contains no generic:

- best hypothesis selector;
- confidence scorer;
- beam search;
- Top-K reasoner;
- global causal score;
- prediction probability;
- contradiction severity score.

Canonical ordering exists only for deterministic enumeration and identity.

It is never a semantic preference.

---

# 111. No Evidence Manufacturing

The following do not create Layer-1 learning evidence:

- internal retrieval;
- repeated retrieval;
- pattern completion;
- reasoning derivation;
- hypothesis generation;
- prediction projection;
- forecast match;
- forecast miss;
- constraint incompatibility;
- constraint clearance;
- causal observational result;
- intervention comparison result;
- RICTE;
- repeated replay verification.

\[
\boxed{
GeneratedProgress\neq ExternalEvidence
}
\]

\[
\boxed{
ExpressionHistory\neq EvidenceHistory
}
\]

Any future Layer-3-to-Core learning interface requires a separate formal design and is unavailable in v0.

---

# 112. Canonical Prohibitions

Layer 3 v0 forbids:

```text
persistent PredictionMemory
persistent CausalMemory
persistent ReasoningMemory
persistent contradiction database
persistent hypothesis database

internal output -> trusted ingress escalation
retrieval -> root authority escalation
derived assertion -> external observation escalation
prediction match -> second observation
prediction miss -> formal negation
prediction outcome -> Core learning evidence
causal result -> Core learning evidence
constraint finding -> Core learning evidence

ASSOCIATIVE -> CAUSES
RICTE -> generic CAUSES
hypothetical -> applied intervention
request -> applied intervention
repeatability -> determinism authority
same replay outcome -> universal NO_EFFECT

path existence -> implication
retrieved text -> executable rule
derived constraint content -> active constraint
natural-language "not" -> FormalNegation
difference -> incompatibility
incompatibility -> logical complement
incompatibility transitive closure
conflict -> winner selection
conflict -> assertion deletion
conflict -> ex falso

scope broadening
dependency deletion
modal-origin erasure
cross-context derived-support reuse without rederivation
historical result -> live authority
descriptor -> capability

Top-K truncation of required complete frontier
budget refund after substantive work
budget transfer between owners
unmetered semantic work
effect commit after owner closure
deferred child-authority creation
```

---

# 113. Prediction Acceptance Obligations

The implementation must prove at least:

- mixed/internal origin cannot become root-anchored forecast;
- trusted-only origin is bound to the exact retrieval/session provenance;
- target identity is source-specific;
- branch target anchors and pattern cells remain distinct;
- an anchor-confirmed but incomplete exact sealed pattern is not matched;
- complete exact sealed pattern reinstatement together with lawful anchor confirmation is matched, without a score or partial-pattern threshold;
- complete pattern reinstatement without lawful anchor confirmation is not matched;
- combining witnesses or reconstructed Cells from different target Assemblies cannot produce a branch match;
- exact future root-seeded Assembly `SourceView` lane is used for `BranchPattern` reinstatement;
- an exact matching `BranchView` cannot complete an otherwise incomplete target `SourceView`;
- `BranchViews` from other sources cannot contribute to future match evaluation;
- branch union cannot contribute to future match evaluation;
- absent target `SourceView` with valid `TargetGuard` is a lawful nonmatch, not `TARGET_STALE`;
- future associative reconstruction cannot self-confirm a forecast;
- atomic direct hits remain distinct from branch targets;
- an atomic carrier reconstructed internally but absent from genuine future root-authorized witnesses is not matched;
- no backdating;
- whole-commitment capacity failure publishes no forecast;
- future capture uses genuine trusted future roots only;
- duplicate future-root processing is idempotent under exact `ForecastEvaluationID`;
- duplicate future occurrences do not advance the horizon or allocate new capture/evaluation work;
- the observation/evaluation ledger is append-only;
- `TargetGuard` prevents target remapping or replacement, including target Assembly replacement, and forces `TARGET_STALE`;
- forecast sealing is all-or-nothing across origin revalidation, escrow, registry, FRR, FDA, and commitment publication;
- normal future Core tick/version advancement does not invalidate the historical origin binding by itself;
- boundary termination works;
- stale target/environment fails closed;
- `MATCHED` does not create extra learning evidence;
- miss does not create negative evidence;
- observation gaps remain inconclusive;
- horizon is logical trusted-occurrence based, with \(1\le H\le H_{max}\), and not wall-clock based;
- a lawful match exactly at offset \(H\) yields `MATCHED`, including after an earlier observation gap;
- missing or failed capture advances its offset and records `OBSERVATION_GAP`, never `PROVEN_EMPTY`;
- explicitly lawfully proven empty capture advances its offset with complete coverage and without creating a gap;
- a horizon completed without a match and with any gap yields `INCONCLUSIVE_OBSERVATION_GAP`, never indefinite `PENDING`;
- a completely lawfully covered horizon without a match yields `WINDOW_ELAPSED_WITHOUT_MATCH`;
- boundary/cancellation/staleness races with evaluation follow the specified linearization order: evaluation first may complete; termination first prevents window admission;
- future evaluation validates `FutureEvaluationBinding`, then `TargetGuard`, then capture, match, and window closure;
- at most one capture allocation and one evaluation allocation exist per offset, and unused escrow cannot be transferred or reused;
- FDA cannot open a CIE, study, or second forecast;
- forecast continuation after invocation close uses only previously delegated FDA;
- forecast work cannot consume parent general budget after delegation.

---

# 114. Causality Acceptance Obligations

The implementation must prove at least:

- association cannot mint causal authority;
- prediction results cannot become causal cases;
- case slots are prospectively frozen;
- the stopping rule is outcome-independent;
- every planned slot is terminally reported;
- separate comparator occurrence sets are disjoint where required by the frozen plan;
- replay/retransmission of one `TrustedCaseOccurrence` is idempotent and never independent evidence;
- outcomes cannot change comparison selection;
- missing case is not automatic negative outcome;
- exact expected outcome yields `MATCH`;
- unequal unlisted lawful outcome yields `UNRESOLVED`;
- exact prospectively listed contrary outcome yields `CONFLICT`;
- missing measurement yields `UNRESOLVED`;
- failed measurement yields `UNRESOLVED`;
- classifier cannot be altered after outcome observation;
- Reasoning incompatibility cannot self-create causal `CONFLICT`;
- `ExplicitConflictOutcomes` cannot overlap `ExpectedOutcome`;
- intervention request is not application;
- hypothetical treatment is not `do(X)`;
- randomization requires protocol authority;
- isolation requires isolation authority;
- closed replay rejects unbound influences;
- `ReplayEnvironmentBinding` revision rejects ABA-style environment reuse;
- exact exogenous schedule is preserved;
- measurement contract is frozen;
- logical time controls semantics;
- same CRCI repeat is verification, not new evidence;
- same deterministic CRCI disagreement is contract violation;
- canonical causal-result issuance revalidates study/RCE/environment/bundle/CRCI atomically before mint;
- different replay origin is a different CRCI;
- `SAME` outcome does not produce universal no-effect claim;
- RICTE remains treatment-operation/replay-origin scoped;
- causal result does not become generic `CAUSES`;
- causal study cannot survive invocation closing;
- late receipts are stale;
- no causal publication occurs after parent closing;
- no adaptive budget top-up exists.

---

# 115. Reasoning Acceptance Obligations

The implementation must prove at least:

- retrieved paths do not create inference licenses;
- executable schemas are fixed in policy;
- formal premises cannot self-execute;
- exact identity is used where specified;
- transitivity requires explicit `Transitive(R)`;
- relation-name keywords do not create semantics;
- every assertion basis is minted only by the exhaustive basis-constructor matrix;
- `EDS=empty` never means fact/trusted truth;
- every derived conclusion has basis `DERIVED`;
- derived EDS is parent EDS union;
- dependency roots cannot be dropped;
- circular justification is rejected;
- lawful independent support may survive a circular alternative;
- same-round outputs are not same-round premises;
- complete work groups are not truncated to fit budget;
- resource-envelope excess is contract violation;
- no schema may invent arbitrary referents;
- no generic scope broadening exists;
- source replay is idempotent and support multiplicity does not create a Cartesian derivation frontier;
- only the two canonical generic v0 schema families are executable;
- a `DERIVED GroundConditional` cannot occupy the Modus Ponens formal conditional role;
- a `DERIVED Transitive(R)` cannot activate transitive composition;
- a lawful `DERIVED` ordinary proposition/relation may serve as a later-round ordinary premise when all AEC/scope/lineage/constraint requirements hold;
- fixed point requires a complete empty next frontier.

---

# 116. Constraint Acceptance Obligations

The implementation must prove at least:

- `Different != Incompatible`;
- text `"not P"` cannot mint `FormalNegation(P)`;
- formal negation targets exact proposition content;
- `MutuallyExclusive` symmetry is schema-declared;
- Explicit Mutual Exclusion never infers participant roles from relation argument position or overlap;
- `MutuallyExclusive` operands are state identities, not arbitrary proposition contents;
- only explicit `GroundState` participant binding can activate this v0 family;
- `R(A,B)` and `R(B,C)` sharing `B` does not by itself create a mutual-exclusion interaction;
- `SingleValued` means at-most-one, not exactly-one;
- missing value is not a violation;
- derived/retrieved constraint content cannot self-activate;
- active constraints are formal-ingress controlled;
- `EDS(F)` is the exact union of participant-assertion and active-constraint-premise dependencies;
- duplicate constraint sources do not multiply semantic work;
- conditional conflicts are applied against the AEC;
- branch assumptions need not appear in every premise EDS to remain active;
- foreign-branch dependencies do not leak;
- constraint profile omission is rejected at policy validation;
- `PreflightNotApplicable` requires a certificate;
- absence of finding is not clearance without complete coverage;
- clearance is exact-use, snapshot, environment, AEC, and role bound;
- `EXISTS` canonical witness is scheduling invariant;
- `ENUMERATE_ALL` requires full coverage;
- blocked premises are not deleted;
- `CLEARED` does not create compatibility proposition;
- incomplete check cannot authorize composition;
- derived support from another AEC cannot bypass current preflight;
- ex falso remains unavailable.

---

# 117. Cross-Capability Acceptance Obligations

The implementation must prove at least:

- modal dependency roots survive arbitrary lawful derivation chains;
- modal dependency roots cannot become capabilities;
- prediction cognitive views contain no live trusted-root handles;
- causal cognitive views contain no live replay/domain/controller handles;
- nested opaque metadata cannot smuggle a capability;
- serialized cognitive data cannot resurrect authority;
- prediction match is not external observation;
- causal result is not generic causal law;
- internal outputs cannot re-enter trusted ingresses without a new external occurrence capability;
- copied/forged occurrence descriptors cannot reconstruct `ExternalOccurrenceCapability`;
- the trusted observation adapter accepts only genuine trusted occurrence authority and is idempotent per occurrence;
- same content from a new real external occurrence remains lawful as a distinct source;
- internal retrieval cannot be purified into trusted authority;
- historical result views cannot reopen operational owners.

---

# 118. Runtime/Concurrency Acceptance Obligations

The implementation must prove at least:

- global barrier order is never inverted;
- invocation closing does not wait while holding the lifecycle barrier;
- forecast sealing and invocation closing are linearly ordered;
- causal publication and invocation closing are linearly ordered;
- owner closure and work authorization are linearly ordered;
- stale owner revision rejects work;
- zero-charge charged work is rejected;
- multiple valid budget owners are rejected;
- wrong work-class budget is rejected;
- forecast budget delegation is a one-way atomic transition to `DELEGATED_FORECAST_POOL`;
- delegated forecast budget can never return or transfer to another owner class;
- effectful work cannot masquerade as pure;
- pure compute has no operational effect API;
- a preauthorized pure computation cannot publish after parent authority expires;
- operational effect commit cannot occur after owner closure;
- committed payload cannot be mutated;
- one effect commit cannot authorize a different effect;
- transport retry does not create a second logical effect;
- child authority cannot be deferred until after parent closure;
- exempt control-plane operations are exactly from the canonical frozen v0 allowlist;
- implementation cannot add a new exempt operation without specification revision;
- exempt operations cannot emit semantic results or external effects;
- exempt wrappers cannot hide charged work;
- unbounded administrative scans are not exempt.

---

# 119. Adversarial Acceptance Matrix

The implementation must include adversarial cases covering at least:

```text
A01 forged InvocationAuthority
A02 same InvocationCause transport retry requests fresh budget
A03 second simultaneous CIE under one invocation
A04 stale CEB publication
A05 Core transition tear during trusted capture
A06 operator directly calls Core mutation
A07 operator reserves its own budget
A08 orchestrator performs semantic ranking

A09 prediction from internal-only retrieval
A10 prediction from mixed retrieval then trusted-subset purification
A11 forecast backdating
A12 duplicate future-root evaluation
A13 prediction MATCH -> second observation
A14 prediction MATCH -> extra y=1
A15 prediction miss -> y=0
A16 prediction miss -> FormalNegation
A17 FDA opens a CIE
A18 FDA opens a causal study
A19 FDA creates another forecast
A20 FDA transferred to another commitment
A21 forecast uses parent budget after delegation
A22 forecast sealing races invocation close

A23 ASSOCIATIVE edge -> causal fact
A24 prediction MATCH -> TrustedCaseOccurrence
A25 derived assertion -> TrustedCaseOccurrence
A26 hypothetical -> AppliedInterventionReceipt
A27 request -> AppliedInterventionReceipt
A28 randomization claimed without protocol authority
A29 isolation claimed without isolation authority
A30 unbound replay influence
A31 branch cross-talk
A32 measurement adapts after seeing outcome
A33 same CRCI disagreement
A34 different ReplayOrigin merged into same CRCI
A35 repeated CRCI counted as independent evidence
A36 SAME outcome -> universal NO_EFFECT
A37 RICTE -> generic CAUSES
A38 causal result -> Core evidence
A39 causal publication races invocation close
A40 late replay receipt after study abort

A41 retrieved conditional -> executable Modus Ponens
A42 retrieved "transitive" -> executable transitivity
A43 relation-name hard-coded semantics
A44 derived conclusion inherits external-observation basis
A45 derived conclusion drops dependency root
A46 circular derivation support
A47 same-round recursion
A48 budget selects first-N inference candidates
A49 FAB-AST opaque metadata injects referent
A50 scope broadening through composition

A51 text "not P" -> FormalNegation
A52 Different -> Incompatible
A53 derived SingleValued -> active constraint
A54 duplicate constraint sources multiply strength/work
A55 conditional conflict from foreign AEC blocks current branch
A56 branch assumption absent from premise EDS is ignored
A57 incomplete preflight profile
A58 fake PreflightNotApplicable
A59 incomplete constraint coverage -> CLEAR
A60 clearance reused under another schema
A61 role-reversed clearance reuse
A62 old-CIE clearance replay
A63 scheduling changes EXISTS witness
A64 BLOCKED -> winner/delete
A65 conflict -> Core negative evidence
A66 P and Neg(P) -> arbitrary Q
A67 derived result from AEC1 bypasses AEC2 constraint gate

A68 PredictionDependencyRoot erased after multi-step reasoning
A69 CausalDependencyRoot becomes StudyAuthority
A70 cognitive view contains live receipt
A71 nested cognitive metadata hides live capability
A72 descriptor reconstructs capability
A73 internal result -> FormalGiven
A74 internal result -> ExternalObservation
A75 causal result -> FormalConstraint
A76 internal Layer-2 result -> trusted root

A77 stale BCB executes after owner close
A78 zero budget owner
A79 two budget owners
A80 wrong owner/work-class charge
A81 consumed charge reused
A82 retired charge resurrected
A83 WEP reused
A84 pure work publishes after closure
A85 effectful work delayed until after closure
A86 committed effect payload mutation
A87 EffectCommit reused for a different effect
A88 transport retry creates second logical effect
A89 deferred child authority creation after parent close
A90 semantic work mislabeled bookkeeping
A91 exempt wrapper starts retrieval
A92 unbounded exempt loop
A93 lock-order inversion
A94 BeginClose waits for children while holding lifecycle barrier
A95 persistent Layer-3 cognitive store introduced

A96 forged/copied ExternalOccurrenceCapability descriptor
A97 same SourceAssertionKey replay counted as new support
A98 source-support multiplicity creates Cartesian derivations
A99 forecast target identity remapped after sealing
A100 forecast observation ledger rewritten/backdated
A101 forecast seal partially publishes escrow/FRR/FDA
A102 outcome-dependent causal stopping rule
A103 planned causal slot omitted from final reporting
A104 same TrustedCaseOccurrence reused as independent comparators
A105 replay environment ABA returns to same descriptor with new revision
A106 replay environment changes between validation and causal-result mint
A107 treatment descriptors with distinct exposure/mechanism collapse to one CRCI
A108 repeated causal receipt counted as independent evidence
A109 conditional constraint finding drops active-constraint dependency from EDS(F)
A110 derived support reuses a mismatched DerivationContextBinding
A111 forecast delegated pool transfers/refunds to invocation or another owner
A112 implementation adds an unlisted charge-exempt semantic operation

A113 anchor confirmation with an incomplete sealed pattern falsely yields MATCHED
A114 complete exact pattern plus lawful anchor confirmation is rejected or subjected to a partial-pattern score
A115 complete pattern without lawful anchor confirmation falsely yields MATCHED
A116 witnesses or reconstructed Cells from different target Assemblies are unioned into one match
A117 internally reconstructed atomic carrier is accepted without future root authorization
A118 lawful match exactly at H loses to elapsed/gap window closure
A119 missing/failed capture stalls an offset, becomes PROVEN_EMPTY, or triggers a second capture allocation
A120 lawfully proven empty capture fails to advance or is misclassified as an observation gap
A121 completed unmatched horizon containing a gap yields WINDOW_ELAPSED_WITHOUT_MATCH or stays PENDING
A122 completely lawfully covered unmatched horizon yields an observation-gap result
A123 duplicate FutureTrustedOccurrenceID advances the horizon, rewrites a gap, or obtains fresh work allocations
A124 boundary/cancellation/staleness race admits evaluation after termination linearized first
A125 termination retroactively invalidates the exact evaluation that lawfully linearized first
A126 final-offset match after an earlier gap is suppressed as INCONCLUSIVE_OBSERVATION_GAP
```

No adversarial case may be closed by weakening Layer 1 or Layer 2.

---

# 120. Conservation Tests

A dedicated Layer-3 conservation suite must compare canonical lower-layer state before and after cognition and prove no unauthorized change in:

- Cells;
- Cell activation except changes independently caused by lawful Core events outside Layer-3 mutation;
- Synapses;
- Synaptic evidence;
- Assemblies;
- memberships;
- Layer-1 temporal learning context;
- Layer-1 recruitment state;
- Layer-1 root/evidence state;
- Layer-2 persistent state, which must remain empty.

The suite must also prove:

\[
\boxed{
\Delta PersistentCognitiveState_{L3}=0
}
\]

after all operational owners become terminal, excluding immutable returned result values and noncognitive audit infrastructure.

---

# 121. Deterministic Serialization / Signatures

Canonical cognitive results used for verification must serialize deterministically.

Operational capabilities, object addresses, wall-clock timestamps, lock state, thread IDs, random UUIDs, and debug counters must not appear in canonical cognitive serialization.

Identity fields must use canonical architecture-defined descriptors.

Capability-free cognitive views may be serialized.

Live authority must not be serializable into reusable authority.

---

# 122. Reference Implementation Contract for Codex

This document is the authoritative Layer-3 architecture candidate after paper review.

## 122.1 Codex MAY

Codex MAY:

- choose clean module decomposition;
- create immutable dataclasses for typed assertions/views;
- use bounded indexes inside CIEs and operational owners;
- use exact derivable caches;
- optimize deterministic candidate scheduling without changing semantics;
- use parallel physical execution where publication remains canonical and deterministic;
- add diagnostics with no decision authority;
- add deterministic serialization/signature tooling;
- choose internal representation of capabilities so long as ordinary callers cannot reconstruct them;
- map logical resource envelopes to implementation work units conservatively.

## 122.2 Codex MUST

Codex MUST:

- preserve the persistent-state-empty thesis;
- preserve all authority boundaries;
- preserve CIE and invocation lifecycle semantics;
- preserve all basis, EDS, scope, lineage, and AEC semantics;
- preserve capability-free cognitive adapters;
- preserve Prediction no-learning-feedback semantics;
- preserve Causality prospective/contrast/replay identification limits;
- preserve Reasoning explicit schema authority;
- preserve Constraint tri-state gate semantics;
- preserve exact cross-context derived-support restrictions;
- preserve budget nonrenewability and exactly-one charge ownership;
- preserve work/effect classification and atomic effect commit;
- preserve the global barrier acquisition order;
- fail closed on stale authority, environment, unknown operation type, unknown capability field, insufficient complete-frontier resources, and contract violations;
- satisfy the acceptance and adversarial obligations.

## 122.3 Codex MUST NOT

Codex MUST NOT:

- modify Layer-1 or Layer-2 semantics to make Layer 3 easier;
- add persistent cognitive Layer-3 memory;
- add a global learned controller;
- add semantic embeddings;
- add hidden confidence/ranking;
- add Top-K truncation where completeness is required;
- infer causal meaning from association;
- infer implication from graph paths;
- turn predictions into observations;
- turn misses into negative evidence;
- turn causal results into generic causal laws;
- turn constraint findings into truth arbitration;
- allow internal authority re-ingress;
- serialize live capabilities;
- permit budget to substitute for expired authority;
- permit effect commit after authority closure;
- silently add planning, analogy, generation, or quantified logic;
- implement before the required comprehension gate is accepted.

---

# 123. Codex Pre-Code Comprehension Gate

Before Codex writes production Layer-3 code, it must return a comprehension report containing at least:

1. proposed module decomposition;
2. all persistent versus transient/operational state structures;
3. invocation cause and authority lifecycle;
4. CIE lifecycle and arena model;
5. exact CEB components and validation points;
6. budget ledger, reservation, charge, and retirement model;
7. canonical assertion identity (`ClaimContentID`, ASK, source support);
8. complete `AssertionBasis` construction authority;
9. EDS and modal dependency propagation;
10. typed scope model;
11. FAB-AST and deep referent closure;
12. derivation lineage and acyclic-support enforcement;
13. round staging and publication plan;
14. Prediction projection versus root-anchored forecast distinction;
15. forecast target, FRR, FDA, and escrow model;
16. proof that Prediction cannot create learning evidence;
17. prospective causal-study model;
18. trusted case/intervention/control/isolation authority boundaries;
19. closed replay, RCE, identification basis, CRCI, and RICTE semantics;
20. proof that causal results cannot become generic causal laws/evidence;
21. inference-schema/formal-premise separation;
22. constraint-schema/constraint-premise separation;
23. exact AEC and cross-context derived-support enforcement;
24. constraint profile completeness validation;
25. clearance/finding tri-state publication;
26. capability-free cross-capability adapter plan;
27. no-internal-authority-reingress enforcement;
28. Invocation lifecycle barrier and global lock order;
29. `OperationContract`, `WorkEffectClass`, BCB, WEP, and `CanonicalEffectDescriptor`;
30. `AuthorizeChargeAndCommitEffect` linearization plan;
31. frozen charge-exempt allowlist and transitive exemption enforcement;
32. deterministic serialization/signature plan;
33. complexity/boundedness argument;
34. acceptance/adversarial test mapping to Sections 113–120;
35. complete basis-minting/ingress capability matrix, including trusted observation admission;
36. exact `SourceAssertionKey` idempotency and non-Cartesian source-support handling;
37. exact `AECIdentity`, `DerivationContextBinding`, and `EDS(F)` construction;
38. prospective causal stopping/slot-reporting/occurrence-disjointness enforcement;
39. `ReplayEnvironmentBinding` monotonic revision and linearizable causal-result issuance;
40. forecast `TargetGuard`, `ForecastEvaluationID`, append-only ledger, and atomic seal transaction;
41. treatment descriptor / canonical pair identity and replay receipt bindings;
42. one-way forecast budget delegation state transition and canonical charge-exempt allowlist;
43. every ambiguity Codex believes remains.

Production implementation must not begin until this interpretation is independently reviewed.

---

# 124. Interface to Layer 4 — Generation

Layer 4 may consume immutable Layer-3 cognitive results, including lawful:

- current assertions;
- prediction views;
- forecast outcomes;
- causal result views;
- derived assertions;
- constraint findings;
- constraint clearance status;
- provenance and scope metadata.

Layer 4 owns future expression/generation policy.

Layer 4 may decide how to verbalize uncertainty, alternatives, predictions, causal results, and conflicts, but it may not rewrite their semantics.

Layer 4 may not:

- convert projection to observation;
- convert RICTE to a universal causal law;
- hide dependency/scope distinctions when those distinctions change meaning;
- turn `CONSTRAINT_CLEARED` / a complete no-finding check into `Compatible`;
- feed generated text back as trusted/formal Layer-3 authority;
- create Core learning evidence merely because text was generated.

Generation is downstream expression, not new epistemic authority.

---

# 125. Architecture Summary

```text
                     +----------------------------------+
                     |      LAYER 4 — GENERATION        |
                     |  expression / decoding / policy   |
                     +----------------^-----------------+
                                      |
                         immutable cognitive views
                                      |
+-------------------------------------------------------------------+
|                    LAYER 3 — COGNITION                            |
|                                                                   |
|  Invocation Authority + finite non-renewable budget               |
|                       |                                           |
|                      CIE                                          |
|                       |                                           |
|        +--------------+---------------+                           |
|        |                              |                           |
|        v                              v                           |
|   PREDICTION                      CAUSALITY                        |
|   projection                      prospective studies             |
|   forecast commitment             closed replay                   |
|   FDA / FRR                       RCE / CRCI / RICTE               |
|        |                              |                           |
|        +---------------+--------------+                           |
|                        |                                          |
|                        v                                          |
|                    REASONING                                      |
|           inference license / composition                         |
|           constraint / contradiction                              |
|                        |                                          |
|             capability-free publication                          |
|                                                                   |
| Persistent cognitive state: NONE                                 |
+-----------------------|-------------------------------------------+
                        | read-only / internal cue authority 0
                        v
+-------------------------------------------------------------------+
|              LAYER 2 — MEMORY & RETRIEVAL                         |
|      bounded immutable reconstruction / association               |
|              Persistent cognitive state: NONE                     |
+-----------------------|-------------------------------------------+
                        | read-only
                        v
+-------------------------------------------------------------------+
|                   LAYER 1 — CORE v0.4                             |
|   Cells | Synapses | Assemblies | LLA | temporal context          |
|                         FROZEN                                    |
+-------------------------------------------------------------------+
```

---

# 126. Design Closure Record

The architecture consolidated by this document incorporates the completed Layer-3 design sequence:

```text
L3 Authority & State Foundation
  CognitiveInferenceEpoch
  Invocation authority
  environment binding
  finite non-renewable budget
  Core transition barrier
  transient state conservation

Prediction architecture
  projection vs forecast commitment
  trusted-only root anchoring
  source-specific targets
  prospective outcome capture
  forecast runtime state
  no-learning-feedback rule

Causality architecture
  prospective causal evidence substrate
  condition/outcome/case authority
  intervention/control/isolation separation
  observational/interventional semantic limits
  closed deterministic replay
  ReplayComparisonEpoch
  IdentificationBasisIdentity
  CanonicalReplayContrastIdentity
  RICTE semantics

Reasoning architecture
  explicit inference licenses
  formal assertion boundary
  scope/dependency/lineage model
  synchronous bounded rounds
  constraint/contradiction semantics
  active constraint authority
  ActiveEpistemicContext
  constraint completeness/clearance
  cross-context derived-support firewall

Final Layer-3 integration
  modal dependency conservation
  capability-free adapters
  no internal authority re-ingress
  ForecastDelegatedAuthority
  unified budget ownership
  invocation lifecycle linearization
  global barrier order
  owner-authority/budget orthogonality
  work effect commit semantics
  charge-exempt control-plane closure
```

The final integrated architecture re-audit concluded with:

```text
BLOCKER = 0
HIGH    = 0
```

for the architecture as designed before document consolidation.

The consolidated paper then underwent its own closure sequence:

```text
L3-PAR01 — Paper-Only Adversarial Review
  BLOCKER = 5
  HIGH    = 7
  VERDICT = REPAIR_REQUIRED

L3-PAR02 — Formal Specification Consolidation Repair
  restored omitted authority, causal, prediction, constraint, identity,
  budget-delegation, and charge-exemption contracts

L3-PAR03 — Final Paper-Only Closure Re-Audit
  BLOCKER = 0
  HIGH    = 0
  VERDICT = PASS
```

PAR03 also verified complete section numbering, balanced Markdown/code/LaTeX delimiters, absence of unresolved TODO/TBD/FIXME markers, and explicit closure of every PAR01 BLOCKER/HIGH finding.

Therefore:

\[
\boxed{
LAYER3\_FORMAL\_SPECIFICATION\_CLOSED
}
\]

This closure applies to the **formal design specification**. It does not mean production implementation, verification, or implementation freeze has occurred.

---

# 127. Formal Closure Invariants

Canonical Layer-3 invariants include the following.

## Authority / state

```text
L3-A01  One accepted InvocationCause cannot mint fresh authority/budget through transport retry.
L3-A02  InvocationAuthority is opaque, lifecycle-bound, and non-reopenable.
L3-A03  At most one CIE is active per invocation at a time.
L3-A04  CIE state is transient and nonresumable after closure.
L3-A05  Persistent cognitive state introduced by Layer 3 is empty.
L3-A06  Internal cognitive progress cannot manufacture external authority.
L3-A07  Historical result views never reconstruct live operational authority.
```

## Assertion / dependency / scope

```text
L3-S01  Claim content, assertion semantics, and source occurrence are distinct identities.
L3-S02  Basis is constructor-controlled, not caller-assigned.
L3-S03  Every generic inference conclusion has basis DERIVED.
L3-S04  Derived EDS is the union of parent EDS and cannot drop dependencies.
L3-S05  Modal origin is preserved through typed dependency roots.
L3-S06  Modal dependency roots are provenance, not capabilities.
L3-S07  Scope is explicit, typed, and cannot be generically broadened.
L3-S08  Natural-language content cannot mint formal reasoning authority.
L3-S09  Source-occurrence replay is idempotent and source multiplicity does not multiply semantic derivations.
L3-S10  Assertion bases are minted only by the exhaustive canonical constructor/ingress matrix.
```

## Prediction

```text
L3-P01  Projection != ForecastCommitment != Observation != Evaluation != Evidence.
L3-P02  Root-anchored forecasts require a trusted-only origin session.
L3-P03  Mixed/internal retrieval cannot be purified into trusted forecast origin.
L3-P04  Forecast targets remain source-specific.
L3-P05  Forecast evaluation consumes future trusted observation only through lawful capture.
L3-P06  MATCHED does not create a second observation or extra y=1.
L3-P07  Miss/nonmatch does not create y=0 or formal negation.
L3-P08  All Prediction v0 learning effect is empty.
L3-P09  Forecast continuation after invocation closure requires preissued FDA.
L3-P10  FDA cannot open CIEs, studies, or new forecasts.
L3-P11  Forecast target identity is guarded and may not be remapped after sealing.
L3-P12  Forecast evaluation identity is commitment+trusted-occurrence idempotent and its observation ledger is append-only.
```

## Causality

```text
L3-C01  ASSOCIATIVE relation != causal relation.
L3-C02  Causality requires prospective contrast.
L3-C03  Nonobservation != negation.
L3-C04  Trusted causal cases require study-bound external occurrence authority.
L3-C05  Intervention request != applied intervention.
L3-C06  Hypothetical reasoning != do(X).
L3-C07  Randomization, isolation, and treatment application are distinct authorities.
L3-C08  Closed replay identification requires a complete explicit identification basis.
L3-C09  CRCI identity includes replay origin and full identification basis.
L3-C10  Repeated same CRCI is verification, not independent evidence.
L3-C11  Deterministic same-CRCI disagreement is a contract violation.
L3-C12  RICTE is treatment-operation/replay-origin scoped and not a generic causal law.
L3-C13  Causal results do not create Core learning evidence.
L3-C14  Causal studies do not survive parent invocation closing in v0.
L3-C15  Causal stopping rules are prospectively frozen and outcome-independent; every planned slot is terminally reported.
L3-C16  Reuse of one trusted case occurrence never creates independent causal evidence; frozen comparator disjointness is enforced.
L3-C17  Replay environment currentness includes a monotonic revision token preventing ABA reuse.
L3-C18  Canonical causal-result issuance revalidates study, RCE, environment, bundle, and CRCI in one linearizable gate.
```

## Reasoning / composition

```text
L3-R01  Path existence != inference license.
L3-R02  InferenceSchema != FormalPremise.
L3-R03  Retrieved/derived content cannot create executable schemas.
L3-R04  Composition uses exact typed identities and explicit premise roles.
L3-R05  Transitivity requires explicit formal Transitive(R).
L3-R06  Derivation justification must be acyclic.
L3-R07  Same-round outputs are not same-round premises.
L3-R08  Completeness frontiers cannot be truncated according to budget.
L3-R09  Resource envelopes are declared before execution.
L3-R10  Ex-falso and unavailable logic families remain unavailable.
```

## Constraint / contradiction

```text
L3-K01  Different != Incompatible.
L3-K02  No detected conflict != compatibility.
L3-K03  Incompatibility requires an explicit frozen ConstraintSchema.
L3-K04  ConstraintSchema != ConstraintPremise.
L3-K05  ConstraintContent != ConstraintActivationAuthority.
L3-K06  Natural-language negation cannot mint FormalNegation.
L3-K07  Missing/unobserved/nonretrieved != negated.
L3-K08  Incompatibility != logical complement and is not transitively closed.
L3-K09  Detection != resolution; no winner/deletion/ranking is implied.
L3-K10  Constraint findings do not create evidence.
L3-K11  ActiveEpistemicContext is explicit and immutable per branch.
L3-K12  Constraint applicability is dependency-, scope-, environment-, and use-bound.
L3-K13  Absence of finding != complete constraint clearance.
L3-K14  Constraint clearance != compatibility claim.
L3-K15  Incomplete constraint check cannot authorize generic co-composition.
L3-K16  Derived support is constraint-context-bound and requires current-context lawful support.
L3-K17  Finding dependencies are exactly the union of participant assertion and active constraint-premise dependencies.
```

## Cross-capability / lifecycle / work

```text
L3-X01  Cross-capability cognitive views are capability-free.
L3-X02  Authority descriptors are not authority capabilities.
L3-X03  Cross-capability adapters cannot strengthen semantics.
L3-X04  Internal outputs cannot re-enter trusted ingresses without new external authority.
L3-X05  Same content does not create new authority.
L3-X06  All charged work has exactly one budget charge owner.
L3-X07  Budget charge never substitutes for live operational authority.
L3-X08  Owner closure and work authorization are linearly ordered.
L3-X09  Global barrier acquisition follows one frozen order.
L3-X10  Invocation closing never waits for children while holding lifecycle barrier.
L3-X11  Pure compute has no operational capability surface.
L3-X12  Operational effects commit only while owner authority is live.
L3-X13  Effect commits authorize exactly one immutable effect.
L3-X14  Transport retry cannot create a second logical effect.
L3-X15  Child authority creation cannot be deferred beyond parent closure.
L3-X16  Every operation is charged work or a frozen exempt control-plane operation.
L3-X17  Exempt control-plane work cannot create semantic output, positive authority, or external effect.
L3-X18  Consumed/retired/delegated budget cannot be transferred or reused.
L3-X19  Forecast budget delegation is a one-way atomic issuance to the forecast-owned pool, not a refundable owner transfer.
L3-X20  Charge-exempt operations are exactly the frozen canonical allowlist and cannot be extended by implementation.
```

---

# 128. Paper-Only Closure Record

The mandatory paper-only gate has been completed. The final re-audit verified all required closure properties:

1. every security-critical symbol/type used by the specification has one canonical meaning or an explicit typed binding;
2. the PAR01 consolidation omissions were restored without reopening Layer-1/Layer-2 semantics;
3. `SourceAssertionKey` replay is idempotent and source multiplicity cannot create Cartesian derivation multiplicity;
4. assertion basis minting and trusted observation ingress are constructor/capability controlled;
5. `AECIdentity`, `DerivationContextBinding`, constraint source/finding identities, and exact `EDS(F)` construction are defined;
6. prediction target guarding, append-only observation accounting, exact evaluation identity, and atomic sealing are defined;
7. causal stopping is outcome-independent, planned slots are fully reported, comparator occurrences obey frozen disjointness, and repeated occurrences are idempotent;
8. closed replay carries monotonic environment revision/currentness and canonical causal-result issuance is linearizable;
9. treatment identity, replay execution receipts, and CRCI discrimination are explicit;
10. forecast budget delegation is a one-way issuance transition and cannot be refunded/transferred;
11. generic v0 inference schema families and the charge-exempt operation allowlist are closed sets;
12. capability-free adapters, no-reingress, no-evidence-manufacturing, lifecycle, barrier-order, and persistent-state contracts remain intact;
13. acceptance/adversarial obligations include regression cases for every repaired paper defect.

Final paper-only verdict:

```text
L3_PAR03_FINAL_PAPER_ONLY_CLOSURE_REAUDIT_PASS
BLOCKER = 0
HIGH    = 0
```

No further architecture/specification repair is authorized without a new concrete finding.

---

# 129. Pre-Implementation Status

```text
Layer 3 architecture                                  CLOSED
Authority / transient-state architecture              CLOSED
Prediction architecture                               CLOSED
Causality architecture                                CLOSED
Reasoning: inference/composition                       CLOSED
Reasoning: constraint/contradiction                    CLOSED
Cross-capability authority/provenance integration      CLOSED
Invocation lifecycle / budget / effect model           CLOSED
Integrated architecture adversarial review             PASS (BLOCKER=0, HIGH=0)

Consolidated formal specification                      CLOSED
Paper-only adversarial review                          PASS (PAR01 -> PAR02 -> PAR03)
Canonical specification closure                        CLOSED
Codex comprehension                                    AUTHORIZED AS NEXT GATE
Production implementation                              NOT AUTHORIZED UNTIL COMPREHENSION ACCEPTED
Acceptance/adversarial verification                    PENDING
Independent repository review                          PENDING
Implementation freeze                                  PENDING
```

The correct current status is:

> **DGCA LITE Layer 3 Cognition v0.2 — FORMAL SPECIFICATION CLOSED, READY FOR CODEX COMPREHENSION / IMPLEMENTATION PLANNING.**

---

# Appendix A — Canonical Type Summary

```text
InvocationCauseID

InvocationAuthority
  cause binding
  runtime binding
  lifecycle revision
  ACTIVE | CLOSING | CLOSED

InvocationBudgetLedger
  general pool
  delegated forecast reservations
  causal study reservations
  consumed / retired state

CognitiveEnvironmentBinding (CEB)
  CoreStateBinding
  L2PolicyBinding
  L3PolicyBinding

CognitiveInferenceEpoch (CIE)
  invocation binding
  CEB
  CIEArena
  lifecycle
  current snapshot/round

ClaimContentID

AssertionSemanticKey (ASK)
  ClaimContentID
  AssertionBasis
  ScopeIdentity
  EpistemicDependencySet

SourceAssertionKey
ExternalOccurrenceCapability
TrustedObservationAdapter
CIEBinding
SnapshotBinding
AECIdentity
DerivationContextBinding

AssertionBasis
  FORMAL_GIVEN
  FORMAL_ASSUMPTION
  EXTERNAL_OBSERVATION
  INTERNAL_RETRIEVAL
  HYPOTHETICAL
  PREDICTION_VIEW
  CAUSAL_RESULT_VIEW
  DERIVED

DependencyRootIdentity
  DependencyKind
  OriginAuthorityBinding
  CanonicalOriginDescriptor

ModalDependencyRoot
  PredictionDependencyRoot
  CausalResultDependencyRoot
  InternalRetrievalDependencyRoot

ScopeIdentity
  ScopeKind
  ScopeAuthorityBinding
  CanonicalDescriptor

FAB-AST

ParentAssertionWitness
AcyclicSupportWitness
DerivationKey
DerivationLineage

ActiveEpistemicContext (AEC)

InferenceSchema
InferenceSchemaResourceEnvelope
InferenceWorkUnit
RoundStagingArena

ActiveConstraintSemanticRecord
ConstraintSemanticKey
ConstraintSourceKey
ConstraintEnvironmentBinding
ConstraintUseBinding
ConstraintCoverageLedger
IncompatibilityView
ConstraintClearanceView
ConstraintGateWitness

ConditionalProjection
ForecastCommitment
ForecastRuntimeRecord
TargetGuard
ForecastEvaluationID
ForecastDelegatedAuthority
PredictionOutcomeCognitiveView

CausalStudyPlan
CausalStudyAuthority
TreatmentDescriptor
CanonicalTreatmentPair
TrustedCaseOccurrence
AppliedInterventionReceipt
ProtocolControlReceipt
ClosedReplayDomainContract
ReplayEnvironmentBinding
EnvironmentRevisionToken
ReplayOrigin
ReplayComparisonEpoch
ReplayExecutionBundle
IdentificationBasisIdentity
CanonicalReplayContrastIdentity (CRCI)
ReplayIdentifiedTreatmentEffect (RICTE)
CausalResultCognitiveView

OperationContract
BudgetChargeBinding
WorkExecutionPermit
CanonicalEffectDescriptor
EffectCommitID
```

No type above is, by itself, persistent cognitive memory.

---

# Appendix B — Canonical Equation / Rule Summary

## Persistent-state conservation

\[
\boxed{
\Delta Core=0,\quad
\Delta Layer2=0,\quad
\Delta PersistentCognitiveState_{L3}=0
}
\]

## Assertion semantic identity

\[
\boxed{
ASK=(ContentID,Basis,ScopeIdentity,EDS)
}
\]

## Derived dependencies

\[
\boxed{
EDS(C)=\bigcup_{p\in Parents(C)}EDS(p)
}
\]

## Premise admissibility in a branch

\[
\boxed{
EDS(P)\subseteq AEC
}
\]

## Constraint applicability dependency condition

\[
\boxed{
EDS(F)\subseteq AEC_{use}
}
\]

together with required participant, scope, environment, profile, and use-binding checks.

## Constraint gate

\[
\boxed{
ConstraintGate(U)\in
\{
BLOCKED(F),\ CLEARED(CV),\ INCOMPLETE
\}
}
\]

Only `CLEARED` authorizes the exact bound generic co-composition.

## Constraint profile completeness

\[
\boxed{
RelevantConstraints(S)\subseteq PreflightProfile(S)
}
\]

## Forecast no-learning effect

\[
\boxed{
LearningEffect(PredictionOutcome)=\varnothing
}
\]

## CRCI

\[
\boxed{
CRCI=
(
Domain,
ReplayOrigin,
CanonicalTreatmentPair,
IdentificationBasisIdentity
)
}
\]

## Work execution

For charged work:

\[
\boxed{
Executable(W)
\iff
LiveAuthority(W)
\land
ExactlyOneValidCharge(W)
\land
CurrentEnvironment(W)
\land
ValidWorkClass(W)
}
\]

## Operational effect authority

\[
\boxed{
EffectCommitted(E)
\Rightarrow
OwnerWasLiveAtLinearization(E)
}
\]

## Budget nonrenewability

\[
\boxed{
CONSUMED\nrightarrow AVAILABLE,
\qquad
RETIRED\nrightarrow AVAILABLE
}
\]

---

# Appendix C — Layer Boundary Summary

```text
Layer 1 -> Layer 3
  allowed only through declared trusted/bounded integration paths
  no writable Core references in cognitive views

Layer 3 -> Layer 1
  forbidden: direct Cell/Synapse/Assembly mutation
  forbidden: automatic learning evidence
  forbidden: prediction/causal/constraint feedback as evidence

Layer 2 -> Layer 3
  allowed: immutable RetrievalResult and typed provenance
  allowed: trusted root information only through the defined trusted authority path
  forbidden: writable Layer-2/Core handles

Layer 3 -> Layer 2
  allowed: bounded internal retrieval requests with authority 0
  forbidden: caller-minted trusted flags/receipts
  forbidden: mutation of in-flight Layer-2 session

Prediction -> Reasoning
  allowed: capability-free typed prediction view
  forbidden: promotion to observation/formal conditional

Causality -> Reasoning
  allowed: capability-free typed causal result view
  forbidden: promotion to generic CAUSES/intervention authority

Reasoning -> Prediction/Causality
  allowed: typed internal claims/hypotheses where explicitly accepted
  forbidden: creating trusted forecast origin
  forbidden: creating TrustedCaseOccurrence
  forbidden: creating AppliedInterventionReceipt

Any internal Layer-3 output -> trusted/formal ingress
  forbidden without a genuinely new external occurrence capability
```

---

# Appendix D — Capability Plane vs Cognitive Plane

```text
COGNITIVE PLANE
  immutable assertions
  typed result views
  descriptors
  scopes
  dependency roots
  provenance IDs
  derivation witnesses

OPERATIONAL AUTHORITY PLANE
  InvocationAuthority
  trusted ingress capabilities
  FDA
  CausalStudyAuthority
  RCE authority
  intervention/control/isolation capabilities
  budget reservations
  publication/effect capabilities

RULE:
  Operational authority may produce validated cognitive data.
  Cognitive data cannot reconstruct operational authority.
```

\[
\boxed{
CognitiveData\not\rightarrow OperationalCapability
}
\]

except through a new independently authorized external/trusted issuance path.

---

# Appendix E — Deferred Capabilities

The following are explicitly deferred and must not be smuggled into Layer-3 v0 implementation:

```text
Analogy
Planning
Goal selection
Action selection
Rule induction
Quantified logic
Belief revision
Truth arbitration
Probabilistic confidence learning
Persistent hypothesis memory
Persistent causal graph
Autonomous long-running causal studies beyond Invocation lifetime
Prediction-to-learning credit assignment
Causal-result-to-learning credit assignment
Constraint-result-to-learning credit assignment
```

Each requires a future explicit architecture review.

---

**End of canonical DGCA LITE Layer-3 formal specification v0.2.**
