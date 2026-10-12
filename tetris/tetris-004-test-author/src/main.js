// Terminal entry point. Gameplay modules will be connected in subsequent tasks.
if (!process.stdin.isTTY || !process.stdout.isTTY) {
  console.error('Tetris requires an interactive terminal. Run npm start in a terminal.');
  process.exitCode = 1;
} else {
  process.stdout.write('Tetris\nPress Ctrl+C to exit.\n');

  // Keep the terminal session open while waiting for player input.
  process.stdin.resume();

  function exit() {
    process.stdin.pause();
    process.exit(0);
  }

  process.once('SIGINT', exit);
  process.once('SIGTERM', exit);
  process.stdin.once('end', exit);
}
