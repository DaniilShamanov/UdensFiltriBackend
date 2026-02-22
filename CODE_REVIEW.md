# Backend Code Review (Post-Fix)

## Scope
Second-pass review after security/correctness fixes + admin expansion request. Focused on:
- security hardening,
- performance/read-path efficiency,
- admin/manager operations completeness,
- pricing and discount controls.

## What is now fixed

1. **Case message create authorization gap**: fixed by validating that non-superusers can only post to their own cases.
2. **Client-authoritative checkout pricing**: fixed; backend now resolves product/service prices from DB and rejects malformed item payloads.
3. **Incorrect nested auth refresh route**: removed.
4. **Overly broad exception handling in Stripe webhook**: replaced with narrower exception branches.
5. **Email uniqueness race condition**: DB-level case-insensitive unique constraint added for non-null emails.
6. **Role metadata exposure (`is_superuser`)**: removed from standard user payload.

## Manager/Admin capability review

### Implemented management capabilities
- Product/category/service CRUD in admin with stronger list/search/filter setup and bulk activate/deactivate actions.
- User assignment controls to `regular_users` / `business_users` via bulk admin actions.
- Group-level discount management via `GroupDiscount` admin model.
- Order status management actions (`paid`, `cancelled`) and richer order admin filters/search.
- Default seeding migration for required business groups + base discounts.

### Security notes (current state)
- Discount logic is server-side and group-based, reducing client tampering risk.
- Checkout refuses ambiguous items (`product_id` xor `service_id`) and mixed currency baskets.
- Webhook remains unauthenticated at DRF permission layer by design, with Stripe signature verification as the trust boundary.

## Performance notes (current state)

### Good
- Most list views already constrain queryset by user/superuser role.
- Admin list pages now use `list_select_related` where useful.

### Still worth improving
1. **N+1 risk in case detail serializer**: case messages are serialized in Python method field without prefetch optimization for retrieve/list-heavy scenarios.
2. **Price/discount lookup per item**: serializer issues per-item queries. For large carts, batch-fetch products/services by IDs first.
3. **Lack of explicit DB indexes for frequent operational filters** (e.g., order status+created_at combos for admin dashboards).

## Remaining recommendations
1. Add prefetching in case detail/message-heavy endpoints.
2. Optimize checkout item resolution using bulk maps (`in` query) instead of per-item `.filter(...).first()`.
3. Add targeted API tests for admin-driven discount changes affecting checkout total.
4. Add explicit monitoring/logging around repeated webhook signature failures.

## Summary
The backend is materially improved in security and manageability compared to the prior state, and now supports the requested manager workflows (group assignment + discount management + product/service/order admin controls). Remaining work is primarily performance optimization and operational observability.
