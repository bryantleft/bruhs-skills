export interface RefundResult {
  refundId: string;
  amountCents: number;
}

export async function refundPayment(
  baseUrl: string,
  paymentRef: string,
  amountCents: number,
): Promise<RefundResult> {
  const res = await fetch(`${baseUrl}/payments/${encodeURIComponent(paymentRef)}/refunds`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ amount_cents: amountCents }),
    signal: AbortSignal.timeout(10_000),
  });
  if (!res.ok) {
    throw new Error(`refund failed: ${res.status} ${await res.text()}`);
  }
  const data = (await res.json()) as { id: string; amount_cents: number };
  return { refundId: data.id, amountCents: data.amount_cents };
}
