# Phase 6: Auth API and Session RBAC Foundation

Phase 6 adds backend-only authentication endpoints backed by the app Postgres
database and the `sessions` table. Tokens are opaque session tokens, not JWTs.

## Endpoints

### `POST /auth/login`

Request:

```json
{
  "email": "student.business.demo@vinuni.edu.vn",
  "password": "Demo@123456"
}
```

Response:

```json
{
  "access_token": "opaque-session-token",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "student.business.demo@vinuni.edu.vn",
    "full_name": "Demo Business Student",
    "preferred_name": "Business Student",
    "roles": ["student"],
    "student_profile": {},
    "institute": {}
  }
}
```

### `GET /auth/me`

Use the bearer token returned by login:

```http
Authorization: Bearer <token>
```

Returns the current safe user profile, roles, optional student profile, and
optional institute information.

### `POST /auth/logout`

Use the same authorization header. Logout revokes the current session by setting
`revoked_at` in the `sessions` table.

## Demo Accounts

Phase 5A seeds demo users with the development-only password:

```text
Demo@123456
```

Useful demo accounts:

- `student.business.demo@vinuni.edu.vn`
- `student.cs.demo@vinuni.edu.vn`
- `student.health.demo@vinuni.edu.vn`
- `student.liberal.demo@vinuni.edu.vn`
- `admin.global.demo@vinuni.edu.vn`
- `admin.business.demo@vinuni.edu.vn`
- `admin.cecs.demo@vinuni.edu.vn`
- `admin.health.demo@vinuni.edu.vn`
- `admin.liberal.demo@vinuni.edu.vn`

Only password hashes are stored. Do not use the demo password outside local or
development demo environments.

## Session Behavior

- Login verifies the PBKDF2-SHA256 password hash.
- A secure opaque token is returned to the client.
- Only a SHA256 hash of the token is stored in `sessions.token_hash`.
- Sessions expire after the demo default window.
- Logout revokes the current session.

## RBAC Foundation

The backend now exposes reusable dependencies:

- `get_current_user`
- `require_roles(*roles)`

Later Student/Admin APIs can use these dependencies to protect route groups.
Frontend integration is intentionally left for a later phase.
