export type TaskCompletionNotification = {
  completedTask: string;
  runName: string;
  completedAt: string;
};

export type TaskCompletionNotifier = {
  notify: (notification: TaskCompletionNotification) => Promise<void>;
};

type TaskCompletionNotifierOptions = {
  webhookUrl?: string;
  appendLog: (entry: string) => void;
  timeoutMs?: number;
};

export function createTaskCompletionNotifier(
  options: TaskCompletionNotifierOptions,
): TaskCompletionNotifier {
  const timeoutMs = options.timeoutMs ?? 5_000;

  if (!options.webhookUrl) {
    options.appendLog('[notification] type=task-complete status=disabled');
    return { notify: async () => {} };
  }

  const webhookUrl = options.webhookUrl;
  return {
    async notify(notification): Promise<void> {
      const controller = new AbortController();
      let timedOut = false;
      const timeout = setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, timeoutMs);

      try {
        const response = await fetch(webhookUrl, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            value1: notification.completedTask,
            value2: notification.runName,
            value3: notification.completedAt,
          }),
          signal: controller.signal,
        });
        if (response.ok) {
          options.appendLog(
            `[notification] type=task-complete status=delivered httpStatus=${response.status}`,
          );
        } else {
          options.appendLog(
            `[notification] type=task-complete status=failed httpStatus=${response.status}`,
          );
        }
      } catch {
        options.appendLog(
          `[notification] type=task-complete status=failed reason=${JSON.stringify(timedOut ? 'timeout' : 'network')}`,
        );
      } finally {
        clearTimeout(timeout);
      }
    },
  };
}
