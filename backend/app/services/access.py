from sqlalchemy import select

from app.models import Case, Transaction
from app.repositories.intelligence import Conflict


def lock_mutable_transaction(repo, transaction_id):
    """Lock case before transaction, matching case linking and closure lock order."""
    repo._write()
    initial = repo._transaction(transaction_id)
    initial_case = initial.case_id
    if initial_case:
        case = repo.session.scalar(
            select(Case)
            .where(Case.case_id == initial_case, Case.owner_id == repo.actor_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if case is None or case.status == "closed":
            raise Conflict("Closed or unavailable cases cannot be modified")
    transaction = repo.session.scalar(
        repo._transactions()
        .where(Transaction.transaction_id == transaction_id)
        .with_for_update(of=Transaction)
        .execution_options(populate_existing=True)
    )
    if transaction is None or transaction.case_id != initial_case:
        raise Conflict("Transaction association changed; refresh before retrying")
    return transaction
