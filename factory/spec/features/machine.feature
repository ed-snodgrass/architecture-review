Feature: Machines

  The factory writes no project code, no plan and no verdict. That work
  is done by three machines — the planner, the doer and the validator —
  each run by a harness: a coding agent such as pi by default, or another
  chosen on the command line for a run. A machine could as well be
  ordinary code; the factory doesn't mind, so long as the machine answers
  with a result: JSON describing the job it did.

  Most examples say what each machine does in them: the planner plans
  the tasks alpha and beta, say, and the validator is never satisfied.
  That shows what the factory gives a machine and what it does with the
  result. Examples tagged @real-agent run a real agent.

  Background:
    Given a copy of the factory
    And a new target
    And a seed describing a game of Tetris
    And the planner plans the tasks alpha and beta
    And the doer does the next task in the plan
    And the validator is always satisfied

  Rule: Each machine runs pi unless another harness is chosen

    Example: No harness is chosen
      Given no harness is chosen
      When the factory runs one pass
      Then pi has been called

    Example: Another harness is chosen for the run
      Given a plan with three tasks, none of them done
      When the factory runs one pass
      Then the doer's chosen harness has been called
      And pi has not been called

  Rule: A machine whose harness cannot be run does no work

    Example: The doer cannot be run
      Given a plan with three tasks, none of them done
      And the doer cannot be run
      When the factory runs one pass
      Then it reports that it could not run the doer
      And there are no new commits

  Rule: The plan is what the planner wrote

    Example: A planner that plans two tasks
      Given no plan
      When the factory runs one pass
      Then the plan has the tasks "alpha" and "beta", and no others

  Rule: The target holds what the doer wrote

    Example: A doer that writes one file
      Given a plan with three tasks, none of them done
      And the doer writes a file called SENTINEL
      When the factory runs one pass
      Then there is one new work commit
      And its only product file is SENTINEL

  Rule: The doer is pointed at the plan and the seed

    The factory cannot hand the doer a task: it never reads the plan. It
    tells the doer where the plan and the seed are, and the doer does the
    rest.

    Example: What the doer is given
      Given a plan with three tasks, none of them done
      When the factory runs one pass
      Then the doer was pointed at the plan and at the seed

  Rule: Validation is what the validator decided

    Example: A validator that is never satisfied
      Given a plan with three tasks, none of them done
      And the factory allows at most three attempts per pass
      And the validator is never satisfied
      When the factory runs one pass
      Then the doer has been called three times
      And there are no new commits

  Rule: Each machine is asked for the result the factory reads

    The factory tells each machine what its result must say. The planner
    says whether the plan is complete, in the field "complete"; the
    validator says whether it is satisfied, in "satisfied", and why not,
    in "findings". Nothing but that question makes a machine answer with
    a result.

    Example: What the planner is asked for
      Given a plan with three tasks, none of them done
      When the factory runs one pass
      Then the planner was asked for a result with the field "complete"

    Example: What the validator is asked for
      Given a plan with three tasks, none of them done
      When the factory runs one pass
      Then the validator was asked for a result with the fields "satisfied" and "findings"

  Rule: A result is the last line of the answer that is JSON

    A machine may say anything before its result. The factory reads only
    the last line of the answer that parses as JSON.

    Example: The validator talks before its result
      Given a plan with three tasks, none of them done
      And the validator says "looks good to me" before its result
      When the factory runs one pass
      Then there is one new work commit

  Rule: What gets built follows the seed

    A factory that had Tetris tucked away inside it would pass every
    example that asks for Tetris. It would not pass this one.

    @real-agent
    Example: A Tetris with different details
      Given every machine runs pi
      And a seed describing Tetris on a board 8 columns wide, started with "npm run play"
      When the factory runs to completion
      Then "npm run play" in the target starts Tetris
      And its board is 8 columns wide
