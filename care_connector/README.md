# Care Back Linking Feature

## Overview
This feature adds clickable links from Odoo records back to the corresponding resources in the Care system. Instead of displaying only the Care ID as plain text, users can now click on "Care Link" to open the resource directly in Care.

## Configuration

### Setting up the Care Base URL

1. Go to **Settings** > **General Settings** in Odoo
2. Scroll down to the **Care Connector** section (under "Care Integration Settings")
3. Enter your Care instance base URL in the **Care Base URL** field
   - Example: `https://care.example.com`
   - Do not include trailing slashes
4. Click **Save**

## URL Patterns

The following URL patterns are currently implemented as placeholders and may need to be updated based on actual Care URL structure:

| Resource Type | Model | Current URL Pattern | Notes |
|--------------|--------|---------------------|-------|
| User | `res.partner` | `{base_url}/users/{x_care_id}` | When `x_care_id_type` is "user" |
| Vendor | `res.partner` | `{base_url}/vendors/{x_care_id}` | When `x_care_id_type` is "vendor" |
| Invoice | `account.move` | `{base_url}/invoices/{x_care_id}` | Placeholder - needs actual path |
| Invoice Line | `account.move.line` | `{base_url}/invoice-lines/{x_care_id}` | Placeholder - needs actual path |
| Product Category | `product.category` | `{base_url}/categories/{x_care_id}` | Placeholder - needs actual path |
| Product | `product.template` | `{base_url}/products/{x_care_id}` | Placeholder - needs actual path |
| Payment | `account.payment` | `{base_url}/payments/{x_care_id}` | Placeholder - needs actual path |
| Bill Counter | `bill.counter` | `{base_url}/bill-counters/{x_care_id}` | Placeholder - needs actual path |

### Updating URL Patterns

To update the URL patterns to match your Care system's actual URLs:

1. Edit the respective model file in `care_connector/models/`
2. Locate the `_compute_care_url` method
3. Update the URL pattern string to match your Care system's routing

Example for `res.partner`:
```python
@api.depends('x_care_id', 'x_care_id_type')
def _compute_care_url(self):
    """Compute the Care URL based on care_id and care_id_type."""
    base_url = self.env['ir.config_parameter'].sudo().get_param('care.base_url', default='')
    for record in self:
        if record.x_care_id and base_url:
            if record.x_care_id_type == 'user':
                # Update this path to match your Care system
                record.x_care_url = f"{base_url}/users/{record.x_care_id}"
            elif record.x_care_id_type == 'vendor':
                # Update this path to match your Care system
                record.x_care_url = f"{base_url}/vendors/{record.x_care_id}"
```

## Usage

Once configured:
1. Navigate to any record that has a Care ID (Partners, Invoices, Products, etc.)
2. You will see a "Care Link" field that displays as a clickable URL
3. Click the link to open the corresponding resource in Care in a new tab
4. If no base URL is configured, the Care Link field will be empty

## Implementation Details

### Technical Changes

- Added `care.base_url` system parameter for storing the Care base URL
- Added `res.config.settings` extension to provide UI for configuration
- Added computed `x_care_url` field to each model that has `x_care_id`
- Modified views to display `x_care_url` using `widget="url"` instead of plain `x_care_id`
- Original `x_care_id` fields are kept but hidden (`invisible="1"`) for reference

### Modified Models

- `res.partner` - Care Partner/User/Vendor links
- `account.move` - Care Invoice links
- `account.move.line` - Care Invoice Line links
- `product.category` - Care Product Category links
- `product.template` - Care Product links
- `account.payment` - Care Payment links
- `bill.counter` - Care Bill Counter links

### Link Behavior

- Links open in a new browser tab
- Links are read-only and cannot be edited manually
- Links are computed dynamically based on the base URL and Care ID
- If either the base URL or Care ID is missing, no link is displayed
