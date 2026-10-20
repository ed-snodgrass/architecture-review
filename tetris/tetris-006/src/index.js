import { Game } from './engine.js';

// The terminal adapter will drive this engine in the next implementation task.
const game = new Game();
console.log(`Tetris engine ready (${game.board[0].length} × ${game.board.length}). Terminal interface not yet implemented.`);
