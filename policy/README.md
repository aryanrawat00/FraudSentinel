# Agent security policies

Reserved for the OPA firewall phase. No agent execution endpoint is enabled yet.
Future tools must pass backend identity, role, case-scope, OPA, and approval
checks before a database executor can run. Implement and test ALLOW, DENY, and
REQUIRE_APPROVAL here before exposing tools.
