Feature: The coding agent

  The factory writes no project code and no plan. Both come from a coding
  agent — an LLM-driven tool such as pi — that the factory calls. Every
  call it makes goes to that agent, and the agent answers each one with a
  result: JSON describing the job it did. pi is the default; another agent
  can be chosen on the command line for a run.

  Most examples say what the agent does in them: it plans the tasks alpha
  and beta, say, or writes a file called SENTINEL. That shows what the
  factory gives the agent and what it does with the answer. Examples
  tagged @real-agent run a real agent.

  Background:
    Given a copy of the factory
    And a new target
    And a seed describing a game of Tetris
    And the agent plans the tasks alpha and beta, and does one task a pass

  Rule: pi is the agent unless another is chosen

    Example: No harness is chosen
      Given no harness is chosen
      When the factory runs one pass
      Then pi has been called

    Example: Another harness is chosen for the run
      When the factory runs one pass
      Then the chosen agent has been called
      And pi has not been called

  Rule: Without an agent, nothing is built

    Example: The chosen agent cannot be run
      Given the agent cannot be run
      And no plan
      When the factory runs one pass
      Then it reports that it could not run the agent
      And there is no plan
      And there are no new commits

  Rule: The plan is what the agent wrote

    Example: An agent that plans two tasks
      Given no plan
      When the factory runs one pass
      Then the plan has the tasks "alpha" and "beta", and no others

  Rule: The target holds what the agent wrote

    Example: An agent that writes one file
      Given a plan with three tasks, none of them done
      And the agent writes a file called SENTINEL
      When the factory runs one pass
      Then there is one new work commit
      And its only product file is SENTINEL

  Rule: The agent is pointed at the plan and the seed

    The factory cannot hand the agent a task: it never reads the plan. It
    tells the agent where the plan and the seed are, and the agent does
    the rest.

    Example: What the agent is given
      Given a plan with three tasks, none of them done
      When the factory runs one pass
      Then the agent was pointed at the plan and at the seed

  Rule: The agent is asked for the result the factory reads

    The factory tells the agent what its result must say: whether the plan
    is complete, in the field "complete". Nothing but that question makes
    an agent answer with a result.

    Example: What the agent is asked for
      Given a plan with three tasks, none of them done
      When the factory runs one pass
      Then the agent was asked for a result with the field "complete"

  Rule: The result is the last line of the answer that is JSON

    An agent may say anything before its result. The factory reads only
    the last line of the answer that parses as JSON.

    Example: The agent talks before its result
      Given a plan in which every task is done
      And the agent says "nothing left to do" before its result
      When the factory runs to completion
      Then the agent has been called once
      And the factory has stopped

  Rule: What gets built follows the seed

    A factory that had Tetris tucked away inside it would pass every
    example that asks for Tetris. It would not pass this one.

    @real-agent
    Example: A Tetris with different details
      Given the agent is pi
      And a seed describing Tetris on a board 8 columns wide, started with "npm run play"
      When the factory runs to completion
      Then "npm run play" in the target starts Tetris
      And its board is 8 columns wide
