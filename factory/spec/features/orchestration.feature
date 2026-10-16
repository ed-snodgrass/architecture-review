Feature: Orchestration

  How the factory runs along its assembly line: when a task is finished,
  when to give up and when to stop. These rules do not care how validation
  is done.

  A machine an example sees at work, part-way through or in a run just
  started, goes on working until the example says it finishes, or the run
  is stopped or run to the end.

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

  Rule: The factory runs as a daemon

    From here on the factory keeps running after the command that starts
    a run returns, and it runs each machine as an ACP agent, speaking the
    Agent Client Protocol to it over stdio. "The factory runs a run" still
    means running it to the end: starting it, then waiting until it has
    finished.

    Example: Starting a run
      Given a plan with one task, not done
      When I start the "tetris" run
      Then the command has returned while the "tetris" run is running
      And the factory is running

  Rule: The factory runs one run at a time

    Example: A second run while one is running
      Given a plan with one task, not done
      And the "tetris" run is running, with the doer part-way through an attempt
      And a new target, with a seed describing a game of Snake
      And the target has the machines planner, doer and validator
      And the "careful" line has been copied into the target
      And a run named "snake", on the "careful" line, with that seed and target
      When I start the "snake" run
      Then the factory refuses
      And the "tetris" run is running

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

  Rule: Stopping a run leaves the factory running

    Example: Stopping the "tetris" run
      Given a plan with one task, not done
      And the "tetris" run is running, with the doer part-way through an attempt
      When I stop the "tetris" run
      Then the "tetris" run is not running
      And the factory is running

  Rule: Stopping the factory stops its run too

    Example: Stopping the factory while a run runs
      Given a plan with one task, not done
      And the "tetris" run is running, with the doer part-way through an attempt
      When I stop the factory
      Then the factory is not running
      And the "tetris" run is not running

  Rule: A stop interrupts the work at once and leaves the run in a sane state

    Stopping is something you choose to do. Every machine that is
    working is interrupted there and then, and the attempt is abandoned:
    nothing is marked done that isn't, and nothing half-finished is
    committed. What the machines had written is left in the target, for
    whoever comes looking. A crash is not a stop; after one, the factory
    makes a best effort to do the same, and no more is asked of it.

    Example: The doer is mid-attempt
      Given a plan with one task, not done
      And the "tetris" run is running, with the doer part-way through an attempt, having said "started"
      When I stop the "tetris" run
      Then the plan shows every task as not done
      And there are no new commits

    Example: The reviewers are mid-review
      Given the three big brains has replaced the validator on the "careful" line
      And every reviewer is always satisfied
      And the synthesiser is always satisfied
      And a plan with one task, not done
      And the "tetris" run is running, with every reviewer part-way through
      When I stop the "tetris" run
      Then the "tetris" run is not running
      And the plan shows every task as not done
      And there are no new commits

  Rule: A stopped run carries on when it is started again

    Example: Starting the "tetris" run again
      Given a plan with one task, not done
      And the "tetris" run is running, with the doer part-way through an attempt, having said "started"
      And I have stopped the "tetris" run
      When the factory runs the "tetris" run, given only its name
      Then the plan shows every task as done
      And there is one new work commit
