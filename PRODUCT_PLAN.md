# From learning lab to a useful product

## Candidate problem

Engineering teams adding persistent memory need repeatable evidence that their application's deletion behavior still works after code, configuration, or dependency changes. Demand for a separate product is a hypothesis.

## First prospective user

A small B2B software team with a deployed assistant, persistent per-user memory, a stated deletion behavior, and an engineer responsible for releases. Find teams that already have this requirement. A future plan to add memory is weaker evidence.

## First real integration

After the SQLite lesson, pick one supported Mem0 OSS version and one storage backend. Verify its current documented behavior. Build an adapter and run a small set of lifecycle tests. Do not assume closed historical issues are still present. A passing current implementation is an important positive control.

Begin with a finite set of synthetic fixtures and a local runner. Record setup outcomes, deletion completion, inspected layers, and reproducible evidence. Explicitly label uninspected conversation stores and caches.

## Learning and build sequence

1. Explain the difference between model weights, context, and stored memory.
2. Run this lab and understand why the deliberate defect fails.
3. Learn embeddings and inspect what one actual memory library writes.
4. Connect the same test contract to a real application using a version-pinned adapter.
5. Package a command-line report that another developer can run.
6. Add CI integration after someone runs the tool on a real project and asks to repeat it.

## Questions for five prospective users

- What exactly does your product promise when someone deletes a memory or account?
- Which stores, summaries, sessions, and caches might still contain that information?
- How do you test this today, and when did you last find a failure?
- Who owns the work, and how much time does it take?
- Would you spend an hour trying a local test on a staging system with synthetic data?

Proceed to a customer-facing prototype if at least three suitable teams are willing to try it. Treat those thresholds as practical experiment criteria, not statistical evidence of a market.

## Adoption and payment hypotheses

A local open-source runner could reduce the barrier to a first trial. Possible paid work later includes maintained adapters, team reports, scheduled regression runs, and integration support. Do not build those before repeated use. A pricing decision needs conversations about the work saved and the buyer's budget.

Useful evidence: a team repeats the test after a release, supplies a real failure scenario, asks for an integration, or agrees to a paid pilot when the work is authorized. Downloads, stars, and compliments alone do not establish a business.

## Competition and stop conditions

General evaluation and security tools can implement custom checks. Memory providers can add lifecycle testing. The proposed product needs to save meaningful setup and maintenance work on this specific problem.

Pause or narrow the idea if integration takes too much customer effort, available tools already solve the need adequately, nobody repeats the tests, or the only users are other tool builders without a budget. A useful open-source contribution is also a valid result of the experiment.

## Boundaries

Use synthetic fixtures and authorized staging environments. Reports describe inspected behavior and coverage. They do not certify privacy compliance or prove that every possible copy has vanished.
