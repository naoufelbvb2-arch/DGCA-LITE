"""Closed ground constructors and bounded DeepReferentClosure. No text parser."""

from ..assertions import validate_ground_referent as validate_referent
from ..identity import CanonicalDescriptor, ClaimContentID
from ..serialization import canonical_identity_bytes


def d(kind, *values):
    return CanonicalDescriptor(kind, values)


def referent(kind, identity):
    node = d(kind, identity)
    validate_referent(node, kind)
    return node


def ground(kind, *values):
    content = ClaimContentID(d(kind, *values))
    validate(content)
    return content


def validate(content, *, allowed_referents=None):
    """Validate the complete closed AST before any schema reads semantic fields.

    A trusted formal source authorizes its entire typed ground constructor tree.
    An inference supplies its parent referent closure and may add no referent.
    """
    nodes = 0
    ancestors = set()
    referents = set()
    shapes = {
        "GroundAtom": (str,),
        "GroundConditional": (ClaimContentID, ClaimContentID),
        "GroundRelation": (CanonicalDescriptor,) * 3,
        "GroundState": (CanonicalDescriptor,) * 2,
        "Transitive": (CanonicalDescriptor,),
        "FormalNegation": (ClaimContentID,),
        "MutuallyExclusive": (CanonicalDescriptor,) * 2,
        "SingleValued": (CanonicalDescriptor,),
        "Assign": (CanonicalDescriptor,) * 3,
        "InternalRetrievalStatement": (bytes,),
        "PredictionOutcomeStatement": (bytes,),
        "CausalResultStatement": (bytes,),
        "ObservedCoreFrontier": (tuple, tuple),
    }

    def visit(claim, depth):
        nonlocal nodes
        nodes += 1
        if nodes > 64 or depth > 16 or type(claim) is not ClaimContentID:
            raise ValueError("FAB node/depth/type bound")
        if id(claim) in ancestors:
            raise ValueError("cyclic FAB")
        node = claim.descriptor
        if type(node) is not CanonicalDescriptor or type(node.kind) is not str:
            raise TypeError("unknown FAB node")
        shape = shapes.get(node.kind)
        if shape is None or type(node.values) is not tuple:
            raise TypeError("undeclared FAB operator")
        if len(node.values) != len(shape):
            raise ValueError("FAB outer arity")
        # No member type or semantics is inspected before the outer arity.
        if any(type(v) is not t for v, t in zip(node.values, shape, strict=True)):
            raise TypeError("FAB member type")
        ancestors.add(id(claim))
        try:
            for value in node.values:
                if type(value) is ClaimContentID:
                    visit(value, depth + 1)
            roles = {
                "GroundRelation": ("relation", "entity", "entity"),
                "GroundState": ("participant", "state"),
                "MutuallyExclusive": ("state", "state"),
                "Transitive": ("relation",),
                "SingleValued": ("slot",),
                "Assign": ("entity", "slot", "value"),
            }.get(node.kind, ())
            for value, role in zip(node.values, roles):
                validate_referent(value, role)
                referents.add(canonical_identity_bytes(value))
            if node.kind == "GroundAtom" and not 0 < len(node.values[0]) <= 256:
                raise ValueError("bounded nonempty proposition name required")
            if node.kind == "InternalRetrievalStatement" and len(node.values[0]) > 8192:
                raise ValueError("bounded retrieval literal required")
            if (
                node.kind in ("PredictionOutcomeStatement", "CausalResultStatement")
                and not 0 < len(node.values[0]) <= 65536
            ):
                raise ValueError("bounded typed prediction literal required")
            if node.kind == "ObservedCoreFrontier":
                frontier, activation = node.values
                if len(frontier) > 256 or len(activation) > 256:
                    raise ValueError("observation outer bounds")
                if any(type(v) is not int or v < 0 for v in frontier):
                    raise TypeError("closed observed Cell identities")
                if tuple(sorted(set(frontier))) != frontier:
                    raise ValueError("canonical observed frontier required")
                for pair in activation:
                    if type(pair) is not tuple or len(pair) != 2:
                        raise ValueError("activation outer pair bound")
                    if type(pair[0]) is not int or type(pair[1]) is not float:
                        raise TypeError("typed observed activation")
            if node.kind == "MutuallyExclusive" and node.values[0] == node.values[1]:
                raise ValueError("self exclusion")
        finally:
            ancestors.remove(id(claim))

    visit(content, 0)
    canonical_identity_bytes(content)
    if allowed_referents is not None and not referents <= allowed_referents:
        raise ValueError("inference invented a referent")
    return frozenset(referents)
