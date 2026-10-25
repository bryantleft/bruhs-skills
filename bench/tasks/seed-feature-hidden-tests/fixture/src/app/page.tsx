import Link from "next/link";
import { totalSpent } from "@/lib/balances";
import { formatCents } from "@/lib/money";
import { listGroups } from "@/lib/store";

export const dynamic = "force-dynamic";

export default function Home() {
  const groups = listGroups();
  return (
    <>
      <h1>Groups</h1>
      <ul className="list">
        {groups.map((g) => (
          <li key={g.id}>
            <Link href={`/groups/${g.id}`}>{g.name}</Link>
            <span className="amount muted">{formatCents(totalSpent(g))} spent</span>
          </li>
        ))}
      </ul>
    </>
  );
}
