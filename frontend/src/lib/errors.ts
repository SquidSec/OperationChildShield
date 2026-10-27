/** An upstream API failure that keeps the HTTP status available to callers. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Status from an upstream error, or null when the failure has no status. */
export function apiErrorStatus(error: unknown): number | null {
  return error instanceof ApiError ? error.status : null;
}

/**
 * Turns any thrown value into copy that is safe to show visitors. Raw API
 * bodies and stack traces stay in server logs; users only get actionable text.
 */
export function friendlyErrorMessage(
  error: unknown,
  fallback = "Something went wrong while loading this data. Please try again."
): string {
  const message = error instanceof Error ? error.message : "";
  if (/timed out/i.test(message)) {
    return "This request took too long. The congressional data source may be busy — please try again in a moment.";
  }
  const status = apiErrorStatus(error);
  if (status !== null && status >= 500) {
    return "Our congressional data source is temporarily unavailable. Please try again shortly.";
  }
  if (status !== null && status >= 400) {
    return "That request could not be completed. Check the details and try again.";
  }
  return fallback;
}
