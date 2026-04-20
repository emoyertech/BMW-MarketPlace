# Data Model

## Entity Relationship Diagram

- Visual representation of entities and relationships (provided separately).

## Core SQL Tables

1. **Users** - Buyer, dealer, and private seller accounts with role and profile settings.
2. **Dealer_Profiles** - Dealership identity, verification, contact details, and inventory preferences.
3. **Vehicles** - Details of listed vehicles, including specs, VIN, and condition.
4. **Listings** - Active listings, seller type, pricing, and status.
5. **Service_History** - Maintenance records associated with vehicles.
6. **Photos** - Images related to listings.
7. **Inquiries** - Buyer inquiries stored for tracking.
8. **Messages** - Conversation records between buyers and sellers.
9. **Reviews** - User-generated reviews and ratings.
10. **Transactions** - Record of completed sales.
11. **Saved_Vehicles** - List of vehicles saved by users for later viewing.
12. **Verification_Events** - Trust and safety records for dealers and private sellers.

## Table Schemas

- Detailed description of each core table including constraints and indexes.

## Key Indexes

- Performance improvement indexes for critical queries.

## Data Flow Descriptions

- Overview of how dealer inventory, private listings, buyer inquiries, and transactions move through the system.

## Privacy/Compliance Notes

- Adherence to regulations concerning user data, seller verification, and transaction records.

## Optional Analytics Tables

- Potential tables for tracking engagement, listing conversion, dealer activity, and user behavior.
