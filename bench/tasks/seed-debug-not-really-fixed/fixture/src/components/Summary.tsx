import { useState } from "react";
import { formatCents, type Totals } from "../cart";

type Props = {
  totals: Totals;
  disabled: boolean;
};

export function Summary({ totals, disabled }: Props) {
  const [code, setCode] = useState("");
  const [paying, setPaying] = useState(false);

  return (
    <aside className="summary" aria-labelledby="summary-heading">
      <h2 id="summary-heading">Order summary</h2>
      <form className="promo" onSubmit={(e) => e.preventDefault()}>
        <label htmlFor="promo-code">Promo code</label>
        <div className="promo-row">
          <input id="promo-code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="TRAIL10" />
          <button type="submit" disabled={!code.trim()}>
            Apply
          </button>
        </div>
      </form>
      <dl className="totals">
        <dt>Subtotal</dt>
        <dd>{formatCents(totals.subtotalCents)}</dd>
        <dt>Shipping</dt>
        <dd>{totals.shippingCents === 0 ? "Free" : formatCents(totals.shippingCents)}</dd>
        <dt>Estimated tax</dt>
        <dd>{formatCents(totals.taxCents)}</dd>
        <dt className="grand">Total</dt>
        <dd className="grand">{formatCents(totals.totalCents)}</dd>
      </dl>
      <button type="button" className="pay" disabled={disabled || paying} onClick={() => setPaying(true)}>
        {paying ? "Processing…" : `Pay ${formatCents(totals.totalCents)}`}
      </button>
    </aside>
  );
}
