export interface PageQuery {
  page?: unknown;
  pageSize?: unknown;
}

export interface Page {
  page: number;
  pageSize: number;
  offset: number;
}

export const MAX_PAGE_SIZE = 100;
const DEFAULT_PAGE_SIZE = 20;

function positiveInt(value: unknown, fallback: number): number {
  const n = Number(value);
  return Number.isInteger(n) && n > 0 ? n : fallback;
}

export function parsePage(query: PageQuery): Page {
  const page = positiveInt(query.page, 1);
  const pageSize = Math.min(MAX_PAGE_SIZE, positiveInt(query.pageSize, DEFAULT_PAGE_SIZE));
  return { page, pageSize, offset: page * pageSize };
}

export function pageMeta(page: Page, total: number) {
  return {
    page: page.page,
    pageSize: page.pageSize,
    total,
    pages: Math.max(1, Math.ceil(total / page.pageSize)),
  };
}
