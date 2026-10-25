export type CartItem = {
  sku: string;
  name: string;
  variant: string;
  priceCents: number;
  quantity: number;
  image: string;
};

export const SAMPLE_CART: CartItem[] = [
  {
    sku: "SB-ULD-LW",
    name: "Ultralight Down Sleeping Bag — Long/Wide, Left Zip",
    variant: "Slate · 20°F",
    priceCents: 38900,
    quantity: 1,
    image: "/img/sleeping-bag.svg",
  },
  {
    sku: "TP-2P",
    name: "Ridgeline 2P Tent",
    variant: "Sand",
    priceCents: 42500,
    quantity: 1,
    image: "/img/tent.svg",
  },
  {
    sku: "HL-400",
    name: "Headlamp 400",
    variant: "Black",
    priceCents: 3995,
    quantity: 2,
    image: "/img/headlamp.svg",
  },
];

export const FREE_SHIPPING_FROM_CENTS = 9900;
export const SHIPPING_CENTS = 895;
export const TAX_RATE = 0.0825;

export type Totals = {
  subtotalCents: number;
  shippingCents: number;
  taxCents: number;
  totalCents: number;
};

export function totals(items: CartItem[]): Totals {
  const subtotalCents = items.reduce((sum, i) => sum + i.priceCents * i.quantity, 0);
  const shippingCents = subtotalCents === 0 || subtotalCents >= FREE_SHIPPING_FROM_CENTS ? 0 : SHIPPING_CENTS;
  const taxCents = Math.round(subtotalCents * TAX_RATE);
  return { subtotalCents, shippingCents, taxCents, totalCents: subtotalCents + shippingCents + taxCents };
}

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export function formatCents(cents: number): string {
  return usd.format(cents / 100);
}
