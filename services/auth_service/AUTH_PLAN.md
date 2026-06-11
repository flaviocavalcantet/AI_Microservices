# Auth Service — Feature Implementation Plan

## Features

1. Username/password login (password stored as bcrypt hash)
2. User registration (username/password or GitHub OAuth)
3. Endpoints for login, register, OAuth
4. Admin role + seeded admin user
5. List users endpoint (admin only)
6. Change user role endpoint (admin only)

---

## Architecture Decisions

### Password storage
`bcrypt` via `passlib[bcrypt]`. Hash stored on the `User` entity as
`password_hash: Optional[str]`. Plain-text password never persisted.

### Provider model
The existing `User.provider` field is `"github"` for OAuth users.
Password users will use `provider = "local"` and
`provider_user_id = username` (consistent with the existing
`(provider, provider_user_id)` unique index).

### Admin user seeding
A `seed_admin_user()` function called at app startup from `create_app()`.
Credentials read from env vars `ADMIN_USERNAME` / `ADMIN_PASSWORD`
(defaults: `admin` / `admin123` — dev only). The seeder is idempotent:
skips if a user with `provider="local"`, `provider_user_id="admin"` already exists.

### Auth middleware / require_auth decorator
A `require_auth` decorator reads the `Authorization: Bearer <token>` header,
validates it via `ValidateTokenUseCase`, and stores claims on `flask.g`.
A `require_role("admin")` decorator wraps `require_auth` and checks the role.
Both live in `presentation/middleware/auth_middleware.py`.

### Admin endpoints placement
New blueprint `admin_bp` at `/api/v1/admin`, registered alongside `auth_bp`.
Keeps admin routes clearly separated from auth routes.

---

## Implementation Order

The order below minimises rework — each step builds cleanly on the previous one.

### Step 1 — Extend the `User` entity
**File:** `domain/entities/user.py`
- Add `password_hash: Optional[str] = None`
- Add `username: Optional[str] = None`
- Update `User.create()` to accept optional `password_hash` and `username`
- Add `set_password(raw: str)` and `check_password(raw: str) -> bool` methods
  using `passlib.context.CryptContext`

### Step 2 — Extend repository interfaces
**File:** `application/ports/interfaces.py`
- Add `find_by_username(username: str) -> Optional[User]` to `IUserRepository`
- Add `list_all() -> List[User]` to `IUserRepository`
- Add `update_roles(user_id: str, roles: List[str]) -> User` to `IUserRepository`

### Step 3 — Update both repository implementations
**Files:** `infrastructure/repositories/in_memory_user_repository.py`,
           `infrastructure/repositories/mongo_user_repository.py`
- Implement the three new interface methods
- In-memory: add `_by_username: Dict[str, str]` index
- Mongo: `find_by_username` queries `provider="local"` + `provider_user_id=username`;
  `list_all` returns all documents; `update_roles` uses `$set`
- Update `_to_document` / `_to_entity` to include `password_hash` and `username`

### Step 4 — New application DTOs
**File:** `application/dto/auth_dto.py`
- `RegisterRequestDTO(username, password, email, display_name)`
- `PasswordLoginRequestDTO(username, password)`
- `UserSummaryDTO(id, username, email, display_name, roles, provider, is_active, created_at)`
- `UpdateRolesRequestDTO(user_id, roles)`

### Step 5 — New use cases
**Files:** `application/use_cases/register_user.py`,
           `application/use_cases/password_login.py`,
           `application/use_cases/admin_ops.py`

`RegisterUserUseCase.execute(dto: RegisterRequestDTO) -> TokenResponseDTO`
- Reject duplicate username or email
- Hash password, create `User(provider="local", ...)`, save, issue token pair

`PasswordLoginUseCase.execute(dto: PasswordLoginRequestDTO) -> TokenResponseDTO`
- Find user by username, verify `check_password()`, issue token pair

`ListUsersUseCase.execute() -> List[UserSummaryDTO]`
- Call `user_repository.list_all()`, map to DTOs

`UpdateUserRolesUseCase.execute(dto: UpdateRolesRequestDTO) -> UserSummaryDTO`
- Validate roles against known set, call `update_roles()`, return summary DTO

### Step 6 — Auth middleware
**File:** `presentation/middleware/auth_middleware.py`
- `require_auth` decorator: extracts Bearer token, calls `ValidateTokenUseCase`,
  stores claims on `g.current_user`; returns 401 on failure
- `require_role(role)` decorator: wraps `require_auth`, checks `g.current_user.roles`;
  returns 403 on failure

### Step 7 — New request schemas
**File:** `presentation/routes/v1/auth/schemas.py`  (additions)
- `RegisterRequest(username, password, email, display_name)`
- `PasswordLoginRequest(username, password)`

### Step 8 — New auth endpoints
**File:** `presentation/routes/v1/auth/controller.py`  (additions)
- `POST /api/v1/auth/register` → `RegisterUserUseCase`
- `POST /api/v1/auth/login/password` → `PasswordLoginUseCase`
  (kept separate from the existing `/login` which is OAuth-only)

### Step 9 — Admin blueprint
**File:** `presentation/routes/v1/admin/controller.py`  (new)
- `GET  /api/v1/admin/users`               — `require_role("admin")` → `ListUsersUseCase`
- `PUT  /api/v1/admin/users/<id>/roles`    — `require_role("admin")` → `UpdateUserRolesUseCase`

### Step 10 — Wire everything in `app.py`
- Register new use cases in `_register_use_cases()`
- Add `seed_admin_user()` call at the end of `create_app()`
- Register `admin_bp` in `_register_blueprints()`

---

## New files summary

| File | Purpose |
|---|---|
| `presentation/middleware/auth_middleware.py` | `require_auth` / `require_role` decorators |
| `application/use_cases/register_user.py` | Registration use case |
| `application/use_cases/password_login.py` | Password login use case |
| `application/use_cases/admin_ops.py` | List users + update roles use cases |
| `presentation/routes/v1/admin/__init__.py` | Blueprint package init |
| `presentation/routes/v1/admin/controller.py` | Admin route handlers |
| `presentation/routes/v1/admin/schemas.py` | Admin request schemas |
| `presentation/routes/v1/admin/mappers.py` | Admin DTO → response dict mappers |

## Modified files summary

| File | Change |
|---|---|
| `domain/entities/user.py` | `password_hash`, `username`, `set_password`, `check_password` |
| `application/ports/interfaces.py` | `find_by_username`, `list_all`, `update_roles` |
| `application/dto/auth_dto.py` | New request/response DTOs |
| `infrastructure/repositories/in_memory_user_repository.py` | New interface methods |
| `infrastructure/repositories/mongo_user_repository.py` | New interface methods + field mapping |
| `presentation/routes/v1/auth/schemas.py` | `RegisterRequest`, `PasswordLoginRequest` |
| `presentation/routes/v1/auth/controller.py` | `/register`, `/login/password` routes |
| `presentation/app.py` | Wire use cases, seed admin, register admin blueprint |
