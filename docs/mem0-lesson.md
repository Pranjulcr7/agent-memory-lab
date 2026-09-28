# Lesson 2: following a memory through a real library

The first lesson created a bug ourselves. This lesson asks what an existing library does. It uses the published `mem0ai==2.1.0` package and `qdrant-client==1.19.1`. These are deliberate test pins, not a promise that they are the latest releases. The adapter rejects other versions so a dependency change requires a new validation run.

## The pieces

| Component | Job in this experiment | Where its information lives |
| --- | --- | --- |
| Mem0 | Coordinates adding, retrieving, deleting, and recording history | Python objects plus the stores below |
| Test embedder | Converts tokens to 128 numbers | Computed locally; the resulting vector goes to Qdrant |
| Qdrant local | Stores vectors alongside text and metadata; searches and filters them | The run's `qdrant/` directory |
| History | Records ADD and DELETE events, including old/new text | The run's `history.sqlite` file |
| Earlier search result | A snapshot that could be put in a model prompt | Python memory and the saved test report |

No separate Qdrant server is needed. Its Python client runs in local mode. The adapter closes both the history connection and the Qdrant client before reopening them against the same files. This is a new client instance, not a claim that we restarted the operating system or cleared every application cache.

## What an embedding does

A vector is a list of numbers. An embedding function turns text into such a list. A trained semantic embedder can place related texts close together even when their words differ. A vector database compares those lists and returns nearby records. It also retains the text or payload needed to reconstruct useful context.

For this integration test, we use a simple substitute: split text into tokens, hash each token into one of 128 positions, count occurrences, and normalize the vector. Shared tokens contribute to similarity. Hash collisions are possible, and synonyms need not look similar. This is not a trained semantic model.

That substitute makes the experiment deterministic and free of inference services. The part under test is what happens to records and retrieved context after deletion. We are not evaluating how well an embedding model understands language. Later, a trained embedder can be tested separately against an application's retrieval requirements.

Inspect `before.point[0].vector` in the report to see the numbers. Inspect `before.point[0].payload` to see the separate text and metadata. The embedding is a search representation; it has not trained the answer model to remember the fact.

## What gets called

The adapter invokes real Mem0 APIs:

```python
memory.add(text, user_id=user_id, infer=False)
memory.search(query, filters={"user_id": user_id}, top_k=20, threshold=0.0)
memory.get(memory_id)
memory.get_all(filters={"user_id": user_id}, top_k=100)
memory.delete(memory_id)
memory.history(memory_id)
```

`infer=False` saves the supplied text without asking an LLM to extract facts. It still computes and stores a vector. The query is always “What is my project code?” and does not contain the synthetic answer.

Only the embedder and LLM factories are substituted during construction. The LLM substitute raises on any attempted call. Factory patches are scoped to construction, so this adapter is intended for a standalone, single-threaded test runner. It is not an application-wide Mem0 configuration layer. The vector store, history, and memory operations are not mocked in the integration tests.

Telemetry is disabled before importing Mem0. All configured data paths belong to the new run directory. The integration suite blocks socket connections and DNS lookups, so unexpected network activity causes a test failure rather than silently using a service.

## The deletion contract

Each run creates three synthetic records:

1. Alice's project code, which should be deleted.
2. Alice's preferred programming language, which must survive.
3. Bob's different project code, which must survive.

User IDs and markers are unique to the run. Before deletion, the runner reopens the clients and confirms the target through lookup, listing, search, its Qdrant point, and history. It also confirms the preservation controls. A missing baseline produces INCONCLUSIVE and the runner does not call delete.

After deletion returns, clients are reopened again. The runner checks the target's absence and the controls' preservation. It also inspects history and keeps the earlier context snapshot as a separate observation. A deletion acknowledgment alone cannot produce a pass.

The default contract requires removal from the inspected retrieval paths and the target Qdrant point. `--require-history-erasure` additionally requires the exact marker to be absent from the target's history. Both are finite requirements for these fixtures, not universal privacy claims.

## Run it and inspect the result

From the repository, with its virtual environment activated:

```bash
python mem0_demo.py
python mem0_demo.py --require-history-erasure
python -m unittest -v
```

The first command reports PASS on the pinned configuration. The second reports FAIL and exits with code 1 because the marker remains in history. The test suite passes because it verifies these expected observations and checks that deliberately broken adapters are caught.

For a predictable directory name, use a path that does not exist yet:

```bash
python mem0_demo.py --data-dir .lab/inspect-one
python -m json.tool .lab/inspect-one/report.json
```

Read these report fields in order:

- `environment`: the required and installed package versions, Python version, and configured fixtures.
- `baseline`: evidence that every required path worked before deletion.
- `before.point`: vector, text, and metadata before deletion.
- `after`: the library and backend responses after deletion and reopening.
- `checks`: the selected contract's assertions.
- `observations`: history retention and the still-existing earlier snapshot.
- `coverage`: inspected paths and explicit exclusions.

You can inspect the actual SQLite history using only Python:

```bash
python - <<'PY'
import sqlite3

with sqlite3.connect("file:.lab/inspect-one/history.sqlite?mode=ro", uri=True) as db:
    rows = db.execute("SELECT event, old_memory, new_memory FROM history").fetchall()
    for row in rows:
        print(row)
PY
```

The ADD event contains the new text. The DELETE event can contain the old text. This is a retained history record, not evidence that `search()` is returning the deleted memory. Whether that history is acceptable depends on the application's stated deletion contract.

The report intentionally contains the synthetic marker, before/after evidence, and an earlier snapshot. It is itself another copy. This experiment does not claim to erase its own test evidence. Reports and data are kept under the Git-ignored `.lab/` directory; no actual user data is needed.

## What remains untested

The fixture has only three records. Search is capped at 20 and listing at 100; neither is an exhaustive scan of a customer's database. We do not test pagination, a bulk account deletion, concurrent requests, inference-generated facts/entities, application summaries, cached prompts, chat transcripts, backups, provider logs, or physical erasure from disk pages.

Mem0's `get()` and `delete()` here use an ID, not an authenticated user session. Calling a library directly does not establish that an application's authorization layer is correct. The user filters and preservation controls check this fixture's behavior, not end-to-end access control.

An exception, missing dependency, version mismatch, failed baseline, or incomplete inspection must never become PASS. The command returns code 2 for INCONCLUSIVE. The standalone unit tests still work without Mem0 installed; optional integration tests are clearly skipped until their dependencies are installed.

## Next useful experiment

Connect the runner to one real application's deletion entry point and the context it actually sends to a model. Keep the synthetic fixtures, baseline, and controls, then add the application's summaries or caches as inspected surfaces. The adapter boundary is there so the contract need not be rewritten for each application.

First ask the team what deletion is supposed to cover. A report that simply flags every retained audit record will not be useful if retaining those records is intentional.

## Sources

- [Pinned Mem0 distribution](https://pypi.org/project/mem0ai/2.1.0/)
- [Pinned Qdrant client distribution](https://pypi.org/project/qdrant-client/1.19.1/)
- [Mem0 OSS configuration](https://docs.mem0.ai/open-source/configuration)
- [Mem0 source repository](https://github.com/mem0ai/mem0)

The reported retention behavior was observed by executing the pinned packages locally. The packages are installed as dependencies; no upstream implementation is copied into this repository.
