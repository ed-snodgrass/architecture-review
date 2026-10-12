import { startTerminal } from './terminal.mjs';

try {
  startTerminal();
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
