import { notFound } from "next/navigation";
import { computeBalances, totalSpent } from "@/lib/balances";
import { formatCents } from "@/lib/money";
import { getGroup } from "@/lib/store";

export const dynamic = "force-dynamic";

export default async function GroupPage({ params }: { params: Promise<{ groupId: string }> }) {
  const { groupId } = await params;
  const group = getGroup(groupId);
  if (!group) notFound();

  const names = new Map(group.members.map((m) => [m.id, m.name]));
  const balances = computeBalances(group);

  return (
    <>
      <h1>{group.name}</h1>
      <p className="muted">
        {group.members.length} people · {formatCents(totalSpent(group))} spent
      </p>

      <h2>Balances</h2>
      <ul className="list">
        {balances.map((b) => (
          <li key={b.memberId}>
            <span>{b.name}</span>
            <span className={`amount ${b.cents > 0 ? "owed" : b.cents < 0 ? "owes" : "muted"}`}>
              {b.cents > 0
                ? `is owed ${formatCents(b.cents)}`
                : b.cents < 0
                  ? `owes ${formatCents(-b.cents)}`
                  : "square"}
            </span>
          </li>
        ))}
      </ul>

      <h2>Expenses</h2>
      {group.expenses.length === 0 ? (
        <p className="muted">No expenses yet.</p>
      ) : (
        <ul className="list">
          {group.expenses.map((e) => (
            <li key={e.id}>
              <span>
                {e.description}
                <br />
                <small className="muted">
                  {names.get(e.paidBy)} paid · {e.date}
                </small>
              </span>
              <span className="amount">{formatCents(e.amountCents)}</span>
            </li>
          ))}
        </ul>
      )}

      {group.repayments.length > 0 && (
        <>
          <h2>Paid back</h2>
          <ul className="list">
            {group.repayments.map((r) => (
              <li key={r.id}>
                <span>
                  {names.get(r.from)} paid {names.get(r.to)}
                  <br />
                  <small className="muted">{r.date}</small>
                </span>
                <span className="amount">{formatCents(r.amountCents)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}
