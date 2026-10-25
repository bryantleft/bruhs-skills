export type Member = {
  id: string;
  name: string;
};

/** Paid by one member, split evenly between `splitAmong` (who may or may not include the payer). */
export type Expense = {
  id: string;
  description: string;
  paidBy: string;
  amountCents: number;
  date: string;
  splitAmong: string[];
};

/** Money one member already sent another to pay them back. */
export type Repayment = {
  id: string;
  from: string;
  to: string;
  amountCents: number;
  date: string;
};

export type Group = {
  id: string;
  name: string;
  members: Member[];
  expenses: Expense[];
  repayments: Repayment[];
};
