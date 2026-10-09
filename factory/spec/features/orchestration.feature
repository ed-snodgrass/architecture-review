Feature: Orchestration

  How the factory runs along its assembly line: when a task is finished,
  when to give up and when to stop. These rules do not care how validation
  is done.

  Background:
    Given a copy of the factory
    And a new target, with a seed describing a game of Tetris
    And the target has the machines planner, doer and validator
    And the target has an assembly line "careful" on which the doer's work is validated
    And a run named "tetris", on the "careful" line, with that seed and target
    And the planner plans the tasks alpha and beta
    And the doer does the next task in the plan
    And the validator is always satisfied

  Rule: The factory works in the target it is given

    The target is a plain output folder. Agent calls work there. The
    factory uses the Git repository containing it, initializing one only
    if none contains it. Work commits include only the selected target's
    generated work, excluding .assembly-lines/. Unrelated staged and
    unstaged changes are left alone.

  Rule: The factory runs the machines its assembly line gives it

    Example: An assembly line with no validator on it
      Given the validator has been taken out of the "careful" line, so the doer goes straight to the planner
      And a plan with three tasks, none of them done
      When the factory runs the "tetris" run
      Then the plan shows every task as done
      And the validator has not been called

  Rule: Each run executes the assembly line it is given

    A target can hold more than one assembly line. Which one a run executes
    is chosen when the run starts; a line never names a target.

    Example: Two lines, one target
      Given the target has an assembly line "quick" on which the doer goes straight to the planner
      And a run named "quick", on the "quick" line, with that seed and target
      And a plan for each run with three tasks of its own, none of them done
      When the factory runs the "tetris" run
      And the factory runs the "quick" run
      Then the validator was called for the "tetris" run
      And the validator was not called for the "quick" run

  Rule: A line copied into another target builds there

    Example: The careful line, copied
      Given a new target, with a seed describing a game of Snake
      And the target has the machines planner, doer and validator
      And the "careful" line has been copied into the target
      And a run named "snake", on the "careful" line, with that seed and target
      And a plan for each run with three tasks of its own, none of them done
      When the factory runs the "tetris" run
      And the factory runs the "snake" run
      Then each target holds only its own run's work

  Rule: The factory does no work on an assembly line it refuses

    Example: The assembly line names a machine the factory does not have
      Given "validator" is misspelt "validater" throughout the "careful" line
      And a plan with three tasks, none of them done
      When the factory runs the "tetris" run
      Then no agent has been called
      And there are no new commits

  Rule: The doer works on one task at a time

    Which task comes next is the planner's business, not the factory's.

    Example: Three tasks remain
      Given a plan with three tasks, none of them done
      When the factory runs the "tetris" run
      Then there are three new work commits
      And each new work commit contains the work for one task

  Rule: A task is finished when validation is satisfied

    Example: The work is right first time
      Given a plan with three tasks, none of them done
      When the factory runs the "tetris" run
      Then the doer has been called three times

    Example: The work is wrong first time
      Given a plan with three tasks, none of them done
      And the validator is not satisfied the first time
      When the factory runs the "tetris" run
      Then the doer has been called four times
      And there are three new work commits

  Rule: A task gives up after a set number of attempts

    An attempt is the doer producing work and validation deciding on it.
    A doer and a validator can oscillate, each attempt introducing a new
    problem, so a task cannot be allowed to run forever. The limit is the
    orchestrator's, not the line's: the line only routes. How it is set is
    up to the student — a flag, a setting, whatever suits what they
    built. A task that gives up is not committed: the work is left where
    it is, for whoever comes looking.

    Example: Validation is never satisfied
      Given a plan with three tasks, none of them done
      And the factory allows at most three attempts at a task
      And the validator is never satisfied
      When the factory runs the "tetris" run
      Then the doer has been called three times
      And it reports that a task hit its limit
      And there are no new commits
      And the factory has stopped

  Rule: The factory commits each time a task is finished

    Example: Three tasks, three work commits
      Given a plan with three tasks, none of them done
      When the factory runs the "tetris" run
      Then there are three new work commits

    Example: Finished work is not redone
      Given a plan whose first task is done
      When the factory runs the "tetris" run
      Then there are two new work commits
      And no new commit contains the work for the first task

  Rule: The factory stops when the planner says the plan is complete

    The planner keeps the plan, so only the planner knows when it is
    complete. It says so in its result, {"complete": true}, and the line
    goes to finish.

    Example: Work remains
      Given a plan with three tasks, none of them done
      When the factory runs the "tetris" run
      Then the plan shows every task as done
      And the factory has stopped

    Example: Every task is already done
      Given a plan in which every task is done
      When the factory runs the "tetris" run
      Then the doer has not been called
      And there are no new commits
      And the factory has stopped

  Rule: The line routes on each machine's result

    Each machine answers with a result: JSON describing the job it did.
    The factory takes the edge whose label matches it, and never looks
    for words in what a machine says.

    Example: The validator answers in prose
      Given a plan with three tasks, none of them done
      And the validator answers in prose, with no result
      When the factory runs the "tetris" run
      Then it reports that it could not read the validator's result
      And there are no new commits
      And the factory has stopped

    Example: A label the result does not have
      Given a plan with three tasks, none of them done
      And the edges from validator are labelled "approved" and "not approved"
      When the factory runs the "tetris" run
      Then it reports that the result of validator has no field "approved"
      And there are no new commits
