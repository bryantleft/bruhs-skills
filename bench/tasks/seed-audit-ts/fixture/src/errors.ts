export class HttpError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "HttpError";
  }
}

export function notFound(what: string): HttpError {
  return new HttpError(404, `${what} not found`);
}
