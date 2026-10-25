# trailpost-checkout

The Trailpost checkout page: cart on the left, order summary and payment on the right,
stacked on phones. Vite + React, no backend (the cart is sample data in `src/cart.ts`).

```sh
npm install
npm run dev        # http://localhost:5173
npm test           # vitest
npm run typecheck
npm run build      # then `npm run preview` to serve dist/
```

Layout: `src/layout.ts` decides how many columns the checkout grid gets for the current
viewport width; `src/useColumns.ts` keeps it in sync on resize.
