"""Unit-4 CIE ownership, coherent capture and atomic arena publication shell.

Trusted infrastructure ONLY: attach already-produced bounded closed values.
No operator, inference/frontier discovery, semantic producer, result adapter,
retrieval dispatch, budget consumption, permit, or effect dispatch lives here.
Future work dispatch must wrap positive work/publication in its canonical
atomic charge contract; these mechanics introduce NO new exemption class.

There is one staged round per CIE. It is claimed before physical builders run;
completion order cannot claim another round or publish a same-round premise.
Full entries are ordered by typed canonical keys, not hashes or arrival order.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from threading import RLock
from weakref import ref

from dgca_lite.memory.config import MemoryConfig

from .arena import (
    ArenaSnapshot,
    CIEPolicy,
    CognitiveResultView,
    clone_snapshot,
    entry_key,
    freeze_entry,
)
from .authority import IngressAbort, _OpaqueHandle
from .identity import (
    CanonicalDescriptor,
    CIEBinding,
    CIEIdentity,
    CognitiveEnvironmentBinding,
    SnapshotBinding,
)
from .ingress import _snapshot
from .invocation import InvocationRuntime, _pinned_cie_parent
from .locks import RankedBarrier, _deferred_cleanup
from .policy import DEFAULT_VALUE_LIMITS
from .serialization import canonical_identity_bytes
from .types import FailureCode, InvocationState


class CognitiveInferenceEpoch(_OpaqueHandle):
    __slots__ = ()


class RoundStagingArena(_OpaqueHandle):
    __slots__ = ()


class CIEAbort(IngressAbort):
    """Failure plus immutable prior committed data, never resumable authority."""

    def __init__(self, code, result=None):
        self.result = result
        super().__init__(code)


def _build_cie_system():
    registry_lock = RLock()
    handles = {}

    @dataclass(slots=True)
    class _Runtime:
        parent: InvocationRuntime
        policy: CIEPolicy
        l2_policy: CanonicalDescriptor
        l3_policy: CanonicalDescriptor
        owner_ref: object = None
        epochs: dict = field(default_factory=dict)
        stage_ids: set = field(default_factory=set)
        retired: bool = False
        opened: bool = False
        work_attached: bool = False
        effect_attached: bool = False
        reasoning_policy: object = None
        prediction_policy: object = None

    @dataclass(slots=True)
    class _Epoch:
        runtime: _Runtime
        authority: object
        invocation: object
        binding: CIEBinding
        binding_bytes: bytes
        lock: object = field(default_factory=lambda: RankedBarrier(3))
        snapshot: object = None
        pending: object = None
        terminal: str = ""
        last_binding: object = None

        def finish(self, status):
            # Caller holds the Invocation lifecycle gate and then arena lock.
            work_owner = self.invocation.work_owner
            if work_owner is not None:
                work_owner.prediction_epoch_close(self.binding)
            self.terminal = status
            self.last_binding = self.snapshot.binding
            self.snapshot = None
            if self.pending is not None:
                self.pending.additions = None
                with registry_lock:
                    key = id(self.pending.token)
                    handles.pop(key, None)
                    self.runtime.stage_ids.discard(key)
            self.pending = None
            if self.invocation.cie_child is self:
                self.invocation.cie_child = None
                self.invocation.nondelegated_children -= 1

        def parent_close(self):
            with self.lock:
                if not self.terminal:
                    self.finish(FailureCode.PARENT_AUTHORITY_STALE.value)

    @dataclass(slots=True)
    class _Stage:
        epoch: _Epoch
        token: RoundStagingArena
        base: bytes
        additions: object = None

    @contextmanager
    def access(handle, role):
        with registry_lock:
            registered = handles.get(id(handle))
            if (
                registered is None
                or registered[0]() is not handle
                or registered[2] != role
                or type(handle) is not registered[3]
            ):
                raise CIEAbort(FailureCode.CIE_STALE)
            runtime, item = registered[1], registered[4]
            owner = runtime.owner_ref()
            if owner is None or runtime.retired:
                raise CIEAbort(FailureCode.CIE_STALE)
        yield runtime, item
        del owner

    def require_live(epoch):
        if epoch.terminal or epoch.snapshot is None:
            raise CIEAbort(FailureCode.CIE_STALE)
        try:
            image = canonical_identity_bytes(epoch.binding)
        except (TypeError, ValueError) as error:
            raise CIEAbort(FailureCode.INTERNAL_CONTRACT_VIOLATION) from error
        if image != epoch.binding_bytes:
            raise CIEAbort(FailureCode.INTERNAL_CONTRACT_VIOLATION)
        if epoch.invocation.cie_child is not epoch:
            raise CIEAbort(FailureCode.INTERNAL_CONTRACT_VIOLATION)

    def terminal_failure(epoch, code):
        try:
            output = CognitiveResultView(code.value, clone_snapshot(epoch.snapshot))
        finally:
            epoch.finish(code.value)
        raise CIEAbort(code, output)

    @contextmanager
    def epoch_guard(runtime, epoch, *, core=False):
        entered = False
        try:
            with _pinned_cie_parent(runtime.parent, epoch.authority, core=core) as (
                _,
                item,
                core_binding,
            ):
                entered = True
                with epoch.lock:
                    try:
                        require_live(epoch)
                    except IngressAbort as error:
                        if error.code is FailureCode.INTERNAL_CONTRACT_VIOLATION:
                            epoch.finish(error.code.value)
                        raise
                    if item is not epoch.invocation:
                        terminal_failure(epoch, FailureCode.INTERNAL_CONTRACT_VIOLATION)
                    if item.lifecycle != (
                        InvocationState.ACTIVE,
                        epoch.binding.invocation_revision,
                    ):
                        terminal_failure(epoch, FailureCode.PARENT_AUTHORITY_STALE)
                    if core:
                        current = CognitiveEnvironmentBinding(
                            core_binding, runtime.l2_policy, runtime.l3_policy
                        )
                        if canonical_identity_bytes(
                            current
                        ) != canonical_identity_bytes(epoch.binding.environment):
                            terminal_failure(epoch, FailureCode.ENVIRONMENT_STALE)
                    yield
        except IngressAbort as error:
            if entered or not core:
                raise
            # Issuer/Core binding unavailable: reduce child authority under the
            # lifecycle gate, never acquire Core from beneath that gate.
            with _pinned_cie_parent(runtime.parent, epoch.authority), epoch.lock:
                require_live(epoch)
                code = (
                    FailureCode.INTERNAL_CONTRACT_VIOLATION
                    if error.code is FailureCode.INTERNAL_CONTRACT_VIOLATION
                    else FailureCode.ENVIRONMENT_STALE
                )
                terminal_failure(epoch, code)

    def checked_snapshot(runtime, snapshot):
        try:
            if len(snapshot.entries) > runtime.policy.max_entries:
                raise ValueError("arena capacity exceeded")
            data = snapshot.canonical_bytes
            if len(data) > runtime.policy.max_snapshot_bytes:
                raise ValueError("snapshot byte capacity exceeded")
            # Returned terminal shell must also fit before any commit.
            CognitiveResultView("PUBLISHED", snapshot)
        except (TypeError, ValueError) as error:
            raise CIEAbort(FailureCode.CAPACITY_ABORT) from error

    def check_runtime(handle, runtime):
        # Never dispatch a validator through caller-controlled self methods.
        with access(handle, "RUNTIME") as (own, _):
            if own is not runtime:
                raise CIEAbort(FailureCode.CIE_STALE)

    class CIERuntime(_OpaqueHandle):
        __slots__ = ()

        def open(self, authority, revision):
            with (
                access(self, "RUNTIME") as (runtime, _),
                _pinned_cie_parent(runtime.parent, authority, revision, core=True) as (
                    _,
                    item,
                    core_binding,
                ),
            ):
                if item.cie_child is not None:
                    raise CIEAbort(FailureCode.CIE_STALE)
                if item.cie_sequence >= runtime.policy.max_cies:
                    raise CIEAbort(FailureCode.CAPACITY_ABORT)
                environment = CognitiveEnvironmentBinding(
                    core_binding, runtime.l2_policy, runtime.l3_policy
                )
                try:
                    binding = _snapshot(
                        CIEBinding(
                            CIEIdentity(item.cause, item.cie_sequence),
                            revision,
                            environment,
                        )
                    )
                    snapshot = ArenaSnapshot(SnapshotBinding(binding, 0, 0), ())
                    checked_snapshot(runtime, snapshot)
                    image = canonical_identity_bytes(binding)
                    token = object.__new__(CognitiveInferenceEpoch)
                    epoch = _Epoch(
                        runtime, authority, item, binding, image, snapshot=snapshot
                    )
                    key = id(token)

                    @_deferred_cleanup
                    def discard_epoch(reference):
                        with _pinned_cie_parent(runtime.parent, authority), epoch.lock:
                            if not epoch.terminal:
                                epoch.finish("ABORTED")
                            with registry_lock:
                                handles.pop(key, None)
                                runtime.epochs.pop(key, None)

                    registered = (
                        ref(token, discard_epoch),
                        runtime,
                        "CIE",
                        CognitiveInferenceEpoch,
                        epoch,
                    )
                    new_epochs = dict(runtime.epochs)
                    new_epochs[id(token)] = epoch
                    next_sequence = item.cie_sequence + 1
                    next_children = item.nondelegated_children + 1
                    with registry_lock:
                        # Exact int-key builtin insertion is the only remaining
                        # allocation. If it fails, no owner state was published.
                        # All following assignments are prebuilt pointer swaps;
                        # no global registry scan/copy is required.
                        handles[id(token)] = registered
                        runtime.epochs = new_epochs
                        item.cie_child = epoch
                        item.cie_sequence = next_sequence
                        item.nondelegated_children = next_children
                        runtime.opened = True
                    return token
                except (TypeError, ValueError) as error:
                    raise CIEAbort(FailureCode.CAPACITY_ABORT) from error

        def snapshot(self, cie):
            with access(cie, "CIE") as (runtime, epoch):
                check_runtime(self, runtime)
                with epoch_guard(runtime, epoch):
                    return clone_snapshot(epoch.snapshot)

        def status(self, cie):
            with access(cie, "CIE") as (runtime, epoch):
                check_runtime(self, runtime)
                with _pinned_cie_parent(runtime.parent, epoch.authority), epoch.lock:
                    return epoch.terminal or "OPEN"

        def stage(self, cie, snapshot, additions):
            """Claim frozen round BEFORE building. No same-round visibility.

            An orchestrator supplies the full bounded, already-produced batch.
            This shell discovers/executes no cognitive work and charges nothing.
            """
            with access(cie, "CIE") as (runtime, epoch):
                check_runtime(self, runtime)
                if runtime.reasoning_policy is not None:
                    raise CIEAbort(FailureCode.EXEMPTION_CONTRACT_VIOLATION)
                with epoch_guard(runtime, epoch, core=True):
                    if type(snapshot) is not ArenaSnapshot:
                        raise CIEAbort(FailureCode.INVALID_INPUT)
                    try:
                        source = snapshot.canonical_bytes
                    except (TypeError, ValueError) as error:
                        raise CIEAbort(FailureCode.INVALID_INPUT) from error
                    if source != epoch.snapshot.canonical_bytes:
                        raise CIEAbort(FailureCode.CIE_STALE)
                    if epoch.pending is not None:
                        raise CIEAbort(FailureCode.CIE_STALE)
                    if (
                        epoch.snapshot.binding.round_identity
                        >= runtime.policy.max_rounds
                    ):
                        terminal_failure(epoch, FailureCode.CAPACITY_ABORT)
                    # Bound the tuple BEFORE inspecting even its first member.
                    if type(additions) is not tuple:
                        raise CIEAbort(FailureCode.INVALID_INPUT)
                    if len(additions) > runtime.policy.max_staged_entries:
                        terminal_failure(epoch, FailureCode.CAPACITY_ABORT)
                    token = object.__new__(RoundStagingArena)
                    stage = _Stage(epoch, token, source)
                    registered = (
                        ref(token),
                        runtime,
                        "STAGE",
                        RoundStagingArena,
                        stage,
                    )
                    staged_ids = set(runtime.stage_ids)
                    staged_ids.add(id(token))
                    with registry_lock:
                        handles[id(token)] = registered
                        runtime.stage_ids = staged_ids
                        epoch.pending = stage
                # Private physical build runs outside Core/lifecycle/arena.
                try:
                    frozen = tuple(freeze_entry(entry) for entry in additions)
                    by_key = {}
                    for entry in frozen:
                        key = entry_key(entry)
                        previous = by_key.get(key)
                        if previous is not None and canonical_identity_bytes(
                            previous.canonical_descriptor()
                        ) != canonical_identity_bytes(entry.canonical_descriptor()):
                            raise CIEAbort(FailureCode.INTERNAL_CONTRACT_VIOLATION)
                        by_key[key] = entry
                    ordered = tuple(by_key[key] for key in sorted(by_key))
                except (TypeError, ValueError, IngressAbort) as error:
                    code = (
                        error.code
                        if isinstance(error, IngressAbort)
                        else FailureCode.INVALID_INPUT
                    )
                    with epoch_guard(runtime, epoch):
                        terminal_failure(epoch, code)
                except BaseException:
                    with epoch_guard(runtime, epoch):
                        epoch.finish(FailureCode.INTERNAL_CONTRACT_VIOLATION.value)
                    raise
                with epoch_guard(runtime, epoch, core=True):
                    if epoch.pending is not stage:
                        terminal_failure(epoch, FailureCode.INTERNAL_CONTRACT_VIOLATION)
                    stage.additions = ordered
                return token

        def publish(self, cie, staging, *, terminal=False):
            if type(terminal) is not bool:
                raise CIEAbort(FailureCode.INVALID_INPUT)
            with (
                access(cie, "CIE") as (runtime, epoch),
                access(staging, "STAGE") as (stage_runtime, stage),
            ):
                check_runtime(self, runtime)
                with epoch_guard(runtime, epoch, core=True):
                    if (
                        stage_runtime is not runtime
                        or stage.epoch is not epoch
                        or epoch.pending is not stage
                        or stage.additions is None
                        or stage.base != epoch.snapshot.canonical_bytes
                    ):
                        raise CIEAbort(FailureCode.CIE_STALE)
                    try:
                        entries = {
                            entry_key(entry): entry for entry in epoch.snapshot.entries
                        }
                        for entry in stage.additions:
                            key = entry_key(entry)
                            previous = entries.get(key)
                            if (
                                previous is not None
                                and previous.canonical_descriptor()
                                != entry.canonical_descriptor()
                            ):
                                terminal_failure(
                                    epoch, FailureCode.INTERNAL_CONTRACT_VIOLATION
                                )
                            entries[key] = entry
                        if len(entries) > runtime.policy.max_entries:
                            terminal_failure(epoch, FailureCode.CAPACITY_ABORT)
                        old_binding = epoch.snapshot.binding
                        new_binding = SnapshotBinding(
                            epoch.binding,
                            old_binding.arena_version + 1,
                            old_binding.round_identity + 1,
                        )
                        candidate = ArenaSnapshot(
                            new_binding, tuple(entries[k] for k in sorted(entries))
                        )
                        checked_snapshot(runtime, candidate)
                        output_snapshot = clone_snapshot(candidate)
                        output = (
                            CognitiveResultView("PUBLISHED", output_snapshot)
                            if terminal
                            else output_snapshot
                        )
                    except (TypeError, ValueError) as error:
                        terminal_failure(epoch, FailureCode.CAPACITY_ABORT)
                        raise AssertionError("unreachable") from error
                    except CIEAbort as error:
                        if (
                            error.code is FailureCode.CAPACITY_ABORT
                            and not epoch.terminal
                        ):
                            terminal_failure(epoch, error.code)
                        raise
                    except BaseException:
                        epoch.finish(FailureCode.INTERNAL_CONTRACT_VIOLATION.value)
                        raise
                    # The ONLY version/round publication. No builder order,
                    # partial additions, charge or new child appears here.
                    epoch.snapshot = candidate
                    epoch.pending = None
                    stage.additions = None
                    with registry_lock:
                        handles.pop(id(staging), None)
                        runtime.stage_ids.discard(id(staging))
                    if terminal:
                        epoch.finish("PUBLISHED")
                    return output

        def abort(self, cie):
            with access(cie, "CIE") as (runtime, epoch):
                check_runtime(self, runtime)
                with epoch_guard(runtime, epoch):
                    output = CognitiveResultView(
                        "ABORTED", clone_snapshot(epoch.snapshot)
                    )
                    epoch.finish("ABORTED")
                    return output

    def create_cie_runtime(parent, *, l2_config=None, policy=None):
        """Trusted composition root: freeze exact typed runtime-owned policies.

        No arbitrary CEB/policy descriptor/currentness callback is accepted.
        One attachment per Invocation runtime; retirement cannot refresh limits.
        """
        if l2_config is None:
            l2_config = MemoryConfig()
        if policy is None:
            policy = CIEPolicy()
        if (
            type(parent) is not InvocationRuntime
            or type(l2_config) is not MemoryConfig
            or type(policy) is not CIEPolicy
        ):
            raise CIEAbort(FailureCode.INVALID_INPUT)
        l2_config.__post_init__()
        policy.__post_init__()
        frozen_l2 = MemoryConfig(
            **{f.name: getattr(l2_config, f.name) for f in fields(MemoryConfig)}
        )
        l2 = _snapshot(
            CanonicalDescriptor(
                "MemoryConfig",
                tuple(
                    (f.name, getattr(frozen_l2, f.name)) for f in fields(MemoryConfig)
                ),
            )
        )
        frozen_policy = CIEPolicy(
            **{f.name: getattr(policy, f.name) for f in fields(CIEPolicy)}
        )
        l3 = _snapshot(
            CanonicalDescriptor(
                "L3Unit4PolicyBinding",
                (
                    frozen_policy.canonical_descriptor(),
                    CanonicalDescriptor(
                        "ValueLimits",
                        tuple(
                            (f.name, getattr(DEFAULT_VALUE_LIMITS, f.name))
                            for f in fields(DEFAULT_VALUE_LIMITS)
                        ),
                    ),
                ),
            )
        )
        with _pinned_cie_parent(parent, core=True) as (domain, _, _):
            if domain.cie_attached:
                raise CIEAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
            owner = object.__new__(CIERuntime)
            runtime = _Runtime(parent, frozen_policy, l2, l3)

            @_deferred_cleanup
            def discard(reference):
                with _pinned_cie_parent(parent):
                    for epoch in runtime.epochs.values():
                        epoch.parent_close()
                    runtime.retired = True
                    with registry_lock:
                        handles.pop(id_owner, None)
                        for key, epoch in runtime.epochs.items():
                            handles.pop(key, None)
                        # Remove staging handles by their local epoch indexes,
                        # never a global registry scan (see stage cleanup below).
                        for key in runtime.stage_ids:
                            handles.pop(key, None)
                    runtime.epochs = {}

            id_owner = id(owner)
            owner_ref = ref(owner, discard)
            runtime.owner_ref = owner_ref
            registered = (owner_ref, runtime, "RUNTIME", CIERuntime, None)
            with registry_lock:
                handles[id_owner] = registered
                domain.cie_attached = True
            return owner

    @contextmanager
    def pinned_work_policy(handle, parent):
        with access(handle, "RUNTIME") as (runtime, _):
            if runtime.parent is not parent or runtime.opened or runtime.work_attached:
                raise CIEAbort(FailureCode.INVALID_POLICY_BINDING)
            yield runtime

    @contextmanager
    def pinned_cie_work(handle, token, item, snapshot, core_binding):
        """Arena-only bridge. Trusted dispatch already holds Core/Life/Ledger."""
        with (
            access(handle, "RUNTIME") as (runtime, _),
            access(token, "CIE") as (own, epoch),
        ):
            if own is not runtime or epoch.invocation is not item:
                raise CIEAbort(FailureCode.CIE_STALE)
            with epoch.lock:
                require_live(epoch)
                if item.lifecycle != (
                    InvocationState.ACTIVE,
                    epoch.binding.invocation_revision,
                ):
                    terminal_failure(epoch, FailureCode.PARENT_AUTHORITY_STALE)
                current = CognitiveEnvironmentBinding(
                    core_binding, runtime.l2_policy, runtime.l3_policy
                )
                if canonical_identity_bytes(current) != canonical_identity_bytes(
                    epoch.binding.environment
                ):
                    terminal_failure(epoch, FailureCode.ENVIRONMENT_STALE)
                if type(snapshot) is not SnapshotBinding or canonical_identity_bytes(
                    snapshot
                ) != canonical_identity_bytes(epoch.snapshot.binding):
                    raise CIEAbort(FailureCode.CIE_STALE)
                yield epoch

    @contextmanager
    def pinned_effect_context(handle, parent, *, bootstrap=False):
        # No Arena/lifecycle acquisition. Caller holds the genuine parent gate.
        with access(handle, "RUNTIME") as (runtime, _):
            if runtime.parent is not parent:
                raise CIEAbort(FailureCode.INVALID_POLICY_BINDING)
            if bootstrap and (runtime.opened or runtime.effect_attached):
                raise CIEAbort(FailureCode.INVALID_POLICY_BINDING)
            yield runtime

    def prepare_reasoning_publication(
        handle, token, item, snapshot, core, additions, terminal
    ):
        """Prebuild an exact arena pointer under the already-held Arena gate."""
        with (
            access(handle, "RUNTIME") as (runtime, _),
            access(token, "CIE") as (own, epoch),
        ):
            if (
                own is not runtime
                or epoch.invocation is not item
                or runtime.reasoning_policy is None
            ):
                raise CIEAbort(FailureCode.CIE_STALE)
            require_live(epoch)
            if epoch.pending is not None or epoch.snapshot.binding != snapshot:
                raise CIEAbort(FailureCode.CIE_STALE)
            if snapshot.round_identity >= runtime.policy.max_rounds:
                raise CIEAbort(FailureCode.CAPACITY_ABORT)
            if (
                type(additions) is not tuple
                or len(additions) > runtime.policy.max_staged_entries
            ):
                raise CIEAbort(FailureCode.CAPACITY_ABORT)
            entries = {entry_key(e): e for e in epoch.snapshot.entries}
            for entry in additions:
                frozen = freeze_entry(entry)
                k = entry_key(frozen)
                if (
                    k in entries
                    and entries[k].canonical_descriptor()
                    != frozen.canonical_descriptor()
                ):
                    raise CIEAbort(FailureCode.INTERNAL_CONTRACT_VIOLATION)
                entries[k] = frozen
            candidate = ArenaSnapshot(
                SnapshotBinding(
                    epoch.binding,
                    snapshot.arena_version + 1,
                    snapshot.round_identity + 1,
                ),
                tuple(entries[k] for k in sorted(entries)),
            )
            checked_snapshot(runtime, candidate)
            from .reasoning.assertions import semantic_records

            semantic_records(
                candidate.entries, runtime.reasoning_policy, candidate.binding
            )
            return epoch, candidate

    def reasoning_capacity(epoch, maximum_additions):
        # Sole active arena owner; a complete group's structural slot envelope
        # cannot be stolen while the genuine dispatch gate holds Life/Arena.
        policy = epoch.runtime.policy
        if (
            type(maximum_additions) is not int
            or maximum_additions < 0
            or maximum_additions > policy.max_staged_entries
            or len(epoch.snapshot.entries) + maximum_additions > policy.max_entries
            or epoch.snapshot.binding.round_identity >= policy.max_rounds
        ):
            raise CIEAbort(FailureCode.CAPACITY_ABORT)

    return (
        CIERuntime,
        create_cie_runtime,
        pinned_work_policy,
        pinned_cie_work,
        pinned_effect_context,
        prepare_reasoning_publication,
        reasoning_capacity,
    )


(
    CIERuntime,
    create_cie_runtime,
    _pinned_work_policy,
    _pinned_cie_work,
    _pinned_effect_context,
    _prepare_reasoning_publication,
    _check_reasoning_capacity,
) = _build_cie_system()
del _build_cie_system
