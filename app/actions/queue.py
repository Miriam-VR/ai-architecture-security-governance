from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol


class ActionQueue(Protocol):
    def send(self, message: dict[str, Any]) -> None: ...


class InlineQueue:
    """Dev/test: delivers synchronously. `deliver_twice=True` simulates SQS at-least-once duplicates."""

    def __init__(self, deliver_twice: bool = False) -> None:
        self.handler: Callable[[dict[str, Any]], Any] | None = None
        self.deliver_twice, self.sent = deliver_twice, []

    def send(self, message: dict[str, Any]) -> None:
        self.sent.append(message)
        if self.handler:
            for _ in range(2 if self.deliver_twice else 1):
                self.handler(message)


class SqsQueue:
    def __init__(self, queue_url: str, region: str, client: Any = None) -> None:
        import boto3

        self._url, self._client = queue_url, client or boto3.client("sqs", region_name=region)

    def send(self, message: dict[str, Any]) -> None:
        self._client.send_message(QueueUrl=self._url, MessageBody=json.dumps(message))
