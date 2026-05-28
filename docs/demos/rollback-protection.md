# Demo: Rollback Protection

## Goal

Show rollback when repair degrades score.

## Flow

- Repair attempt lowers evaluation score
- EvalOS rolls back to previous best response
- Trace logs rollback event
