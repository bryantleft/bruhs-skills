import { formatCents, type CartItem } from "../cart";

type Props = {
  item: CartItem;
  onQuantity: (quantity: number) => void;
};

export function CartLine({ item, onQuantity }: Props) {
  return (
    <li className="line" data-testid="cart-line">
      <img className="thumb" src={item.image} alt="" width={64} height={64} />
      <div className="line-info">
        <p className="line-name" title={item.name}>
          {item.name}
        </p>
        <p className="line-variant">{item.variant}</p>
        <div className="qty">
          <button type="button" aria-label={`One fewer ${item.name}`} onClick={() => onQuantity(item.quantity - 1)}>
            −
          </button>
          <span aria-label="Quantity">{item.quantity}</span>
          <button type="button" aria-label={`One more ${item.name}`} onClick={() => onQuantity(item.quantity + 1)}>
            +
          </button>
        </div>
      </div>
      <p className="line-price" data-testid="line-price">
        {formatCents(item.priceCents * item.quantity)}
      </p>
    </li>
  );
}
