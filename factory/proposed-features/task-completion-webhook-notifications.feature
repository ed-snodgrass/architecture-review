@task-completion-webhook
Feature: Task completion webhook notifications

  Task completion notifications are optional observability. The planner tells
  the factory which task it resolved after approved work is committed, and the
  factory reports that event without reading or interpreting the plan itself.
  Notification delivery never changes machine execution, routing, commits, or
  the outcome of the run.

  Background:
    Given a copy of the factory
    And a new target, with a seed describing a game of Tetris
    And the target has the machines planner, doer and validator
    And the target has an assembly line "careful" on which the doer's work is validated
    And a run named "tetris", on the "careful" line, with that seed and target
    And the planner plans the tasks alpha and beta
    And the doer does the next task in the plan
    And the validator is always satisfied
    And a plan with two tasks, neither done

  Rule: A resolved task produces one notification

    Example: Each completed task is delivered with its run and completion time
      Given a task-completion webhook that responds with 204
      And no plan
      And the planner keeps its plan in prose
      And the doer keeps its plan in prose
      When the factory runs the "tetris" run
      Then the factory exits successfully
      And the webhook received task-completion notifications for "alpha" and "beta"
      And each notification names the "tetris" run and has a UTC completion time
      And the run log records two delivered task-completion notifications
      And the run log does not reveal the webhook secret

  Rule: Notification configuration and planner data are optional

    Example: An unconfigured webhook is reported once per run
      Given no task-completion webhook is configured
      When the factory runs the "tetris" run
      Then the factory exits successfully
      And there are two new work commits
      And the run log records once that task-completion notifications are disabled

    Example: Missing completed-task data skips delivery
      Given a task-completion webhook that responds with 204
      And the planner omits completedTask after completing a task
      When the factory runs the "tetris" run
      Then the factory exits successfully
      And there are two new work commits
      And the webhook received no requests
      And the run log records two skipped task-completion notifications

  Rule: Delivery failure never affects the assembly line

    Example: A non-success response is attempted once per completed task
      Given a task-completion webhook that responds with 429
      When the factory runs the "tetris" run
      Then the factory exits successfully
      And there are two new work commits
      And the webhook received exactly 2 requests
      And the run log records two failed task-completion notifications with HTTP status 429
      And the run log does not reveal the webhook secret

    Example: A network failure does not stop later machines
      Given an unreachable task-completion webhook
      When the factory runs the "tetris" run
      Then the factory exits successfully
      And there are two new work commits
      And the run log records two failed task-completion notifications
      And the run log does not reveal the webhook secret

    Example: A slow webhook is abandoned after five seconds
      Given a task-completion webhook whose first response takes ten seconds
      When the factory runs the "tetris" run
      Then the factory exits successfully
      And there are two new work commits
      And the webhook received exactly 2 requests
      And the run waited about five seconds for notifications
      And the run log records a timed-out task-completion notification
