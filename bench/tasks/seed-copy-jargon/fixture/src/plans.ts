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
    tagline:
      "Perfect for passionate builders, indie hackers and side-project visionaries who are ready to take the very first step on their reliability journey without any upfront investment whatsoever.",
    features: [
      "Up to 5 monitors to kickstart your uptime story",
      "Checks every 5 minutes, delivering peace of mind around the clock",
      "Email alerts that keep you in the loop when it matters most",
      "1 beautifully branded public status page to wow your users",
    ],
    cta: "Start your journey",
  },
  {
    id: "team",
    name: "Team",
    monthlyCents: 2400,
    tagline:
      "Designed from the ground up for fast-moving, high-velocity teams that want to leverage best-in-class monitoring to supercharge collaboration and unlock their full potential.",
    features: [
      "Up to 50 monitors to scale seamlessly as you grow",
      "Lightning-fast 30-second checks from 6 global regions",
      "SMS, Slack and PagerDuty alerts for a truly omnichannel experience",
      "5 seats so your whole squad can collaborate in real time",
      "1 year of historical data to power data-driven decisions",
    ],
    cta: "Supercharge your team",
    highlighted: true,
  },
  {
    id: "business",
    name: "Business",
    monthlyCents: 9900,
    tagline:
      "The ultimate enterprise-grade solution for forward-thinking organizations that demand world-class reliability, robust governance and a truly holistic approach to operational excellence.",
    features: [
      "Up to 500 monitors for mission-critical, at-scale workloads",
      "SSO (SAML) to seamlessly streamline secure access",
      "Unlimited seats, because great things happen together",
      "A 99.9% uptime SLA backed by our ironclad commitment to you",
    ],
    cta: "Talk to our experts",
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
