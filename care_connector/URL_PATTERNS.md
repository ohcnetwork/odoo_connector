# Care URL Patterns - Awaiting User Input

## Purpose
This file lists all the URL patterns that need to be configured to match the actual Care system routing.

## Required Information

Please provide the actual URL patterns for the following resources in your Care system:

### 1. Partners (Users)
- **Current Placeholder**: `{base_url}/users/{uuid}`
- **Actual Pattern**: _________________
- **Example URL**: _________________

### 2. Partners (Vendors) 
- **Current Placeholder**: `{base_url}/vendors/{uuid}`
- **Actual Pattern**: _________________
- **Example URL**: _________________

### 3. Invoices (Account Moves)
- **Current Placeholder**: `{base_url}/invoices/{uuid}`
- **Actual Pattern**: _________________
- **Example URL**: _________________

### 4. Invoice Lines (Account Move Lines)
- **Current Placeholder**: `{base_url}/invoice-lines/{uuid}`
- **Actual Pattern**: _________________
- **Example URL**: _________________

### 5. Product Categories
- **Current Placeholder**: `{base_url}/categories/{uuid}`
- **Actual Pattern**: _________________
- **Example URL**: _________________

### 6. Products (Product Templates)
- **Current Placeholder**: `{base_url}/products/{uuid}`
- **Actual Pattern**: _________________
- **Example URL**: _________________

### 7. Payments
- **Current Placeholder**: `{base_url}/payments/{uuid}`
- **Actual Pattern**: _________________
- **Example URL**: _________________

### 8. Bill Counters
- **Current Placeholder**: `{base_url}/bill-counters/{uuid}`
- **Actual Pattern**: _________________
- **Example URL**: _________________

## Instructions

1. Fill in the "Actual Pattern" column with the correct URL pattern from your Care system
2. Provide an example URL for each resource type
3. The `{uuid}` placeholder represents the `x_care_id` value
4. The `{base_url}` will be configured in Odoo settings

## Example Format

If your Care system uses patterns like:
- User profiles: `https://care.example.com/user/profile/abc-123-def`
- Then the pattern would be: `{base_url}/user/profile/{uuid}`

## After Providing Patterns

Once you provide these patterns, I will update the corresponding `_compute_care_url` methods in each model file.
