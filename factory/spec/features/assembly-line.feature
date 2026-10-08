Feature: Assembly line

  The assembly line is the route through the factory's machines, written
  as a Graphviz graph the factory reads before it does any work. The
  factory has one assembly line, kept in its own folder. These rules are
  about the line itself — which lines the factory will accept — not about
  running along one. Running is in orchestration.feature.

  start and finish mark where the line begins and ends. Every other node
  names a machine the factory has: one configured in its folder under that
  name. An edge only routes. Its label names a field of the result of the
  machine it leaves: the edge is taken when that field is true, and one
  labelled "not" and the field's name when it is false. An edge with no
  label is taken whatever the result. The planner decides whether there is
  more to do: it is the only machine with an edge to finish.

  Background:
    Given a copy of the factory
    And a new target
    And this assembly line:
      """
      digraph assembly_line {
        start -> planner
        planner -> doer        [label="not complete"]
        planner -> finish      [label="complete"]
        doer -> validator
        validator -> doer      [label="not satisfied"]
        validator -> planner   [label="satisfied"]
      }
      """

  Rule: The factory accepts an assembly line it can run

    Example: The line as it stands
      When the factory reads the assembly line
      Then it accepts it

    Example: The validator is taken out
      Given the validator has been taken out, so the doer goes straight to the planner
      When the factory reads the assembly line
      Then it accepts it

  Rule: The factory refuses an assembly line naming a machine it does not have

    Example: A misspelt validator
      Given "validator" is misspelt "validater" throughout the assembly line
      When the factory reads the assembly line
      Then it refuses it
      And it reports that it has no machine called "validater"

  Rule: The factory refuses an assembly line that cannot reach finish

    Example: Satisfied work has nowhere to go
      Given the edge from validator to planner has been taken out
      When the factory reads the assembly line
      Then it refuses it
      And it reports that finish cannot be reached from validator
