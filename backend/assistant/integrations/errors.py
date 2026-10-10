"""Errors safe for API responses; never expose tokens or provider request URLs."""


class ConfigError(RuntimeError):
    """A required provider credential, model, or optional dependency is missing."""


class ProviderError(RuntimeError):
    """A remote provider failed or returned an invalid response."""


class UnsafeURLError(ValueError):
    """A research URL would cross the public-internet boundary."""
