"""Shared pure target-grammar policy; callers own result-state semantics."""

import ast
import warnings

TARGET_GRAMMAR = (3, 13)


def parse_source(text: str) -> ast.Module:
    # Target warnings can contain literals; never forward them as diagnostics.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        warnings.simplefilter("ignore", DeprecationWarning)
        return ast.parse(
            text, filename="<repolens-source>", feature_version=TARGET_GRAMMAR, optimize=0
        )
