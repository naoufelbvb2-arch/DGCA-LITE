# DGCA LITE — Layer 2: Memory & Retrieval

**Canonical Mathematical and Implementation Specification — v0.4**  
**Status:** SPECIFICATION CLOSED · READY FOR CODEX COMPREHENSION / IMPLEMENTATION  
**Dependency:** `01_CORE_v0.4.md` — Layer 1 Core, FROZEN  
**Layer-2 persistent cognitive state:** NONE

---

## Abstract

DGCA LITE Layer 2 defines memory retrieval as **transient reconstruction from the persistent distributed structure already stored by Layer 1**. It does not introduce a second memory database, an episodic record primitive, a learned retrieval model, a global ranking function, or persistent retrieval state.

The layer consumes a coherent, bounded, immutable materialization of Core state and performs five operations:

1. bounded source discovery;
2. lane-scoped pattern reconstruction;
3. root-witness pattern separation;
4. one-hop directed temporal-associative retrieval;
5. authority-free target reconstruction.

The governing principle is:

\[
\boxed{
\text{Core stores learned structure; Layer 2 reconstructs transient memory state from it.}
}
\]

A complete retrieval session is a deterministic, read-only transformation:

\[
\boxed{
\mathcal R(\Omega_R)\rightarrow R
}
\]

where \(\Omega_R\) is a frozen retrieval universe and \(R\) is an immutable transient `RetrievalResult`.

Layer 2 never creates learning evidence, never mutates Cells, Synapses, Assemblies, temporal learning context, recruitment state, or root ledgers, and never replays retrieved state through the Surface Event learning path.

---

# 1. Purpose and Scope

Layer 2 answers one question:

> Given a bounded cue and the persistent structure already learned by Core, what distributed structures can be lawfully reconstructed without changing Core state or manufacturing evidence?

Layer 2 contains:

- trusted/internal cue separation;
- coherent bounded snapshot acquisition;
- Assembly-source discovery;
- residual atomic sources for unassembled cue Cells;
- pattern reconstruction;
- pattern separation metadata;
- directed temporal-associative retrieval;
- target-branch reconstruction;
- retrieval provenance;
- canonical immutable result construction.

Layer 2 does **not** contain:

- persistent `MemoryObject` or `EpisodeObject` primitives;
- semantic tokenization or embeddings;
- learning or evidence updates;
- Assembly mutation;
- global graph search;
- Top-K retrieval ranking;
- a learned retrieval scorer;
- global confidence or ambiguity scalars;
- causal inference;
- semantic relation classification;
- planning or reasoning policy;
- language generation;
- exact episodic replay;
- exact historical lag reconstruction;
- reverse associative retrieval;
- `CROSS_TERRITORY` retrieval in v0.

---

# 2. Layer Discipline

Layer 2 depends on Layer 1 but may not redefine Layer-1 semantics.

Layer 1 remains the sole authority for:

- `Cell`;
- `Synapse`;
- `Assembly`;
- activation semantics;
- `LOCAL`, `ASSOCIATIVE`, and `CROSS_TERRITORY` scopes;
- Synaptic strength/evidence semantics;
- \(Q\)-quality;
- Assembly membership;
- temporal learning context;
- root/evidence authority;
- recruitment and resource mechanics.

A higher-layer retrieval defect must not be repaired by silently modifying Layer 1. A proven Layer-1 defect requires a formal Core revision.

Layer 2 is read-only with respect to Core:

\[
\boxed{\Delta Core=0}
\]

including:

\[
\Delta Cell=0,
\quad
\Delta Synapse=0,
\quad
\Delta Assembly=0,
\]

\[
\Delta TemporalLearningContext=0,
\quad
\Delta Recruitment=0,
\quad
\Delta RootLedger=0.
\]

---

# 3. Core Values Consumed by Layer 2

For a directed scoped Synapse `i -> j`, Layer 1 defines:

\[
C_{ij}^{s}=\frac{E_{ij}^{s}}{E_{max}}
\]

and:

\[
\boxed{Q_{ij}^{s}=S_{ij}^{s}C_{ij}^{s}}
\]

Layer 2 reads these derived values but does not persist independent copies with cognitive authority.

For reciprocal `LOCAL` structural support:

\[
\boxed{
R_{ij}^{L}=
\begin{cases}
\min(Q_{ij}^{LOCAL},Q_{ji}^{LOCAL}),
& \text{if both LOCAL directions exist and are CONSOLIDATED}\\
0, & \text{otherwise.}
\end{cases}
}
\]

Layer 2 does not redefine this relation.

For directed associative retrieval, only `CONSOLIDATED` `ASSOCIATIVE` Synapses participate.

---

# 4. Retrieval Parameters

Layer 2 introduces only the following principal calibration parameters:

\[
\boxed{K_C}
\]

maximum merged cue cardinality;

\[
\boxed{0<\theta_{PC}\le1}
\]

pattern-reconstruction admission threshold;

\[
\boxed{0<\theta_{AR}\le1}
\]

directed associative-entry threshold.

No architectural theorem requires an ordering between \(\theta_{PC}\), \(\theta_{AR}\), and Layer-1 \(\theta_A\).

Layer 2 also reads Layer-1 configuration values required by its mathematics, including at least:

\[
\theta_A,\ \theta_{active},\ K_{max},\ M_{max},\ E_{max}.
\]

These values are frozen per retrieval session inside \(\Theta_R\).

---

# 5. Entry Modes and Authority Boundary

Layer 2 exposes two conceptual entry modes.

## 5.1 Internal retrieval

\[
\boxed{RetrieveInternal(C_I^{raw})}
\]

This mode has no trusted external-root authority:

\[
\boxed{C_T=\varnothing}
\]

and therefore:

\[
\boxed{\mathcal A_0=\varnothing.}
\]

Layer 3 may use this mode for chained retrieval, but all supplied seeds remain internal.

## 5.2 Trusted post-Core-event retrieval

\[
\boxed{RetrieveAfterCoreEvent(\mathcal K_t,C_I^{raw})}
\]

where \(\mathcal K_t\) is a transient `TrustedRetrievalReceipt` created only by the trusted Core↔Layer-2 integration path immediately after a successful Core event commit.

The public retrieval caller must not be able to assign an `origin=CORE_ACTIVE` flag, manufacture a trusted receipt, or promote internal seeds into root-authorized witnesses.

---

# 6. TrustedRetrievalReceipt

The receipt is an **operational authority capability**, not persistent cognitive state.

Conceptually:

\[
\boxed{
\mathcal K_t=
(
CoreInstance,
postCommitVersion,
postCommitTick,
rootID,
\mathcal L_t,
A_t^+
)
}
\]

where:

- `CoreInstance` binds the receipt to one Core instance;
- `postCommitVersion` and `postCommitTick` identify the just-committed state;
- `rootID` identifies the accepted Surface Event root;
- \(\mathcal L_t\) is the trusted event's learning-active frontier;
- \(A_t^+\) contains the corresponding post-tick activation values.

The receipt:

- is transient;
- is not a memory record;
- is not serialized as a way to restore authority later;
- is not part of canonical `RetrievalResult`;
- becomes stale after Core advances;
- must not be constructible through the general Layer-3 retrieval API.

A runtime implementation may represent this capability however it wishes provided these authority constraints hold.

---

# 7. Coherent Retrieval Acquisition

Retrieval mathematics begins only after a successful acquisition:

\[
\boxed{
Acquire(Core,C_I^{raw},\mathcal K_t?)\rightarrow\Omega_R
}
\]

with:

\[
\boxed{
\Omega_R=
(C_T,C_I,C_0,\mathcal S_0,\mathcal A_0,\Sigma_R,\Theta_R)
}
\]

After acquisition:

\[
\boxed{\Omega_R\text{ is immutable.}}
\]

No settling begins before acquisition completes.

---

# 8. Acquisition Coherence

At acquisition start:

\[
v_0=Core.version,
\qquad
t_0=Core.tick.
\]

Capture the required Core configuration or an exact canonical fingerprint:

\[
\phi_0=Fingerprint(CoreConfig).
\]

After bounded snapshot materialization:

\[
v_1=Core.version,
\qquad
\phi_1=Fingerprint(CoreConfig).
\]

Acquisition succeeds only if:

\[
\boxed{v_0=v_1\land\phi_0=\phi_1.}
\]

If Core mutates during capture, the version changes, configuration changes, or the acquisition cannot otherwise prove a coherent read:

\[
\boxed{SNAPSHOT\_ABORTED.}
\]

No partial retrieval universe is published.

---

# 9. Trusted Receipt Validation

If no receipt is supplied:

\[
\boxed{C_T=\varnothing.}
\]

If a receipt is supplied, it is valid only if:

\[
\boxed{\mathcal K_t.CoreInstance=Core}
\]

and:

\[
\boxed{\mathcal K_t.postCommitVersion=v_0}
\]

and:

\[
\boxed{\mathcal K_t.postCommitTick=t_0.}
\]

Otherwise:

\[
\boxed{STALE\_TRUSTED\_ROOT.}
\]

A stale receipt is never silently downgraded to an internal cue.

---

# 10. Canonical Trusted Cue

For a valid trusted receipt:

\[
\boxed{\mathcal A_0=\mathcal L_t}
\]

and:

\[
\boxed{C_T(i)=A_i^+(t)\quad\forall i\in\mathcal L_t.}
\]

There is no caller-selected subset, Top-K filter, rescaling, normalization, or magnitude override.

Each trusted Cell must still be committed in the captured Core state, and its activation must match the trusted post-event value and satisfy:

\[
C_T(i)\ge\theta_{active}.
\]

A mismatch means the receipt and Core state are not coherent and acquisition aborts.

Cells in \(\mathcal A_0\) are **Root-Authorized Witnesses**. They are not independent external roots. Multiple witness Cells may all derive from the same Surface Event root.

Therefore witness-set cardinality must not be reinterpreted as a count of independent observations.

---

# 11. Internal Cue

The raw internal cue is a finite partial function:

\[
C_I^{raw}:CellID\rightarrow(0,1].
\]

Every value must be finite.

During acquisition, every internal cue Cell must be currently committed in the same coherent Core state. Invalid IDs, uncommitted Cells, NaN, infinity, zero, or values greater than one cause:

\[
\boxed{INVALID\_CUE.}
\]

After validation, denote the resulting map by \(C_I\).

Internal cue magnitude never grants root authority.

---

# 12. Canonical Merged Cue

Define the canonical merged cue drive:

\[
\boxed{C_0:\mathcal S_0\rightarrow(0,1]}
\]

by:

\[
\boxed{
C_0(i)=
\begin{cases}
C_T(i), & i\in dom(C_T)\\
C_I(i), & i\notin dom(C_T)\land i\in dom(C_I).
\end{cases}
}
\]

Trusted provenance therefore has priority over internal magnitude.

The merged seed set is:

\[
\boxed{\mathcal S_0=dom(C_0)=dom(C_T)\cup dom(C_I).}
\]

Root-authorized witnesses are:

\[
\boxed{\mathcal A_0=dom(C_T).}
\]

Thus:

\[
\boxed{\mathcal A_0\subseteq\mathcal S_0.}
\]

Authority is frozen after acquisition:

\[
\boxed{\mathcal A_0^{final}=\mathcal A_0^{initial}.}
\]

---

# 13. Cue Cardinality

The merged cue must satisfy:

\[
\boxed{1\le|\mathcal S_0|\le K_C.}
\]

If:

\[
|\mathcal S_0|=0,
\]

return:

\[
\boxed{EMPTY\_CUE.}
\]

If:

\[
|\mathcal S_0|>K_C,
\]

return:

\[
\boxed{CUE\_CAPACITY\_ABORT.}
\]

The implementation must not truncate, sample, sort-and-cut, or choose the strongest \(K_C\) seeds.

---

# 14. RetrievalSnapshot

Layer 2 does not retain Layer-1 `TickSnapshot` as its settling state.

Instead it constructs a bounded, independently materialized, immutable:

\[
\boxed{\Sigma_R.}
\]

After acquisition:

\[
\boxed{\Sigma_R\text{ contains no live mutable Core references.}}
\]

Only the bounded retrieval closure is copied. Layer 2 never deep-copies the global network.

---

# 15. Source Assembly Discovery

Discover Assembly sources only through cue membership indexes:

\[
\boxed{
\mathcal H_0=
\bigcup_{i\in\mathcal S_0}Memberships(i).
}
\]

No global Assembly scan is permitted.

Since Layer 1 bounds memberships:

\[
|Memberships(i)|\le M_{max},
\]

therefore:

\[
\boxed{|\mathcal H_0|\le K_CM_{max}.}
\]

---

# 16. Residual Atomic Sources

A cue Cell with no Assembly membership is not discarded.

Define:

\[
\boxed{
\mathcal U_S=
\{i\in\mathcal S_0:Memberships(i)=\varnothing\}.
}
\]

Each such Cell becomes an independent transient Atomic Source.

Canonical source identity is a disjoint union:

\[
\boxed{
SourceID=
("ASM",h)\ \dot\cup\ ("ATOM",i).
}
\]

Distinct Atomic Sources are never merged into one synthetic pattern merely because they appeared in the same cue.

---

# 17. Source Closure

The complete Cell set that can act as a retrieval source is:

\[
\boxed{
V_S=
\left(\bigcup_{h\in\mathcal H_0}V_h\right)
\cup
\mathcal U_S.
}
\]

Snapshot acquisition materializes:

- the identified source Assemblies;
- their member sets;
- required membership records;
- the reciprocal consolidated `LOCAL` structure needed by source reconstruction;
- each Atomic Source Cell;
- all consolidated outgoing `ASSOCIATIVE` Synapses from \(V_S\).

---

# 18. Source LOCAL Closure

For each source Assembly \(h\), materialize exactly the `LOCAL` Synapses required to derive \(R_{ij}^{L}\) among its members.

Candidate, one-directional, non-LOCAL, or non-consolidated relationships contribute:

\[
R_{ij}^{L}=0.
\]

Layer 2 does not create or infer missing reverse edges.

---

# 19. Directed ASSOCIATIVE Closure

For each:

\[
i\in V_S,
\]

materialize only outgoing Synapses satisfying:

```text
scope = ASSOCIATIVE
state = CONSOLIDATED
```

Define:

\[
\boxed{
E_A=
\{(i,j):i\in V_S,
scope_{ij}=ASSOCIATIVE,
state_{ij}=CONSOLIDATED\}.
}
\]

For each:

\[
(i,j)\in E_A,
\]

use:

\[
\boxed{A_{ij}=Q_{ij}^{ASSOCIATIVE}.}
\]

Layer 2 never reapplies the temporal learning kernel \(\kappa(\Delta)\). Any historical temporal weighting is already reflected in the persistent Synapse state produced by Layer 1.

---

# 20. `CROSS_TERRITORY` Scope

`CROSS_TERRITORY` Synapses are outside Layer-2 v0 retrieval semantics:

\[
\boxed{CROSS\_TERRITORY\ retrieval\notin Scope(L2\ v0).}
\]

An implementation must not reinterpret `CROSS_TERRITORY` as `ASSOCIATIVE`.

Future multimodal retrieval requires a separate explicit Layer-2 revision or extension.

---

# 21. Possible Target Closure

From the captured associative edges, define all possible target Cells:

\[
\boxed{
V_A=\{j:\exists i\;(i,j)\in E_A\}.
}
\]

Discover possible target Assemblies locally:

\[
\boxed{
\mathcal T^{possible}=
\bigcup_{j\in V_A}Memberships(j).
}
\]

Materialize:

- all target Assembly identities in \(\mathcal T^{possible}\);
- their member sets;
- required target membership records;
- all reciprocal consolidated `LOCAL` structure required for target reconstruction.

After this step:

\[
\boxed{\Sigma_R=CLOSED.}
\]

No further Core read is permitted during the session.

---

# 22. Snapshot Capacity Failure

If the complete bounded retrieval closure cannot be materialized under runtime resource limits:

\[
\boxed{SNAPSHOT\_CAPACITY\_ABORT.}
\]

The implementation must not fall back to:

- Top-K Assemblies;
- highest-quality edges;
- first-N targets;
- partial snapshot publication;
- random truncation.

Runtime capacity is an execution constraint, not a cognitive ranking rule.

---

# 23. Frozen Parameter View

Acquisition also freezes:

\[
\boxed{\Theta_R}
\]

containing all calibration values required for the session.

No stage after acquisition reads live configuration.

---

# 24. Empty Product Convention

Throughout Layer 2:

\[
\boxed{\prod_{\varnothing}=1.}
\]

Therefore a Cell with no lawful supporters has:

\[
Z=1,
\qquad
D=0.
\]

Because \(\theta_{PC}>0\) and \(\theta_{AR}>0\), unsupported Cells cannot become eligible.

---

# 25. Seed State and Exact-One Provenance

Pattern reconstruction requires both a drive value and exact-one provenance.

Define a Seed State map:

\[
\boxed{
\eta:S\rightarrow(0,1]\times\{0,1\}.
}
\]

For each seed \(i\):

\[
\eta(i)=(r(i),\xi(i)).
\]

Here:

- \(r(i)\) is the retrieval drive;
- \(\xi(i)=1\) means the drive is semantically/exactly one through lawful defining factors, not merely numerically rounded to one.

Crucially:

\[
\boxed{ExactOne\neq Authority.}
\]

A fully active internal seed may have \(\xi=1\) while still having zero root authority.

---

# 26. Lane-Scoped Pattern Reconstruction Kernel

The canonical reconstruction function is:

\[
\boxed{
\mathcal P(G,\eta)\rightarrow L^\star.
}
\]

Its domain requires:

\[
\boxed{
\varnothing\neq S=dom(\eta)\subseteq V_G.
}
\]

All drives are finite and in \((0,1]\).

The kernel does **not** perform:

- Assembly candidate discovery;
- membership lookup;
- associative traversal;
- expansion beyond \(V_G\);
- Core mutation;
- learning.

---

# 27. Reconstruction Lane State

For a reconstruction lane, define:

\[
\boxed{
L^{(k)}=(S^{(k)},r,\xi,\tau,F^{(k)},Z^{(k)}).
}
\]

where:

- \(S^{(k)}\) is the admitted Cell set;
- \(r(i)\in(0,1]\) is frozen retrieval drive after admission;
- \(\xi(i)\in\{0,1\}\) is exact-one provenance;
- \(\tau(i)\in\mathbb N_0\) is admission round;
- \(F^{(k)}\) is the current frontier;
- \(Z^{(k)}\) is the residual support state for frontier Cells.

The final lane view is:

\[
\boxed{
L^\star=(S^\star,r,\xi,\tau,Prov).
}
\]

Operational frontier/residual state is discarded after reconstruction.

---

# 28. Reconstruction Neighborhood

For an Assembly \(G\) and member \(j\):

\[
\boxed{
N_G(j)=
\{i\in V_G\setminus\{j\}:R_{ij}^{L}\ge\theta_A\}.
}
\]

Only qualifying reciprocal consolidated `LOCAL` structure participates.

---

# 29. Reconstruction Initialization

Let:

\[
S^{(0)}=dom(\eta).
\]

For every seed:

\[
(r(i),\xi(i))=\eta(i),
\qquad
\tau(i)=0.
\]

Initial frontier:

\[
\boxed{
F^{(0)}=
\left(\bigcup_{i\in S^{(0)}}N_G(i)\right)
-
S^{(0)}.
}
\]

For every initial frontier Cell \(j\):

\[
\boxed{
Z^{(0)}(j)=
\prod_{i\in S^{(0)}\cap N_G(j)}
\left(1-r(i)R_{ij}^{L}\right).
}
\]

---

# 30. Semantic Residual Invariant

For every inactive candidate Cell \(j\) at round \(k\):

\[
\boxed{
Z^{(k)}(j)=
\prod_{i\in S^{(k)}\cap N_G(j)}
\left(1-r(i)R_{ij}^{L}\right).
}
\]

Define completion drive:

\[
\boxed{D^{(k)}(j)=1-Z^{(k)}(j).}
\]

This equation defines semantics. Implementations should maintain it incrementally rather than recompute all prior contributions every round.

---

# 31. Incremental Residual Rule

Each supporter contribution \((i,j)\) may enter the residual product for \(j\) at most once, when \(i\) first becomes admitted.

For an existing frontier Cell remaining inactive:

\[
\boxed{
Z^{(k+1)}(j)=
Z^{(k)}(j)
\prod_{i\in P^{(k)}\cap N_G(j)}
\left(1-r(i)R_{ij}^{L}\right).
}
\]

A Cell entering the frontier for the first time receives residual state consistent with the semantic residual invariant above.

Canonical supporter multiplication order is ascending Cell ID.

---

# 32. Pattern Reconstruction Eligibility

If:

\[
0<\theta_{PC}<1,
\]

define:

\[
\rho_{PC}=1-\theta_{PC}.
\]

The synchronous admission proposal batch is:

\[
\boxed{
P^{(k)}=
\{j\in F^{(k)}:Z^{(k)}(j)\le\rho_{PC}\}.
}
\]

All eligibility tests in a round use the same pre-round lane state.

---

# 33. Exact-One Reconstruction Semantics

Exact-one provenance propagates independently of ordinary floating-point residual evaluation.

For an inactive candidate \(j\), define:

\[
\boxed{
\xi_{new}(j)=1
\iff
\exists i\in S^{(k)}\cap N_G(j):
\xi(i)=1\land R_{ij}^{L}=1.
}
\]

When:

\[
\theta_{PC}=1,
\]

a Cell is eligible iff:

\[
\boxed{\xi_{new}(j)=1.}
\]

This prevents floating-point underflow from manufacturing an exact drive of one.

---

# 34. Synchronous Admission and Freeze-on-Admission

Admit the proposal batch simultaneously:

\[
\boxed{
S^{(k+1)}=S^{(k)}\cup P^{(k)}.
}
\]

For every newly admitted Cell \(j\):

\[
\boxed{\tau(j)=k+1.}
\]

If:

\[
\xi_{new}(j)=1,
\]

then:

\[
\boxed{\xi(j)=1,\qquad r(j)=1.}
\]

Otherwise:

\[
\boxed{\xi(j)=0,\qquad r(j)=1-Z^{(k)}(j).}
\]

Once admitted, \(r(j)\) and \(\xi(j)\) remain frozen for the rest of the retrieval session.

---

# 35. Frontier Update

After synchronous admission:

\[
\boxed{
F^{(k+1)}=
\left[
F^{(k)}
\cup
\bigcup_{i\in P^{(k)}}N_G(i)
\right]
-
S^{(k+1)}.
}
\]

If:

\[
P^{(k)}=\varnothing,
\]

reconstruction reaches a fixed point and stops.

---

# 36. Reconstruction Termination and Complexity

Each Cell can be admitted at most once:

\[
\boxed{
K^{productive}\le|V_G|-|dom(\eta)|.
}
\]

A literal implementation may recheck frontier Cells across rounds. Therefore the canonical conservative bound is:

\[
\boxed{
T_{\mathcal P}=O(|V_G|^2+|E_G^L|).
}
\]

Since:

\[
|V_G|\le K_{max},
\]

and:

\[
|E_G^L|=O(K_{max}^2),
\]

we obtain:

\[
\boxed{T_{\mathcal P}=O(K_{max}^2).}
\]

An optimized dirty-frontier scheduler may reduce repeated checks only if it is semantically identical.

---

# 37. Source Assembly Reconstruction

For each source Assembly:

\[
h\in\mathcal H_0,
\]

define source seeds:

\[
\boxed{Seed_h=V_h\cap\mathcal S_0.}
\]

Define seed state:

\[
\boxed{
\eta_h(i)=
\left(
C_0(i),
\mathbf1[C_0(i)=1]
\right),
\quad i\in Seed_h.
}
\]

Then:

\[
\boxed{
L_h^\star=\mathcal P(G_h,\eta_h).
}
\]

Root-authorized witness set:

\[
\boxed{W_h=V_h\cap\mathcal A_0.}
\]

and:

\[
\boxed{W_h^{final}=W_h^{initial}.}
\]

Pattern completion cannot create root-authorized witnesses.

---

# 38. Source Overlap Graph

Pattern separation operates only among Assembly Sources.

Define an undirected overlap graph:

\[
\boxed{\mathcal O=(\mathcal H_0,E_O)}
\]

where:

\[
\boxed{
\{h,g\}\in E_O
\iff
h\ne g
\land
Seed_h\cap Seed_g\ne\varnothing.
}
\]

Separation Families are connected components:

\[
\boxed{\mathcal F=CC(\mathcal O).}
\]

An isolated source candidate is a singleton Family.

---

# 39. Canonical Family Identity

For:

\[
F\in\mathcal F,
\]

define:

\[
\boxed{
FamilyID(F)=
("FAM",tuple(sorted(F))).
}
\]

Family IDs are structural and deterministic. They carry no semantic authority.

---

# 40. Direct Root-Witness Dominance

Two Assembly candidates are directly comparable only when they have a direct overlap edge.

Define:

\[
\boxed{
h\succ_R g
\iff
\{h,g\}\in E_O
\land
W_h\supset W_g.
}
\]

The inclusion is strict.

Equal witness sets remain non-dominating.

Incomparable witness sets remain non-dominating.

The connected Family does not create transitive semantic competition where no direct overlap exists.

---

# 41. Undominated Set

For each Family:

\[
\boxed{
U(F)=
\{h\in F:\nexists g\in F,\ g\succ_Rh\}.
}
\]

Being undominated does **not** assert truth or select a winner.

Dominated Assembly Sources are not deleted; separation records metadata only.

If:

\[
\mathcal A_0=\varnothing,
\]

no root-witness dominance exists.

---

# 42. Atomic Source Activity

For an Atomic Source:

\[
x=("ATOM",i),
\]

define:

\[
\boxed{X_x=\{i\}.}
\]

Its retrieval state is:

\[
\boxed{r_x(i)=C_0(i)}
\]

and:

\[
\boxed{\xi_x(i)=\mathbf1[C_0(i)=1].}
\]

Atomic Sources do not enter the overlap graph, Separation Families, or root-witness dominance relation.

---

# 43. Assembly Source Activity

For an Assembly Source:

\[
x=("ASM",h),
\]

with:

\[
L_h^\star=(S_h^\star,r_h,\xi_h,\tau_h,Prov_h),
\]

define:

\[
\boxed{X_x=S_h^\star.}
\]

For every:

\[
i\in X_x,
\]

use:

\[
\boxed{r_x(i)=r_h(i)}
\]

and:

\[
\boxed{\xi_x(i)=\xi_h(i).}
\]

Thus every source type has a complete, explicit activity/provenance view before associative retrieval begins.

---

# 44. Unified Source Universe

Define:

\[
\boxed{
\mathcal X=
\{("ASM",h):h\in\mathcal H_0\}
\cup
\{("ATOM",i):i\in\mathcal U_S\}.
}
\]

Every source in \(\mathcal X\) is processed independently.

No evidence is aggregated across distinct SourceIDs.

---

# 45. Directed Temporal-Associative Semantics

A stored relation:

\[
i\xrightarrow{ASSOCIATIVE}j
\]

means only that Layer 1 contains persistent evidence of directed historical downstream association from \(i\) to \(j\) within its bounded learning rules.

Layer 2 does not infer from this alone:

- `is_a`;
- `part_of`;
- `same_as`;
- semantic similarity;
- physical causation;
- exact next-event identity;
- exact temporal lag;
- historical episode identity;
- reverse association.

Thus:

\[
\boxed{AssociativeRetrieval\neq EpisodicReplay.}
\]

---

# 46. Associative Contributors

For Source \(x\in\mathcal X\) and possible target Cell \(j\):

\[
\boxed{
I_x(j)=
\{i\in X_x:(i,j)\in E_A\}.
}
\]

If:

\[
I_x(j)=\varnothing,
\]

then by empty-product convention:

\[
Z_x^A(j)=1,
\qquad
D_x^A(j)=0.
\]

---

# 47. Associative Residual and Drive

For a supported target Cell:

\[
\boxed{
Z_x^A(j)=
\prod_{i\in I_x(j)}
\left(1-r_x(i)A_{ij}\right).
}
\]

Canonical multiplication order is ascending source Cell ID.

Ordinary associative drive is:

\[
\boxed{D_x^A(j)=1-Z_x^A(j).}
\]

---

# 48. Exact-One Associative Provenance

Define:

\[
\boxed{
\xi_x^A(j)=1
\iff
\exists i\in I_x(j):
\xi_x(i)=1
\land
A_{ij}=1.
}
\]

Then define canonical associative seed drive:

\[
\boxed{
c_x^A(j)=
\begin{cases}
1, & \xi_x^A(j)=1\\
1-Z_x^A(j), & \text{otherwise.}
\end{cases}
}
\]

Exact-one provenance is preserved independently of floating-point rounding.

---

# 49. Associative Eligibility

If:

\[
0<\theta_{AR}<1,
\]

define:

\[
\rho_{AR}=1-\theta_{AR}.
\]

A target Cell qualifies iff:

\[
\boxed{
j\in Y_x\iff Z_x^A(j)\le\rho_{AR}.}
\]

If:

\[
\theta_{AR}=1,
\]

eligibility is defined exactly by:

\[
\boxed{
j\in Y_x\iff\xi_x^A(j)=1.}
\]

No floating underflow may manufacture a perfect associative hit.

---

# 50. Associative Authority Firewall

Every:

\[
j\in Y_x
\]

has origin:

```text
INTERNAL_ASSOCIATIVE
```

and:

\[
\boxed{Authority(j)=false.}
\]

Even:

\[
c_x^A(j)=1
\]

does not create root authority.

Associative results cannot alter:

- \(\mathcal A_0\);
- \(W_h\);
- Family membership;
- direct root-witness dominance;
- source reconstruction state.

---

# 51. Direct Associative Hits

Every:

\[
j\in Y_x
\]

is a lawful Direct Associative Hit, whether or not it belongs to an Assembly.

If:

\[
Memberships(j)=\varnothing,
\]

it remains an unassembled Direct Hit associated with its SourceID.

Layer 2 does not create an Assembly for it.

---

# 52. Target Assembly Discovery

For each Source \(x\):

\[
\boxed{
\mathcal T_x=
\bigcup_{j\in Y_x}Memberships(j).
}
\]

Because all possible memberships were already captured in \(\Sigma_R\):

\[
\mathcal T_x\subseteq\mathcal T^{possible}.
\]

No live membership lookup is allowed.

---

# 53. Canonical Target Branch Identity

For every:

\[
g\in\mathcal T_x,
\]

define:

\[
\boxed{
BranchID=
(SourceID,("ASM",g)).
}
\]

Several target seed Cells from the same SourceID into the same Assembly form one branch.

The same target Assembly reached from different SourceIDs produces distinct branches.

---

# 54. Target Seed State

For branch \((x,g)\), define:

\[
\boxed{S_{x,g}=Y_x\cap V_g.}
\]

Define target seed state:

\[
\boxed{
\eta_{x,g}(j)=
\left(
c_x^A(j),
\xi_x^A(j)
\right),
\quad j\in S_{x,g}.
}
\]

Target authority is always empty:

\[
\boxed{\mathcal A_{x,g}=\varnothing.}
\]

---

# 55. Target Reconstruction

Target Assembly \(g\) is already known.

Therefore target completion calls only the lane-scoped kernel:

\[
\boxed{
L_{x,g}^\star=
\mathcal P(G_g,\eta_{x,g}).
}
\]

It must not perform Assembly candidate rediscovery.

This prevents target seeds from recursively opening additional target Assemblies outside their already-created canonical branches.

---

# 56. One-Hop Invariant

After target reconstruction:

\[
L_{x,g}^\star,
\]

no further `ASSOCIATIVE` traversal is permitted in the same session.

\[
\boxed{AssociativeDepth=1.}
\]

Longer chains require new Layer-2 sessions orchestrated by Layer 3. Outputs reused as new seeds remain internal and gain no root authority.

---

# 57. Branch and Lane Isolation

Distinct branches do not share mutable retrieval lane state.

For:

\[
(SourceID_1,g)\ne(SourceID_2,g),
\]

the branches remain distinct even if their reconstructed target Cell sets are identical.

For:

\[
(x,g_1)\ne(x,g_2),
\]

the target Assemblies settle independently even if they overlap in Cells.

Source and target lanes never alias simply because:

\[
h=g.
\]

A self-target branch is legal but remains a distinct branch and cannot feed back into its source lane.

---

# 58. No-Feedback Dependency Rule

The legal causal order is:

\[
\boxed{
Cue
\rightarrow
SourceReconstruction
\rightarrow
Separation
\rightarrow
Association
\rightarrow
TargetReconstruction.
}
\]

Forbidden feedback includes:

\[
Target\not\rightarrow Source,
\]

\[
Association\not\rightarrow Separation,
\]

\[
TargetQuality\not\rightarrow RootAuthority,
\]

\[
Completion\not\rightarrow RootWitnesses.
\]

---

# 59. Retrieval Provenance

Retrieval provenance is transient and distinct from Layer-1 learning provenance.

Conceptual canonical identities include:

Source completion:

\[
\boxed{("PC",SourceID,j,\tau(j))}
\]

Directed association:

\[
\boxed{("AR",SourceID,j)}
\]

Target completion:

\[
\boxed{("TPC",SourceID,("ASM",g),j,\tau(j))}
\]

A runtime may represent these structures more compactly or hash them canonically, provided their identity is determined only by canonical structure and not by wall-clock time, random UUIDs, memory addresses, or iteration accidents.

---

# 60. Canonical RetrievalResult

A successful retrieval publishes exactly one immutable logical result:

\[
\boxed{
R=
(
RootView,
SourceViews,
DirectHits,
BranchViews
).
}
\]

No partially built result is visible to higher layers.

---

# 61. RootView

Define:

\[
\boxed{
RootView=
(
trustedRootID?,
C_0,
\mathcal A_0
).
}
\]

For internal-only retrieval:

```text
trustedRootID = None
```

`RootView` contains values/IDs only and no writable Core references.

---

# 62. SourceViews

For an Assembly Source:

```text
SourceID = ("ASM", h)
kind = ASSEMBLY
seed_state
root_authorized_witnesses
reconstructed_cells
retrieval_drive
exact_one_flags
admission_rounds
FamilyID
direct_root_dominance_relations
provenance
```

For an Atomic Source:

```text
SourceID = ("ATOM", i)
kind = ATOMIC
cell_id
seed_drive
exact_one
root_authorized = true | false
provenance
```

Atomic Sources have no `FamilyID` and no Assembly separation status.

---

# 63. DirectHits

Conceptually:

\[
\boxed{
DirectHits:
SourceID\mapsto
\{(j,c_x^A(j),\xi_x^A(j),Prov)\}.
}
\]

It includes **all** qualifying direct associative hits, whether assembled or unassembled.

Unassembled status is derived from captured membership data rather than duplicated as independent cognitive state.

---

# 64. BranchViews

Each branch contains at least:

```text
BranchID
SourceID
TargetID = ("ASM", g)
target_seed_state
reconstructed_target_cells
retrieval_drive
exact_one_flags
admission_rounds
provenance
```

Branches are never deduplicated across different SourceIDs.

---

# 65. Result Ordering

Canonical serialization orders:

1. Assembly Sources before Atomic Sources;
2. source numeric IDs ascending within kind;
3. target Assembly IDs ascending;
4. Cell IDs ascending;
5. supporter IDs ascending;
6. Families by their canonical `FamilyID` tuple.

Ordering exists only for deterministic representation. It grants no cognitive preference.

---

# 66. No Global Confidence or Forced Winner

Layer 2 v0 does not produce:

- global retrieval confidence;
- global ambiguity score;
- best memory;
- single chosen hypothesis;
- ranked target list.

It returns structural evidence and alternatives directly.

Layer 3 may reason over these structures later, but must not retroactively change what Layer 2 retrieved.

---

# 67. Diagnostics Are Not Cognitive Inputs

Implementation diagnostics may include:

- snapshot size;
- source candidate count;
- target branch count;
- support count;
- maximum single contribution;
- settling rounds;
- cache hits;
- timings.

But:

\[
\boxed{Diagnostics\notin DecisionInputs.}
\]

Changing instrumentation must not change the canonical result.

---

# 68. Numerical Reference Profile

The reference implementation must use a canonical numerical profile compatible with Layer 1.

At minimum:

- binary64-compatible reference arithmetic;
- ascending Cell ID order for multiplicative reductions;
- no parallel reassociation in the canonical path;
- no hidden epsilon in eligibility rules;
- exact threshold semantics as specified;
- exact-one provenance derived from defining factors, not from rounded output alone;
- canonical, lossless serialization for behavioral signatures.

Thus, for the same frozen retrieval universe:

\[
\boxed{
\Omega_R^{(1)}=\Omega_R^{(2)}
\Rightarrow
R^{(1)}=R^{(2)}.
}
\]

---

# 69. Operational IDs

A runtime may use a noncanonical session handle for tracing or logs.

However:

\[
\boxed{OperationalSessionID\notin CanonicalCognitiveResult.}
\]

Operational identifiers must not affect decisions, ordering, provenance authority, or behavioral signatures.

---

# 70. Failure Atomicity

Retrieval builds its result privately.

Canonical publication order is:

```text
BUILD
  -> VALIDATE
  -> PUBLISH ONCE
```

If one target branch fails internally after other branches have completed:

\[
\boxed{INTERNAL\_ABORT}
\]

and no partial `RetrievalResult` is published.

A branch that simply reaches fixed point without admitting additional Cells is a lawful result, not a failure.

---

# 71. Canonical Failure States

The principal non-cognitive failure outcomes are:

```text
INVALID_CUE
EMPTY_CUE
CUE_CAPACITY_ABORT
STALE_TRUSTED_ROOT
SNAPSHOT_ABORTED
SNAPSHOT_CAPACITY_ABORT
INTERNAL_ABORT
```

These do not produce a complete cognitive `RetrievalResult`.

A successful session may lawfully contain zero associative hits or seed-only reconstructions.

---

# 72. Retrieval Conservation

Throughout acquisition and retrieval:

\[
\boxed{Core^{post}=Core^{pre}}
\]

with respect to Layer-2 authority.

Layer 2 does not mutate:

- Cell activation;
- Cell commitment;
- Synapses;
- Synaptic `S`, `E`, state, or scope;
- Assemblies or memberships;
- temporal learning context;
- root allocation/ledgers;
- recruitment state;
- Core configuration.

---

# 73. Retrieval Is Not Learning Evidence

All retrieved/internal activity has zero independent learning origin:

\[
\boxed{O_r=0.}
\]

Therefore Layer 2 cannot create lawful Layer-1 evidence mass merely because reconstruction or association occurred.

Retrieved state must not be automatically fed through the Core Surface Event path as though it were an external observation.

\[
\boxed{Retrieval\neq ExternalObservation.}
\]

---

# 74. Persistent-State Discipline

The authoritative statement is:

\[
\boxed{PersistentCognitiveState_{L2}=\varnothing.}
\]

Permitted non-cognitive persistent/administrative material may include:

- Layer-2 configuration;
- logs;
- instrumentation;
- exact derivable caches.

Any cache must satisfy:

\[
\boxed{R_{cache}=R_{no-cache}.}
\]

Layer 2 must not persist:

- prior winners;
- retrieval activations;
- learned retrieval confidence;
- branch preference;
- previous session separation decisions;
- persistent completion state;
- any second memory database.

---

# 75. Source-Space Bound

Let:

\[
H=|\mathcal H_0|\le K_CM_{max}
\]

and:

\[
U=|\mathcal U_S|\le K_C.
\]

Then:

\[
\boxed{
|V_S|\le HK_{max}+U
}
\]

and therefore:

\[
\boxed{
|V_S|\le K_C(M_{max}K_{max}+1).
}
\]

---

# 76. Session-Derived Synaptic Bound

For nonempty \(V_S\), define:

\[
\boxed{
B_R=
\max_{i\in V_S}synaptic\_budget(i).
}
\]

\(B_R\) is derived from the frozen snapshot and is not a learned parameter.

Then:

\[
\boxed{
|E_A|\le
K_C(M_{max}K_{max}+1)B_R.
}
\]

---

# 77. Target-Branch Bound

A conservative upper bound on canonical target branches is:

\[
\boxed{
N_B\le
K_CB_RM_{max}(M_{max}K_{max}+1).
}
\]

Deduplication of repeated target Assemblies within one SourceID may reduce actual branch count but is not required for the bound.

---

# 78. Integrated Runtime Bound

Each target branch uses one reconstruction lane with:

\[
T_{\mathcal P}=O(K_{max}^2).
\]

Therefore a conservative dominant Layer-2 bound is:

\[
\boxed{
T_{L2}=
O\left(
K_CB_RM_{max}K_{max}^{2}
(M_{max}K_{max}+1)
\right).
}
\]

The dominant expanded form is:

\[
\boxed{
O(K_CM_{max}^{2}B_RK_{max}^{3}).
}
\]

The architectural property that matters most is:

\[
\boxed{N_{global}\notin T_{L2}.}
\]

Normal retrieval work is bounded by the cue and local structural/resource bounds rather than total network size.

---

# 79. Governing Family MR-1 — Retrieval Authority

MR-1 requires:

1. trusted authority can originate only from the trusted post-Core-event path;
2. internal callers cannot mint authority;
3. trusted and internal cues are separate before canonical merge;
4. trusted values override colliding internal magnitudes;
5. \(\mathcal A_0\) is frozen before reconstruction;
6. completion, association, and target reconstruction cannot expand authority;
7. exact-one drive is not authority;
8. witness cardinality is not independent-root count.

---

# 80. Governing Family MR-2 — Bounded Reconstruction

MR-2 requires:

1. candidate discovery only from bounded membership indexes;
2. residual Atomic Sources for unassembled seeds;
3. lane-scoped reconstruction \(\mathcal P(G,\eta)\);
4. reciprocal consolidated LOCAL support only;
5. synchronous admission;
6. freeze-on-admission;
7. monotonic Cell admission;
8. finite settling;
9. lane isolation;
10. root-witness separation without forced winner.

---

# 81. Governing Family MR-3 — Directed Associative Continuation

MR-3 requires:

1. only consolidated `ASSOCIATIVE` Synapses participate;
2. traversal follows stored direction only;
3. no reapplication of the temporal learning kernel;
4. source hypotheses remain separate;
5. target seed authority is always empty;
6. BranchID is `(SourceID, TargetAssemblyID)`;
7. target completion is lane-scoped only;
8. `AssociativeDepth = 1` per session;
9. exact lag, episode identity, and semantic relation type are not inferred.

---

# 82. Governing Family MR-4 — Retrieval Conservation

MR-4 requires:

1. coherent acquisition;
2. bounded materialized immutable snapshot;
3. frozen per-session configuration;
4. no live Core reads after closure;
5. no Core mutation;
6. no learning-evidence leakage;
7. deterministic identities and arithmetic;
8. failure atomicity;
9. immutable result publication;
10. no persistent cognitive Layer-2 state.

---

# 83. Core Theorems / Required Properties

The implementation and acceptance suite must demonstrate the following.

## T-01 — Persistent Conservation

\[
\boxed{Core^{post}=Core^{pre}}
\]

for every Layer-2 retrieval operation except unrelated external Core activity outside the session's captured immutable state.

## T-02 — Finite Termination

All candidate sets, Assembly sizes, branches, and reconstruction rounds are finite, and associative depth is one.

\[
\boxed{\mathcal R(\Omega_R)\text{ terminates finitely.}}
\]

## T-03 — Locality / Remote-State Independence

If disconnected remote Core state does not enter the retrieval closure, adding it cannot change the result.

## T-04 — Authority Non-Escalation

\[
\boxed{\mathcal A_0^{final}=\mathcal A_0^{initial}.}
\]

## T-05 — Hypothesis Non-Mixing

Distinct SourceIDs and BranchIDs do not share mutable retrieval evidence or lane state.

## T-06 — Deterministic Replay

Same \(\Omega_R\), same numerical profile, and same canonical serialization yield the same canonical result.

---

# 84. Known Capability Boundaries

Layer 2 v0 deliberately does not provide the following.

## 84.1 No exact episodic co-binding

Separate associative Synapses may have been learned from different historical occurrences. Layer 2 may reconstruct a pattern supported by distributed history but cannot prove all supports belonged to one episode.

## 84.2 No exact temporal lag

Persistent associative Synapses do not preserve the exact original \(\Delta\) or a lag histogram usable for literal replay.

## 84.3 Forward association only

Stored direction is respected. Reverse lookup is not automatically inferred.

## 84.4 One associative hop per session

Long chains belong to Layer-3 orchestration across separate sessions.

## 84.5 Freeze-on-admission is conservative

A Cell admitted with one drive is not subsequently amplified by later supporters in the same session.

## 84.6 Weak distributed chains may stop

A lawful pattern may remain partially reconstructed if support never reaches \(\theta_{PC}\).

## 84.7 Threshold calibration remains experimental

\(\theta_{PC}\) and \(\theta_{AR}\) are calibration parameters, not learned parameters in v0.

## 84.8 Cross-session continuity is not guaranteed across Core mutation

A previously returned internal Cell ID may be reused only if it remains valid and committed in the current Core state; the new session always reads current Core structure and grants no old authority.

---

# 85. Forbidden Behaviors

The following are explicitly prohibited in Layer 2 v0:

```text
x persistent MemoryObject / EpisodeObject database
x learned retrieval weights outside Core Synapses
x global scan of all Cells or Assemblies during normal retrieval
x global ranking or forced best-memory selection
x Top-K truncation as semantic fallback
x beam search across associative paths
x more than one ASSOCIATIVE hop per session
x Candidate ASSOCIATIVE edges participating in retrieval
x implicit reverse ASSOCIATIVE traversal
x CROSS_TERRITORY edges treated as ASSOCIATIVE
x target-seed candidate rediscovery
x cross-source evidence aggregation
x completion-created root authority
x associative-result feedback into source separation
x Layer-2 retrieval activity entering Layer-1 evidence automatically
x live Core reads after RetrievalSnapshot closure
x writable Core references in RetrievalResult
x random / clock-derived canonical cognitive IDs
x diagnostics influencing cognitive decisions
x stale cache changing results
x partial result publication after internal failure
```

---

# 86. Canonical Execution Order

The reference execution order is normative:

```text
1. Receive raw Internal Cue and optional trusted post-Core-event receipt.
2. Read Core version/tick/configuration boundary.
3. Validate trusted receipt, if present.
4. Derive canonical Trusted Cue from its learning-active frontier.
5. Validate Internal Cue against the same Core state.
6. Construct canonical merged cue C0.
7. Freeze root-authorized witness set A0.
8. Enforce merged cue bound K_C.
9. Discover source Assemblies from bounded membership indexes.
10. Derive residual Atomic Sources.
11. Materialize source Assemblies and source LOCAL structure.
12. Materialize consolidated outgoing ASSOCIATIVE structure.
13. Discover possible target Assemblies from captured target memberships.
14. Materialize target Assemblies and target LOCAL structure.
15. Recheck Core version/configuration coherence.
16. Freeze Ω_R; no further live Core reads.
17. Reconstruct every Assembly Source with P(G, eta).
18. Construct Source Overlap Graph and Separation Families.
19. Compute direct root-witness dominance metadata.
20. Build the unified source universe including Atomic Sources.
21. Compute directed associative hits for every source.
22. Form canonical (SourceID, TargetAssemblyID) branches.
23. Reconstruct every target branch with lane-scoped P(G, eta).
24. Construct canonical provenance and immutable result views.
25. Validate the complete result.
26. Atomically publish one RetrievalResult.
27. Destroy operational session state.
```

The order is not freely permutable. In particular:

\[
SnapshotClosure\prec AllSettling,
\]

\[
SourceReconstruction\prec Separation,
\]

\[
Separation\prec Association,
\]

\[
Association\prec TargetReconstruction.
\]

---

# 87. Acceptance and Verification Specification

Implementation is not considered complete because the functions merely execute. It must demonstrate architectural, mathematical, determinism, safety, and locality acceptance.

## 87.1 Acquisition tests

The suite must prove:

- internal-only retrieval creates no trusted authority;
- only trusted integration can produce a valid receipt;
- a receipt from another Core instance is rejected;
- a stale version/tick receipt is rejected;
- Core mutation during acquisition aborts rather than mixes states;
- configuration change during acquisition aborts;
- snapshot contains no live mutable Core references;
- cue overflow fails rather than truncates;
- invalid/NaN/Inf cue values fail closed;
- colliding trusted/internal Cell IDs use trusted drive only.

## 87.2 Snapshot/locality tests

The suite must prove:

- source candidates come only from seed memberships;
- unassembled cue Cells become Atomic Sources;
- remote disconnected graph additions do not change the result;
- only consolidated outgoing `ASSOCIATIVE` edges from the bounded source closure are copied;
- target Assembly discovery uses only captured target memberships;
- no live Core read occurs after closure;
- snapshot-capacity failure never returns a truncated result.

## 87.3 Pattern reconstruction tests

The suite must prove:

- seed magnitudes affect reconstruction;
- exact-one provenance is distinct from authority;
- candidate LOCAL edges cannot support reconstruction;
- one-directional LOCAL edges cannot support reconstruction;
- synchronous admission is iteration-order invariant;
- each Cell is admitted at most once;
- freeze-on-admission is enforced;
- exact-one propagation obeys the factor/provenance rule;
- \(\theta_{PC}=1\) cannot pass because of floating underflow alone;
- unsupported frontier Cells never admit;
- reconstruction terminates on every bounded Assembly.

## 87.4 Pattern separation tests

The suite must prove:

- overlap graph uses source seed overlap only;
- Families are connected components;
- direct dominance requires a direct overlap edge;
- strict root-witness superset dominates a strict subset;
- equal witness sets remain non-dominating;
- incomparable witness sets remain non-dominating;
- root-free sessions have no root dominance;
- dominated hypotheses are preserved rather than deleted;
- associative outcomes cannot alter separation metadata.

## 87.5 Associative retrieval tests

The suite must prove:

- only `CONSOLIDATED ASSOCIATIVE` edges participate;
- traversal follows stored direction only;
- temporal kernel is not reapplied;
- several weak supports combine by noisy-OR residual semantics;
- many weak supports do not create a ranking winner because no ranking exists;
- exact-one associative provenance is deterministic;
- \(\theta_{AR}=1\) cannot pass through underflow alone;
- source hypotheses do not share associative evidence;
- Atomic Sources can retrieve through their own legal associative edges;
- unassembled direct hits are preserved;
- `CROSS_TERRITORY` edges are excluded.

## 87.6 Target-branch tests

The suite must prove:

- same source + same target Assembly yields one branch with aggregated target seed set;
- different sources + same target Assembly yield distinct branches;
- self-target branch remains isolated from its source lane;
- target authority is always empty;
- target reconstruction does not run candidate discovery;
- target reconstruction cannot launch another association hop;
- overlapping target Assemblies settle independently.

## 87.7 Conservation tests

The suite must compare canonical Core state before and after retrieval and prove zero change in:

- Cells;
- activation;
- Synapses;
- Assembly records;
- memberships;
- temporal context;
- recruitment state;
- root/evidence state.

It must also prove that retrieval outputs are not passed through Core learning automatically.

## 87.8 Determinism tests

The suite must prove:

- repeated identical \(\Omega_R\) gives bit-equivalent canonical result;
- iteration insertion order does not change result;
- cache enabled/disabled does not change result;
- diagnostics enabled/disabled do not change result;
- operational session IDs do not appear in canonical result;
- canonical source/branch/family ordering is stable.

## 87.9 Failure-atomicity tests

The suite must prove:

- failure during snapshot acquisition publishes nothing;
- failure during source reconstruction publishes nothing;
- failure during association publishes nothing;
- failure during the last target branch publishes no earlier partial branches;
- lawful zero-hit retrieval still returns a successful result;
- seed-only reconstruction is not treated as failure.

---

# 88. Adversarial Acceptance Matrix

The implementation must include adversarial cases covering at least:

```text
A01 caller authority forgery
A02 stale TrustedRetrievalReceipt
A03 cross-Core receipt reuse
A04 cue collision trusted vs internal
A05 cue overflow / no truncation
A06 snapshot tearing during acquisition
A07 snapshot capacity pressure
A08 remote disconnected graph pollution
A09 duplicate Assembly memberships
A10 giant overlapping source family
A11 equal root-witness sets
A12 incomparable root-witness sets
A13 candidate LOCAL support injection
A14 one-directional LOCAL support injection
A15 exact-one floating underflow attack
A16 weak-support mass accumulation
A17 generic target hub explosion
A18 same target from multiple source hypotheses
A19 Atomic Source to assembled target
A20 Atomic Source to unassembled target
A21 self-target branch
A22 A -> B -> A cycle inside one session
A23 reverse ASSOCIATIVE inference attempt
A24 candidate ASSOCIATIVE edge injection
A25 CROSS_TERRITORY contamination
A26 target candidate-rediscovery attempt
A27 target-to-source feedback attempt
A28 retrieval-to-learning leakage
A29 cache poisoning
A30 nondeterministic UUID/clock provenance
A31 partial result exposure
A32 concurrent retrieval session isolation
```

No adversarial case may be closed by weakening a Layer-1 invariant.

---

# 89. Reference Implementation Contract for Codex

This document is the authoritative Layer-2 design contract.

## 89.1 Codex MAY

Codex MAY:

- choose clean module/file decomposition;
- create transient immutable dataclasses for retrieval state;
- create a Layer-2 bounded snapshot representation;
- use exact derivable caches;
- use private helper indexes inside a session;
- optimize the frontier scheduler while preserving semantics;
- add instrumentation and property tests;
- add deterministic serialization for test signatures;
- expose \(K_C\), \(\theta_{PC}\), and \(\theta_{AR}\) as Layer-2 calibration configuration.

## 89.2 Codex MUST

Codex MUST:

- preserve all equations and invariants semantically;
- treat Layer 1 as frozen/read-only;
- separate trusted and internal entry paths;
- prevent caller-minted root authority;
- materialize an independent bounded immutable retrieval snapshot;
- implement Atomic Sources;
- implement \(\mathcal P(G,\eta)\) with synchronous admission and freeze-on-admission;
- preserve exact-one provenance independently of authority;
- implement direct root-witness separation exactly;
- use only forward consolidated `ASSOCIATIVE` edges;
- enforce one associative hop per session;
- isolate branches by `(SourceID, TargetAssemblyID)`;
- publish results atomically;
- guarantee no Core mutation;
- satisfy the acceptance and adversarial suites.

## 89.3 Codex MUST NOT

Codex MUST NOT:

- modify `Cell`, `Synapse`, or `Assembly` schema;
- alter LLA, Core evidence, recruitment, or Assembly semantics;
- add a persistent memory database;
- add semantic embeddings or semantic labels;
- add a learned ranking/scoring network;
- invent global confidence;
- choose a forced winner among lawful alternatives;
- truncate candidates with Top-K;
- introduce multi-hop associative graph search;
- reinterpret `CROSS_TERRITORY` as `ASSOCIATIVE`;
- write retrieval activation back to Core;
- call the Surface Event learning path for retrieved output;
- silently change equations for benchmark performance.

---

# 90. Codex Pre-Code Comprehension Gate

Before Codex writes production Layer-2 code, it must return a comprehension report containing:

1. proposed module decomposition;
2. all transient state structures;
3. trusted/internal API boundary;
4. bounded snapshot capture plan;
5. exact definition of `C0`, `A0`, `SourceID`, `FamilyID`, and `BranchID`;
6. exact \(\mathcal P(G,\eta)\) equations and round ordering;
7. exact pattern-separation rule;
8. exact associative retrieval equations;
9. exact-one provenance handling;
10. one-hop enforcement mechanism;
11. Core read-only/conservation enforcement points;
12. failure-atomic publication plan;
13. deterministic serialization/signature plan;
14. complexity argument showing no global network scan;
15. test matrix mapped to Sections 87 and 88;
16. any ambiguity it believes remains.

Production implementation must not begin until this interpretation is reviewed.

---

# 91. Interface to Layer 3 — Cognition

Layer 3 may consume:

- `RootView`;
- Assembly and Atomic `SourceViews`;
- Family/root-dominance metadata;
- Direct Associative Hits;
- Target `BranchViews`;
- retrieval provenance.

Layer 3 may start new internal retrieval sessions using valid committed Cell IDs from a prior result, but those inputs remain internal:

\[
\boxed{Authority=0.}
\]

Layer 3 owns any future:

- reasoning;
- planning;
- multi-session associative chaining;
- hypothesis evaluation;
- answer selection;
- query semantics.

Layer 2 does not perform those tasks.

---

# 92. Architecture Summary

```text
                        LAYER 3 — COGNITION
                                ^
                                |
                    Immutable RetrievalResult
                                |
        +------------------------------------------------+
        |         LAYER 2 — MEMORY & RETRIEVAL           |
        |                                                |
        |  Trusted/Internal Entry Boundary               |
        |                 |                              |
        |      Coherent Bounded Acquisition              |
        |                 |                              |
        |     Immutable RetrievalSnapshot                |
        |                 |                              |
        |    +------------+-------------+                |
        |    |                          |                |
        | Assembly Sources        Atomic Sources         |
        |    |                          |                |
        | P(G, eta)                     |                |
        |    |                          |                |
        | Pattern Separation            |                |
        |    +-------------+------------+                |
        |                  |                             |
        |     Directed Temporal Association              |
        |                  |                             |
        |          Canonical Target Branches             |
        |                  |                             |
        |              P(G, eta)                         |
        |                  |                             |
        |       Atomic Immutable Publication             |
        +------------------|-----------------------------+
                           | READ ONLY
                           v
        +------------------------------------------------+
        |             LAYER 1 — CORE v0.4                |
        |                    FROZEN                       |
        |                                                |
        | Cells | Synapses | Assemblies | LLA | Context |
        +------------------------------------------------+
```

---

# 93. Design Closure Record

The canonical specification incorporates the completed design and review sequence for Layer 2:

```text
Pattern Completion design and adversarial review
Pattern Separation design and adversarial review
Directed Associative Retrieval design
Associative Retrieval AMR01
Associative Retrieval AMR02
Layer-2 Integration Design
Integrated Adversarial Final Review IAFR01
Formal Mathematical Specification v0.1
Formal Specification Audit FSA01
Formal Mathematical Specification v0.2
Formal Specification Audit FSA02
Formal Mathematical Specification v0.3 Closure Candidate
Closure Consistency Check CCC01
Final closure integration into v0.4
```

CCC01 identified five closure-text gaps and no architecture failure:

1. canonical merged cue drive;
2. complete Assembly/Atomic source activity definitions;
3. exact-one provenance as part of reconstruction state;
4. conservative reconstruction complexity theorem;
5. complete canonical `RetrievalResult` codomain.

All five are integrated into this document.

A final consistency pass over the assembled v0.4 specification found no remaining open definition, domain, dependency-cycle, Layer-1 compatibility, authority, conservation, or result-schema blocker.

Therefore:

\[
\boxed{
LAYER2\_FORMAL\_SPECIFICATION\_CLOSED
}
\]

This closure applies to the **design specification**, not to implementation verification.

Layer 2 becomes implementation-frozen only after:

1. Codex comprehension review;
2. production implementation;
3. acceptance/adversarial verification;
4. repository architecture review;
5. deterministic replay/signature verification;
6. exact implementation commit identification;
7. final closure/freeze record.

---

# 94. Pre-Implementation Status

```text
Layer 2 architecture                         CLOSED
Formal mathematics                           CLOSED
Authority model                              CLOSED
Snapshot/acquisition model                   CLOSED
Pattern reconstruction                       CLOSED
Pattern separation                           CLOSED
Atomic Sources                               CLOSED
Directed associative retrieval               CLOSED
Target reconstruction                        CLOSED
Canonical result/provenance                  CLOSED
Conservation/failure semantics               CLOSED
Complexity/locality contract                 CLOSED
Formal closure consistency                   PASS

Codex comprehension                          PENDING
Production implementation                    PENDING
Acceptance verification                      PENDING
Independent repository review                PENDING
Implementation freeze                        PENDING
```

The correct current status is:

> **DGCA LITE Layer 2 Memory & Retrieval v0.4 — SPECIFICATION CLOSED, READY FOR CODEX COMPREHENSION.**

---

# Appendix A — Canonical Transient Type Summary

```text
TrustedRetrievalReceipt
  CoreInstance binding
  postCommitVersion
  postCommitTick
  rootID
  learning_frontier
  next_activation values

RetrievalUniverse Ω_R
  C_T
  C_I
  C_0
  S_0
  A_0
  Σ_R
  Θ_R

SourceID
  ("ASM", assembly_id)
  ("ATOM", cell_id)

SeedState η(i)
  drive r(i)
  exact_one ξ(i)

ReconstructionLane L*
  admitted_cells S*
  retrieval_drive r
  exact_one ξ
  admission_round τ
  provenance

FamilyID
  ("FAM", tuple(sorted(assembly_ids)))

BranchID
  (SourceID, ("ASM", target_assembly_id))

RetrievalResult
  RootView
  SourceViews
  DirectHits
  BranchViews
```

No type above is persistent cognitive memory.

---

# Appendix B — Canonical Equation Summary

## Core scoped quality consumed by Layer 2

\[
Q_{ij}^{s}=S_{ij}^{s}\frac{E_{ij}^{s}}{E_{max}}
\]

## Reciprocal LOCAL structural support

\[
R_{ij}^{L}=
\begin{cases}
\min(Q_{ij}^{LOCAL},Q_{ji}^{LOCAL}),
& \text{both directions consolidated}\\
0,&otherwise
\end{cases}
\]

## Canonical merged cue

\[
C_0(i)=
\begin{cases}
C_T(i),&i\in dom(C_T)\\
C_I(i),&otherwise
\end{cases}
\]

\[
\mathcal S_0=dom(C_0),
\qquad
\mathcal A_0=dom(C_T)
\]

## Pattern residual

\[
Z^{(k)}(j)=
\prod_{i\in S^{(k)}\cap N_G(j)}
(1-r(i)R_{ij}^{L})
\]

\[
D^{(k)}(j)=1-Z^{(k)}(j)
\]

## Pattern admission for \(\theta_{PC}<1\)

\[
Z^{(k)}(j)\le1-\theta_{PC}
\]

## Exact-one pattern provenance

\[
\xi_{new}(j)=1
\iff
\exists i:\xi(i)=1\land R_{ij}^{L}=1
\]

## Direct root dominance

\[
h\succ_Rg
\iff
\{h,g\}\in E_O
\land
W_h\supset W_g
\]

## Associative residual

\[
Z_x^A(j)=
\prod_{i\in I_x(j)}
(1-r_x(i)A_{ij})
\]

## Exact-one associative provenance

\[
\xi_x^A(j)=1
\iff
\exists i:\xi_x(i)=1\land A_{ij}=1
\]

## Associative drive

\[
c_x^A(j)=
\begin{cases}
1,&\xi_x^A(j)=1\\
1-Z_x^A(j),&otherwise
\end{cases}
\]

## Associative admission for \(\theta_{AR}<1\)

\[
Z_x^A(j)\le1-\theta_{AR}
\]

## Branch identity

\[
BranchID=(SourceID,("ASM",g))
\]

## Dominant runtime bound

\[
T_{L2}=
O\left(
K_CB_RM_{max}K_{max}^{2}
(M_{max}K_{max}+1)
\right)
\]

---

# Appendix C — Canonical Prohibitions at the Layer Boundary

```text
Core -> Layer 2:
  allowed: immutable bounded reads
  allowed: trusted just-committed receipt through trusted adapter

Layer 2 -> Core:
  forbidden: Cell writes
  forbidden: Synapse writes
  forbidden: Assembly writes
  forbidden: temporal-context writes
  forbidden: recruitment
  forbidden: root/evidence creation
  forbidden: retrieved state replay as external observation

Layer 3 -> Layer 2:
  allowed: internal cue Cells + drives
  forbidden: trusted-origin flags
  forbidden: trusted receipt minting
  forbidden: modifying an in-flight session

Layer 2 -> Layer 3:
  allowed: immutable RetrievalResult
  forbidden: writable Core references
  forbidden: hidden winner/confidence authority
```

---

# Appendix D — Closure Invariants

```text
MR1-01  Trusted authority is derived, never caller-assigned.
MR1-02  Internal drive cannot amplify colliding trusted drive.
MR1-03  Root-authorized witness set is frozen before reconstruction.
MR1-04  Exact-one drive is not authority.
MR1-05  Association and completion cannot create authority.

MR2-01  Source discovery is membership-index bounded.
MR2-02  Unassembled seeds survive as independent Atomic Sources.
MR2-03  Reconstruction is lane-scoped to one known Assembly.
MR2-04  Only reciprocal consolidated LOCAL support reconstructs Assemblies.
MR2-05  Admission is synchronous.
MR2-06  Admission is monotonic and freeze-on-admission.
MR2-07  Reconstruction terminates finitely.
MR2-08  Distinct lanes do not mix state.

MR3-01  Only consolidated forward ASSOCIATIVE edges are traversed.
MR3-02  Temporal learning decay is not reapplied at retrieval.
MR3-03  Source branches never merge associative evidence.
MR3-04  Target seeds are authority-free.
MR3-05  Branch identity includes source and target identities.
MR3-06  Target completion performs no candidate rediscovery.
MR3-07  Associative depth is exactly at most one per session.
MR3-08  No exact lag, episode identity, or semantic relation is inferred.

MR4-01  Acquisition must prove one coherent Core/configuration state.
MR4-02  RetrievalSnapshot is bounded and independently immutable.
MR4-03  No live Core read occurs after snapshot closure.
MR4-04  Layer 2 performs no Core mutation.
MR4-05  Retrieval never creates Layer-1 learning evidence.
MR4-06  Canonical identities contain no randomness or wall-clock authority.
MR4-07  Result publication is atomic.
MR4-08  Failure publishes no partial cognitive result.
MR4-09  Persistent cognitive state introduced by Layer 2 is empty.
MR4-10  Same frozen retrieval universe yields the same canonical result.
```

---

**End of canonical Layer-2 specification.**
