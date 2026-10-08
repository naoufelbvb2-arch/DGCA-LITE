"""Unit-10 executable acceptance ledger for canonical sections 113--119.

This is test evidence, not a second specification or a governance/freeze file.
Rows retain the verbatim canonical obligation. Each mapping names the concrete
assertion checked by its behavioral regression, not just a similarly named test.
PASS is emitted ONLY from an actual complete JUnit verification run in which
every associated parameterized case passed. Collection/name checks alone never
establish behavioral acceptance.

Run this module with the full-suite JUnit path to print all 295 reviewed rows.
"""

import ast
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC_SHA = "37e4f77bb427f75257e67e5f65ac2cd44bfa42c4844365a17ef6d9a009f4b6d1"

# key | test module | behavioral regression | observed assertion/gate
EVIDENCE = """
P01|prediction|genuine_root_source_not_exact_origin_branch|Trusted root provenance is distinct from associative branch provenance.
P02|prediction|target_discovery_preserves_source_specificity|Equal Cells in different source targets retain different typed target identities.
P03|prediction|exact_source_lane_no_unions|Only the exact root-seeded SourceView lane plus lawful anchors matches the entire sealed pattern; BranchViews/unions never repair missing Cells.
P04|prediction|atomic_only_root_witness|Atomic match requires a genuine root witness, not reconstructed associative activation.
P05|prediction|gap_advances_not_empty|Failed capture consumes the offset once and records OBSERVATION_GAP, never PROVEN_EMPTY.
P06|prediction|last_offset_match_wins_after_gap|A lawful match at H wins even after a previous gap.
P07|prediction|supported_target_missing_source_is_not_stale|Absent exact SourceView is nonmatch while its TargetGuard remains valid.
P08|prediction|seal_publication_failure_rolls_back_every_positive_component|Injected seal failure preserves escrow, FRR, FDA registry and commitment together.
P09|prediction|horizon_fail_closed_without_charge|Bool, zero, negative and over-policy logical horizons fail before charge.
P10|prediction|whole_mixed_origin_never_purifies|Selecting a trusted subset cannot upgrade mixed/internal projection origin to ROOT_ANCHORED.
P11|prediction|fda_cannot_open_cie_admit_invocation_or_use_general_budget|Genuine FDA cannot mint Invocation/CIE or consume another owner's general pool.
P12|prediction|boundary_first_prevents_window_admission|Termination-first admits no future evaluation.
P13|prediction|target_guard_removed_assembly_does_not_capture|Removed/replaced target fails currentness before capture allocation.
P14|prediction|genuine_receipt_cannot_call_private_future_delivery_outside_trusted_event|Copied/private-delivery inputs cannot create a genuine future occurrence.
P15|prediction|duplicate_delivery_zero_new_units_and_gap_never_rewritten|Same occurrence allocates neither capture nor evaluation again and cannot rewrite the append-only gap ledger.
P16|prediction|no_prediction_learning_feedback_complete_core_equality|Match/miss/gap Core state equals a control engine receiving only the same genuine events.
P17|prediction|capture_eval_use_exact_escrow_only_and_no_general_fallback|Capture/evaluate consume only the exact delegated pool, not parent general units.
P18|prediction|seal_linearizes_before_begin_close_and_fda_continues|Seal-first publishes all delegated components and FDA remains usable after parent close.
P19|prediction|evaluation_then_cancel_is_linearizable|Evaluation-first result survives subsequent cancellation; termination cannot backdate it.
P20|prediction|explicit_empty_trusted_capture_not_missing|Lawfully proven empty capture advances complete coverage without a gap.
P21|prediction|no_internal_or_descriptor_observation_ingress|Internal results, modal views and copied descriptors fail trusted observation admission.
P22|prediction|full_default_horizon_gap_coverage_completes|Entire logical unmatched horizon with a gap terminalizes INCONCLUSIVE, not PENDING or negative evidence.
P23|prediction|nonmatch_advances_and_final_closes|A fully covered unmatched horizon terminalizes WINDOW_ELAPSED_WITHOUT_MATCH.
P24|prediction|insufficient_complete_escrow_no_partial_seal|A complete commitment that cannot reserve its whole escrow publishes nothing.
P25|prediction|prediction_adapter_retains_modal_root_and_never_negative_assertion|MATCH remains PREDICTION_VIEW; miss does not become FormalNegation and all views retain their modal root.
P26|prediction|core_event_order_not_thread_completion_orders_offsets|Offset order is genuine Core occurrence order, independent of worker completion.
P27|prediction|seal_idempotent_and_parent_closed_cannot_recover_authority|Exact seal retry is history, not backdating or fresh FDA issuance after close.
P28|prediction|terminal_state_clears_private_cognition_and_retires_only_unused|Terminal forecast releases semantic payload and retires only unused, nontransferable units.
C01|causality|exact_prospective_classifier|Exact expected/explicit contrary/unlisted outcomes classify MATCH/CONFLICT/UNRESOLVED respectively.
C02|causality|missing_is_unresolved_not_negative|Missing/failed measurement is UNRESOLVED, not implicit negative/CONFLICT.
C03|causality|classifier_overlap_duplicate_order_rejected|Expected and explicit conflict sets cannot overlap or be noncanonical.
C04|causality|incomplete_slots_no_selection_or_partial_result|Every prospective slot is reported; unresolved slots cannot be omitted for a favorable comparison.
C05|causality|same_crci_disagreement_detected_not_new_evidence|Same deterministic CRCI with disagreeing outcomes is CONTRACT_VIOLATION, not independent support.
C06|causality|new_origin_different_crci|Changing exact ReplayOrigin changes CRCI even for equal selected outcomes.
C07|causality|replay_complete_rict_e_and_budget|Genuine complete isolated replay yields scoped RICTE and exact escrow conservation.
C08|causality|independent_comparator_reuse_rejected|One trusted occurrence cannot supply independent comparator slots.
C09|causality|observational_occurrence_idempotent_and_distinct|Same occurrence replay is idempotent; independent authorized occurrences remain distinct.
C10|causality|interventional_request_not_application|Request/hypothesis data cannot substitute for genuine AppliedInterventionReceipt.
C11|causality|randomization_not_inferred_from_application|Application authority is not protocol/randomization authority.
C12|causality|environment_aba_invalidates_origin_study_rce|Monotone replay environment revision rejects A-B-A reuse despite descriptor equality.
C13|causality|bound_physical_and_measurement_contract|Physical closure, isolation, exogenous schedule and measurement must match their exact frozen contract.
C14|causality|classifier_mutation_after_open_not_active_plan_revision|Post-observation classifier mutation cannot replace the prospective plan.
C15|causality|domain_issuer_pinned_through_final_publication|Study/RCE/environment/issuer remain current through atomic final result issuance.
C16|causality|close_wins_race_with_result_publication|Parent-close-first forbids late paid causal publication without refund.
C17|causality|study_abort_invalidates_late_receipts_and_historical_views|Study abort revokes RCE/late receipts; historical views cannot revive owners.
C18|causality|internal_and_hypothetical_data_not_cases|Internal/derived/hypothetical content cannot mint trusted causal case authority.
C19|causality|genuine_fda_cannot_open_study_or_pay_causal_work|FDA and forecast pool cannot become study authority or causal escrow.
C20|causality|learned_core_and_temporal_context_conserved|Causal work preserves complete learned Core and temporal state.
C21|causality|lifetime_study_capacity_and_no_semantic_history|Prospective bounded study capacity is nonrenewable and terminal records retain no cognitive payload.
C22|causality|frontier_independent_of_outcome_and_remaining_budget|Frozen case work frontier is not selected by observed outcome or residual budget.
C23|causality|rce_registry_rollback_revokes_reused_weak_handle_id|Failed insertion and reused weak IDs cannot revive a rolled-back RCE.
C24|causality|returned_origin_and_bundle_do_not_alias_private_state|Returned immutable data cannot mutate the operational replay origin/bundle.
C25|causality|equal_outcomes_not_no_effect|SAME outcomes issue only scoped comparison data, never universal NO_EFFECT.
C26|causality|causal_adapter_is_modal_literal_not_formal_rule|Causal result is literal CAUSAL_RESULT_VIEW with mandatory origin, not CAUSES or a rule license.
C27|causality|escrow_charge_is_causal_not_general|Causal owner spends its own frozen escrow, never parent/forecast fallback.
C28|causality|repetitions_one_identity_not_new_evidence|Repeated same CRCI is verification, not independent causal evidence.
C29|causality|full_treatment_identity|Exposure/mechanism/schedule differences remain distinct complete treatment/CRCI identities.
C30|causality|branch_and_receipt_completion_order_not_result_identity|Lawful branch completion permutations preserve canonical result bytes.
C31|causality|begin_close_aborts_studies_rces_and_retires|Invocation closing aborts child studies/RCEs and retires unused study escrow.
C32|causality|outcome_based_substitution_rejected|Observed outcome cannot select replacement cases or alter the stopping rule.
C33|causality|bundle_complete_opaque_exact_rce|Incomplete, foreign or unbound influence/controller bundles fail exact RCE validation.
R01|reasoning|schema_is_closed_not_caller_selected|Only the two frozen exact InferenceSchema descriptors dispatch; caller extensions are rejected.
R02|reasoning|ground_mp_no_implicit_execution|Formal conditional content alone does not execute; exact conditional and ordinary premise derive only DERIVED conclusion.
R03|reasoning|transitive_composition_needs_explicit_exact_property|No relation-name convention activates composition without authorized exact Transitive(R).
R04|reasoning|derived_ordinary_later_round_not_same_round|DERIVED ordinary assertions are usable only in a later committed synchronous round.
R05|reasoning|nonformal_rule_role_rejected_before_support_matching|All nonformal bases are rejected in formal conditional/transitivity roles before support matching.
R06|reasoning|derived_conditional_cannot_be_rule|DERIVED GroundConditional cannot acquire formal rule-premise authority.
R07|reasoning|derived_transitivity_property_cannot_activate_composition|DERIVED Transitive(R) cannot license composition.
R08|reasoning|assumption_dependencies_never_discharge|Derived EDS is exact parent union and formal assumptions never discharge their root.
R09|reasoning|duplicate_source_occurrences_do_not_multiply_work|Exact source replay creates no duplicate support/frontier; independent support is not confidence arithmetic.
R10|reasoning|content_cycle_has_independent_support_but_no_circular_justification|No conclusion appears in its support ancestry.
R11|reasoning|independent_support_survives_circular_alternative|A circular alternative cannot erase an independent lawful acyclic support.
R12|reasoning|scope_identity_never_broadens|Different exact ScopeIdentity premises do not compose.
R13|reasoning|deep_closure_and_cycles_and_opaque_metadata|Closed FAB rejects invented deep referents, cycles and opaque payloads.
R14|reasoning|multi_candidate_budget_group_never_publishes_first_n|Insufficient complete group budget publishes no favored prefix of candidates.
R15|reasoning|incomplete_semantic_group_has_no_partial_publication|Capacity excess is explicit incompleteness with no partial semantic group publication.
R16|reasoning|real_internal_l2_result_enters_reasoning_without_strengthening|Actual L2 result remains INTERNAL_RETRIEVAL with lineage, never formal/trusted authority.
R17|reasoning|support_context_and_cycle|Foreign producing context and circular parent support fail current-context rederivation.
R18|reasoning|core_and_layer2_never_mutate|Reasoning leaves canonical complete lower-layer state unchanged.
R19|reasoning|ancestry_bound_is_incompleteness_not_fixed_point|An unrepresentable next frontier is CAPACITY_ABORT, never a falsely complete fixed point.
F01|reasoning|natural_language_negation_is_not_formal|Text 'not P' cannot mint formal proposition complement.
F02|reasoning|negation_blocks_exact_use_no_ex_falso|Exact formal negation blocks the use but preserves assertions and never derives arbitrary Q.
F03|reasoning|b02_exact_state_conflict_symmetry_preserves_assertions|Explicit same-participant state conflict is symmetric and never deletes its participants.
F04|reasoning|b02_no_heuristic_conflict_or_interaction|Relation argument position/overlap and different participants do not activate mutual exclusion.
F05|reasoning|b02_formal_constraint_shape_rejects_before_issuance|MutuallyExclusive requires StateIdentity referents, not proposition operands.
F06|reasoning|all_three_constraint_families_and_exact_assignments|SingleValued checks exact entity/slot unequal values only; no missing-value/exactly-one rule exists.
F07|reasoning|derived_constraint_shape_cannot_self_activate|Derived constraint-shaped content remains data and does not enter active constraints.
F08|authority_ingress|nonformal_data_cannot_activate_constraints|Only genuine formal constraint-source issuance under the allowed bases admits active premises.
F09|reasoning|b02_constraint_assumption_and_participant_eds_exact|Finding EDS equals participant union plus active constraint dependencies.
F10|reasoning|duplicate_constraint_sources|Duplicate constraint sources preserve one semantic constraint without multiplying work.
F11|reasoning|constraint_assumption_branches|AEC activates its assumed constraint even if that root is absent from the ordinary premises; foreign branch cannot block base.
F12|reasoning|profile_cannot_omit_relevant_family|All required families are validated and fake NotApplicable/no-interaction certificates are rejected.
F13|reasoning|incomplete_or_positive_is_not_clearance|Incomplete/positive findings cannot mint clearance or compatibility propositions.
F14|reasoning|historical_clearance_and_stale_snapshot_cannot_publish|Clearance is exact schema, role, AEC, snapshot and environment use-bound, not reusable authority.
F15|reasoning|query_order_and_incomplete_coverage|EXISTS selects the canonical first witness independently of input order; ENUMERATE_ALL requires full coverage.
F16|reasoning|b02_relation_overlap_has_empty_mutual_exclusion_check_frontier|R(A,B), R(B,C) overlap creates no participant-state interaction.
F17|reasoning|b02_exact_constraint_scope_does_not_broaden|An active constraint cannot broaden its exact scope into another use.
I01|authority_ingress|object_new_and_copied_fields_cannot_forge_capability|object.__new__, copied fields and fake issuers do not validate live occurrence authority.
I02|authority_ingress|nested_capabilities_and_live_lower_layer_handles_fail_closed|Closed cognitive metadata rejects nested live capabilities/receipts.
I03|authority_ingress|same_occurrence_replay_and_independent_equal_content_are_distinct|Genuine source replay is idempotent; independently authorized equal content is a distinct occurrence.
I04|authority_ingress|observation_requires_genuine_receipt_and_occurrence_is_not_content|Only genuine current trusted occurrence authority issues EXTERNAL_OBSERVATION.
I05|authority_ingress|genuine_internal_and_trusted_l2_result_views_cannot_reenter_ingress|L2 result/RootView data does not reconstruct genuine receipt/occurrence authority.
I06|authority_ingress|given_and_assumption_bases_have_exact_constructor_dependencies|Basis constructors preserve their exact formal source/assumption roots; empty EDS does not grant truth authority.
I07|authority_ingress|descriptors_copied_views_and_basis_labels_are_not_capabilities|Canonical descriptors/basis labels cannot self-mint formal, observation or constraint authority.
I08|authority_ingress|capability_copy_and_serialization_are_rejected|Copy/deepcopy/pickle/serialization cannot transport a live handle.
I09|authority_ingress|core_transition_barrier_covers_network_commit_and_temporal_publication|Trusted capture cannot observe Network/TemporalStream transition tearing.
T01|invocation_budget|object_new_forgery_never_validates|Forged InvocationAuthority/ledger handles fail issuer validation.
T02|invocation_budget|one_cause_one_authority_one_nonrenewable_budget|Transport retry of one InvocationCause cannot mint fresh budget.
T03|cie_arena|second_simultaneous_cie_rejected_and_sequential_indices_not_reused|One invocation has one active CIE and never reuses a closed CIE identity.
T04|cie_arena|stale_ceb_at_publication_terminalizes_without_backdating|Stale CEB cannot publish; prior immutable snapshot remains history.
T05|work_authorization|real_runtime_lock_inversions_cannot_call_accounting_or_core|Operator cannot call Core/accounting under later-ranked Work locks.
T06|work_authorization|complete_gate_uses_all_six_lock_ranks|Actual charged gate obeys Core < Life < Budget < Arena < Owner < Registry.
T07|cie_arena|close_does_not_wait_for_private_stage_builder|BeginClose is nonwaiting under Life; resumed child cannot publish.
T08|work_authorization|stale_revision_cannot_authorize|Stale/noncanonical owner revision fails before spending work.
T09|work_authorization|wrong_reservation_cross_owner_and_cross_runtime|Wrong/zero/ambiguous reservation-owner binding cannot authorize WEP.
T10|work_authorization|caller_contract_classification_cannot_override_policy|Caller budget/effect/authority classification cannot override the frozen operation contract.
T11|invocation_budget|double_consumption_retired_resurrection_and_reservation_reuse|Consumed/retired units cannot be reused or resurrected.
T12|work_authorization|two_concurrent_execution_claims_run_worker_once|One WEP authorizes one pure worker claim only.
T13|work_authorization|running_worker_finishes_after_close_without_publication|Preauthorized pure work may finish locally but cannot publish after owner closure.
T14|effect_commit|close_first_consumes_nothing_and_publishes_nothing|Effect commit after closure is rejected, not deferred dispatch.
T15|effect_commit|nested_alias_capture_and_post_commit_payload_target_mutation|Committed effect payload is privately frozen and cannot be retargeted by returned aliases.
T16|effect_commit|altered_retry_requires_new_lawful_commit_and_charge|EffectCommit history cannot authorize a different effect.
T17|effect_commit|concurrent_duplicate_commits_converge_and_consume_once|Exact transport retries converge on one commit/charge.
T18|effect_commit|no_internal_reingress_or_deferred_children_after_close|Result/effect descriptors cannot recreate children after parent closure.
T19|work_authorization|exact_six_exempt_handlers_are_administrative_only|Exemption catalogue is exactly the six frozen administrative handlers.
T20|work_authorization|seventh_and_semantic_exemptions_fail_closed|Unknown or semantic exemption is rejected before work.
T21|work_authorization|exempt_dispatch_cannot_hide_callbacks_traversal_or_publication|Exempt wrappers cannot run semantic callbacks, retrieval, traversal or publication.
T22|effect_commit|pure_charge_wep_and_worker_output_cannot_authorize_effect|Pure compute has no effect authority API; effectful work cannot disguise itself as pure.
T23|effect_commit|every_adjacent_lock_inversion_is_rejected|Each neighboring barrier inversion fails before acquisition.
T24|work_authorization|worker_failure_burns_permit_without_refund|Substantive failed work consumes its permit/charge without refund.
T25|cie_arena|complete_lower_layer_and_budget_conservation|CIE lifecycle leaves Core/L2 persistent state unchanged and preserves exact budget accounting.
T26|work_authorization|dispatch_epoch_is_authorization_order_not_completion|Administrative ordinal assignment is authorization order, not scheduling-dependent semantic ranking.
T27|effect_commit|interruption_after_budget_swap_rolls_back_before_logical_commit|Fault injection rolls back unpublished budget/registry/effect pointer together.
U01|integration_closure|minimal_atomic_prediction_actual_modal_derivation|Actual genuine H1 MATCH imports one complete Prediction view and paid Reasoning derives Q with exact modal EDS under existing bounds.
U02|integration_closure|genuine_rict_e_actual_modal_derivation|Actual scoped RICTE imports one complete Causal view and paid Reasoning derives Q without any stronger basis.
U03|integration_closure|modal_roots_survive_actual_later_synchronous_round|Actual Q then R derivations in committed rounds preserve complete modal roots and lineage.
U04|integration_closure|shared_three_capability_chain_budget_and_conservation|One highest runtime executes all three capabilities; general/forecast/causal pools and lower-layer state are conserved.
U05|integration_closure|full_stack_close_vs_replay_publication_fda_survives|Same stack close rejects late paid replay publication, aborts studies/RCEs without waiting, and delegated FDA continues independently.
U06|integration_closure|complete_import_capacity_abort_has_no_partial_modal_group|Legitimate small snapshot capacity returns CAPACITY_ABORT with no partial view/assertion/support group or Core change.
U07|integration_closure|canonical_modal_group_allocation_independent_of_completion|Complete canonical import ordinal allocation ignores lawful thread completion ordering and exact replay creates no duplicate group.
""".strip()

# Each position is the corresponding exact bullet in the pinned specification.
# These assignments are reviewed manually; no keyword matching or coverage
# inference is used. Multiple keys require ALL their behavioral cases to pass.
SECTION_EVIDENCE = {
    113: """P10 P01 P02 P03 P03 P03 P03 P03 P03 P03 P03 P03 P07 P03
    P04 P04 P27 P24 P14 P15 P15 P15 P13 P08 P01+P18 P12 P13
    P16 P16 P05 P09 P06 P05 P20 P22 P23 P12+P19 P13+P03+P05
    P15+P17 P11+C19 P18 P17""",
    114: """C18+C26 C19+C18 C14 C22+C32 C04 C08 C09 C32 C02 C01
    C01 C01 C02 C02 C14 C01+C18 C03 C10 C18 C11 C13 C33 C12
    C13 C13 C07 C28 C05 C15 C06 C25 C07+C26 C26 C31 C17 C16 C21+C27""",
    115: """R16+R05 R01 R02 R03 R03 R03 I06+I07 R02+I06 R02
    R08 R08+U03 R10 R11 R04 R14 T10 R13 R12 R09 R01 R06 R07 R04 R19+R02""",
    116: """F04 F01 F02 F03 F04 F05 F03 F16 F06 F06 F07 F08 F09
    F10 F11 F11 F11 F12 F12 F13+F15 F14 F15 F15 F03+F02 F13
    F13+F15 R17+F14 F02""",
    117: """U03 U01+U02+I07 I02+U01 I02+U02 I02 I08+T18 P25
    C26 I05+P21 I01 I04 I03 I05+R16 T18+C17+P27""",
    118: """T06+T23 T07+U05 P18+P12 C16+U05 T13+T14 T08 T09
    T09 T10 P08+P17 P17+C19 T22 T22 T13 T14 T15 T16 T17 T18
    T19 T20 T21 T21 T21""",
    119: """T01 T02 T03 T04 I09 T05 T05+T10 T26+R14
    P10 P10 P27 P15 P21+P25 P16 P16 P25 P11 C19 P11 P11+P27 P17 P18+P12
    C18+C26 C19+C18 C18 C10 C10 C11 C13 C33 C33 C14 C05 C06 C28 C25 C26 C20 C16 C17
    R05+R16 R03+R05 R03 R02 R08 R10 R04 R14 R13 R12
    F01 F04 F07 F10 F11 F11 F12 F12 F13+F15 F14 F14 F14 F15 F02 F02+R18 F02 R17+F14
    U03 U02+I07 I02 I02 I01+I07 R16+I07 I05+P21 F08 I05
    T08+T13 T09 T09 T10 T11 T11 T12 T13 T14 T15 T16 T17 T18 T20 T21 T21 T23 T07 T25+C21+P28
    I01 I03 R09 P13 P15 P08 C22+C32 C04 C08 C12 C15 C29 C09 F09 R17 P17+C19 T20
    P03 P03 P03 P03 P04 P06 P05+P15 P20 P22 P23 P15 P12 P19 P06""",
}


def evidence():
    result = {}
    for line in EVIDENCE.splitlines():
        identifier, module, name, check = line.split("|", 3)
        assert identifier not in result
        result[identifier] = (module, "test_" + name, check)
    return result


def obligations():
    data = (ROOT / "03_COGNITION.md").read_bytes()
    assert hashlib.sha256(data).hexdigest() == SPEC_SHA
    text = data.decode("utf8")
    sections = {}
    for section in range(113, 120):
        part = text.split(f"# {section}. ", 1)[1].split(f"# {section + 1}. ", 1)[0]
        sections[section] = (
            re.findall(r"^A\d{2,3} (.+)$", part, re.MULTILINE)
            if section == 119
            else re.findall(r"^- (.+)$", part, re.MULTILINE)
        )
    return sections


def rows():
    checks = evidence()
    result = []
    for section, contents in obligations().items():
        assignments = SECTION_EVIDENCE[section].split()
        assert len(contents) == len(assignments), (
            section,
            len(contents),
            len(assignments),
        )
        for index, (obligation, assignment) in enumerate(
            zip(contents, assignments, strict=True), 1
        ):
            result.append(
                {
                    "id": f"A{index:02}" if section == 119 else f"{section}.{index:02}",
                    "section": section,
                    "obligation": obligation,
                    "evidence": tuple(checks[k] for k in assignment.split("+")),
                }
            )
    return result


def verification_matrix(junit_path):
    """Use actual behavioral-run results, including every parameter instance."""
    executed = {}
    for case in ET.parse(junit_path).iter("testcase"):
        module = case.attrib["classname"].split(".")[-1]
        name = case.attrib["name"].split("[", 1)[0]
        executed.setdefault((module, name), []).append(
            all(case.find(tag) is None for tag in ("failure", "error", "skipped"))
        )
    matrix = []
    for row in rows():
        passed = all(
            (cases := executed.get(("test_" + module, name))) and all(cases)
            for module, name, _check in row["evidence"]
        )
        matrix.append(dict(row, status="PASS" if passed else "BLOCKED"))
    return matrix


def test_acceptance_manifest_covers_every_canonical_obligation():
    counts = {113: 42, 114: 37, 115: 24, 116: 28, 117: 14, 118: 24, 119: 126}
    assert {s: len(v) for s, v in obligations().items()} == counts
    ledger = rows()
    assert len(ledger) == len({r["id"] for r in ledger}) == 295
    for module, name, check in evidence().values():
        source = (Path(__file__).parent / f"test_{module}.py").read_text(
            encoding="utf8"
        )
        methods = {
            n.name: n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
        }
        method = next(
            n
            for n in ast.parse(source).body
            if isinstance(n, ast.FunctionDef) and n.name == name
        )
        # Regression bodies have concrete assertions or rejection assertions;
        # do not accept a label, empty test, xfail or placeholder as evidence.
        assert check and any(
            isinstance(n, ast.Assert)
            or (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr == "raises"
            )
            for tree in (
                method,
                *(
                    methods[call.func.id]
                    for call in ast.walk(method)
                    if isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id in methods
                ),
            )
            for n in ast.walk(tree)
        ), name


if __name__ == "__main__":
    matrix = verification_matrix(sys.argv[1])
    for row in matrix:
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))
    assert len(matrix) == 295 and all(row["status"] == "PASS" for row in matrix)
