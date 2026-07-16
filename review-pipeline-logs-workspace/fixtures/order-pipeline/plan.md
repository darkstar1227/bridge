# Plan: Order Processing Pipeline

## Overview

When a customer places an order, the pipeline validates the order, charges
the payment method, decrements inventory, then sends a confirmation email.

## Pipeline Steps

1. **Validate order** — triggered by an incoming order event. Success signal:
   logs `order validated` with the order id and item count. Expected output:
   item count must be >= 1.
2. **Charge payment** — triggered after validation succeeds. Success signal:
   logs `charge succeeded` with a charge id and amount. Expected output:
   charge amount must match the order total.
3. **Update inventory** — triggered after the charge succeeds. Success
   signal: logs `inventory updated` with the SKU and quantity decremented.
   Expected output: quantity decremented must equal the item count from
   step 1.
4. **Send confirmation email** — triggered after inventory update succeeds.
   Success signal: logs `confirmation email sent` with the recipient
   address.

## Verification Expectations

Every step should log both a start and a completion/success line, with
enough detail (order id, amounts, SKUs) to debug a single order without
re-running the pipeline.
