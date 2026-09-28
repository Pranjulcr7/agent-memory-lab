# Agent Memory Lab

A small learning project that shows how information can remain available to an agent after an incomplete deletion.

Two local experiments explain and test memory deletion. Lesson 1 uses a deliberately simplified SQLite store. Lesson 2 tests `mem0ai==2.1.0` with `qdrant-client==1.19.1`, local Qdrant storage, and Mem0's SQLite history. Both use synthetic data and make no LLM calls. This is an early testing prototype, not a production security certification. Use Python 3.10 or later; the integration was verified on Python 3.12.

## Run lesson 1: storage and context

```bash
git clone https://github.com/Pranjulcr7/agent-memory-lab.git
cd agent-memory-lab
python3 demo.py
python3 -m unittest -v test_memory_lab
```

The demo intentionally prints a FAIL for incomplete deletion and a PASS for the corrected case in a fresh session. Those are expected findings. It also shows that a previously built context still contains information after database deletion. The six unit tests verify these outcomes, including that another user's data survives.

## Run lesson 2: real Mem0 storage

From the repository directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-mem0.txt
python mem0_demo.py
python -m unittest -v
```

The experiment needs no API key, model download, or Docker service. Installing packages needs internet access; the integration tests block network connections during the experiment. Each run creates a new directory under `.lab/` containing synthetic data and `report.json`. These files are ignored by Git.

The observed result for the pinned versions is a retrieval `PASS`: the deleted memory disappears from lookup, listing, search, and its Qdrant point after clients are reopened. The old text remains in Mem0's history and in the earlier context snapshot. Unrelated memories belonging to the same user and another user remain available.

To require removal of the marker from history as well:

```bash
python mem0_demo.py --require-history-erasure
```

This stricter contract reports `FAIL` on the tested version because history retains the marker. That is a finding against our selected requirement, not a claim that Mem0 violates its documented contract. Exit codes are `0` for PASS, `1` for FAIL, and `2` for INCONCLUSIVE. Add `--json` for machine-readable stdout.

**What is substituted:** only the model dependencies. A deterministic token-hash embedder replaces learned embeddings, and an LLM fixture raises if called. Mem0's storage, search, history, and deletion implementations run unchanged with `infer=False`. This tests memory lifecycle behavior, not semantic retrieval quality or generated answers.

Read [the Mem0 lesson](docs/mem0-lesson.md) for the storage layout, report walkthrough, and explanation of embeddings. The full suite has 17 tests, including four integration tests. Without the optional dependencies, those four are explicitly skipped; run inside the virtual environment above to exercise them.

## 1. What memory means

Three separate things are often called memory:

| Thing | What it holds | How it changes |
| --- | --- | --- |
| Model weights | Patterns learned during training | Training or fine-tuning changes them. Ordinary retrieval does not. |
| Context for the next model call | Instructions, recent messages, retrieved notes, tool results | The application assembles and sends it for an inference request. |
| Application storage | Conversation records, saved facts, summaries, checkpoints, documents, sometimes vectors and graphs | Application code or a memory service writes and reads it. |

An agent normally remembers a personal fact because the application saves it and later includes it in the model's input. This does not normally require retraining the model.

Thread-scoped state can itself be persisted to a database. Restarting a Python process therefore does not necessarily erase conversation state. A fresh session and a restarted process are also different operations: an application can restore the old session from a checkpoint.

## 2. How one fact gets saved and used

Suppose a synthetic user says: "My project code is orchid-7412."

1. The application receives the message and authenticates the user.
2. Code or an extraction model selects a fact worth saving.
3. The application writes text and metadata, for example `user_id`, `memory_id`, source message ID, and timestamp.
4. Some systems also calculate an embedding, a numeric representation useful for similarity search. The original text or a reference to it is usually stored as well.
5. On a later question, the application retrieves relevant, authorized records and places their text into the next model input.
6. The model can then use that supplied information in its answer.

An embedding is not the fact being learned into the answer model's weights. It is a search representation. A vector database is one storage/search choice; SQL, key-value stores, files, and graph databases can also participate. Embeddings are not required for every memory design.

User IDs and namespaces are organization mechanisms. The application must enforce authorization using trusted identity; letting a caller choose someone else's ID is not access control.

## 3. Why deletion needs tests

The same fact can be represented in several places. A raw record might have a corresponding profile summary, graph relationship, cached retrieval result, saved conversation, or checkpoint. A deletion's intended scope must be explicit. Deleting one saved note does not automatically mean deleting the original chat transcript, and a product may intentionally retain some records that are no longer available to its agent.

For this lab, the contract is deliberately small:

> After deleting Alice's project-code fact and its known derived summary, a fresh session built from these two tables must not contain her synthetic marker. Bob's data must remain available.

In lesson 1, the database has two tables, `facts` and `summaries`. Each summary has exactly one source record. In real systems a summary can mix many sources; deleting or regenerating it requires more careful lineage handling.

`delete_record_only()` deliberately removes just the row in `facts`. `delete_record_and_summary()` removes both known stored copies in one database transaction. Neither operation reaches into an existing `AgentSession` object's already-loaded context.

Lesson 1's retrieval loads all rows for one user. Its summary is built with a fixed string, not a model. These simplifications keep the storage behavior visible. There is no embedding model, semantic search, network API, or generated answer in that lesson.

## 4. Read the files in this order

1. `memory_lab.py`: inspect `remember()` and the two deletion methods.
2. `read_context()`: see how stored text becomes model input material.
3. `AgentSession`: see why an existing context is a separate copy.
4. `demo.py`: follow the save, delete, reopen, and probe sequence.
5. `test_memory_lab.py`: inspect the external outcomes the checks require.

`make_prompt()` stops at the input a model would receive. There is intentionally no claim about how a real model would answer it.

For lesson 2, read `mem0_adapter.py`, then `deletion_check.py`, then `mem0_demo.py`. The adapter connects to the library, the runner evaluates a contract, and the command prints and saves the report. `test_deletion_check.py` introduces defective adapters to test the runner; `test_mem0_integration.py` exercises actual Mem0 and Qdrant.

## 5. How our eventual tester would work

The Mem0 adapter is a first implementation of this pattern. A future adapter would connect the testing runner to a customer's application. It would implement operations such as creating a synthetic user, writing a fact, searching, deleting, starting a fresh session, and inspecting the storage surfaces the customer exposes. The current command creates an isolated local fixture; it does not connect to customer systems.

For each test, the runner would:

1. Confirm that the synthetic fact can be retrieved before deletion. Otherwise a later absence could simply mean setup never worked.
2. Trigger the customer's real deletion operation and wait for the documented completion condition or deadline.
3. Check storage and retrieval through the covered paths.
4. Construct a clean follow-up query without reintroducing the deleted fact in the question or chat history.
5. When model behavior is in scope, run several probes and capture the retrieved context as well as the answers.
6. Verify that an unrelated user's allowed data still works.

Use deterministic assertions for IDs, synthetic markers, and storage state. Semantic or paraphrase checks may need additional evaluation. An LLM judge can make mistakes, so it must not be the sole deletion oracle.

Our report would distinguish FAIL, PASS FOR TESTED SCOPE, and INCONCLUSIVE. Missing credentials, incomplete adapters, failed setup, and uninspected stores must not silently turn into a pass.

Lesson 1's exact-marker test inspects assembled context. Lesson 2 additionally inspects library lookup, listing, search, the target Qdrant point, and history for a three-record fixture. Neither proves universal forgetting, semantic erasure, deletion from backups or provider logs, or compliance with a law. Neither tests information encoded in trained model weights.

## 6. Exercises

- Before running the demo, predict which stored copy survives `delete_record_only()`.
- After deleting both stored copies, inspect `original_session.context`. Why does it still contain the marker?
- Change the two synthetic users to share a `memory_id`. Confirm deleting one user's fact leaves the other user's fact intact.
- Explain why putting `orchid-7412` in the follow-up question would invalidate a test of forgetting.

## 7. Repository

Maintained by [Pranjul Gupta](https://github.com/Pranjulcr7). The project is available at [Pranjulcr7/agent-memory-lab](https://github.com/Pranjulcr7/agent-memory-lab).

## 8. Startup direction

See `PRODUCT_PLAN.md`. The isolated Mem0 integration now provides a concrete report to discuss with prospective users. Testing an actual application's memory paths and establishing repeated use are the next milestones. A working integration alone is not evidence of product demand.

## References checked on September 28, 2026

- [LangChain memory concepts](https://docs.langchain.com/oss/python/concepts/memory)
- [Mem0 adding memories](https://docs.mem0.ai/core-concepts/memory-operations/add)
- [Mem0 deletion operations](https://docs.mem0.ai/core-concepts/memory-operations/delete)
- [AWS: secure agent memory and state](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentsec01.html)

These references describe real systems. The teaching code is independently written and intentionally simplified.
