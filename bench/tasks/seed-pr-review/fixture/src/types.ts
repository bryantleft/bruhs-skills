export type WebhookEvent = {
  id: string;
  type: string;
  createdAt: string;
  data: Record<string, unknown>;
};
