"""Example and template sources for ``c4_model``."""

from __future__ import annotations

import json

#: The classic internet banking system, at all three levels.
BANKING: dict = {
    "title": "Internet banking system",
    "description": "Customers view balances and make payments online",
    "people": [
        {
            "id": "customer",
            "name": "Personal Banking Customer",
            "description": "A customer of the bank, with personal bank accounts",
        },
        {
            "id": "staff",
            "name": "Back Office Staff",
            "description": "Bank staff who handle customer support",
            "external": False,
        },
    ],
    "systems": [
        {
            "id": "banking",
            "name": "Internet Banking System",
            "description": "Lets customers view their accounts and make payments",
            "containers": [
                {
                    "id": "web",
                    "name": "Web Application",
                    "technology": "Java and Spring MVC",
                    "kind": "app",
                    "description": "Delivers the static content and the single-page app",
                },
                {
                    "id": "spa",
                    "name": "Single-Page App",
                    "technology": "TypeScript and React",
                    "kind": "web",
                    "service": "react",
                    "description": "All the internet banking features, in the browser",
                },
                {
                    "id": "api",
                    "name": "API Application",
                    "technology": "Java and Spring Boot",
                    "kind": "app",
                    "description": "Internet banking features over a JSON/HTTPS API",
                    "components": [
                        {
                            "id": "signin",
                            "name": "Sign In Controller",
                            "technology": "Spring MVC Rest Controller",
                            "description": "Lets users sign in to the banking system",
                        },
                        {
                            "id": "accounts",
                            "name": "Accounts Summary Controller",
                            "technology": "Spring MVC Rest Controller",
                            "description": "Lists a customer's accounts and balances",
                        },
                        {
                            "id": "security",
                            "name": "Security Component",
                            "technology": "Spring Bean",
                            "description": "Signing in, changing passwords",
                        },
                        {
                            "id": "facade",
                            "name": "Mainframe Banking Facade",
                            "technology": "Spring Bean",
                            "description": "A facade onto the mainframe banking system",
                        },
                        {
                            "id": "notifier",
                            "name": "Notification Publisher",
                            "technology": "Spring Bean",
                            "description": "Publishes account events for e-mail delivery",
                        },
                    ],
                },
                {
                    "id": "events",
                    "name": "Account Events",
                    "technology": "Amazon SQS",
                    "kind": "queue",
                    "service": "aws:sqs",
                    "description": "Account changes waiting to be e-mailed",
                },
                {
                    "id": "mailer",
                    "name": "Mail Sender",
                    "technology": "AWS Lambda",
                    "kind": "function",
                    "service": "aws:lambda",
                    "description": "Turns account events into e-mails",
                },
                {
                    "id": "db",
                    "name": "Database",
                    "technology": "PostgreSQL",
                    "kind": "db",
                    "service": "postgres",
                    "description": "Users, hashed credentials and access logs",
                },
            ],
        },
        {
            "id": "mainframe",
            "name": "Mainframe Banking System",
            "description": "Core banking: customers, accounts, transactions",
            "external": True,
        },
        {
            "id": "email",
            "name": "E-mail System",
            "description": "The internal Microsoft Exchange e-mail system",
            "external": True,
        },
    ],
    "relations": [
        {"from": "customer", "to": "web", "label": "Visits", "technology": "HTTPS"},
        {"from": "customer", "to": "spa", "label": "Views balances, makes payments"},
        {"from": "web", "to": "spa", "label": "Delivers to the browser"},
        {
            "from": "spa",
            "to": "signin",
            "label": "Signs in",
            "technology": "JSON/HTTPS",
        },
        {
            "from": "spa",
            "to": "accounts",
            "label": "Reads accounts",
            "technology": "JSON/HTTPS",
        },
        {"from": "signin", "to": "security", "label": "Uses"},
        {"from": "accounts", "to": "facade", "label": "Uses"},
        {
            "from": "security",
            "to": "db",
            "label": "Reads and writes",
            "technology": "JDBC",
        },
        {
            "from": "facade",
            "to": "mainframe",
            "label": "Uses",
            "technology": "XML/HTTPS",
        },
        {"from": "accounts", "to": "notifier", "label": "Uses"},
        {
            "from": "notifier",
            "to": "events",
            "label": "Publishes account events",
            "technology": "SQS",
            "async": True,
        },
        {
            "from": "mailer",
            "to": "events",
            "label": "Polls",
            "technology": "SQS",
            "async": True,
        },
        {
            "from": "mailer",
            "to": "email",
            "label": "Sends e-mail",
            "technology": "SMTP",
        },
        {"from": "email", "to": "customer", "label": "Sends e-mails to"},
        {"from": "staff", "to": "mainframe", "label": "Uses"},
    ],
}

#: The smallest useful model: one person, one system with two containers.
TEMPLATE_MODEL: dict = {
    "title": "My system",
    "people": [{"id": "user", "name": "User"}],
    "systems": [
        {
            "id": "app",
            "name": "My System",
            "containers": [
                {"id": "api", "name": "API", "technology": "Python", "kind": "app"},
                {
                    "id": "db",
                    "name": "Database",
                    "technology": "PostgreSQL",
                    "kind": "db",
                },
            ],
        }
    ],
    "relations": [
        {"from": "user", "to": "api", "label": "Uses", "technology": "HTTPS"},
        {"from": "api", "to": "db", "label": "Reads and writes", "technology": "SQL"},
    ],
}

EXAMPLE = json.dumps(BANKING, indent=2)
TEMPLATE = json.dumps(TEMPLATE_MODEL, indent=2)
