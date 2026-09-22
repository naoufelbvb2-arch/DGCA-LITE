# DGCA LITE — Layer 1: Core Architecture and Unified Learning Algorithm

**Canonical Implementation Specification — v0.4**  
**Status:** SPECIFICATION CLOSED · READY FOR CONFORMANCE REPAIR · BASELINE CODE EXISTS  
**Learning specification:** DGCA LITE Learning Algorithm (LLA v0)  
**Date:** 22 September 2026

---

## Abstract

DGCA LITE is a sparse, local-learning cognitive architecture designed to acquire structure continuously without backpropagation, global retraining, or semantic state embedded inside low-level computational units. Layer 1 defines the complete computational substrate on which all later memory, reasoning, prediction, generation, sensory, curriculum, and agent layers must operate.

The Core consists of a sparse three-dimensional logical network, minimal Cells, directed Synapses carrying strength and evidence mass, emergent overlapping Assemblies, a deterministic sparse-compositional surface interface, a temporal event stream, continuous local activation dynamics, and a unified learning algorithm (LLA v0). The design explicitly separates transient activation from persistent knowledge; separates relationship strength from confidence in that relationship; prevents internal recurrence from manufacturing evidence; prevents inactivity from causing forgetting; bounds recruitment and synaptic growth; expands structure rather than deleting consolidated knowledge under capacity pressure; and permits Assembly membership to emerge only from distributed, reciprocal, evidence-backed local structure.

This document is the canonical design contract for Layer 1. It is intended to be sufficient for implementation without reference to prior DGCA code, historical RFCs, or conversational design notes. Numerical thresholds remain calibration parameters unless explicitly fixed by an invariant. Layer 2 and above may consume Core interfaces but must not silently redefine Core semantics.

---

## 1. Purpose and Scope

Layer 1 answers one question: **what is the smallest complete substrate on which DGCA LITE can receive structured experience, activate locally, learn continuously, form distributed representations, preserve consolidated knowledge, and remain capable of future expansion?**

The Core contains:

- a sparse 3D logical network;
- `Cell`;
- `Synapse`;
- `Assembly`;
- continuous activation dynamics;
- deterministic sparse-compositional Surface Events;
- temporal ordering `T1 -> T2 -> ... -> Tn`;
- hard episode boundaries;
- DGCA LITE Learning Algorithm (LLA v0);
- resource competition, structural expansion, and reclamation;
- deterministic tick/commit semantics.

The Core **does not** contain episodic recall, pattern completion, pattern separation, explicit predictive cognition, causal inference, generation policy, semantic tokenization, dense embeddings, learned encoders, agent logic, goals, planning, or task-specific reward machinery. Those belong to later layers.

### 1.1 Layer discipline

A higher layer may use Core state and Core operations. It may not repair a higher-layer problem by silently changing Cell, Synapse, Assembly, evidence, or LLA semantics. A proven Core defect requires an explicit Core revision and full downstream regression.

---

## 2. Design Principles

### 2.1 Sparse by construction

Sparsity applies simultaneously to storage, activation, learning, and connectivity. The system must not merely store a sparse graph while activating or scanning it densely.

### 2.2 Local learning

Persistent change must be attributable to local state, local neighbors, lawful external evidence, and bounded temporal context. No Core operation may require a full-network optimization pass.

### 2.3 Cells are computationally dumb

A Cell contains no concept, word, image, label, confidence, memory identifier, prediction, reward, or semantic type. Knowledge is expressed by distributed structure and directed relationships.

### 2.4 Knowledge lives primarily in Synapses and distributed structure

A Synapse stores the learned state of a directed relationship. An Assembly records the membership boundary of an already-emerged stable local structure; it does not own semantic knowledge separate from its members and Synapses.

### 2.5 Activity is not knowledge

Activation is transient. Persistent knowledge is not erased because activation returns to zero.

### 2.6 Inactivity is not forgetting

Consolidated knowledge does not decay merely because time passes or it is unused.

### 2.7 Repetition strengthens; novelty recruits

Repeated familiar experience should mainly update existing structure. Recruitment is driven by residual novelty and capacity requirements, not by repetition count alone.

### 2.8 Internal activity is not independent evidence

Recall, recurrence, pattern completion, generation, or repeated callbacks caused by one external root event may not manufacture new independent evidence for the relationship that caused them.

### 2.9 Direction is learned, not assumed symmetric

`A -> B` and `B -> A` are independent Synapses with independent strength and evidence. Bidirectional accessibility, when learned, is represented by two directed edges.

### 2.10 Structural expansion is preferred over destructive forgetting

When a location is saturated with consolidated knowledge, lawful novelty recruits additional local structure rather than deleting stable knowledge simply to create room.

---

## 3. Layer 1 Architecture Overview

```text
Sparse compositional Surface Event
              |
              v
        T1 -> T2 -> T3 -> ...
              |
              v
        External sparse drive
              |
              v
      Continuous Cell activation
              |
              v
      Directed Synaptic propagation
              |
              v
        Evidence-backed learning
              |
              v
          Assemblies emerge
              |
              v
      Stable distributed substrate
```

The persistent Core may be summarized as:

```text
NETWORK
  |
  +-- CELL
  |
  +-- SYNAPSE
  |
  +-- ASSEMBLY
  |
  +-- LLA v0
```

The language interface provides Surface Events to the network but contains no semantic model.

---

## 4. Network

### 4.1 Initial logical capacity

The initial design target is:

```text
N = 1,000,000 logical Cells
```

This is a capacity target, not a requirement to instantiate one million heavyweight runtime objects. Uncommitted capacity may be represented implicitly or compactly.

### 4.2 Territories

The logical network contains three organizational territories:

```text
LANGUAGE
AUDIO
VISION
```

Territory is an organizational prior, not a semantic Cell type. Layer 1 implementation and early training focus exclusively on `LANGUAGE`. `AUDIO` and `VISION` must remain structurally addressable and architecturally pluggable, but no current Core behavior may depend on their implementation.

### 4.3 3D position and locality

Each Cell has a deterministic logical position:

```text
P(i) = (x_i, y_i, z_i)
```

`P(i)` may be derived from `id`; it need not be redundantly stored. Position must have computational meaning through locality, recruitment, connection eligibility, and resource-bounded neighborhood search.

Define a locality predicate:

\[
L_{ij} = \mathbf{1}[d(P(i),P(j)) \le r_s]
\]

where `r_s` is the locality radius applicable to the relevant Synapse scope. The exact metric and radius are implementation/calibration parameters, but every local operation must have a finite bound.

### 4.4 No global scan invariant

No standard learning, recruitment, Assembly, or propagation operation may scan all `N` Cells or all Synapses. Diagnostics may perform global scans offline; runtime cognition may not.

---

## 5. Cell

### 5.1 Canonical state

```text
CELL
|
+-- id
+-- territory
+-- committed
+-- activation
+-- synaptic_budget
```

No other persistent cognitive field is permitted in Core v0 without a Core revision.

### 5.2 Field semantics

- `id`: stable logical identity.
- `territory`: organizational territory.
- `committed`: whether the Cell currently participates in persistent learned structure.
- `activation`: transient scalar activity.
- `synaptic_budget`: bound on persistent outgoing structural relationships.

### 5.3 Conceptual states

The following are derived interpretations, not stored enums:

```text
UNCOMMITTED: committed = false, activation ~= 0
DORMANT:     committed = true,  activation ~= 0
ACTIVE:      activation >= theta_active
```

### 5.4 Activation domain and sparse frontiers

\[
A_i(t)\in[0,1]
\]

Core distinguishes numerical activation, learning activity, and emission. They are governed by global calibration thresholds:

\[
\boxed{0<\theta_{active}\le\theta_{emit}\le1}
\]

After next activation is computed, define the learning-active frontier:

\[
\boxed{\mathcal L_t=\{i\mid committed(i)=true\land A_i^+(t)\ge\theta_{active}\}}
\]

Only Cells in `L_t` may generate current-event evidence, become current temporal targets, or be retained as historical learning sources. Sub-threshold numerical activation has no evidence authority.

Propagation uses the emission frontier from the frozen pre-tick snapshot:

\[
\boxed{\mathcal E_t=\{i\mid committed(i)=true\land A_i(t)\ge\theta_{emit}\}}
\]

Only Cells in `E_t` emit through Synapses during the activation calculation. Runtime implementations must maintain sparse frontiers rather than enumerate all committed Cells.

### 5.5 Cell lifecycle

```text
receive
  -> integrate
  -> activate
  -> emit
  -> adapt locally
  -> recover
```

The Cell itself does not decide what its activation means.

---

## 6. Continuous Activation Dynamics

### 6.1 Effective scoped Synaptic quality

For each scoped directed Synapse `i -> j` with scope `s`:

\[
C_{ij}^{s}=\frac{E_{ij}^{s}}{E_{max}}
\]

\[
\boxed{Q_{ij}^{s}=S_{ij}^{s}C_{ij}^{s}}
\]

If several scoped Synapses exist for the same ordered Cell pair, activation combines them once:

\[
\boxed{Q_{ij}^{eff}=1-\prod_{s\in Scopes(i,j)}(1-Q_{ij}^{s})}
\]

`C`, `Q^s`, and `Q_eff` are derived values and are not persistent cognitive fields.

### 6.2 Local drive integration

Let `X_j(t) in [0,1]` be external input drive to Cell `j` at tick `t`. Let `N_j^-` contain only eligible incoming sources in the frozen emission frontier. Define:

\[
D_j(t)=1-(1-X_j(t))\prod_{i\in N_j^-}\left(1-A_i(t)Q_{ij}\right)
\]

Properties:

- `D_j(t)` remains in `[0,1]`;
- multiple weak inputs can accumulate;
- no single summation can explode without bound;
- a high raw `S` with very low `E` produces weak propagation through low `Q`.

### 6.3 Activation update

\[
\boxed{
A_j(t+1)=\operatorname{clip}\left((1-\delta_A)A_j(t)+\gamma_A D_j(t),0,1\right)
}
\]

where `delta_A` is recovery/decay of transient activation and `gamma_A` is drive gain. These are calibration parameters.

### 6.4 Sparse emission

Only Cells satisfying the runtime active/emission criterion participate in outgoing propagation. This criterion must be global or structurally derived; it must not add semantic state to Cell.

### 6.5 Snapshot rule

All activation for tick `t+1` is computed from a frozen snapshot of tick `t`. In-place asynchronous updates that make results depend on iteration order are forbidden.

---

## 7. Synapse

### 7.1 Canonical state

```text
SYNAPSE
|
+-- target_id
+-- strength
+-- evidence_mass
+-- state
+-- scope
```

When stored in the source Cell's adjacency structure, `source_id` is implicit and must not be duplicated unless required by storage tooling.

### 7.2 Strength

\[
S_{ij} \in [0,1]
\]

`S` estimates the current degree to which the directed relation is supported by adjudicated evidence.

### 7.3 Evidence mass

\[
E_{ij} \in [0,E_{max}]
\]

`E` is **accumulated adjudicated evidence mass**, not a raw repetition count. It measures how much lawful information has participated in the estimate represented by `S`, regardless of whether that evidence supported or opposed the relation.

### 7.4 State

```text
CANDIDATE
CONSOLIDATED
```

`CANDIDATE` represents tentative learned structure. `CONSOLIDATED` represents evidence-backed persistent structure. Consolidation is not an irreversible lock.

### 7.5 Scope and canonical Synapse identity

Core v0 uses one directed Synapse primitive with three scopes:

```text
LOCAL
ASSOCIATIVE
CROSS_TERRITORY
```

Scope is immutable for the lifetime of a Synapse. Canonical identity is:

\[
\boxed{(source,target,scope)}
\]

Different scopes may therefore coexist between the same ordered pair and each consumes one outgoing budget slot.

Creation scope is determined by lawful relation class:

- intra-event, same-territory structural evidence (`Delta = 0`) -> `LOCAL`;
- temporal past-to-current, same-territory evidence (`1 <= Delta <= H`) -> `ASSOCIATIVE`;
- different-territory evidence, when future modalities are enabled -> `CROSS_TERRITORY`.

Root evidence deduplication uses `(root,source,target,scope)`.

Self-Synapses are forbidden for every scope:

\[
\boxed{source\ne target}
\]

Schema validation and proposal generation must reject `i = j`.

### 7.6 Directionality

A bidirectionally accessible relation is represented as:

```text
A -> B : S_AB, E_AB
B -> A : S_BA, E_BA
```

The two directions may differ arbitrarily according to experience.

---

## 8. Assembly

### 8.1 Canonical state

```text
ASSEMBLY
|
+-- id
+-- territory
+-- members
```

The Assembly stores no semantic label, strength, evidence, confidence, salience, prediction, reward, or activation history.

### 8.2 Definition

An Assembly is a persistent record of a local set of Cells whose `LOCAL` Synapses have become sufficiently distributed, reciprocal, connected, and evidence-backed that the set behaves as a stable distributed structural unit.

An Assembly is **not** a container holding a concept. A label such as `APPLE` may exist in debugging or analysis only.

### 8.3 Overlap

A Cell may belong to more than one Assembly, subject to bounded resource/membership constraints. Overlap enables compositional reuse and prevents a one-concept-per-Cell architecture.

### 8.4 Reciprocal structural quality

Assembly membership may use only reciprocal, CONSOLIDATED `LOCAL` Synapses:

\[
\boxed{
R_{ij}^{L}=\begin{cases}
\min(Q_{ij}^{LOCAL},Q_{ji}^{LOCAL}), & \text{if both LOCAL edges exist and are CONSOLIDATED}\\
0, & \text{otherwise}
\end{cases}}
\]

Candidate Synapses never establish Assembly membership.

### 8.5 FORM and bounded candidate discovery

Assembly work is triggered from **derived reciprocal-support changes**, not from a global Assembly scan.

For an unordered same-territory Cell pair `{u,v}`, let `R_pre^L(u,v)` be reciprocal LOCAL structural quality in the immutable pre-tick snapshot and `R_post^L(u,v)` the value in the deterministic post-learning/post-resource Synaptic overlay. Define the changed-LOCAL-support set:

\[
\boxed{\Delta_L=\{\{u,v\}\mid R_{pre}^{L}(u,v)\ne R_{post}^{L}(u,v)\}}
\]

The comparison is performed only for Cell pairs touched by lawful LOCAL Synaptic proposals, lifecycle transitions, creation, pruning, or other bounded local changes in the current transaction. Computing `Delta_L` must not require scanning untouched Synapses.

FORM seeds are endpoints of pairs in `Delta_L` whose post-overlay relation qualifies:

\[
R_{post}^{L}(u,v)\ge\theta_A
\]

From each unique seed Cell, perform deterministic same-territory BFS over the **post-overlay** qualifying reciprocal LOCAL graph using ascending Cell IDs.

A candidate `G` must satisfy:

\[
K_{min}\le|G|\le K_{max}
\]

and spatial diameter:

\[
\operatorname{diameter}(G)\le r_A
\]

The frontier is fail-closed. Before adding a qualifying neighbor `v`, evaluate `G' = G union {v}`. If `|G'| > K_max` or `diameter(G') > r_A`, reject the entire FORM proposal for that seed. Do not truncate, partition, skip the node, or search for a fitting subset.

Define:

\[
deg_G(i)=\sum_{j\in G,j\ne i}\mathbf1[R_{ij}^{L}\ge\theta_A]
\]

\[
CoreCoverage(G)=\frac{\sum_{i\in G}\mathbf1[deg_G(i)\ge d_{min}]}{|G|}
\]

`EvidenceConnected(G)` means that the qualifying reciprocal LOCAL graph induced by `G` is connected. `Local(G)` means one territory and diameter no greater than `r_A`. `ResourceValid(G)` requires valid size, no duplicate member set, every Cell below membership bound `M_max`, and all local resource limits satisfied.

\[
\boxed{
\begin{aligned}
FormAssembly(G)=&\;Local(G)\land EvidenceConnected(G)\\
&\land CoreCoverage(G)\ge\rho\land ResourceValid(G)
\end{aligned}
}
\]

For deterministic FORM arbitration, define cohesion for every candidate with `|G| >= 2`:

\[
\boxed{
Cohesion(G)=
\frac{
\sum_{\{u,v\}\subseteq G,\;u<v}R_{uv}^{L}
}{
\binom{|G|}{2}
}
}
\]

If `|G| < 2`, `Cohesion(G)=0` and the candidate is invalid for FORM. Missing, Candidate, one-directional, non-LOCAL, non-CONSOLIDATED, or otherwise nonqualifying pairs contribute `R^L=0`; they remain in the denominator. No epsilon is used because a valid FORM candidate has at least two members.

Duplicate candidate member sets generated from different seeds are deduplicated before arbitration.

### 8.6 GROW and specificity

For Cell `x` and Assembly `A`:

\[
\boxed{D(x,A)=\frac{\sum_{j\in A}\mathbf1[R_{xj}^{L}\ge\theta_A]}{|A|}}
\]

Reliable reciprocal ASSOCIATIVE support is:

\[
R_{xk}^{A}=\begin{cases}
\min(Q_{xk}^{ASSOCIATIVE},Q_{kx}^{ASSOCIATIVE}), & \text{if both ASSOCIATIVE edges are CONSOLIDATED}\\
0, & \text{otherwise}
\end{cases}
\]

Combine reliable same-territory spread after reciprocity is computed separately per scope:

\[
\boxed{U_{xk}=1-(1-R_{xk}^{L})(1-R_{xk}^{A})}
\]

Then:

\[
\boxed{Spec(x,A)=\frac{\sum_{j\in A}R_{xj}^{L}}{\sum_{k\in\mathcal N_{spec}(x)}U_{xk}+\varepsilon}}
\]

`CROSS_TERRITORY` and Candidate edges are excluded from specificity. Growth requires same territory, diameter of `A union {x}` no greater than `r_A`, valid resources, and:

\[
\boxed{D(x,A)\ge\rho_G\land Spec(x,A)\ge\sigma_G}
\]

For GROW arbitration define the exact transient mean reciprocal LOCAL support:

\[
\boxed{MeanR(x,A)=\frac{\sum_{j\in A}R_{xj}^{L}}{|A|}}
\]

Every member of `A` remains in the denominator. Missing or nonqualifying LOCAL reciprocal support contributes zero. No epsilon is used because a valid pre-existing Assembly has at least one member. `MeanR` is transient arbitration information only and is never stored in the Assembly.

#### 8.6.1 Canonical bounded GROW candidate workset

GROW candidates are derived only from `Delta_L`; Core never scans all non-members or all Assemblies.

For every changed pair `{u,v} in Delta_L` satisfying:

\[
R_{post}^{L}(u,v)\ge\theta_A
\]

construct candidates as follows:

- for every pre-existing Assembly `A` in the bounded membership index of `u`, if `v notin A`, propose `(A,v)`;
- for every pre-existing Assembly `A` in the bounded membership index of `v`, if `u notin A`, propose `(A,u)`.

No other Assembly is considered because of that changed pair. In particular, Core does not search nearby Assemblies that contain neither endpoint.

Candidate identity is:

```text
(assembly_id, candidate_cell_id)
```

Duplicate identities produced by several changed pairs are deduplicated before scoring. The enumeration order before metric ranking is stable: changed pairs ordered by `(min_cell_id, max_cell_id)`, then Assembly ID ascending, then candidate Cell ID ascending.

Because each Cell has bounded Assembly membership `M_max` and `Delta_L` is generated only by bounded local Synaptic changes, GROW discovery remains locally bounded.

### 8.7 MAINTAIN and structural arbitration

Maintenance is event-driven; inactivity alone never removes membership. Use hysteresis:

\[
\rho_G>\rho_{keep},\qquad \sigma_G>\sigma_{keep}
\]

A member remains iff:

\[
D(x,A)\ge\rho_{keep}\land Spec(x,A)\ge\sigma_{keep}
\]

#### 8.7.1 Canonical affected-Assembly workset

MAINTAIN never scans every Assembly.

Let `R_pre^A(u,v)` and `R_post^A(u,v)` be reciprocal CONSOLIDATED ASSOCIATIVE support before and after the current Synaptic/resource transaction overlay. Define:

\[
\boxed{
\Delta_S=
\{\{u,v\}\mid
R_{pre}^{L}(u,v)\ne R_{post}^{L}(u,v)
\;\lor\;
R_{pre}^{A}(u,v)\ne R_{post}^{A}(u,v)
\}
}
\]

As with `Delta_L`, this set is computed only from bounded pairs touched by current LOCAL/ASSOCIATIVE evidence updates, lifecycle transitions, creation, pruning, or other lawful local structural changes.

The initial MAINTAIN workset is exactly:

\[
\boxed{
\mathcal A_{maint}=
\bigcup_{\{u,v\}\in\Delta_S}
\left(Memberships(u)\cup Memberships(v)\right)
}
\]

where `Memberships(x)` is the bounded Assembly-membership index for Cell `x` in the pre-GROW/pre-FORM overlay. Duplicate Assembly IDs are removed and the workset is processed in ascending Assembly ID.

This trigger is sufficient because `D` can change only through reciprocal LOCAL support and `Spec` can change through reciprocal LOCAL or ASSOCIATIVE support. Candidate-only changes that leave both derived reciprocal supports unchanged do not trigger MAINTAIN.

#### 8.7.2 Canonical exact-member-set collision arbitration

MAINTAIN may lawfully cause two distinct pre-existing Assemblies to collapse to the same final member set. Exact duplicate member sets are forbidden, so the collision must be resolved before GROW begins.

For every surviving MAINTAIN outcome `A -> G`, perform an exact-set lookup against:

- all other surviving MAINTAIN outcomes in the current bounded workset; and
- the exact-member-set Assembly index for any pre-existing Assembly outside the MAINTAIN workset whose member set already equals `G`.

This is an exact-index operation only; it must not scan all Assemblies.

For every collision group sharing the same final member set `G`, define the canonical survivor:

\[
\boxed{A_{survive}=\min\{assembly\_id\mid members(A)=G\}}
\]

All other Assembly records in that exact-set collision group are deleted in the same structural transaction. Their Synapses are untouched. Membership indexes are updated to reference only the surviving Assembly ID.

This operation is **administrative exact-duplicate elimination**, not `MERGE`: it performs no union of distinct member sets, no averaging or transfer of Synaptic state, and creates no new Assembly identity. Assembly IDs carry no cognitive score or semantic authority; the minimum-ID rule exists only to make duplicate elimination deterministic.

Collision resolution occurs after MAINTAIN fixed points are computed and before GROW metrics/resource counts are frozen. Therefore GROW sees the deduplicated post-MAINTAIN membership overlay.

For GROW, `ResourceValid(x,A)` additionally requires that the proposed exact set `members(A) union {x}` is not already the member set of another surviving Assembly. If it is, that GROW proposal is rejected; GROW never deletes or replaces another Assembly identity to resolve an exact-set collision. FORM retains its existing duplicate-set rejection/deduplication rules.

Assembly structural processing is canonical:

```text
MAINTAIN -> GROW -> FORM
```

**MAINTAIN:** process only Assemblies in `A_maint`. For each affected pre-existing Assembly, remove all failing members simultaneously for a maintenance round, recompute on the reduced member set, and repeat to a bounded local fixed point. Membership removals inside that Assembly are part of the same local fixed point and therefore require no global rescan. If size falls below `K_min` or remaining qualifying LOCAL structure is disconnected, remove the Assembly record but not its Synapses.

**GROW:** only surviving pre-existing Assemblies may grow, and only canonical `(A,x)` candidates from Section 8.6.1 are evaluated. Metrics are computed from the stable post-MAINTAIN overlay before any GROW admission. Valid proposals are ranked by descending `D`, descending `Spec`, descending `MeanR`, then ascending Assembly ID and Cell ID. Resource predicates are rechecked against the evolving membership overlay; `D`, `Spec`, and `MeanR` are not recomputed because of same-tick admissions.

**FORM:** discover only from the canonical changed qualifying LOCAL seeds in Section 8.5. Rank valid proposals by descending `CoreCoverage`, descending `Cohesion`, then lexicographic canonical member IDs. Missing/nonqualifying member pairs contribute zero to `Cohesion` but remain in its denominator. Recheck resource validity before each acceptance. Assembly IDs are assigned at commit by lexicographic final member set.

Newly formed Assemblies cannot GROW in the same tick. GROW/FORM admissions do not recursively trigger additional same-tick GROW/FORM searches. GROW or FORM admissions also do not cause a second MAINTAIN pass during the same tick.

### 8.8 No MERGE/SPLIT in v0

`MERGE` and `SPLIT` are deliberately excluded from Core v0. They may be added only if experiments demonstrate a structural failure that FORM, GROW, MAINTAIN, association, and overlap cannot solve.

---

## 9. Sparse Compositional Surface Representation

### 9.1 Surface Event, not semantic token

The temporal input unit is a **Surface Event**. For English prose this is commonly a word-like span, punctuation mark, number, symbol, newline, or other mechanically segmented surface unit.

The event is not a token ID and carries no semantic embedding.

```text
Surface Event
    -> deterministic decomposition
    -> sparse compositional signature
    -> external drive in LANGUAGE territory
```

### 9.2 Requirements

A Surface representation must be deterministic, sparse, compositional, non-semantic, open-vocabulary, order-bearing, and reconstructable. Surface features are mechanical interface objects, not Cells, and never own Synapses.

### 9.3 Reversible backbone

For an event, exact surface bytes are encoded with an unambiguous mechanical order-bearing backbone, for example positional UTF-8 byte features:

```text
byte(value, position)
```

plus explicit boundaries/chunk metadata. The exact coding may vary only if exact round-trip is preserved within documented event-length bounds. Long events use deterministic reversible continuation/chunking; silent truncation is forbidden.

### 9.4 Overlap features and Mechanical Entry Projection

Additional deterministic character/byte n-grams or local fragments may provide surface overlap. They carry no semantics and may never compromise reconstructability.

Each mechanical feature `f` deterministically projects to a bounded ordered set of logical LANGUAGE receptor Cell IDs:

\[
\boxed{\Pi(f)=\{j_1,\ldots,j_m\}}
\]

`Pi` is deterministic, stateless, non-semantic, bounded, and independent of learned state. For event feature set `F_t`, define receptor pool:

\[
\boxed{P_t=\bigcup_{f\in F_t}\Pi(f)}
\]

and receptor external drive:

\[
\boxed{X_u^{entry}=1-\prod_{f\in F_t,\,u\in\Pi(f)}(1-X_f)}
\]

Uncommitted receptors may be inspected for recruitment but do not propagate, emit evidence, or participate in Assemblies. Once committed, the same mechanical projection can drive them on later matching/overlapping Surface Events.

### 9.5 Unknown words

There is no `UNK` token. A previously unseen event remains representable because its surface components remain representable.

### 9.6 Numbers, code, and symbols

The same mechanism applies to:

```text
527
x = x + 1
C++
foo_bar
[3, 7]
<=
\n
indentation/whitespace events where the domain requires them
```

No separate numeric RFC or programming-language vocabulary is required at the Core level.

### 9.7 Multilinguality

Core representation is Unicode/UTF-8 surface-based and therefore not restricted to English. Early training focuses on English, but no semantic encoder specific to English is permitted inside Core. Languages may require different mechanical segmentation policies at the interface; they must not require different learning semantics.

---

## 10. Temporal Stream and Episode Boundaries

### 10.1 Temporal ordering

Surface Events are presented sequentially:

```text
T1 -> T2 -> T3 -> ... -> Tn
```

There are no positional embeddings in Core. Order is represented by actual temporal succession and learned directed relationships.

### 10.2 Temporal kernel

For temporal distance `Delta`:

\[
\kappa(\Delta)=
\begin{cases}
 e^{-\alpha\Delta}, & 0\le\Delta\le H \\
 0, & \Delta>H
\end{cases}
\]

`H` is the bounded temporal learning horizon. Core v0.4 requires:

\[
\boxed{H\ge1}
\]

This lower bound is architectural rather than semantic: at least one bounded temporal record must exist so newly recruited mechanically addressable Cells can remain locally accountable until their provenance either receives structure or expires through the canonical context-eviction workset in Section 16.3. Setting `H=0` is therefore invalid in Core v0.4.

### 10.3 Hard boundary and root lifecycle

A `HARD_BOUNDARY` denotes that the next Surface Event is not temporally continuous with the preceding stream. Before processing the new event, Core must finalize the prior root, clear bounded temporal context and evidence ledger, and set activation of the materialized active frontier to zero. Persistent Cells, Synapses, evidence, states, and Assemblies are unchanged.

Across a HARD_BOUNDARY:

\[
\boxed{\kappa(\Delta)=0}
\]

and no activation, contextual novelty signal, or temporal evidence may leak across the boundary. Punctuation is not automatically a hard boundary.

Core creates exactly one external evidence root for each accepted Surface Event. The root is open only for that event's deterministic tick, then finalized at atomic commit; its deduplication ledger may then be discarded. Historical learning-active activations retained in bounded context do not keep old roots open. Internal/recalled/generated activity has `O_r = 0` for independent evidence and finalized roots cannot reopen.

## 11. DGCA LITE Learning Algorithm — LLA v0

LLA v0 is the complete Core learning lifecycle:

```text
RECRUIT
  -> CONNECT
  -> LEARN
  -> CONSOLIDATE / COMPETE
```

Assembly FORM/GROW/MAINTAIN consumes the resulting Synaptic structure; it is not a separate semantic learning engine.

---

## 12. RECRUIT — Novelty-Driven Structural Allocation

### 12.1 Receptor-level surface familiarity

Mechanical features do not participate in Synaptic equations. Let:

\[
W_t=\sum_{u\in P_t}X_u^{entry}
\]

If `W_t = 0`, set `M_s = 0`; otherwise:

\[
\boxed{M_s=\frac{\sum_{u\in P_t}X_u^{entry}\mathbf1[committed(u)]}{W_t}}
\]

Define committed reuse receptors:

\[
R_t=\{u\in P_t\mid committed(u)=true\land X_u^{entry}>0\}
\]

with `r_u = X_u^{entry}`.

### 12.2 Context compatibility

If no lawful prior temporal context exists, set:

\[
\boxed{M_c=1}
\]

If `R_t` is empty, define `M_s=0`, `M_c=1`, and therefore `nu=1`.

Otherwise, contextual compatibility uses only directed `ASSOCIATIVE` Synapses from historical learning-active Cells into current committed receptors:

\[
\boxed{c_u=1-\prod_{(i,\Delta)\in\mathcal C_t}(1-A_i^{hist}Q_{iu}^{ASSOCIATIVE}\kappa(\Delta))}
\]

Both Candidate and Consolidated ASSOCIATIVE edges contribute according to evidence-weighted quality. Then:

\[
\boxed{M_c=\frac{\sum_{u\in R_t}r_uc_u}{\sum_{u\in R_t}r_u}}
\]

### 12.3 Context-aware novelty

\[
\boxed{\nu_t=1-M_sM_c}
\]

This makes new surface high-novelty, familiar surface in familiar context low-novelty, and familiar surface in incompatible context contextually novel.

### 12.4 Ordinary recruitment

\[
K_{ordinary}^{request}=\begin{cases}
0,&\nu_t<\theta_R\\
\min(K_R,\lceil K_R\nu_t\rceil),&\nu_t\ge\theta_R
\end{cases}
\]

Ordinary recruitment may choose only uncommitted Cells in `P_t`, ranked by descending `X_u^{entry}` then ascending Cell ID. At commit, selected Cells become `committed=true, activation=0`. They do not participate in evidence, propagation, CONNECT, or Assembly operations during their recruitment tick; later matching Surface Events can mechanically drive them.

### 12.5 Shared event recruitment ceiling

Ordinary recruitment and structural expansion share one strict per-event ceiling:

\[
\boxed{K_{ordinary}+K_{expansion}\le K_R}
\]

Ordinary recruitment has first priority. Expansion uses only remaining capacity. Unique newly committed Cells, not proposal attempts, count toward the ceiling.

## 13. CONNECT — Exhaustive Bounded Evidence Proposal and Candidate Creation

### 13.1 Evidence-eligible frontier

Only committed Cells in the current learning-active frontier `L_t` may be current evidence sources/targets. Temporal context stores only historical `L_t` members and their committed `A^+` values.

### 13.2 Exhaustive LOCAL proposal enumeration

For every current source `i in L_t`, enumerate every `j in N_LOCAL(i) intersect L_t`, excluding `i=j`. Generate exactly one ordered `LOCAL` proposal `i -> j`. If both directions are eligible, both are generated independently. No hidden Top-K, sampling, winner selection, or budget-aware suppression is permitted before evidence discovery.

For the current root:

\[
\boxed{q_{ij}^{LOCAL}=O_rD_{ij}^{(r)}A_i^+(t)A_j^+(t)}
\]

### 13.3 Exhaustive temporal ASSOCIATIVE enumeration

For each historical event within `1 <= Delta <= H`, every historical learning-active source `i` enumerates every current target `j in N_ASSOC(i) intersect L_t`, excluding `i=j`. Direction is strictly past-to-current:

\[
\boxed{q_{ij}^{ASSOCIATIVE}=O_rD_{ij}^{(r)}A_i^{hist}A_j^+(t)\kappa(\Delta)}
\]

No reverse current-to-past edge is inferred automatically.

### 13.4 Root-level aggregation and conflict

Evidence identity is `(root,source,target,scope)`. For proposals with the same adjudicated `y`, aggregate using:

\[
\boxed{q^*=\max(q_1,\ldots,q_n)}
\]

Never sum path multiplicity. If the same identity contains both `y=1` and `y=0` within one root, mark a transient relation-level conflict and contribute:

\[
\boxed{\Delta S=0,\quad\Delta E=0}
\]

The conflicted key is consumed for the root; the whole event need not abort.

### 13.5 Creation eligibility

An absent scoped Synapse may be created only from lawful positive evidence:

\[
q\ge\theta_{create},\qquad y=1
\]

Negative evidence cannot create an absent relation. New-edge proposals remain provisional until resource arbitration and are admitted as `CANDIDATE` only. A newly recruited Cell is never an endpoint of same-tick CONNECT.

## 14. LEARN — Evidence-Weighted Relationship Update

### 14.1 Evidence target

Core v0 uses adjudicated binary targets:

\[
\boxed{y\in\{0,1\}}
\]

`y=1` is positive support; `y=0` is explicit lawful contrary evidence. Non-observation is not negative evidence.

### 14.2 Update

For an existing Synapse with current strength `S`, evidence mass `E`, new lawful mass `q`, and target `y`:

\[
\lambda=\frac{q}{E+q}
\]

\[
\boxed{S'=S+\lambda(y-S)=\frac{ES+qy}{E+q}}
\]

\[
\boxed{E'=\min(E_{max},E+q)}
\]

If `q=0`, no update occurs. `E_max` is bounded effective adjudicated evidence mass, not a lifetime observation count. Even when `E=E_max`, later lawful evidence continues to modify `S`; incoming `q` is not clipped to zero.

### 14.3 New Synapse initialization

An admitted new positive edge begins:

\[
\boxed{S_{new}=1,\qquad E_{new}=\min(q,E_{max})}
\]

with state `CANDIDATE`. One root cannot create and consolidate the same Synapse.

### 14.4 Evidence is not callback count

One external root contributes at most once per scoped directed identity after aggregation/adjudication. Internal recurrence, recall, future pattern completion, generation, or repeated callbacks from that root do not multiply evidence.

## 15. CONSOLIDATE — Persistent Evidence-Backed Structure

### 15.1 Existing-edge lifecycle ordering

Evidence updates are first computed for Synapses that existed at tick start. Then provisional lifecycle transitions are evaluated before resource pruning.

An existing `CANDIDATE` becomes `CONSOLIDATED` iff:

\[
\boxed{S'\ge\theta_S\land E'/E_{max}\ge\theta_E\land SynapseResourceValid(i,j,s)}
\]

An existing `CONSOLIDATED` edge demotes to `CANDIDATE` after lawful evidence iff:

\[
\boxed{S'<\theta_{demote}},\qquad \theta_{demote}<\theta_S
\]

A Candidate that consolidates becomes protected before pruning. A newly demoted Candidate may be prune-eligible in the same tick under explicit pressure.

### 15.2 SynapseResourceValid

For an existing `(i,j,s)`, resource validity requires committed endpoints, `i != j`, unique scoped identity, finite bounded `S/E`, valid territory/scope and scope-specific spatial eligibility, a lawful existing budget slot, outgoing degree no greater than `B_i`, and no Core invariant violation. Consolidation consumes no new slot.

### 15.3 Creation tick is not consolidation tick

A newly admitted edge remains `CANDIDATE` for the entire creation tick even if its initial `S/E` exceed consolidation thresholds. The earliest consolidation can occur is after lawful evidence from a later independent external root.

### 15.4 No time decay

Core contains no persistent strength, evidence, state, or membership decay rule driven solely by elapsed time or inactivity.

## 16. COMPETE — Resource-Bounded Structural Maintenance

### 16.1 Budget and deterministic new-edge arbitration

For source Cell `i`:

\[
\boxed{degree^+_{persistent}(i)\le B_i}
\]

Existing edge updates consume no new slot. For absent positive proposal `p=(i,j,s,q)`, define:

\[
\boxed{Q_{new}(p)=\frac{\min(q,E_{max})}{E_{max}}}
\]

For one source, sort new proposals by descending `Q_new`, descending `q`, ascending target ID, then canonical scope order `LOCAL < ASSOCIATIVE < CROSS_TERRITORY`.

If a free slot exists, admit. Otherwise consider only existing `CANDIDATE` edges with `Q < theta_prune`; select the minimum `Q` with stable edge-key tie-breaking. Replace only if `Q_new` is strictly greater. Equal quality preserves the existing edge. A same-tick newly admitted edge is not prune-eligible in that batch. `CONSOLIDATED` edges are never deleted merely to admit novelty.

### 16.2 Structural expansion

A blocked creation proposal may trigger expansion only when its `q >= theta_create`, required outgoing capacity is saturated, no lawful Candidate replacement exists, stable occupying structure is protected, and `nu >= theta_R`.

Expansion commits mechanically addressable uncommitted receptor Cells from the relevant current/historical Surface representation reserve. It never picks arbitrary unreachable nearby Cells. The blocked relation remains rejected for the current root; extension Cells inherit no edge, evidence, Assembly membership, or semantic identity.

Ordinary and expansion recruitment share `K_R`. After ordinary allocation, let:

\[
\boxed{K_{remain}=K_R-K_{ordinary}}
\]

Every canonical blocked-relation expansion request `e` has its own maximum allocation bound:

\[
\boxed{
K_{expand}^{max}(e)=
\min\left(
K_R,
\left\lceil K_R\nu_t\right\rceil,
|Reserve(e)|
\right)
}
\]

The bound is evaluated once from the current event's canonical novelty `nu_t` and that request's deterministic eligible uncommitted receptor reserve. It does not depend on source-processing order. If the request has no eligible reserve, its bound is zero.

Expansion requests are ranked by descending blocked `q`, ascending source ID, target ID, and canonical scope order. Allocation then proceeds in deterministic rounds. In each round every ranked request may receive at most one still-unreserved receptor Cell, chosen from its own reserve by the canonical receptor-reserve ranking. A request remains eligible in later rounds only while:

- its allocated count is strictly below `K_expand^max(e)`;
- its reserve still contains an eligible uncommitted unreserved Cell;
- the shared event capacity `K_remain` is nonzero.

Rounds stop when `K_remain = 0`, every request has reached its per-request bound, or every remaining reserve is exhausted. Thus, for example, with `K_remain=4`, two requests each having bound at least two and sufficient disjoint reserves receive `2+2` under round-robin arbitration; if each request's bound is one, allocation stops at `1+1` and unused event capacity remains unused.

Overlapping receptor candidates can be reserved only once in the transaction overlay. If an earlier-ranked request reserves a Cell preferred by a later request, the later request considers its next eligible reserve Cell. The blocked relation itself remains rejected for the current root; expansion creates future capacity, not current-root knowledge.

### 16.3 Orphan reclamation

Orphan reclamation is **event-driven and locally triggered**. Core v0.4 does not scan all committed Cells and does not maintain an unbounded orphan scheduler.

#### 16.3.1 Prospective post-commit temporal context

Before orphan evaluation, the engine constructs the deterministic **prospective post-commit temporal context** that would exist if the current tick commits successfully:

1. start from the frozen pre-tick bounded context;
2. if a `HARD_BOUNDARY` is requested, mark all pre-boundary records for eviction;
3. include the current event's mechanical Surface provenance and committed learning-active `A+` values;
4. apply the bounded horizon `H`, identifying any oldest records that would be evicted by the successful append.

These changes are staged only; the live temporal stream is not mutated until the whole tick commits.

A temporal record references both:

- its stored historical learning-active Cell IDs; and
- the receptor Cell IDs contained in its stored mechanical receptor provenance required for later deterministic expansion/re-addressing.

Let `T_pre` be the Cell IDs referenced by the frozen pre-tick temporal context and `T_post` the IDs referenced by the prospective post-commit context. Define temporal-expiration candidates:

\[
\boxed{W_{expire}=T_{pre}\setminus T_{post}}
\]

Because at most `H` bounded temporal records are inspected, this operation is local with respect to temporal context and never scans the Network.

#### 16.3.2 Canonical orphan review workset

Let:

- `W_edge` be endpoints of Synapses deleted/pruned in the current resource transaction;
- `W_assembly` be Cells removed from Assembly membership by MAINTAIN or by deletion of an Assembly record;
- `W_expire` be the temporal-expiration set above.

The exact orphan review workset is:

\[
\boxed{W_{orphan}=W_{edge}\cup W_{assembly}\cup W_{expire}}
\]

Duplicate Cell IDs are removed and evaluation order is ascending Cell ID. No other committed Cell is inspected for reclamation in that tick.

Current ordinary/expansion allocations remain transaction reservations and cannot be reclaimed during the same tick. To prevent a reservation from becoming permanently unreachable after commit, any expansion receptor chosen from historical provenance must come from a provenance record that survives into the prospective post-commit temporal context. Ordinary recruitment from the current Surface Event is referenced by the current event record because `H >= 1`.

#### 16.3.3 Reclamation predicate

A committed Cell `i in W_orphan` is reclaimable only in the final post-resource/post-Assembly/post-context overlay when all are true:

- no incident CONSOLIDATED Synapse survives;
- no incident CANDIDATE Synapse survives;
- no Assembly membership survives;
- no current transaction reference remains;
- `i notin T_post`;
- no current ordinary/expansion reservation targets `i`;
- post-tick numeric activation is below `theta_active`.

For activation, use the deterministic post-tick activation overlay: `A_i^+` where computed; otherwise the Cell's unchanged canonical activation. Exact floating zero is not required.

At atomic commit reclamation sets:

```text
committed = false
activation = 0
```

Its logical ID and deterministic position remain reusable. Reclamation is caused only by lawful structural/provenance changes; elapsed time by itself never weakens or deletes knowledge.

The context-eviction trigger closes the tentative-capacity lifecycle: a recruited Cell that never acquires Synaptic or Assembly support is revisited when the last bounded Surface provenance that protects it expires.

## 17. Assembly Operations Under LLA

Assembly operations consume the deterministic post-learning/post-resource Synaptic overlay. Structural order is fixed:

```text
MAINTAIN -> GROW -> FORM
```

Only reciprocal CONSOLIDATED `LOCAL` edges qualify for membership structure. `ASSOCIATIVE` edges affect specificity only as reliable external spread; `CROSS_TERRITORY` never establishes membership.

The bounded discovery, arbitration, hysteresis, fail-closed `K_max/r_A` frontier behavior, fixed-point MAINTAIN, deterministic GROW ranking, deterministic FORM ranking, and no-same-tick structural recursion rules in Section 8 are normative.

## 18. Deterministic Tick and Commit Semantics

One external Surface Event is processed in the following canonical order:

```text
1. Accept external event and create one-tick external root.
2. Apply HARD_BOUNDARY transient reset when requested.
3. Encode mechanical Surface features, reversible signature, receptor pool, and sparse drive.
4. Freeze Network state, activation, indexes, Assemblies, and lawful temporal context.
5. Compute receptor familiarity M_s, context compatibility M_c, and novelty nu.
6. Compute local drive from frozen emission frontier and scoped Q_eff.
7. Compute A+(t) without live-state mutation and derive learning-active frontier L_t.
8. Exhaustively collect bounded LOCAL and temporal ASSOCIATIVE evidence proposals.
9. Aggregate duplicate identities with max(q); adjudicate y conflicts; apply root deduplication.
10. Compute S'/E' for existing Synapses.
11. Apply provisional lifecycle transitions to existing Synapses.
12. Build absent-edge proposals and resolve per-source budget arbitration/pruning.
13. Allocate ordinary recruitment and remaining shared expansion recruitment.
14. Build deterministic post-learning/resource transaction overlay.
15. MAINTAIN pre-existing Assemblies to bounded local fixed point, then resolve exact-member-set MAINTAIN collisions.
16. GROW surviving pre-existing Assemblies using frozen growth metrics and evolving resource checks.
17. FORM new Assemblies by bounded deterministic BFS and arbitration.
18. Construct the prospective post-commit temporal context and canonical `W_orphan`; evaluate lawful reclamation on the final structural/context overlay.
19. Validate the complete Network + temporal transaction and all invariants.
20. Atomically publish persistent Network changes and the staged temporal/root state as one successful tick.
21. Finalize the external root and discard its ledger.
22. Advance to the next external event.
```

Newly recruited Cells are administrative recruitment records only during their recruitment tick and are excluded from evidence, CONNECT, propagation, and Assembly processing until a later external event.

All next activation calculations use the pre-tick snapshot. Later structural stages may consume immutable transaction overlays from earlier stages but may never observe a partially mutated live graph. Temporal/root mutations are part of the same transactional authority: a failed tick must leave Network state, temporal context, root-allocation state, and boundary state exactly as they were before the event was accepted.

### 18.1 Determinism

All equal-score choices use canonical stable ordering. Persistent mutations are proposed first, validated as one transaction, and committed atomically. Same initial state, configuration, events, roots, and boundaries must yield identical canonical state.

## 19. Derived Values and Stored-State Discipline

The following are derived and should not normally be persisted as cognitive state:

```text
C_ij          evidence confidence fraction
Q_ij          effective Synaptic quality
R_ij          reciprocal Assembly structural quality
novelty nu    event-level recruitment signal
CoreCoverage  Assembly formation statistic
D(x,A)        distributed membership integration
Spec(x,A)     structural specificity
```

Persisting caches for performance is permitted only if they are exact invalidatable caches with no independent cognitive authority.

---

## 20. Core Invariants

The reference implementation must enforce at least the following invariants.

### I-01 — Cell semantic purity

No Cell contains semantic labels or concept-specific learned state.

### I-02 — Synaptic ownership of learned relation state

Persistent directed relationship learning is expressed through Synapse state, not duplicated in Assembly or Agent state.

### I-03 — Bounded activation

\[
0\le A_i\le1
\]

for every Cell and tick.

### I-04 — Bounded strength and evidence

\[
0\le S_{ij}\le1
\]

\[
0\le E_{ij}\le E_{max}
\]

### I-05 — Evidence provenance

Internally generated recurrence cannot create independent external evidence.

### I-06 — Root deduplication

A single external root cannot inflate one relation through repeated callbacks.

### I-07 — Hard-boundary isolation

No temporal learning crosses a hard boundary.

### I-08 — No inactivity forgetting

No consolidated relationship or Assembly membership is weakened solely because it was unused.

### I-09 — Local runtime authority

Core learning and structural mutation operate on bounded neighborhoods only.

### I-10 — Resource boundedness

Recruitment, outgoing persistent Synapses, active propagation, and Assembly operations are bounded.

### I-11 — Structural expansion before consolidated destruction

Stable knowledge is not deleted solely to admit new novelty when unused local capacity can be recruited.

### I-12 — LOCAL-only Assembly structure

`ASSOCIATIVE` and `CROSS_TERRITORY` Synapses cannot directly satisfy Assembly membership criteria.

### I-13 — Directional independence

Updating `i -> j` does not implicitly update `j -> i`.

### I-14 — Deterministic reference semantics

Given identical initial state, inputs, hard boundaries, parameters, and evidence provenance, the reference implementation produces identical persistent results.

### I-15 — Surface interface non-semanticity

Surface representation contains no semantic dictionary, learned embedding, task label, or concept lookup.

### I-16 — Surface reconstructability

Within documented event bounds, the reversible backbone can reconstruct the original Surface Event exactly.

### I-17 — No persistent cognitive cache authority

Any optimization cache must be derivable from canonical state and must not influence semantics when stale or absent.

---

## 21. Forbidden Behaviors

The following are explicitly prohibited in Layer 1:

```text
x backpropagation
x dense semantic embeddings
x BPE/WordPiece-style semantic token IDs as the Core representation
x fixed semantic vocabulary
x UNK semantic token
x learned semantic state inside the encoder
x semantic labels inside Cell or Assembly
x global network scans in normal learning/runtime cognition
x time-based decay of consolidated knowledge
x internal recall/generation manufacturing evidence
x callback duplication manufacturing evidence
x unbounded Cell recruitment
x unbounded Synaptic fan-out
x automatic symmetric edge updates
x deleting consolidated knowledge merely to admit novelty
x using ASSOCIATIVE/CROSS_TERRITORY edges as Assembly membership proof
x hidden reasoning or learning authority in the Agent layer
x future-layer prediction logic inside Core
x in-place tick updates whose results depend on iteration order
```

---

## 22. Parameter Surface

The mathematical structure is frozen; numerical calibration is not. The following are representative experimental parameters:

```text
activation:
  delta_A, gamma_A, theta_active/theta_emit

locality / timing:
  r_s, alpha, H

recruitment:
  theta_R, K_R

connection / learning:
  theta_create, E_max

consolidation:
  theta_S, theta_E, theta_demote

competition:
  theta_prune

assembly:
  theta_A, K_min, K_max, d_min, rho,
  rho_G, sigma_G, rho_keep, sigma_keep

surface interface:
  maximum event length / continuation rule,
  overlap-feature families and sparse fan-out
```

Calibration may change these values without constituting a Core architecture change, provided all invariants remain satisfied.

---

## 23. Complexity and Resource Expectations

### 23.1 Logical Cells versus instantiated state

One million logical Cells do not imply one million heavyweight runtime objects. Uncommitted Cells may be implicit. Persistent memory should scale primarily with committed Cells, Synapses, and Assembly membership.

### 23.2 Expected dominant memory cost

Synapses are expected to dominate persistent memory. This is why `synaptic_budget`, candidate competition, sparse locality, and expansion discipline are Core requirements.

### 23.3 Runtime work

Normal tick cost should scale with:

```text
active Cells
+ eligible local incoming/outgoing Synapses
+ bounded local proposal neighborhoods
```

not with total network capacity.

### 23.4 Scale independence

Cell, Synapse, Assembly, and LLA semantics must not depend on `N = 1,000,000`. Future scaling to larger networks should change capacity and engineering strategy, not the meaning of the primitives.

---

## 24. Failure Modes the Core Must Prevent

### F-01 — Representation explosion

Repeated familiar inputs continually recruit new Cells.

**Required prevention:** novelty-driven bounded recruitment and reuse.

### F-02 — Semantic encoder leakage

Meaning is precomputed in the Surface interface.

**Required prevention:** mechanical, non-semantic sparse composition only.

### F-03 — Decoder irreversibility

The input signature loses exact surface order and cannot be reconstructed.

**Required prevention:** reversible backbone plus order-bearing features.

### F-04 — Callback evidence inflation

One external event triggers recurrent loops that increase Evidence repeatedly.

**Required prevention:** root dedup and origin gates.

### F-05 — False cross-sample learning

Adjacent unrelated samples create temporal Synapses.

**Required prevention:** HARD_BOUNDARY.

### F-06 — Catastrophic inactivity forgetting

Stable knowledge disappears because it is old or dormant.

**Required prevention:** no time-based persistent decay.

### F-07 — Plasticity saturation

A Cell with only consolidated outgoing edges can never participate in new learning.

**Required prevention:** bounded structural expansion.

### F-08 — Giant semantic blob

Strong associations cause Assemblies to absorb related but independent concepts.

**Required prevention:** distributed reciprocal specificity and LOCAL-only membership evidence.

### F-09 — One-sense surface trap

A familiar spelling can never recruit structure for a new contextual sense.

**Required prevention:** context-aware novelty.

### F-10 — Orphan capacity leak

Failed tentative learning permanently consumes Cells.

**Required prevention:** orphan reclamation.

### F-11 — Update-order nondeterminism

Different iteration order produces different learned state.

**Required prevention:** frozen snapshots and atomic commit semantics.

### F-12 — Negative-evidence abuse

Failure to mention a relation is interpreted as evidence that it is false.

**Required prevention:** only explicit lawful negative evidence may use `y=0`.

---

## 25. Acceptance and Verification Specification

Implementation of Layer 1 is not considered complete because unit tests merely execute. It must demonstrate architectural and behavioral acceptance.

### 25.1 Surface representation tests

The suite must prove:

- identical Surface Events yield identical sparse signatures;
- small surface changes yield controlled overlap rather than unrelated IDs;
- unknown events are representable without vocabulary mutation;
- bounded events reconstruct exactly from the reversible backbone;
- order changes are distinguishable;
- numbers, punctuation, operators, identifiers, and code-like strings are representable;
- Unicode/UTF-8 events do not require semantic language-specific vocabularies.

### 25.2 Temporal tests

The suite must prove:

- `A -> B` temporal evidence is distinguishable from `B -> A`;
- learning respects the bounded temporal horizon;
- no temporal learning crosses `HARD_BOUNDARY`;
- independent samples remain isolated.

### 25.3 Activation tests

The suite must prove:

- activation always remains within `[0,1]`;
- inactive Cells recover toward zero;
- low-evidence high-strength Synapses have low effective propagation through `Q`;
- multiple supported inputs can combine without numerical explosion;
- tick results are invariant to iteration order.

### 25.4 Evidence tests

The suite must prove:

- one lawful root can contribute at most once per relation;
- internal recurrence contributes zero independent evidence;
- `S` follows the evidence-weighted update equation;
- `E` saturates at `E_max`;
- high-evidence relations resist isolated contrary evidence but remain correctable by repeated lawful contrary evidence;
- absence alone never creates negative evidence.

### 25.5 Recruitment tests

The suite must prove:

- unfamiliar patterns recruit bounded local Cells;
- familiar repeated patterns converge toward reuse;
- contextual mismatch can create novelty for a familiar surface form;
- recruitment never exceeds per-event limits;
- deterministic tie-breaking produces repeatable selection.

### 25.6 Consolidation and forgetting tests

The suite must prove:

- weak one-shot candidates do not become authoritative merely because `S` is initially high;
- supported repeated relations consolidate;
- consolidated relations survive long inactivity unchanged;
- actual contrary evidence can demote a relation through hysteresis;
- candidate pruning occurs only under lawful competition/resource conditions.

### 25.7 Capacity tests

The suite must prove:

- synaptic budgets are never exceeded;
- weak unsupported candidates can free capacity;
- saturated consolidated structure triggers bounded expansion instead of destructive deletion;
- extension Cells receive no automatic semantic privilege;
- orphan Cells are reclaimable without deleting supported knowledge.

### 25.8 Assembly tests

The suite must prove:

- sparse accidental co-activation does not FORM an Assembly;
- connected distributed reciprocal evidence can FORM one;
- one strong edge does not establish membership;
- strong association can remain outside an Assembly;
- GROW requires distributed reciprocal specificity;
- members may overlap across Assemblies within configured bounds;
- `ASSOCIATIVE` and `CROSS_TERRITORY` edges cannot directly satisfy membership;
- lawful structural weakening can remove membership through MAINTAIN;
- inactivity alone cannot remove membership.

### 25.9 Architecture tests

The suite must include static or runtime checks that detect:

- semantic fields added to Cell/Assembly;
- global scans in normal Core paths;
- hidden time-decay of persistent knowledge;
- automatic reverse-edge mutation;
- unauthorized persistent caches with cognitive authority;
- future-layer reasoning logic imported into Core.

---

## 26. Reference Implementation Contract for Codex

An implementation agent receiving this document must treat it as authoritative.

### 26.1 MAY

The implementation MAY:

- choose clean modules and internal data structures;
- represent uncommitted capacity implicitly;
- use exact derivable caches for performance;
- batch mathematically equivalent operations;
- implement deterministic indexing structures for local neighborhoods;
- add diagnostics, instrumentation, property tests, and serialization;
- expose calibration parameters through configuration.

### 26.2 MUST

The implementation MUST:

- preserve all equations and invariants semantically;
- preserve sparse/local runtime behavior;
- implement evidence provenance/root dedup;
- implement hard boundaries;
- keep persistent primitives minimal;
- implement deterministic snapshot/commit semantics;
- separate canonical state from derived/cached state;
- test all acceptance categories in Section 25.

### 26.3 MUST NOT

The implementation MUST NOT:

- add a semantic embedding layer;
- add global reasoning or global learning authority;
- add hidden semantic fields to Cells, Synapses, or Assemblies;
- add time-based persistent decay;
- implement future Memory/Cognition/Generation behavior as a shortcut;
- weaken resource bounds;
- replace evidence semantics with raw callback counts;
- silently alter equations to improve benchmark performance;
- implement MERGE/SPLIT without an explicit Core revision.

### 26.4 Pre-code comprehension gate

Before writing production code, the implementation agent should return:

1. its module decomposition;
2. canonical state structures;
3. the exact equations it will implement;
4. invariant enforcement points;
5. deterministic tick/commit plan;
6. test matrix mapped to Section 25;
7. any ambiguity it believes remains.

Production implementation should begin only after that interpretation is reviewed.

---

## 27. Interfaces to Future Layers

### 27.1 Layer 2 — Memory & Retrieval

May consume:

- Cell activation;
- `Q`-weighted Synaptic propagation;
- Assembly membership;
- directed local/associative structure.

Must not redefine LLA evidence or persistent Core primitives.

### 27.2 Layer 3 — Cognition

May provide explicit lawful negative evidence only through a documented evidence interface, for example after a properly defined prediction failure. It may not treat mere non-occurrence as negative evidence.

### 27.3 Layer 4 — Generation

May use reversible surface structure to map learned language activity back toward Surface Events. Generated/internal activity cannot self-certify as external evidence.

### 27.4 Layer 5 — Encoders

Future Audio/Vision encoders must produce sparse drives compatible with the same Core. They may not change Cell/Synapse/Assembly semantics.

### 27.5 Layer 6 — Curriculum

Controls what experiences are presented and in what sequence. It does not redefine how LLA learns.

### 27.6 Layer 7 — Agent/UX

Must remain a thin interface. It may route input/output and coordinate user interaction, but may not become a parallel memory or reasoning engine.

---

## 28. Design Lineage and Deliberate Departures from Original DGCA

DGCA LITE inherits mechanisms that proved valuable in the original DGCA project—local relationship creation, repetition-sensitive strengthening, consolidation, episode isolation, local assemblies, bounded structure, and directional/predictive recurrence concepts—while deliberately refusing to reproduce the accumulated document and law complexity of the earlier architecture.

Key departures include:

```text
Original-style multiple learning laws
  -> one Unified Learning Algorithm (LLA v0)

raw word-like semantic handling
  -> sparse compositional reconstructable Surface Events

persistent knowledge decay through inactivity
  -> evidence/resource competition only

locked knowledge state
  -> evidence-weighted stability with lawful reversibility

separate assembly confirmation counters
  -> Synaptic evidence itself establishes structural eligibility

head-position asymmetry rules
  -> direction learned from temporal evidence

future-layer fixes inside Core
  -> strict layer ownership
```

The goal is not to discard the evidence accumulated by DGCA, but to preserve validated mechanisms while removing architectural debt.

---

## 29. Pre-Implementation Closure Status

At publication of this specification:

```text
Architecture                  COMPLETE
Cell                          COMPLETE
Activation dynamics           COMPLETE
Synapse                       COMPLETE
Evidence semantics            COMPLETE
Assembly FORM/GROW/MAINTAIN   COMPLETE
Surface representation        COMPLETE
Temporal stream/boundaries    COMPLETE
LLA v0 mathematics            COMPLETE
Resource mechanics            COMPLETE
Deterministic tick semantics  COMPLETE
Adversarial final review      COMPLETE

Production implementation     BASELINE v0.3 EXISTS
Conformance repair to v0.4   PENDING
Acceptance verification       PENDING
Repository review             PENDING
Final Layer-1 freeze          PENDING
```

Therefore the correct status is:

> **DGCA LITE Layer 1 Core v0.4 — SPECIFICATION CLOSED, READY FOR CONFORMANCE REPAIR.**

The Layer becomes fully `FROZEN` only after implementation, acceptance verification, repository architecture review, and an exact implementation commit are appended to the closure manifest.

---

## Appendix A — Canonical Primitive Summary

```text
CELL
  id
  territory
  committed
  activation
  synaptic_budget

SYNAPSE
  target_id
  strength
  evidence_mass
  state = CANDIDATE | CONSOLIDATED
  scope = LOCAL | ASSOCIATIVE | CROSS_TERRITORY

ASSEMBLY
  id
  territory
  members
```

---

## Appendix B — Canonical Equation Summary

### Scoped evidence-weighted Synaptic quality

\[
C_{ij}^{s}=E_{ij}^{s}/E_{max},\qquad Q_{ij}^{s}=S_{ij}^{s}C_{ij}^{s}
\]

\[
Q_{ij}^{eff}=1-\prod_s(1-Q_{ij}^{s})
\]

### Cell drive and activation

\[
D_j(t)=1-(1-X_j(t))\prod_{i\in\mathcal E_t}(1-A_i(t)Q_{ij}^{eff})
\]

\[
A_j(t+1)=clip((1-\delta_A)A_j(t)+\gamma_AD_j(t),0,1)
\]

### Learning and emission frontiers

\[
\mathcal L_t=\{i: committed(i)\land A_i^+(t)\ge\theta_{active}\}
\]

\[
\mathcal E_t=\{i: committed(i)\land A_i(t)\ge\theta_{emit}\}
\]

### Mechanical receptor projection

\[
P_t=\bigcup_{f\in F_t}\Pi(f)
\]

\[
X_u^{entry}=1-\prod_{f:u\in\Pi(f)}(1-X_f)
\]

### Surface familiarity and context

\[
M_s=\frac{\sum_{u\in P_t}X_u^{entry}\mathbf1[committed(u)]}{\sum_{u\in P_t}X_u^{entry}}
\]

with `M_s=0` when denominator is zero.

\[
c_u=1-\prod_{(i,\Delta)\in\mathcal C_t}(1-A_i^{hist}Q_{iu}^{ASSOCIATIVE}\kappa(\Delta))
\]

\[
M_c=\frac{\sum_{u\in R_t}X_u^{entry}c_u}{\sum_{u\in R_t}X_u^{entry}}
\]

with `M_c=1` when no lawful prior context exists.

\[
\nu_t=1-M_sM_c
\]

### Temporal kernel

\[
\kappa(\Delta)=\begin{cases}e^{-\alpha\Delta},&0\le\Delta\le H\\0,&\Delta>H\end{cases}
\]

A HARD_BOUNDARY overrides temporal continuity and yields zero cross-boundary contribution.

### Lawful evidence

\[
q_{ij}^{LOCAL}=O_rD_{ij}^{(r)}A_i^+A_j^+
\]

\[
q_{ij}^{ASSOCIATIVE}=O_rD_{ij}^{(r)}A_i^{hist}A_j^+\kappa(\Delta)
\]

Duplicates for one `(root,source,target,scope,y)` use `q* = max(q_k)`. Conflicting `y` within one root contributes zero evidence for that identity.

### Evidence-weighted learning

\[
\lambda=\frac{q}{E+q}
\]

\[
S'=S+\lambda(y-S)
\]

\[
E'=\min(E_{max},E+q)
\]

### Recruitment

\[
K_{ordinary}^{request}=0\;\text{if}\;\nu<\theta_R;\quad
K_{ordinary}^{request}=\min(K_R,\lceil K_R\nu\rceil)\;\text{otherwise}
\]

\[
K_{ordinary}+K_{expansion}\le K_R
\]

For each expansion request `e`:

\[
K_{expand}^{max}(e)=\min\left(K_R,\lceil K_R\nu_t\rceil,|Reserve(e)|\right)
\]

### Reciprocal Assembly structure

\[
R_{ij}^{L}=\min(Q_{ij}^{LOCAL},Q_{ji}^{LOCAL})
\]

only when both LOCAL edges are CONSOLIDATED; otherwise zero.

\[
D(x,A)=\frac{\sum_{j\in A}\mathbf1[R_{xj}^{L}\ge\theta_A]}{|A|}
\]

\[
U_{xk}=1-(1-R_{xk}^{L})(1-R_{xk}^{A})
\]

\[
Spec(x,A)=\frac{\sum_{j\in A}R_{xj}^{L}}{\sum_{k\in\mathcal N_{spec}(x)}U_{xk}+\varepsilon}
\]

\[
MeanR(x,A)=\frac{\sum_{j\in A}R_{xj}^{L}}{|A|}
\]

\[
Cohesion(G)=\frac{\sum_{\{u,v\}\subseteq G,\;u<v}R_{uv}^{L}}{\binom{|G|}{2}}
\]

Missing or nonqualifying reciprocal LOCAL pairs contribute zero to `MeanR`/`Cohesion` numerators while remaining represented by the fixed denominators defined in Section 8.

### Consolidation and demotion

Existing Candidate -> Consolidated when:

\[
S'\ge\theta_S\land E'/E_{max}\ge\theta_E\land SynapseResourceValid
\]

Existing Consolidated -> Candidate when:

\[
S'<\theta_{demote}
\]

A newly created Synapse remains Candidate throughout its creation tick.

## Appendix C — Layer 1 Closure Manifest

```yaml
Specification:
  DGCA LITE Layer 1 Core v0.4

Specification SHA-256:
  5324d423b341b1f17da1cc0c53e59cfb59c7724b0f9ed19b323fb4bee5e3b2b7

Implementation repository:
  https://github.com/naoufelbvb2-arch/DGCA-LITE.git

Reviewed implementation commit:
  beb10058b09f44e8a1ed737dca81db4d1091473e

Parent implementation commit:
  75d5e9eb8f10009d85762291eb9c593bd67c9bee

Package:
  dgca-lite 0.4.0

Reference configuration:
  CoreConfig defaults at reviewed implementation commit
  logical_capacity = 1,000,000
  Python >= 3.12

Test manifest:
  Full pytest: 91 passed
  Deterministic replay verification: 2 passed
  Ruff: All checks passed
  Distribution wheel: built successfully

Promoted verification:
  pytest: 91 passed in 10.83s
  deterministic replay: 2 passed in 1.27s
  wheel SHA-256:
  0b9464d526e9edf3d24e8d71bf4b02d889bdeab7d7506c4be8a1024730b4f727

Acceptance result:
  PASS

Architecture review:
  R01_INDEPENDENT_REVIEW_PASS
  No remaining architectural drift found
  No Layer 2+ functionality present

Known limitations:
  Numerical calibration parameters remain experimental as explicitly permitted by v0.4.
  Current production focus is LANGUAGE; Audio/Vision integration remains deferred.
  CROSS_TERRITORY learning origination is not enabled in Layer 1 language-only operation.
  Layer 2 Memory/Retrieval and all higher cognitive layers are intentionally absent.
  Verification is repository/local-test based; no GitHub CI status check is currently configured.
  Wheel archive SHA may vary between builds unless reproducible-build tooling is introduced; this does not alter canonical implementation state.

Final frozen specification version:
  DGCA LITE Layer 1 Core v0.4

Status:
  FROZEN
```

---

**End of Canonical Layer 1 Specification**
