import { computeBalances } from "@/lib/balances";
import { settleUp } from "@/lib/settle";
import { getGroup } from "@/lib/store";

export async function GET(_request: Request, { params }: { params: Promise<{ groupId: string }> }) {
  const { groupId } = await params;
  const group = getGroup(groupId);
  if (!group) {
    return Response.json({ error: "group not found" }, { status: 404 });
  }
  return Response.json({ payments: settleUp(computeBalances(group)) });
}
