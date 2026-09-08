class ConversionError(ValueError):
    """Raised when input JSX cannot be represented by the supported A2UI subset."""


class ParseError(ConversionError):
    """Raised for invalid or unsupported declarative JSX syntax."""


class ValidationError(ConversionError):
    """Raised when a JSX or A2UI component violates its contract."""


class A2UIProtocolOutputError(ValidationError):
    """Raised when the compiler emits A2UI that violates the wire protocol."""
