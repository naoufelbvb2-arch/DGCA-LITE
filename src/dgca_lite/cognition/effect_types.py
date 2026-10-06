"""Closed mechanical Unit-6 harness vocabulary, NOT production effect licences.

No semantic/domain effect type is enabled in Unit 6. These two internal test
operations exercise logical registry commits, with/without CIE requirements.
Only the private fixed harness catalogue accepts them. No callback registration.
"""

from enum import Enum


class _MechanicalEffectOperation(Enum):
    AUDIT_ONLY = "UNIT6_MECHANICAL_AUDIT_ONLY"
    CIE_AUDIT_ONLY = "UNIT6_MECHANICAL_CIE_AUDIT_ONLY"
