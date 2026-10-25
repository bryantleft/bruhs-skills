import { totalSpent } from "@/lib/balances";
import { listGroups } from "@/lib/store";

export function GET() {
  const groups = listGroups().map((g) => ({
    id: g.id,
    name: g.name,
    members: g.members,
    totalCents: totalSpent(g),
  }));
  return Response.json({ groups });
}
