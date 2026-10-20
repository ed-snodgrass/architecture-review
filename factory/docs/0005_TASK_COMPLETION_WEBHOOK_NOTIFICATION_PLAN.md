# Task Completion Webhook Notification Plan

## Outcome

After the planner resolves a completed task during a run, the factory sends a
best-effort webhook notification containing the completed task, run name, and
completion time. Notifications are optional observability: they never affect
machine execution, assembly-line routing, or the outcome of a run.

The planner remains the sole owner and interpreter of `plan.md`. The factory
does not read or parse the plan to produce notifications.

## Planner result contract

On a planner turn after validated work has been committed, ask the planner to
include the task it marked complete:

```json
{
  "complete": false,
  "completedTask": "Add focused acceptance tests"
}
```

Initial planning turns continue to require only `complete`. The factory uses
`completedTask` only for notification delivery; it does not use the field for
routing or task selection.

If `completedTask` is missing, empty, or malformed on a post-commit planner
turn, log that notification delivery was skipped and continue the run.

## Configuration

Read the webhook URL from:

```text
FACTORY_TASK_COMPLETE_WEBHOOK_URL
```

The URL is a secret. Never commit it, include it in an error, or write it to a
run log. The previously shared IFTTT key should be rotated before this feature
is configured.

When the environment variable is absent, disable notifications and write one
informational log entry for the run. This does not affect execution.

## Webhook request

Send one HTTP POST for each task reported complete. Use the IFTTT webhook's
three value fields:

```json
{
  "value1": "Add focused acceptance tests",
  "value2": "arch-r-006",
  "value3": "2026-10-20T12:09:20.000Z"
}
```

- `value1`: the planner's post-update `completedTask` text
- `value2`: the run name
- `value3`: the factory-generated ISO-8601 completion time in UTC

Task counts and ordinal positions are out of scope. If one planner result ever
reports more than one completed task, send one request per task; the initial
slice may keep `completedTask` singular because the planner currently marks
only one task finished per post-commit turn.

## Delivery behavior

- Make exactly one delivery attempt per completed task.
- Await the attempt before continuing, for at most five seconds.
- Treat any `2xx` response as successful delivery.
- Log success, a non-success HTTP status, a network failure, or a timeout.
- Do not retry `429`, `5xx`, timeouts, or network errors.
- Catch every notification error; never call the factory's failure path.
- Never change the planner result or assembly-line route because of delivery.
- Do not persist a queue or replay missed notifications after a restart.
- Accept that a process crash may lose a notification.

Notification processing must not interrupt a machine. It runs only after the
planner has returned its result, and failures remain isolated from subsequent
machine execution.

## Design

Keep transport concerns outside the orchestrator:

1. The orchestrator recognizes a planner turn made with `completingTask` set,
   after approved work was committed.
2. It reads `completedTask` from that planner result without opening
   `plan.md`.
3. It invokes an injected task-completion notifier with the task text, run
   name, and current time.
4. A notifier component constructs the IFTTT payload, applies the five-second
   timeout, performs the HTTP request, and produces secret-safe log events.

The CLI supplies the configured notifier and run name. Tests inject a fake
notifier and never contact IFTTT.

Suggested log events:

```text
[notification] type=task-complete status=disabled
[notification] type=task-complete status=skipped reason="missing completedTask"
[notification] type=task-complete status=delivered httpStatus=200
[notification] type=task-complete status=failed httpStatus=429
[notification] type=task-complete status=failed reason="timeout"
```

Do not include the webhook URL, key, request headers, or credential-bearing
response content in these events.

## Acceptance and verification

- An initial planner turn does not send a notification.
- A post-commit planner turn with a valid `completedTask` sends exactly one
  request.
- Separate completed tasks produce separate requests.
- The payload contains the exact completed task text, run name, and a valid
  UTC ISO-8601 completion time.
- The factory never reads `plan.md` to construct a notification.
- Missing configuration produces one informational log entry per run and no
  request.
- A missing, empty, or malformed `completedTask` produces a skipped log entry
  and no request.
- `2xx` responses are logged as delivered.
- `429`, `5xx`, other non-success statuses, network failures, and timeouts are
  logged without retries.
- A request is abandoned after five seconds.
- Delivery is awaited for the final completed task before the worker exits.
- Every notification failure leaves machine calls, routing, commits, and run
  success unchanged.
- Logs never contain the configured URL or key.
- Tests use an injected fake transport or local test server and never call the
  real webhook.

Run the non-real-agent suite and type checker from `factory/`:

```sh
npm test
npm run typecheck
```

## Deferred

- Task totals or ordinal positions
- Reading or parsing `plan.md`
- Retries, backoff, or `Retry-After` handling
- Durable queues, delivery replay, or deduplication across process crashes
- Multiple webhook destinations
- Per-run or per-target notification configuration
- Provider-specific payloads beyond the current IFTTT `value1`–`value3`
  contract
