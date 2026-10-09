Feature: Choosing where to build

  The first invocation of a run requires a target. Later invocations can
  use the target the run remembers. A target is a plain folder; targets and the factory
  may share a repository. Work commits affect only the selected target's
  generated work, leaving unrelated staged and unstaged changes alone.

  Background:
    Given a copy of the factory
    And a new target, with a seed describing a game of Tetris
    And the target has the machines planner, doer and validator
    And the target has an assembly line "careful" on which the doer's work is validated
    And a run named "tetris", on the "careful" line, with that seed and target
    And the factory has staged and unstaged changes
    And the planner plans the tasks alpha and beta
    And the doer does the next task in the plan
    And the validator is always satisfied

  Rule: A new run needs a target

    Example: No target on the first invocation
      Given no target is chosen
      When the factory runs the "tetris" run
      Then it reports that a target is required
      And no agent has been called
      And the factory's own files and unrelated uncommitted changes are as they were

  Rule: The factory uses an existing repository without disturbing other work

    Example: A target shares the factory's repository
      Given a plan with three tasks, none of them done
      When the factory runs the "tetris" run
      Then the target uses the containing repository
      And there are three new work commits
      And each new work commit contains the work for one task
      And the factory's own files and unrelated uncommitted changes are as they were

  Rule: Git is initialized only outside an existing repository

    Example: A target has no containing repository
      Given the target is outside any Git repository
      When the factory runs the "tetris" run
      Then the target is a Git repository
      And the work for alpha and beta has been committed
      And the factory's own files and unrelated uncommitted changes are as they were
