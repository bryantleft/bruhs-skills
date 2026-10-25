/** Widest viewport (px) that still gets the stacked, single-column checkout. */
export const STACK_BELOW = 380;

/** Columns for the checkout grid: cart and summary side by side, or stacked on phones. */
export function columnsFor(viewportWidth: number): 1 | 2 {
  return viewportWidth < STACK_BELOW ? 1 : 2;
}
