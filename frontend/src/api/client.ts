import type { ApiErrorPayload } from "../types";

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "";
const REQUEST_TIMEOUT_MS = 8_000;

export class ApiError extends Error {
  readonly status: number;
  readonly isTimeout: boolean;

  constructor(message: string, status: number, isTimeout = false) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.isTimeout = isTimeout;
  }
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as ApiErrorPayload;
    return payload.detail ?? `Request failed with status ${response.status}`;
  } catch {
    return `Request failed with status ${response.status}`;
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const signal = init?.signal ?? controller.signal;

  try {
    const response = await fetch(`${baseUrl}${path}`, {
      ...init,
      signal,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...init?.headers
      }
    });

    if (!response.ok) {
      throw new ApiError(await parseError(response), response.status);
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The NEXORA backend did not respond in time.", 408, true);
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export const apiClient = {
  get<T>(path: string): Promise<T> {
    return request<T>(path, { method: "GET" });
  },
  post<T>(path: string, body: unknown): Promise<T> {
    return request<T>(path, { method: "POST", body: JSON.stringify(body) });
  }
};
