Feature: Fan out

  Running a line that fans out and back in. A machine with several
  unlabelled edges out runs every machine they lead to, at the same time;
  those branches meet at one machine, which runs once, after all of them.
  Each branch is run as that machine would be run anywhere, with its own
  prompt: fanning out says nothing about the branches being alike.

  The examples use the three big brains: the doer's work fans out to
  three reviewers, reviewer_1 to reviewer_3, which meet at a synthesiser,
  and the synthesiser decides.

    doer -> reviewer_1, reviewer_2 and reviewer_3
    reviewer_1, reviewer_2 and reviewer_3 -> synthesiser
    synthesiser -> doer     [label="not satisfied"]
    synthesiser -> planner  [label="satisfied"]

  A machine an example sees at work goes on working until the example
  says it finishes, or the run finishes.

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

  Rule: Every branch runs once, then the machine where they meet

    Example: One attempt
      Given a plan with one task, not done
      When the factory runs the "tetris" run
      Then every reviewer has been called once
      And the synthesiser has been called once
      And there is one new work commit

  Rule: The branches run at the same time

    No branch waits for another to finish before it starts. Reviewers
    that each wait until all three have begun can only finish if they run
    at the same time.

    Example: Reviewers that wait for each other
      Given a plan with one task, not done
      And no reviewer finishes until all three have begun
      When the factory runs the "tetris" run
      Then every reviewer has been called once
      And there is one new work commit

  Rule: Each branch is asked for a result

    A branch's edge names no field, but what it found still has to reach
    the machine where the branches meet.

    Example: What the reviewers are asked for
      Given a plan with one task, not done
      When the factory runs the "tetris" run
      Then every reviewer was asked for a result

  Rule: Where the branches meet, the machine is given their results and nothing else

    Example: What the synthesiser is given
      Given a plan with one task, not done
      And every reviewer is not satisfied, with a finding of its own: "report 1", "report 2" or "report 3"
      When the factory runs the "tetris" run
      Then the synthesiser was given "report 1", "report 2" and "report 3"
      And it was not given the work for the first task

    Example: The reports disagree
      Given a plan with one task, not done
      And the second reviewer is not satisfied, with the finding "report 1"
      When the factory runs the "tetris" run
      Then the synthesiser was given "report 1"
      And there is one new work commit

  Rule: The line routes on the result of the machine where the branches meet

    Example: Nobody but the synthesiser decides
      Given a plan with three tasks, none of them done
      And the factory allows at most three attempts at a task
      And the synthesiser is never satisfied
      When the factory runs the "tetris" run
      Then the doer has been called three times
      And there are no new commits

    Example: The synthesiser rejects the doer's first attempt
      Given a plan with one task, not done
      And every reviewer is not satisfied, with a finding of its own: "report 1", "report 2" or "report 3"
      And the synthesiser is not satisfied the first time
      When the factory runs the "tetris" run
      Then the doer was given the synthesiser's findings
      And it was not given "report 1"

  Rule: A branch that fails stops the run

    A branch that cannot be run, or answers with no result, leaves the
    machine where the branches meet with less than it needs. The factory
    says which branch failed, and stops: it stops the other branches, runs
    nothing after them and commits nothing.

    Example: A reviewer answers in prose
      Given a plan with one task, not done
      And the second reviewer answers in prose, with no result
      When the factory runs the "tetris" run
      Then it reports that it could not read reviewer_2's result
      And the synthesiser has not been called
      And there are no new commits
      And the factory has stopped

    Example: A reviewer cannot be run
      Given a plan with one task, not done
      And the second reviewer cannot be run
      When the factory runs the "tetris" run
      Then it reports that it could not run reviewer_2
      And the synthesiser has not been called
      And there are no new commits
      And the factory has stopped

  Rule: The branches check the work the doer just produced

    Example: Earlier work is not rechecked
      Given a plan whose first task is done
      When the factory runs the "tetris" run
      Then every reviewer was given the work for the second task
      And it was not given the work for the first task

  Rule: The three big brains' reviewers do the same job on different models

    This is the three big brains' choice, not something fanning out
    requires. Its reviewers are configured alike, apart from their models,
    so each is given the same prompt, and three providers' models look at
    the same work in the same way.

    Example: Three reviewers, one prompt
      Given a plan with one task, not done
      When the factory runs the "tetris" run
      Then every reviewer was given the same prompt

  Rule: What the reviewers look for is chosen, not fixed

    The student picks the lens the reviewers bring to the work —
    testability, single responsibility, usability, internationalisation,
    security. All three reviewers are given the same one. The factory does
    not care which. It is the choice that teaches, so this spec leaves it
    open on purpose.

    Example: The lens goes to every reviewer
      Given a plan with one task, not done
      And the reviewers' lens is testability
      When the factory runs the "tetris" run
      Then every reviewer was given "testability"

    @real-agent
    Example: Reviewers that look at testability
      Given every machine runs pi
      And the reviewers' lens is testability
      When the factory runs the "tetris" run
      Then the reviewers' findings are about testability
