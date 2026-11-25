"""Small, executable examples shipped with Ruleset Notebook."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NotebookExample:
    """A named rules-and-inputs draft that can be loaded in the GUI."""

    key: str
    title: str
    description: str
    rules_text: str
    inputs_text: str
    expected_outputs: tuple[str, ...]


EXAMPLES = (
    NotebookExample(
        key="addition",
        title="Addition by counting",
        description="Recursion, guards, ordered rules, and multiple inputs.",
        rules_text="""\
# Move one unit from y to x until y reaches zero.
add(x, 0) => x
add(x, y) => add(inc(x), dec(y)) when y > 0
""",
        inputs_text="""\
add(2, 3)
add(10, 4)
""",
        expected_outputs=("5", "14"),
    ),
    NotebookExample(
        key="multiply-divide",
        title="Multiply and divide from add/sub",
        description="Repeated addition and subtraction over positive whole numbers.",
        rules_text=(
            """\
# Base arithmetic axioms: move one unit at a time.
add-zero: add(x, 0) => x
add-step: add(x, y) => add(inc(x), dec(y)) when y > 0
sub-zero: sub(x, 0) => x
sub-step: sub(x, y) => sub(dec(x), dec(y)) when y > 0

# Multiplication is repeated addition.
mul-zero: mul(x, 0) => 0
mul-step: mul(x, y) => add(x, mul(x, dec(y))) when y > 0

# Division tracks a quotient while repeatedly subtracting a positive divisor.
div-start: div(x, y) => quotient(x, y, 0) when y > 0
"""
            "quotient-step: quotient(x, y, "
            "count) => quotient(sub(x, y), y, inc(count)) when x >= y "
            "and y > 0\n"
            """\
quotient-done: quotient(x, y, count) => count when x < y and y > 0
"""
        ),
        inputs_text="""\
sub(9, 4)
mul(3, 4)
mul(6, 2)
div(12, 3)
div(14, 4)
""",
        expected_outputs=("5", "12", "12", "4", "3"),
    ),
    NotebookExample(
        key="factorial",
        title="Recursive factorial",
        description="Base case and guarded recursion for integers from 0 to 20.",
        rules_text="""\
factorial-zero: factorial(0) => 1
factorial-step: factorial(n) => mul(n, factorial(dec(n))) when n > 0
""",
        inputs_text="""\
factorial(0)
factorial(1)
factorial(5)
factorial(10)
factorial(20)
""",
        expected_outputs=("1", "1", "120", "3628800", "2432902008176640000"),
    ),
    NotebookExample(
        key="larger",
        title="Choose the larger value",
        description="A guarded rule followed by an ordered fallback rule.",
        rules_text="""\
# The first matching rule wins, so the unguarded rule is the fallback.
larger-left: larger(x, y) => x when x >= y
larger-right: larger(x, y) => y
""",
        inputs_text="""\
larger(9, 4)
larger(2, 7)
larger(-1, -1)
""",
        expected_outputs=("9", "7", "-1"),
    ),
    NotebookExample(
        key="records",
        title="Unpack simple records",
        description="Structural patterns bind and extract parts of nested data.",
        rules_text="""\
unbox: unbox(box(x)) => x
first: first(pair(x, y)) => x
second: second(pair(x, y)) => y
""",
        inputs_text="""\
unbox(box(42))
first(pair("Ada", "Lovelace"))
second(pair(10, 20))
""",
        expected_outputs=("42", "'Ada'", "20"),
    ),
    NotebookExample(
        key="booleans",
        title="Boolean logic and De Morgan's laws",
        description="Truth tables for not/and/or plus symbolic De Morgan rewrites.",
        rules_text="""\
# Negation.
not-true: not(true) => false
not-false: not(false) => true

# Conjunction truth table.
and-true-true: and(true, true) => true
and-true-false: and(true, false) => false
and-false-true: and(false, true) => false
and-false-false: and(false, false) => false

# Disjunction truth table.
or-true-true: or(true, true) => true
or-true-false: or(true, false) => true
or-false-true: or(false, true) => true
or-false-false: or(false, false) => false

# De Morgan's laws are most visible with unresolved symbolic inputs.
de-morgan-and: not(and(x, y)) => or(not(x), not(y))
de-morgan-or: not(or(x, y)) => and(not(x), not(y))
""",
        inputs_text="""\
not(true)
and(true, false)
or(false, true)
not(and(left, right))
not(or(left, right))
not(and(true, false))
""",
        expected_outputs=(
            "False",
            "False",
            "True",
            "or(not(left()), not(right()))",
            "and(not(left()), not(right()))",
            "True",
        ),
    ),
    NotebookExample(
        key="purchase-approvals",
        title="Purchase approvals",
        description="Route requests by amount or send restricted purchases to finance.",
        rules_text="""\
# purchase(request ID, category, amount in cents)
# Restricted purchases go to finance at any amount.
restricted-purchase: purchase(id, restricted(), cents) => finance_review(id)
# Team leads review up to $500, managers up to $5,000, then finance.
team-lead: purchase(id, kind, cents) => lead_review(id) when cents <= 50000
manager: purchase(id, kind, cents) => manager_review(id) when cents <= 500000
finance: purchase(id, kind, cents) => finance_review(id)
""",
        inputs_text="""\
purchase(101, restricted(), 20000)
purchase(102, standard(), 50000)
purchase(103, standard(), 50001)
purchase(104, standard(), 500000)
purchase(105, standard(), 500001)
""",
        expected_outputs=(
            "finance_review(101)",
            "lead_review(102)",
            "manager_review(103)",
            "manager_review(104)",
            "finance_review(105)",
        ),
    ),
    NotebookExample(
        key="invoice-reconciliation",
        title="Invoice reconciliation",
        description="Match invoice numbers and calculate payment differences in cents.",
        rules_text=(
            """\
# invoice(invoice number, amount due in cents)
# payment(referenced invoice number, amount paid in cents)
paid-in-full: reconcile(invoice(id, cents), payment(id, cents)) => matched(id)
"""
            "underpaid: reconcile(invoice(id, due), payment(id, paid))"
            " => underpayment(id, sub(due, paid)) when paid < due\n"
            "overpaid: reconcile(invoice(id, due), payment(id, paid))"
            " => overpayment(id, sub(paid, due)) when paid > due\n"
            "wrong-invoice: reconcile(invoice(id, due), payment(ref, paid))"
            " => unmatched_payment(ref)\n"
        ),
        inputs_text="""\
reconcile(invoice(3001, 12500), payment(3001, 12500))
reconcile(invoice(3002, 12500), payment(3002, 12000))
reconcile(invoice(3003, 12500), payment(3003, 13250))
reconcile(invoice(3004, 12500), payment(3999, 12500))
""",
        expected_outputs=(
            "matched(3001)",
            "underpayment(3002, 500)",
            "overpayment(3003, 750)",
            "unmatched_payment(3999)",
        ),
    ),
    NotebookExample(
        key="expense-review",
        title="Expense review",
        description="Review a batch of claims for receipts and category limits.",
        rules_text="""\
# claim(claim ID, category, amount in cents, receipt status)
missing-receipt: claim(id, kind, cents, missing()) => needs_receipt(id)
# Sample caps are $50 for meals, $100 for transport, and $75 for supplies.
meal-cap: claim(id, meal(), cents, attached()) => check_cap(id, cents, 5000)
transport-cap: claim(id, transport(), cents, attached()) => check_cap(id, cents, 10000)
supplies-cap: claim(id, supplies(), cents, attached()) => check_cap(id, cents, 7500)
unknown-category: claim(id, kind, cents, attached()) => manual_review(id)

above-cap: check_cap(id, cents, cap) => over_limit(id, sub(cents, cap)) when cents > cap
within-cap: check_cap(id, cents, cap) => approved(id)
""",
        inputs_text="""\
claim(201, meal(), 4200, attached())
claim(202, meal(), 5000, attached())
claim(203, meal(), 5001, attached())
claim(204, transport(), 10050, attached())
claim(205, supplies(), 6700, attached())
claim(206, meal(), 6500, missing())
claim(207, training(), 3800, attached())
""",
        expected_outputs=(
            "approved(201)",
            "approved(202)",
            "over_limit(203, 1)",
            "over_limit(204, 50)",
            "approved(205)",
            "needs_receipt(206)",
            "manual_review(207)",
        ),
    ),
)

DEFAULT_EXAMPLE = EXAMPLES[0]


def example_by_key(key: str) -> NotebookExample:
    """Return a shipped example by its stable key."""

    for example in EXAMPLES:
        if example.key == key:
            return example
    raise KeyError(key)
