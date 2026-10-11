export interface DispatchRequestPayload {
  text: string;
  scenario: unknown;
  context: unknown;
  timeMinutes?: number;
}

export interface DispatchResponse {
  assistantText?: string;
  scenario?: unknown;
  frame?: unknown;
  [key: string]: unknown;
}

export function toggleDispatchInput(isOpen: boolean): boolean {
  return !isOpen;
}

export function createDispatchPayload(
  text: string,
  scenario: unknown,
  context: unknown,
): DispatchRequestPayload {
  return { text: text.trim(), scenario, context };
}

export type DispatchFetcher = (
  input: string,
  init: { method: string; headers: Record<string, string>; body: string },
) => Promise<{ ok: boolean; status: number; json: () => Promise<DispatchResponse> }>;

export async function submitDispatch(
  fetcher: DispatchFetcher,
  endpoint: string,
  text: string,
  scenario: unknown,
  context: unknown,
  timeMinutes = 30,
): Promise<DispatchResponse> {
  const payload = { ...createDispatchPayload(text, scenario, context), timeMinutes };
  if (!payload.text) throw new Error('Dispatch text is required');

  const response = await fetcher(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`dispatch ${response.status}`);
  return response.json();
}

export const api = { toggleDispatchInput, createDispatchPayload, submitDispatch };
(globalThis as typeof globalThis & { AeroDispatch?: typeof api }).AeroDispatch = api;
