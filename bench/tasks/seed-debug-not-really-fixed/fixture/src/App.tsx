import { useState } from "react";
import { SAMPLE_CART, totals, type CartItem } from "./cart";
import { CartLine } from "./components/CartLine";
import { Summary } from "./components/Summary";
import { useColumns } from "./useColumns";

export function App() {
  const [items, setItems] = useState<CartItem[]>(SAMPLE_CART);
  const columns = useColumns();

  const setQuantity = (sku: string, quantity: number) =>
    setItems((current) =>
      current.flatMap((i) => (i.sku !== sku ? [i] : quantity > 0 ? [{ ...i, quantity }] : [])),
    );

  return (
    <div className="page">
      <header className="topbar">
        <span className="brand">Trailpost</span>
        <span className="secure">Secure checkout</span>
      </header>
      <div className="checkout" style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}>
        <section className="cart" aria-labelledby="cart-heading">
          <h1 id="cart-heading">Your cart</h1>
          {items.length === 0 ? (
            <p className="empty">Your cart is empty.</p>
          ) : (
            <ul className="lines">
              {items.map((item) => (
                <CartLine key={item.sku} item={item} onQuantity={(q) => setQuantity(item.sku, q)} />
              ))}
            </ul>
          )}
        </section>
        <Summary totals={totals(items)} disabled={items.length === 0} />
      </div>
    </div>
  );
}
