"""Billing Support Assistant — a local support-agent demo with bounded execution controls.

Billing Support Assistant reads customer-scoped records and proposes a resolution,
then authorizes every money/account-touching action through a deny-by-default
policy gate and a grounding gate before acting. When an action isn't explicitly
allowed, or can't be grounded in the customer's records, Billing Support Assistant escalates to a
local human-review case file. Arbitrary answer prose is not semantically verified.
"""

__version__ = "0.1.0"
