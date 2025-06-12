API Endpoints:
Authentication:

POST /api/auth/login/ - User login
POST /api/auth/logout/ - User logout

User Management (Admin):

GET /api/users/ - List all users
POST /api/users/ - Create new user
GET /api/users/{id}/ - Get user details
PUT /api/users/{id}/ - Update user
DELETE /api/users/{id}/ - Delete user

Products & Inventory:

GET /api/products/ - List products (with search, category filter)
POST /api/products/ - Create product
GET /api/products/{id}/ - Get product details
PUT /api/products/{id}/ - Update product
POST /api/products/{id}/update-stock/ - Update stock quantity

Categories:

GET /api/categories/ - List categories
POST /api/categories/ - Create category
PUT /api/categories/{id}/ - Update category

Sales (POS):

GET /api/sales/ - List sales (with date/cashier filters)
POST /api/sales/ - Create new sale transaction
GET /api/sales/{id}/ - Get sale details

Analytics:

GET /api/dashboard/stats/ - Get dashboard statistics

