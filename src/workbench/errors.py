"""Errors that stop a run. Each message says what is wrong and what to add or fix."""


class WorkbenchError(Exception):
    """Base for errors that abort the run before outputs can be trusted."""


class InputError(WorkbenchError):
    """A required input file is missing or malformed."""


class ContractError(WorkbenchError):
    """An Order Form or Amendment could not be turned into cited Contract Terms."""
