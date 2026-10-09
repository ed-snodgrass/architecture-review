#!/usr/bin/env node

import { Game } from './game.js';
import { renderGame } from './render.js';

process.stdout.write(renderGame(new Game()));
