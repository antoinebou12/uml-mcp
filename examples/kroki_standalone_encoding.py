#!/usr/bin/env python3
"""Standalone Kroki encoding utilities (Option B).

Self-contained script with no project dependencies. Copy this file if you need
Kroki URL generation in another repo without the full Kroki client.

Uses compressobj for encoding that matches Kroki's expectations.
"""

import base64
import zlib


def encode_for_kroki(text: str) -> str:
    """Compress and base64url-encode text for Kroki GET requests."""
    if not text:
        return ""
    compress_obj = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=15)
    compressed = compress_obj.compress(text.encode("utf-8")) + compress_obj.flush()
    encoded = base64.urlsafe_b64encode(compressed).decode("ascii")
    return encoded.replace("+", "-").replace("/", "_")


def kroki_url(
    code: str,
    diagram_type: str = "plantuml",
    fmt: str = "svg",
    base: str = "https://kroki.io",
) -> str:
    """Build a Kroki diagram URL from diagram source code."""
    return f"{base.rstrip('/')}/{diagram_type}/{fmt}/{encode_for_kroki(code)}"


if __name__ == "__main__":
    code = """@startuml
title Banking App - Class Diagram

class Customer {
  - id: string
  - name: string
  - email: string
  + getAccounts(): List<Account>
  + openAccount(accountType: string): Account
}

class Account {
  - accountNumber: string
  - balance: decimal
  - openedAt: DateTime
  + deposit(amount: decimal): void
  + withdraw(amount: decimal): boolean
  + getBalance(): decimal
  + getTransactions(): List<Transaction>
}

class Transaction {
  - id: string
  - amount: decimal
  - date: DateTime
  - type: string
  + getDetails(): string
}

Customer "1" -- "*" Account : owns >
Account "1" -- "*" Transaction : contains >
@enduml"""

    print(kroki_url(code))
