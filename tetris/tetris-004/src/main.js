#!/usr/bin/env node

import { startTerminalGame } from './terminal.js';

if (!startTerminalGame()) process.exitCode = 1;
