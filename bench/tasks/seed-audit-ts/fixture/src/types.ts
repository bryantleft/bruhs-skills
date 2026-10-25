export type Role = "customer" | "admin";
export type OrderStatus = "pending" | "paid" | "shipped" | "refunded" | "cancelled";

export interface User {
  id: number;
  email: string;
  name: string;
  password_hash: string;
  role: Role;
  created_at: string;
}

export type PublicUser = Pick<User, "id" | "email" | "name" | "role">;

export interface Product {
  id: number;
  sku: string;
  name: string;
  price_cents: number;
  stock: number;
}

export interface Order {
  id: number;
  user_id: number;
  status: OrderStatus;
  total_cents: number;
  note: string | null;
  payment_ref: string | null;
  created_at: string;
}

export interface OrderItem {
  id: number;
  order_id: number;
  product_id: number;
  quantity: number;
  unit_price_cents: number;
}

export interface OrderInput {
  items: { productId: number; quantity: number }[];
  note?: string;
}

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Express {
    interface Request {
      user?: PublicUser;
    }
  }
}
