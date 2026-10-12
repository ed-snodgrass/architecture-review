# CLI help plan

## Goal

Make `cli.ts --help` a successful, side-effect-free command that explains
every supported argument, whether it is required, and its default behavior.

## BDD-first implementation

1. Keep `spec/features/cli-help.feature` red with scenarios for standalone
   help, new-run settings, machine options, execution defaults, and behavior
   flags.
2. Add a help check before run, target, seed, line, or assembly-line loading
   so `--help` works without a configured run or target and invokes no agent.
3. Centralize the option descriptions beside the CLI option parsing so help
   cannot drift from supported flags.
4. Print usage and the argument descriptions to standard output, then exit
   with status `0`.
5. Implement the missing Cucumber steps and run the focused feature.
6. Run the complete BDD suite and TypeScript typecheck.

## Documented defaults

- `--harness`: `pi` when no machine configuration or override supplies one.
- Machine-specific harness overrides: `pi` by default, using the machine's
  configured harness when present.
- `--max-attempts`: `3`.
- `--validator-lens`: the validator machine's configured lens, when present.
- `--quiet`: logging remains enabled unless this flag is supplied.
- `--check-assembly-line`: normal execution remains the default.

## Required behavior

- A new run requires `--run`, `--target`, `--seed`, and `--line`.
- A saved run can be resumed with `--run` alone.
- `--help` takes precedence over normal argument validation and execution.