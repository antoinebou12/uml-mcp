#!/usr/bin/env python3
"""Generate Kroki diagram URLs using the project's Kroki client (Option A).

This is the recommended approach: use the Kroki client for encoding and URL
generation. It supports all diagram types and output formats, with validation.
"""

from tools.kroki.kroki import Kroki

# Example: Banking App class diagram (from banking-class.puml)
CODE = """@startuml
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


def main() -> None:
    client = Kroki()
    url = client.get_url("plantuml", CODE, "svg")
    print(url)


if __name__ == "__main__":
    main()
