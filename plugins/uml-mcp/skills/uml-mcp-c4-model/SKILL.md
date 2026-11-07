---
name: uml-mcp-c4-model
description: Draw a C4 model readers can drill into, from context to containers to components (c4_model).
---

# C4 model

Follow `skill://uml-mcp-diagrams/SKILL.md`. One JSON model covers the three C4 levels. The SVG is the level you choose, in C4 notation with a legend; the page starts there and opens a system into its containers and a container into its components, with breadcrumbs back up.

## Types

| Type | Use for | Example prompt |
| --- | --- | --- |
| `c4_model` | a C4 model to explore: system context, then containers, then components | C4 model of our e-commerce platform: shoppers, the storefront, order and payment services, Postgres, a Kafka topic, Stripe. Let me click into each level. |

## Steps

1. Check the live catalog (`list_diagram_types` or `uml://types`); the bundled plugins are on by default, but a server may turn them off with `plugins.bundled: false`.
2. Read the type's example from `uml://examples` and keep its field names.
3. Call `validate_uml`; an error names the field and, for a bad reference, lists the known ids, so fix it and validate again.
4. Render with `generate_uml_image` for a chat image, or `generate_uml` with `output_format: "html"` for the interactive page in the MCP App viewer. Clients without MCP Apps still get the PNG and SVG.
5. Pass `theme` (`auto`, `dark`, `light`) rather than editing colours.

## Example

```json
{"title":"Internet banking system","description":"Customers view balances and make payments online","people":[{"id":"customer","name":"Personal Banking Customer","description":"A customer of the bank, with personal bank accounts"},{"id":"staff","name":"Back Office Staff","description":"Bank staff who handle customer support","external":false}],"systems":[{"id":"banking","name":"Internet Banking System","description":"Lets customers view their accounts and make payments","containers":[{"id":"web","name":"Web Application","technology":"Java and Spring MVC","kind":"app","description":"Delivers the static content and the single-page app"},{"id":"spa","name":"Single-Page App","technology":"TypeScript and React","kind":"web","service":"react","description":"All the internet banking features, in the browser"},{"id":"api","name":"API Application","technology":"Java and Spring Boot","kind":"app","description":"Internet banking features over a JSON/HTTPS API","components":[{"id":"signin","name":"Sign In Controller","technology":"Spring MVC Rest Controller","description":"Lets users sign in to the banking system"},{"id":"accounts","name":"Accounts Summary Controller","technology":"Spring MVC Rest Controller","description":"Lists a customer's accounts and balances"},{"id":"security","name":"Security Component","technology":"Spring Bean","description":"Signing in, changing passwords"},{"id":"facade","name":"Mainframe Banking Facade","technology":"Spring Bean","description":"A facade onto the mainframe banking system"},{"id":"notifier","name":"Notification Publisher","technology":"Spring Bean","description":"Publishes account events for e-mail delivery"}]},{"id":"events","name":"Account Events","technology":"Amazon SQS","kind":"queue","service":"aws:sqs","description":"Account changes waiting to be e-mailed"},{"id":"mailer","name":"Mail Sender","technology":"AWS Lambda","kind":"function","service":"aws:lambda","description":"Turns account events into e-mails"},{"id":"db","name":"Database","technology":"PostgreSQL","kind":"db","service":"postgres","description":"Users, hashed credentials and access logs"}]},{"id":"mainframe","name":"Mainframe Banking System","description":"Core banking: customers, accounts, transactions","external":true},{"id":"email","name":"E-mail System","description":"The internal Microsoft Exchange e-mail system","external":true}],"relations":[{"from":"customer","to":"web","label":"Visits","technology":"HTTPS"},{"from":"customer","to":"spa","label":"Views balances, makes payments"},{"from":"web","to":"spa","label":"Delivers to the browser"},{"from":"spa","to":"signin","label":"Signs in","technology":"JSON/HTTPS"},{"from":"spa","to":"accounts","label":"Reads accounts","technology":"JSON/HTTPS"},{"from":"signin","to":"security","label":"Uses"},{"from":"accounts","to":"facade","label":"Uses"},{"from":"security","to":"db","label":"Reads and writes","technology":"JDBC"},{"from":"facade","to":"mainframe","label":"Uses","technology":"XML/HTTPS"},{"from":"accounts","to":"notifier","label":"Uses"},{"from":"notifier","to":"events","label":"Publishes account events","technology":"SQS","async":true},{"from":"mailer","to":"events","label":"Polls","technology":"SQS","async":true},{"from":"mailer","to":"email","label":"Sends e-mail","technology":"SMTP"},{"from":"email","to":"customer","label":"Sends e-mails to"},{"from":"staff","to":"mainframe","label":"Uses"}]}
```
