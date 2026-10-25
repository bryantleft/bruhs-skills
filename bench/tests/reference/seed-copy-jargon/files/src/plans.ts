export type Plan = {
  id: "hobby" | "team" | "business";
  name: string;
  /** monthly price in cents; 0 = free */
  monthlyCents: number;
  tagline: string;
  features: string[];
  cta: string;
  highlighted?: boolean;
};

export const PLANS: Plan[] = [
  {
    id: "hobby",
    name: "Hobby",
    monthlyCents: 0,
    tagline: "For side projects.",
    features: ["5 monitors", "Checks every 5 minutes", "Email alerts", "1 status page"],
    cta: "Start for free",
  },
  {
    id: "team",
    name: "Team",
    monthlyCents: 2400,
    tagline: "For teams running production sites and APIs.",
    features: [
      "50 monitors",
      "30-second checks from 6 regions",
      "SMS, Slack and PagerDuty alerts",
      "5 seats",
      "1 year of history",
    ],
    cta: "Start a free trial",
    highlighted: true,
  },
  {
    id: "business",
    name: "Business",
    monthlyCents: 9900,
    tagline: "For larger organizations.",
    features: ["500 monitors", "SSO (SAML)", "Unlimited seats", "99.9% uptime SLA"],
    cta: "Contact sales",
  },
];

/** "$24" for whole dollars, "$24.50" otherwise, "Free" for 0. */
export function formatPrice(cents: number): string {
  if (cents === 0) return "Free";
  const dollars = cents / 100;
  return Number.isInteger(dollars) ? `$${dollars}` : `$${dollars.toFixed(2)}`;
}

/** Yearly billing: pay for 10 months, get 12. */
export function yearlyCents(monthlyCents: number): number {
  return monthlyCents * 10;
}
