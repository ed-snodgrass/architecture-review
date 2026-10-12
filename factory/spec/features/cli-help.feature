Feature: CLI help

  The factory's help output is the command-line contract. It explains every
  supported argument, when it is required, and the default used when an
  optional argument is omitted.

  Rule: Help can be requested without a run

    Example: The help command succeeds on its own
      Given a copy of the factory
      When the factory runs with "--help"
      Then the factory exits successfully
      And the help output describes the factory command
      And no agent has been called

  Rule: Help documents run settings

    Example: Help lists the inputs for a new run
      Given a copy of the factory
      When the factory runs with "--help"
      Then the help output describes "--run"
      And the help output describes "--target"
      And the help output describes "--seed"
      And the help output describes "--line"
      And the help output says those settings are required for a new run

  Rule: Help documents machine and execution options

    Example: Help lists machine options and defaults
      Given a copy of the factory
      When the factory runs with "--help"
      Then the help output describes "--harness"
      And the help output says the default harness is "pi"
      And the help output describes machine-specific harness overrides
      And the help output describes "--validator-lens"
      And the help output describes "--max-attempts"
      And the help output says the default maximum attempts is "3"

    Example: Help lists run behavior flags and defaults
      Given a copy of the factory
      When the factory runs with "--help"
      Then the help output describes "--quiet"
      And the help output says logging is enabled by default
      And the help output describes "--check-assembly-line"
      And the help output describes "--help"
