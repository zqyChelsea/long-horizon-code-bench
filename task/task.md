# Task: Optimize the Throughput of the exchange-core Matching Engine

You are maintaining `exchange-core`, a real-world open-source financial exchange matching engine.

The current implementation runs successfully and passes the baseline functional tests. Your goal is to continuously improve aggregate throughput across multiple trading workloads in a fixed evaluation environment while preserving matching behavior, account state, risk controls, and public API correctness. Improvements should not trade throughput for unacceptable tail latency, CPU inefficiency, or memory growth.

## Workspace

The repository is located at:

```text
/home/workspace/exchange-core
```

You may modify:

- `src/main/java/`
- `src/main/resources/`

The build descriptor, Maven wrapper/configuration, baseline tests, Judge configuration, and hidden tests are immutable and are not part of the submitted artifact.

Only files under `src/main/` are editable and included in scored submissions. Build output and feedback files are managed by the harness.

## Local Validation

```bash
bash /home/public_tests/run_public_tests.sh
```

## Submit for Evaluation

```bash
bash /home/submit/submit.sh
```

After each valid submission, the system returns a structured Test Report containing the current score, historical best score, score change for the current iteration, test-group results, performance-group results, newly introduced regressions, hard-gate status, and remaining budget.

## Constraints

- Do not change the externally observable behavior of order placement, movement, cancellation, matching, or reporting APIs.
- Do not violate price-time priority, account balances, margin rules, fees, order-book consistency, or state determinism.
- Do not modify, delete, or bypass tests or scoring logic.
- Do not access hidden tests, reference solutions, the Oracle, Git history, or an online implementation of the target project.
- External network access, browser/search tools, remote repositories, and remote tool connectors are unavailable.
- Do not fabricate throughput output, logs, exit codes, or evaluation results.
- All scored changes must remain within the permitted submission paths.
- The total time budget is 12 hours.

At the end of the task, the system evaluates the best valid artifact saved during the run against the final held-out test suite.
