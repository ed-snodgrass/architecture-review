Feature: Convergent fan-out review

  Parallel reviewers inspect every attempt independently. When they reject
  work, the machine where their branches meet gives the doer one concrete
  repair contract. Review after a repair verifies that contract and still
  checks the changed work for regressions and newly exposed violations of the
  current task.

  Background:
    Given a copy of the factory
    And a new target, with a seed describing a game of Tetris
    And the target has the machines planner, doer and validator
    And the target has an assembly line "careful" on which the doer's work is validated
    And a run named "tetris", on the "careful" line, with that seed and target
    And the three big brains has replaced the validator on the "careful" line
    And the planner plans the tasks alpha and beta
    And the doer does the next task in the plan
    And every reviewer is always satisfied
    And the synthesiser is always satisfied

  Rule: Review is bounded by the current task

    Example: Reviewers receive the task's requirements
      Given a plan with one task, not done
      When the factory runs the "tetris" run
      Then every reviewer was given the seed and the plan
      And every reviewer was told to review the first unfinished task
      And every reviewer was given the changed product files

    Example: A review lens is guidance rather than a reason to reject
      Given a plan with one task, not done
      And the reviewers' lens is single responsibility
      When the factory runs the "tetris" run
      Then every reviewer was told that a blocking finding must identify a current-task requirement, test failure or regression
      And every reviewer was told to treat later-task work and optional refactors as advisory

  Rule: Rejection produces an actionable repair contract

    Example: The synthesiser rejects with structured findings
      Given a plan with one task, not done
      And reviewers report overlapping blocking findings about the current task
      And the synthesiser rejects with one consolidated repair finding
      When the factory runs the "tetris" run
      Then the doer was given one finding with an id, requirement, evidence, repair and verification
      And the doer was not given the reviewers' duplicate findings

    Example: A rejection without findings cannot cause a blind retry
      Given a plan with one task, not done
      And the synthesiser answers that it is not satisfied with no findings
      When the factory runs the "tetris" run
      Then it reports that the synthesiser rejected the work without findings
      And the doer has been called once
      And there are no new commits
      And the factory has stopped

    Example: An acceptance with blocking findings is inconsistent
      Given a plan with one task, not done
      And the synthesiser answers that it is satisfied with a blocking finding
      When the factory runs the "tetris" run
      Then it reports that the synthesiser accepted the work with findings
      And there are no new commits
      And the factory has stopped

  Rule: The doer accounts for every requested repair

    Example: Repair dispositions accompany the next review
      Given a plan with one task, not done
      And the synthesiser rejects the first attempt with findings "TEST-1" and "USE-1"
      And the doer reports a repair disposition for every finding
      When the factory runs the "tetris" run
      Then every reviewer was given findings "TEST-1" and "USE-1" on the second attempt
      And every reviewer was given the doer's repair dispositions on the second attempt

  Rule: Every repair is reviewed for resolved findings and regressions

    Example: All reviewers run again after a repair
      Given a plan with one task, not done
      And the synthesiser rejects the first attempt with the finding "TEST-1"
      And the synthesiser accepts the second attempt
      When the factory runs the "tetris" run
      Then every reviewer has been called twice
      And every reviewer was asked to verify "TEST-1" on the second attempt
      And every reviewer was asked to inspect the repair for regressions and newly exposed current-task violations
      And there is one new work commit

    Example: A repair can introduce a new blocking finding
      Given a plan with one task, not done
      And the synthesiser rejects the first attempt with the finding "TEST-1"
      And a reviewer resolves "TEST-1" but reports regression "REG-1" on the second attempt
      And the synthesiser rejects the second attempt with the finding "REG-1"
      And the synthesiser accepts the third attempt
      When the factory runs the "tetris" run
      Then the doer was given "TEST-1" before the second attempt
      And the doer was given "REG-1" before the third attempt
      And every reviewer has been called three times
      And there is one new work commit

    Example: An unresolved finding remains in the repair contract
      Given a plan with one task, not done
      And the synthesiser rejects the first attempt with the finding "TEST-1"
      And a reviewer says "TEST-1" is unresolved on the second attempt
      And the synthesiser rejects the second attempt with the finding "TEST-1"
      And the synthesiser accepts the third attempt
      When the factory runs the "tetris" run
      Then the doer was given "TEST-1" before the second and third attempts
      And there is one new work commit

  Rule: Advisories do not keep a task in the repair loop

    Example: Optional improvements accompany accepted work
      Given a plan with one task, not done
      And a reviewer reports an optional refactor as an advisory
      And the reviewers report no blocking findings
      When the factory runs the "tetris" run
      Then the synthesiser was given the advisory
      And the synthesiser accepted with no findings
      And the doer has been called once
      And there is one new work commit

  Rule: Repair context belongs only to the current task

    Example: The next task receives no stale repair findings
      Given a plan with two tasks, neither done
      And the synthesiser rejects the first attempt at the first task with the finding "FIRST-1"
      And the synthesiser accepts every later attempt
      When the factory runs the "tetris" run
      Then the doer was given "FIRST-1" on the repair attempt
      And the doer was not given "FIRST-1" while doing the second task
      And there are two new work commits

