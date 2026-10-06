# Static Python testing observations

`TestingStaticAnalyzer` (`testing-static`, Category.TESTING) consumes only the
existing detached bounded PythonSourceSnapshot. It never reads files, imports
target code, executes tests/conftest/nox, installs dependencies or loads plugins.
Registration, execution and explicit-policy reports use unchanged Phase 3 APIs.

## Exact observed conventions

Candidate filenames match `test_.+.py` or `.+_test.py` literally: a nonempty
name segment is required, the suffix is exactly lowercase `.py`, and matching
is case-sensitive on every platform. Candidates can be at the root or any depth;
a `tests/` directory alone is insufficient. Exact ancestor components `example`,
`examples`, `fixture`, `fixtures`, `testdata`, `test_data` exclude candidate paths.
This deliberate conservative guard can omit real suites in those directories.
`myexamples/test_api.py` counts; `examples/test_demo.py` does not.
`tests/test_api.py` and `tests/api_test.py` count; `test_api.py.old`, `test_api.pyi`,
`conftest.py`, ordinary modules and nonstandard `checks.py` do not.
Existing acquisition eligibility/exclusions and source budgets still apply.

Within each candidate, inspect only direct module-level functions (including
async) with a `test_` prefix and nonempty suffix, and direct similarly named
methods in a module-level class whose name starts with `Test` or whose literal
base is `TestCase` or `unittest.TestCase`. These are syntactic shapes, not resolved
framework bindings. Aliases, inherited methods, conditional/nested declarations,
other attribute bases, generation and custom loaders are outside this convention.
A `Test*` class without a matching direct method is insufficient. Comments,
strings, fixture/import names and pytest/unittest imports alone are insufficient.
Decorators, constructors, rebinding and custom collectors can change collection;
even a recognized shape never proves collection, importability or execution.
No independent framework identity or framework-configuration finding is exposed.

## Rules and evidence

| ID | Severity | Observation |
| --- | --- | --- |
| TEST001 | INFO | No conventional Python test sources observed in the available snapshot |
| TEST002 | INFO | A candidate source has no directly visible conventional test declarations |

Both are advisories because custom discovery/generation can invalidate any
broader absence claim. TEST001 is repository-level evidence with no invented
path/line; its ID is `testing-static:TEST001`. TEST002 occurs once per candidate,
with its relative path and no invented line; its ID is
`testing-static:TEST002:` plus SHA-256 of the exact UTF-8 relative path. IDs omit
roots, timestamps and source literals. Findings sort by exact identifier and
never contain bodies, literals or parser diagnostics. The immutable typed catalog
validates stable TEST plus three-digit IDs, enum/category membership and text.
The analyzer selects no weights or penalties; INFO has zero deduction under
the domain contract and Phase 9 [product policy](../scoring-calibration.md).
Completed testing currently scores 100 even with these observations; that is
no measured test effectiveness or test pass rate.

## Configuration and coverage limits

Testing configuration is not interpreted in this phase. Names such as pytest.ini,
tox.ini, setup.cfg, pyproject.toml and .coveragerc are inventory entries only;
malformed/unknown configuration content changes no testing finding because it
is not read. Near-match `.example` filenames have no configuration meaning either.
`noxfile.py` and `conftest.py` may be bounded Python snapshot data but are never
executed and do not alone establish tests or configured testing. No new content
boundary, configuration system or runtime dependency is added.
Custom pytest python_files/hooks, plugins, unittest loaders and other frameworks
can use unobserved names or shapes. Absence findings do not establish no tests.
**Target coverage is unavailable / not measured.** No percentages, file ratios,
line ratios or inferred branches are computed. RepoLens development-suite
coverage measures RepoLens itself and says nothing about target coverage.

## States and parsing

Unavailable source data yields FAILED; an empty available snapshot yields
NOT_APPLICABLE. Any selected Python source, including stub-only snapshots, makes
this observation applicable; stubs never count as executable test candidates.
No candidate yields COMPLETED with TEST001. Successfully inspected candidates
yield COMPLETED, with TEST002 only for files lacking recognized declarations.
Only candidates need AST parsing; invalid ordinary modules do not invalidate the
narrow filename/structure observation. Invalid candidate syntax or unsupported
3.14-only syntax yields UNSUPPORTED, discarding all partial findings. Parser
MemoryError/RecursionError yields sanitized FAILED and no partial findings.
Unavailable states retain existing incomplete-score semantics.

`analyzers.python_ast` centralizes the unchanged Python 3.13 feature_version,
optimize=0 and scoped target-warning suppression policy shared with Phase 5.
Each analyzer remains independently usable, with no mutable AST cache. Candidates
parse once per testing call. Feature-version parsing is best effort, not an exact
older-interpreter emulator; budgets do not provide an OS process/resource sandbox.
The same convention/grammar/identity fixtures run under Python 3.13 and 3.14.
