"""Domain-specific errors surfaced by the audio and modeling pipeline."""


class VoxNeuroError(Exception):
    """Base class for expected user-facing failures."""


class AudioReadError(VoxNeuroError):
    """Raised when an audio container cannot be decoded safely."""


class AudioValidationError(VoxNeuroError):
    """Raised when a recording fails one or more configured quality checks."""


class FeatureExtractionError(VoxNeuroError):
    """Raised when required acoustic measurements cannot be calculated."""


class DatasetError(VoxNeuroError):
    """Raised when dataset structure or provenance checks fail."""


class ModelCompatibilityError(VoxNeuroError):
    """Raised when a model bundle and incoming feature schema disagree."""
