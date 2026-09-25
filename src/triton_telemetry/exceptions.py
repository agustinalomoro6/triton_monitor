

from __future__ import annotations


class TritonError(Exception):

    pass


class ProviderTimeoutError(TritonError):

    pass


class CorruptedPayloadError(TritonError):
  
    pass


class NetworkPeeringError(TritonError):
    pass
