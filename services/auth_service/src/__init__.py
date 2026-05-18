"""Auth Service: Authentication and Authorization

Responsibility: User authentication, JWT token management, permission verification

Architecture Layers:
- domain/: Pure business logic for user management and permissions
- application/: Use cases for login, registration, permission checks
- infrastructure/: MongoDB user storage, encryption
- presentation/: HTTP routes for auth endpoints

Security considerations:
- Password hashing with bcrypt
- JWT tokens with configurable expiration
- CORS policy enforcement
- Rate limiting on auth endpoints
"""

__version__ = "1.0.0"
__author__ = "AI Platform Team"
