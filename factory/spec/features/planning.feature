Feature: Planning

  How the planner makes the plan from the seed, and keeps it true.

  Background:
    Given a copy of the factory
    And a new target
    And a seed describing a game of Tetris
    And the planner plans the tasks alpha and beta
    And the doer does the next task in the plan
    And the validator is always satisfied

  Rule: The seed is the assembly line's only input

    What to build comes from the seed alone. The assembly line is given
    the seed and nothing else.

    @real-agent
    Example: The assembly line is given a seed and nothing else
      Given every machine runs pi
      When the factory runs
      Then Tetris has been built in the target

  Rule: The seed is selected on the command line

    A seed argument is required alongside the target argument. Relative
    paths are resolved from the caller's working directory. The factory
    gives machines the resolved seed path so they can read it from the
    target. There is no default seed.

    Example: No seed argument
      Given no seed is chosen
      And no plan
      When the factory runs
      Then it reports that there is no seed
      And no agent has been called
      And there is no plan

    Example: There is no seed
      Given the seed has been deleted
      And no plan
      When the factory runs
      Then it reports that there is no seed
      And no agent has been called
      And there is no plan

  Rule: The planner writes the plan before any work is done

    Example: A seed with no plan yet
      Given no plan
      When the factory runs
      Then the planner was called before the doer
      And the plan shows every task as done

    Example: A plan already exists
      Given a plan with three tasks, none of them done
      When the factory runs
      Then the plan still has those three tasks

    @real-agent
    Example: The plan comes from the seed
      Given every machine runs pi
      And no plan
      When the factory runs
      Then every task in the plan comes from the seed

  Rule: Each target keeps its own plan

    The plan is .factory/plan.md inside the selected target. That folder
    holds the generation's plan, which the factory commits with its work.
    A fresh target starts without a plan; selecting an existing target
    resumes its plan. The factory never shares a plan between targets.

    Example: The first run
      Given no plan
      When the factory runs
      Then the plan is .factory/plan.md in the target
      And there is no plan in the factory's folder


  Rule: The planner keeps the plan, and the factory never reads it

    The planner writes the plan. Once a task's work is committed, the
    planner marks it done, and its result says whether any task is
    left. The doer works from the plan too. The factory only knows whether
    there is a plan, and the machines' results.

    Example: A run carries on from the last
      Given a plan whose first task is done
      When the factory runs
      Then the plan shows every task as done
      And there are two new work commits

    Example: Work that gave up is not recorded
      Given a plan with three tasks, none of them done
      And the factory allows at most three attempts at a task
      And the validator is never satisfied
      When the factory runs
      Then the plan shows every task as not done

    Example: A plan no factory could parse
      Given the planner keeps its plan in prose
      And the doer keeps its plan in prose
      And no plan
      When the factory runs
      Then the work for alpha and beta has been committed

  Rule: A successful run records the final plan with the work

    The plan is part of the target's history. Before stopping successfully,
    the factory records the latest plan, including any updates made after
    a task's work was committed. A completed run leaves no uncommitted
    changes in the target. Plan-only commits do not represent extra tasks.

    Example: Finish the tasks and record their final state
      Given a plan with three tasks, none of them done
      When the factory runs
      Then the plan shows every task as done
      And there are three new work commits
      And the committed plan matches the plan on disk
      And the target has no uncommitted changes
