export interface SSECallbacks {
  onToken(token: string): void;
  onError(error: string): void;
  onDone(): void;
}

export async function streamChat(
  message: string,
  callbacks: SSECallbacks,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;

  try {
    response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
      signal,
    });
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : "Network error";
    callbacks.onError(errorMessage);
    callbacks.onDone();
    return;
  }

  if (!response.ok) {
    callbacks.onError(`Request failed with status ${response.status}`);
    callbacks.onDone();
    return;
  }

  if (!response.body) {
    callbacks.onError("Response body is empty");
    callbacks.onDone();
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) {
          continue;
        }

        const data = line.slice(6);

        if (data === "[DONE]") {
          return;
        }

        try {
          const parsed = JSON.parse(data) as Record<string, unknown>;

          if (typeof parsed.token === "string") {
            callbacks.onToken(parsed.token);
          } else if (typeof parsed.error === "string") {
            callbacks.onError(parsed.error);
          }
        } catch {
          // malformed JSON line — skip
        }
      }
    }
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : "Stream read error";
    callbacks.onError(errorMessage);
  } finally {
    reader.releaseLock();
    callbacks.onDone();
  }
}
