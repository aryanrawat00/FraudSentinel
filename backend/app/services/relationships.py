"""Bounded directed graph from observed transfers; associations are not identity."""

from collections import defaultdict

from sqlalchemy import or_

from app.models import Transaction
from app.schemas.workflow import GraphQuery


class RelationshipService:
    def __init__(self, repo):
        self.repo = repo

    def graph(self, account_id, query: GraphQuery | None = None):
        query = query or GraphQuery()
        root = self.repo._account(account_id)
        discovered = {account_id}
        frontier = {account_id}
        records = {}
        truncated = False
        for _ in range(query.depth):
            statement = self.repo._transactions().where(
                or_(
                    Transaction.source_account_id.in_(frontier),
                    Transaction.destination_account_id.in_(frontier),
                ),
                Transaction.is_synthetic.is_(root.is_synthetic),
            )
            if records:
                statement = statement.where(Transaction.transaction_id.not_in(records))
            if query.occurred_from:
                statement = statement.where(Transaction.occurred_at >= query.occurred_from)
            if query.occurred_before:
                statement = statement.where(Transaction.occurred_at < query.occurred_before)
            remaining = query.limit - len(records)
            rows = list(
                self.repo.session.scalars(
                    statement.order_by(
                        Transaction.occurred_at.desc(), Transaction.transaction_id
                    ).limit(remaining + 1)
                )
            )
            truncated |= len(rows) > remaining
            next_frontier = set()
            for row in rows[:remaining]:
                if not row.source_account_id or not row.destination_account_id:
                    continue
                records[row.transaction_id] = row
                next_frontier.update([row.source_account_id, row.destination_account_id])
            frontier = next_frontier - discovered
            discovered |= next_frontier
            if truncated or not frontier:
                break
        return self.from_records(account_id, list(records.values()), query.depth, truncated)

    @staticmethod
    def from_records(account_id, rows, depth=0, truncated=False):
        """Build findings for a pre-scoped bounded set, including disconnected case records."""
        records = {
            row.transaction_id: row
            for row in rows
            if row.source_account_id and row.destination_account_id
        }
        discovered = {account_id} if account_id else set()
        discovered.update(
            a
            for row in records.values()
            for a in (row.source_account_id, row.destination_account_id)
        )
        pairs = defaultdict(list)
        devices = defaultdict(list)
        for row in records.values():
            pairs[(row.source_account_id, row.destination_account_id)].append(row)
            if row.device_id:
                devices[row.device_id].append(row)
        edges = []
        findings = []

        def finding(kind, accounts, rows, description):
            findings.append(
                {
                    "type": kind,
                    "account_ids": sorted(set(accounts)),
                    "source_transaction_ids": sorted({r.transaction_id for r in rows}),
                    "description": description,
                    "classification": "system_finding",
                }
            )

        for (source, destination), rows in sorted(pairs.items()):
            edges.append(
                {
                    "source": source,
                    "destination": destination,
                    "relationship_type": "recorded_transfer",
                    "transaction_count": len(rows),
                    "transaction_ids": sorted(r.transaction_id for r in rows),
                    "completed_count": sum(r.status == "completed" for r in rows),
                    "explanation": (
                        "Recorded directed transactions; pending/failed/unknown statuses "
                        "do not prove settled funds."
                    ),
                }
            )
            if len(rows) >= 3:
                finding(
                    "repeated_transfers",
                    [source, destination],
                    rows,
                    "Repeated recorded transfers; repetition alone is not suspicious activity "
                    "or shared ownership.",
                )
        outgoing = defaultdict(set)
        for source, destination in pairs:
            outgoing[source].add(destination)
        for source, destinations in sorted(outgoing.items()):
            if len(destinations) >= 3:
                rows = [r for d in destinations for r in pairs[(source, d)]]
                finding(
                    "fan_out",
                    [source, *destinations],
                    rows,
                    "One account has multiple recorded counterparties in this bounded graph; "
                    "review timing and business purpose.",
                )
        sources = sorted(outgoing)
        for index, source in enumerate(sources):
            for other in sources[index + 1 :]:
                common = outgoing[source] & outgoing[other]
                if common:
                    rows = [
                        r for d in common for key in [(source, d), (other, d)] for r in pairs[key]
                    ]
                    finding(
                        "shared_counterparty",
                        [source, other, *common],
                        rows,
                        "Accounts share recorded counterparties; "
                        "common ownership is not established.",
                    )
        seen_cycles = set()
        for source in sources:
            for second in outgoing[source]:
                for third in outgoing.get(second, set()):
                    if source in outgoing.get(third, set()) and len({source, second, third}) == 3:
                        cycle = (source, second, third)
                        key = min(cycle[i:] + cycle[:i] for i in range(3))
                        if key not in seen_cycles:
                            seen_cycles.add(key)
                            rows = (
                                pairs[(source, second)]
                                + pairs[(second, third)]
                                + pairs[(third, source)]
                            )
                            finding(
                                "directed_cycle",
                                cycle,
                                rows,
                                "A three-account directed cycle is recorded. This does not "
                                "establish chronological fund flow or laundering.",
                            )
        for rows in devices.values():
            accounts = {r.source_account_id for r in rows}
            if len(accounts) > 1:
                finding(
                    "shared_device",
                    accounts,
                    rows,
                    "Multiple source accounts have the same observed device reference; "
                    "account ownership is not inferred.",
                )
        # Dense graphs can have many inferred pairs; expose the bound explicitly.
        finding_truncated = len(findings) > 100
        return {
            "root_account_id": account_id,
            "nodes": [{"account_id": a, "is_root": a == account_id} for a in sorted(discovered)],
            "edges": edges,
            "findings": findings[:100],
            "transaction_count": len(records),
            "truncated": truncated or finding_truncated,
            "depth": depth,
            "limitations": [
                "Bounded observed graph, not a complete financial network.",
                "No legal identity, ownership, geographic proximity "
                "or fraud conclusion is inferred.",
                "Synthetic and non-synthetic datasets are analyzed separately.",
            ],
        }
