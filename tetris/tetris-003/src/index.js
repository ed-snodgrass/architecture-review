#!/usr/bin/env node

import { runGame } from './terminal.js';

try {
  runGame();
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
