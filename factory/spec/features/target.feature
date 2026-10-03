Feature: Choosing where to build

  A target is a plain output folder selected on the command line alongside
  the seed. Relative paths are from the caller's working directory;
  absolute paths work too. Targets may share a Git repository. Each has
  its own plan, and commits include only the selected target's work
  and plan. A completed game never prevents a different
  target being built.

  Background:
    Given a copy of the factory
    And a new target
    And a seed describing a game of Tetris
    And the factory has staged and unstaged changes
    And the agent plans the tasks alpha and beta, and does one task a pass

  Rule: A target must be chosen explicitly

    Example: No target argument
      Given no target is chosen
      When the factory runs one pass
      Then it reports that a target is required
      And no agent has been called
      And the factory's own files and unrelated uncommitted changes are as they were

  Rule: A target uses its containing repository

    Example: A fresh output folder
      Given the target folder does not exist
      When the factory runs one pass
      Then the target uses the containing repository
      And the plan is .factory/plan.md in the target
      And the factory's own files and unrelated uncommitted changes are as they were

  Rule: Git is initialized only for a target outside any repository

    Example: A standalone output folder
      Given the target is outside any Git repository
      When the factory runs one pass
      Then the target is a Git repository
      And the plan is .factory/plan.md in the target
      And the factory's own files and unrelated uncommitted changes are as they were

  Rule: An absolute path selects the same target

    Example: A relative path and an absolute path identify the same target
      When the factory builds the target "a-generation" to completion
      And the factory builds the same target using its absolute path
      Then the target "a-generation" is unchanged
      And there are no new commits
      And the factory's own files and unrelated uncommitted changes are as they were

  Rule: Targets do not share plans or work

    Scenario Outline: Build two versions and revisit the first
      When the factory builds the target "<first>" to completion
      And the factory builds the target "<second>" to completion
      Then the targets "<first>" and "<second>" each have their own completed plan and committed work
      And the target "<first>" is unchanged
      When the factory builds the target "<first>" to completion
      Then the target "<second>" is unchanged
      And there are no new commits
      And the factory's own files and unrelated uncommitted changes are as they were

      Examples:
        | first                | second               |
        | tetris/tetris-001    | tetris/tetris-002    |
        | build outputs/game 1 | build outputs/game 2 |
