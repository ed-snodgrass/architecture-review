Feature: Test author

  A test author is an optional machine on an assembly line. It creates
  objective tests for a task before the doer implements that task. The doer
  may use the tests, but must not change them. The validator runs the tests
  before applying its configured review lens.

  Background:
    Given a copy of the factory
    And a new target, with a seed describing a game of Tetris
    And the target has the machines planner, test_author, doer and validator
    And the target has an assembly line "careful" with a test author before the doer
    And a run named "tetris" on the "careful" line, with that seed and target
    And the planner plans the task alpha

  Rule: The test author writes tests before the doer works

    Example: A task receives tests before implementation
      When the factory runs the "tetris" run
      Then the test author has been called before the doer
      And the doer was given the task's tests

  Rule: A task can have no applicable tests

    Example: Documentation work passes through the test author
      Given the test author says no tests are applicable
      When the factory runs the "tetris" run
      Then the doer has been called
      And the run continues without tests

  Rule: The doer cannot change tests

    Example: Test edits by the doer are rejected
      Given the test author has written the task's tests
      And the doer changes a test while implementing the task
      When the factory runs the "tetris" run
      Then the factory reports that the doer changed tests
      And the doer's work has not been committed

  Rule: The doer can request revised tests

    The doer must not edit tests. When the assembly line explicitly routes
    a doer's `tests_need_revision` result to the test author, the doer
    explains the need in `findings` and the test author revises the tests.

    Example: The doer returns to the test author for revised tests
      Given an assembly line where test revision requests return to the test author
      And the test author has written the task's tests
      And the doer says the tests need revision with findings
      When the factory runs the "tetris" run
      Then the test author has been called again with the doer's findings
      And the doer's work has not been committed
      And the doer attempt count starts over after the revised tests

  Rule: Validation runs tests before applying its lens

    Example: The validator receives the test gate and its lens
      Given the test author has written the task's tests
      And the validator's lens is "usability"
      When the factory runs the "tetris" run
      Then the validator was told to run the task's tests first
      And the validator was given the lens "usability"

  Rule: Incorrect tests can return to the test author

    Example: Validator feedback repairs a test
      Given an assembly line where incorrect tests return to the test author
      And the validator says the tests are incorrect the first time
      When the factory runs the "tetris" run
      Then the test author has been called again with the validator's findings
      And the run finishes after the corrected tests pass
