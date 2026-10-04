Feature: Validation

  How the factory decides the doer's work is good enough.

  Background:
    Given a copy of the factory
    And a new target
    And a seed describing a game of Tetris
    And the planner plans the tasks alpha and beta
    And the doer does the next task in the plan
    And the validator is always satisfied

  Rule: A validator checks the work the doer just produced

    Example: Earlier work is not rechecked
      Given a plan whose first task is done
      When the factory runs one pass
      Then the validator was given the work for the second task
      And it was not given the work for the first task

  Rule: What a validator looks for is chosen, not fixed

    The student picks the lens a validator brings to the work —
    testability, single responsibility, usability, internationalisation,
    security. The factory does not care which. It is the choice that
    teaches, so this spec leaves it open on purpose.

    Example: The lens goes to the validator
      Given a plan with three tasks, none of them done
      And the validator's lens is testability
      When the factory runs one pass
      Then the validator was given "testability"

    @real-agent
    Example: A validator that looks at testability
      Given every machine runs pi
      And the validator's lens is testability
      When the factory runs one pass
      Then the validator's findings are about testability

    @real-agent
    Example: A validator that looks at something else
      Given every machine runs pi
      And the validator's lens is internationalisation
      When the factory runs one pass
      Then the validator's findings are about internationalisation

  Rule: A validator's findings go back to the doer

    The validator's result says whether it is satisfied and, if not,
    what it found: {"satisfied": false, "findings": [...]}.

    Example: The first attempt is not good enough
      Given a plan with three tasks, none of them done
      And the validator is not satisfied the first time
      When the factory runs one pass
      Then the doer was given the validator's findings

  Rule: A validator reports findings, and changes neither the plan nor the work

    @real-agent
    Example: The first task's work is untestable
      Given every machine runs pi
      And the validator's lens is testability
      When the doer's first attempt at a task is untestable
      Then the validator has changed neither the plan nor the work

  Rule: The doer records each finding as a subtask of the task in progress

    A finding is about the task the doer is working on, so it stays with
    that task. It does not become a new task in the plan, and the task is
    not done until its subtasks are.

    @real-agent
    Example: A finding on the first task
      Given every machine runs pi
      And the validator's lens is testability
      When the doer's first attempt at a task is untestable
      Then that task has a subtask for the finding
      And the plan has no new task
